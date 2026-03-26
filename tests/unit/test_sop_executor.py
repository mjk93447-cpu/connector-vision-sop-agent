"""
Unit tests for src/sop_executor.py — ROI / target_type field threading (v3.5.0 Task 5).

Verifies that:
- A step with a "roi" field passes roi as a tuple to control_engine.click_target()
- A step with a "target_type" field passes it to control_engine.click_target()
- A step without "roi" / "target_type" still works (backward compat, roi=None)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.control_engine import ControlEngine, ControlResult
from src.sop_executor import SopExecutor
from src.vision_engine import DetectionConfig, VisionEngine


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_bgr(h: int = 100, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


@pytest.fixture
def vision() -> VisionEngine:
    """VisionEngine without loading actual YOLO weights."""
    with patch.object(VisionEngine, "_load_model", return_value=None):
        v = VisionEngine(DetectionConfig(confidence_threshold=0.5))
    return v


@pytest.fixture
def control(vision: VisionEngine) -> ControlEngine:
    """ControlEngine with mocked ClassRegistry.load()."""
    with patch("src.control_engine.ClassRegistry") as mock_reg_cls:
        mock_reg = MagicMock()
        mock_reg.is_non_text.return_value = False
        mock_reg_cls.load.return_value = mock_reg
        engine = ControlEngine(vision_agent=vision)
    return engine


@pytest.fixture
def executor(vision: VisionEngine, control: ControlEngine) -> SopExecutor:
    return SopExecutor(vision=vision, control=control)


def _ok_result() -> ControlResult:
    return ControlResult(success=True, coords=(10, 20), duration=0.01)


def _fail_result() -> ControlResult:
    return ControlResult(success=False, coords=None, duration=0.01, error="not found")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSopExecutorRoi:
    """ROI field is extracted from step and forwarded to click_target."""

    def test_step_roi_passed_to_control_engine(self, executor: SopExecutor) -> None:
        """Step with 'roi' list → click_target receives roi as tuple."""
        step = {
            "id": "mold_left",
            "name": "Mold Left",
            "type": "click",
            "target": "mold_left_label",
            "roi": [0, 100, 960, 400],
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            success, _ = executor.run_step(step)

        assert success is True
        mock_click.assert_called_once()
        _args, kwargs = mock_click.call_args
        assert kwargs.get("roi") == (0, 100, 960, 400)

    def test_step_target_type_passed(self, executor: SopExecutor) -> None:
        """Step with 'target_type' → click_target receives target_type."""
        step = {
            "id": "icon_step",
            "name": "Icon Step",
            "type": "click",
            "target": "some_icon",
            "target_type": "NON_TEXT",
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            success, _ = executor.run_step(step)

        assert success is True
        mock_click.assert_called_once()
        _args, kwargs = mock_click.call_args
        assert kwargs.get("target_type") == "NON_TEXT"

    def test_step_without_roi_still_works(self, executor: SopExecutor) -> None:
        """Step without 'roi' → click_target receives roi=None (backward compat)."""
        step = {
            "id": "login",
            "name": "Login",
            "type": "click",
            "target": "login_button",
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            success, _ = executor.run_step(step)

        assert success is True
        mock_click.assert_called_once()
        _args, kwargs = mock_click.call_args
        assert kwargs.get("roi") is None
        assert kwargs.get("target_type") is None

    def test_step_roi_and_target_type_together(self, executor: SopExecutor) -> None:
        """Step with both roi and target_type → both forwarded correctly."""
        step = {
            "id": "mold_left",
            "name": "Mold Left",
            "type": "click",
            "target": "mold_left_label",
            "roi": [10, 20, 800, 300],
            "target_type": "NON_TEXT",
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            success, _ = executor.run_step(step)

        assert success is True
        _args, kwargs = mock_click.call_args
        assert kwargs.get("roi") == (10, 20, 800, 300)
        assert kwargs.get("target_type") == "NON_TEXT"

    def test_step_id_passed_to_control_engine(self, executor: SopExecutor) -> None:
        """Step 'id' field is forwarded as step_id to click_target."""
        step = {
            "id": "my_step_id",
            "name": "My Step",
            "type": "click",
            "target": "some_button",
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            executor.run_step(step)

        _args, kwargs = mock_click.call_args
        assert kwargs.get("step_id") == "my_step_id"

    def test_click_sequence_roi_passed(self, executor: SopExecutor) -> None:
        """click_sequence type also forwards roi/target_type to each click."""
        step = {
            "id": "apply_open",
            "name": "Apply & Open",
            "type": "click_sequence",
            "targets": ["apply_button", "open_icon"],
            "roi": [0, 0, 1920, 500],
            "target_type": "TEXT",
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            success, _ = executor.run_step(step)

        assert success is True
        assert mock_click.call_count == 2
        for call in mock_click.call_args_list:
            _args, kwargs = call
            assert kwargs.get("roi") == (0, 0, 1920, 500)
            assert kwargs.get("target_type") == "TEXT"

    def test_failed_click_returns_false(self, executor: SopExecutor) -> None:
        """When click_target fails, run_step returns (False, error_message)."""
        step = {
            "id": "bad_step",
            "name": "Bad Step",
            "type": "click",
            "target": "missing_button",
            "roi": [0, 0, 100, 100],
        }

        with patch.object(
            executor.control, "click_target", return_value=_fail_result()
        ):
            success, msg = executor.run_step(step)

        assert success is False
        assert "not found" in msg or "click" in msg.lower()

    def test_unknown_step_type_returns_false(self, executor: SopExecutor) -> None:
        """Unknown step type must return (False, message)."""
        step = {"id": "x", "name": "X", "type": "teleport"}
        success, msg = executor.run_step(step)
        assert success is False
        assert "teleport" in msg


# ---------------------------------------------------------------------------
# New step types: auth_sequence / input_text / mold_setup (v3.8)
# ---------------------------------------------------------------------------


class TestAuthSequence:
    """auth_sequence type: LOGIN click → PW field click → type_text → OK/Enter."""

    def test_auth_sequence_success(self, executor: SopExecutor) -> None:
        """All sub-steps succeed → run_step returns (True, ...)."""
        step = {
            "id": "login",
            "name": "Login",
            "type": "auth_sequence",
            "login_button": "login_button",
            "password_field": "password_field",
            "ok_button": "ok_button",
        }
        from src.control_engine import ControlResult

        ok_click = ControlResult(success=True, coords=(10, 20), duration=0.01)
        ok_type = ControlResult(success=True, coords=None, duration=0.01)
        ok_press = ControlResult(success=True, coords=None, duration=0.01)

        executor.control.click_target = MagicMock(return_value=ok_click)
        executor.control.type_text = MagicMock(return_value=ok_type)
        executor.control.press_key = MagicMock(return_value=ok_press)

        success, msg = executor.run_step(step)

        assert success is True
        # type_text called once with password
        executor.control.type_text.assert_called_once()
        args = executor.control.type_text.call_args
        assert args[0][0] == "1111"  # default password

    def test_auth_sequence_login_fail(self, executor: SopExecutor) -> None:
        """If LOGIN button not found → return (False, ...)."""
        step = {
            "id": "login",
            "name": "Login",
            "type": "auth_sequence",
            "login_button": "login_button",
            "password_field": "password_field",
            "ok_button": "ok_button",
        }
        fail_click = _fail_result()

        executor.control.click_target = MagicMock(return_value=fail_click)
        executor.control.type_text = MagicMock()
        executor.control.press_key = MagicMock()

        success, msg = executor.run_step(step)

        assert success is False
        assert "LOGIN" in msg or "login" in msg.lower()
        executor.control.type_text.assert_not_called()

    def test_auth_sequence_reads_password_from_config(self) -> None:
        """password read from config['password'], not hardcoded."""
        from unittest.mock import patch, MagicMock
        from src.vision_engine import DetectionConfig, VisionEngine
        from src.control_engine import ControlEngine, ControlResult

        with patch.object(VisionEngine, "_load_model", return_value=None):
            v = VisionEngine(DetectionConfig(confidence_threshold=0.5))
        with patch("src.control_engine.ClassRegistry") as mock_cls:
            mock_cls.load.return_value = MagicMock()
            ctrl = ControlEngine(vision_agent=v)

        executor = SopExecutor(
            vision=v,
            control=ctrl,
            config={"password": "9999"},
        )

        ok = ControlResult(success=True, coords=(1, 2), duration=0.01)
        executor.control.click_target = MagicMock(return_value=ok)
        executor.control.type_text = MagicMock(
            return_value=ControlResult(success=True, coords=None, duration=0.01)
        )
        executor.control.press_key = MagicMock(
            return_value=ControlResult(success=True, coords=None, duration=0.01)
        )

        step = {
            "id": "login",
            "name": "Login",
            "type": "auth_sequence",
            "login_button": "login_button",
            "password_field": "password_field",
            "ok_button": "ok_button",
        }
        success, _ = executor.run_step(step)
        assert success is True
        typed_text = executor.control.type_text.call_args[0][0]
        assert typed_text == "9999"


class TestInputText:
    """input_text type: click field → type_text → press Enter."""

    def test_input_text_success(self, executor: SopExecutor) -> None:
        from src.control_engine import ControlResult

        step = {
            "id": "axis_x",
            "name": "Axis-X",
            "type": "input_text",
            "target": "axis_x_field",
            "text": "123",
            "clear_first": True,
        }
        ok_click = ControlResult(success=True, coords=(50, 60), duration=0.01)
        ok_type = ControlResult(success=True, coords=None, duration=0.01)
        ok_press = ControlResult(success=True, coords=None, duration=0.01)

        executor.control.click_target = MagicMock(return_value=ok_click)
        executor.control.type_text = MagicMock(return_value=ok_type)
        executor.control.press_key = MagicMock(return_value=ok_press)

        success, msg = executor.run_step(step)

        assert success is True
        executor.control.type_text.assert_called_once()
        call_args = executor.control.type_text.call_args
        assert call_args[0][0] == "123"
        assert call_args[1].get("clear_first") is True
        # Enter pressed after typing
        executor.control.press_key.assert_called_with("enter")

    def test_input_text_field_not_found(self, executor: SopExecutor) -> None:
        step = {
            "id": "axis_y",
            "name": "Axis-Y",
            "type": "input_text",
            "target": "axis_y_field",
            "text": "0",
        }
        executor.control.click_target = MagicMock(return_value=_fail_result())
        executor.control.type_text = MagicMock()

        success, msg = executor.run_step(step)

        assert success is False
        assert "axis_y_field" in msg
        executor.control.type_text.assert_not_called()

    def test_input_text_default_text_is_zero(self, executor: SopExecutor) -> None:
        from src.control_engine import ControlResult

        step = {
            "id": "axis_x",
            "name": "Axis-X",
            "type": "input_text",
            "target": "axis_x_field",
            # no 'text' key → should default to "0"
        }
        ok = ControlResult(success=True, coords=(1, 2), duration=0.01)
        executor.control.click_target = MagicMock(return_value=ok)
        executor.control.type_text = MagicMock(return_value=ok)
        executor.control.press_key = MagicMock(return_value=ok)

        success, _ = executor.run_step(step)
        assert success is True
        assert executor.control.type_text.call_args[0][0] == "0"


class TestMoldSetup:
    """mold_setup type: click label → drag ROI."""

    def test_mold_setup_success(self, executor: SopExecutor) -> None:
        from src.control_engine import ControlResult

        step = {
            "id": "mold_left",
            "name": "Mold Left",
            "type": "mold_setup",
            "label_target": "mold_left_label",
            "drag_start": [100, 200],
            "drag_end": [800, 350],
            "roi": [0, 0, 960, 1080],
        }
        ok_click = ControlResult(success=True, coords=(10, 20), duration=0.01)
        ok_drag = ControlResult(success=True, coords=(800, 350), duration=0.05)

        executor.control.click_target = MagicMock(return_value=ok_click)
        executor.control.drag_roi = MagicMock(return_value=ok_drag)

        success, msg = executor.run_step(step)

        assert success is True
        executor.control.click_target.assert_called_once()
        executor.control.drag_roi.assert_called_once_with((100, 200), (800, 350))

    def test_mold_setup_label_fail_skips_drag(self, executor: SopExecutor) -> None:
        step = {
            "id": "mold_right",
            "name": "Mold Right",
            "type": "mold_setup",
            "label_target": "mold_right_label",
            "drag_start": [100, 200],
            "drag_end": [800, 350],
        }
        executor.control.click_target = MagicMock(return_value=_fail_result())
        executor.control.drag_roi = MagicMock()

        success, msg = executor.run_step(step)

        assert success is False
        assert "mold_right_label" in msg
        executor.control.drag_roi.assert_not_called()

    def test_mold_setup_drag_fail(self, executor: SopExecutor) -> None:
        from src.control_engine import ControlResult

        step = {
            "id": "mold_left",
            "name": "Mold Left",
            "type": "mold_setup",
            "label_target": "mold_left_label",
            "drag_start": [100, 200],
            "drag_end": [800, 350],
        }
        ok_click = ControlResult(success=True, coords=(10, 20), duration=0.01)
        fail_drag = ControlResult(
            success=False, coords=None, duration=0.01, error="drag error"
        )

        executor.control.click_target = MagicMock(return_value=ok_click)
        executor.control.drag_roi = MagicMock(return_value=fail_drag)

        success, msg = executor.run_step(step)

        assert success is False
        assert "drag" in msg.lower()


class TestNewStepFallback:
    """get_steps() fallback includes all new step IDs."""

    def test_fallback_has_12_steps(self, executor: SopExecutor) -> None:
        # Point executor at a non-existent path to trigger fallback
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        assert len(steps) == 12

    def test_fallback_has_auth_sequence_login(self, executor: SopExecutor) -> None:
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        login = next(s for s in steps if s["id"] == "login")
        assert login["type"] == "auth_sequence"

    def test_fallback_has_axis_x_and_y(self, executor: SopExecutor) -> None:
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        ids = [s["id"] for s in steps]
        assert "axis_x" in ids
        assert "axis_y" in ids

    def test_fallback_has_verify_left_right(self, executor: SopExecutor) -> None:
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        ids = [s["id"] for s in steps]
        assert "verify_left" in ids
        assert "verify_right" in ids

    def test_fallback_no_image_source(self, executor: SopExecutor) -> None:
        """image_source was removed from standard SOP in v3.8."""
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        ids = [s["id"] for s in steps]
        assert "image_source" not in ids

    def test_password_default(self, executor: SopExecutor) -> None:
        assert executor._password == "1111"

    def test_password_from_config(self) -> None:
        from unittest.mock import MagicMock

        v = MagicMock()
        c = MagicMock()
        executor = SopExecutor(vision=v, control=c, config={"password": "5678"})
        assert executor._password == "5678"
