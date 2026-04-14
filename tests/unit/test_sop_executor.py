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

    def test_step_yolo_class_passed_as_detection_label(
        self, executor: SopExecutor
    ) -> None:
        """yolo_class should be forwarded to click_target as detection_label."""
        step = {
            "id": "click_mold_left_tab",
            "name": "Click Mold Left Tab",
            "type": "click",
            "target": "click_mold_left_tab",
            "target_type": "NON_TEXT",
            "yolo_class": "mold_left_label",
        }

        with patch.object(
            executor.control, "click_target", return_value=_ok_result()
        ) as mock_click:
            success, _ = executor.run_step(step)

        assert success is True
        _args, kwargs = mock_click.call_args
        assert kwargs.get("detection_label") == "mold_left_label"

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

    def test_fallback_has_40_steps(self, executor: SopExecutor) -> None:
        # v3.9: fallback expanded to 40 atomic steps
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        assert len(steps) == 40

    def test_fallback_has_login_click_steps(self, executor: SopExecutor) -> None:
        """v3.9: login is now 4 atomic steps instead of 1 auth_sequence."""
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        ids = [s["id"] for s in steps]
        assert "login_click_btn" in ids
        assert "login_type_password" in ids
        assert "login_confirm" in ids

    def test_fallback_has_axis_steps(self, executor: SopExecutor) -> None:
        """v3.9: axis steps are now atomic click + type_text + press_key."""
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        ids = [s["id"] for s in steps]
        assert "axis_x_click_field" in ids
        assert "axis_x_type_value" in ids
        assert "axis_y_click_field" in ids
        assert "axis_y_type_value" in ids

    def test_fallback_has_verify_steps(self, executor: SopExecutor) -> None:
        """v3.9: verify steps expanded to navigate + wait + confirm."""
        from pathlib import Path

        executor._sop_steps_path = Path("/nonexistent/sop_steps.json")
        steps = executor.get_steps()
        ids = [s["id"] for s in steps]
        assert "verify_left_confirm" in ids
        assert "verify_right_confirm" in ids

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


# ---------------------------------------------------------------------------
# Dry-run mode tests (CP-4)
# ---------------------------------------------------------------------------


class TestDryRun:
    """dry_run=True must skip all UI interactions and return success."""

    @pytest.fixture
    def dry_executor(self, vision: VisionEngine, control: ControlEngine) -> SopExecutor:
        return SopExecutor(vision=vision, control=control, dry_run=True)

    def test_dry_run_flag_stored(self, dry_executor: SopExecutor) -> None:
        assert dry_executor._dry_run is True

    def test_dry_run_default_false(self, executor: SopExecutor) -> None:
        assert executor._dry_run is False

    def test_dry_run_click_no_control_call(self, dry_executor: SopExecutor) -> None:
        """dry_run click step must NOT call control.click_target."""
        dry_executor.control.click_target = MagicMock()
        step = {"id": "s", "name": "S", "type": "click", "target": "login_button"}
        success, msg = dry_executor.run_step(step)
        assert success is True
        assert "[DRY-RUN]" in msg
        dry_executor.control.click_target.assert_not_called()

    def test_dry_run_drag_no_control_call(self, dry_executor: SopExecutor) -> None:
        """dry_run drag step must NOT call control.drag_roi."""
        dry_executor.control.drag_roi = MagicMock()
        step = {
            "id": "d",
            "name": "D",
            "type": "drag",
            "start": [100, 200],
            "end": [800, 350],
        }
        success, msg = dry_executor.run_step(step)
        assert success is True
        assert "[DRY-RUN]" in msg
        dry_executor.control.drag_roi.assert_not_called()

    def test_dry_run_type_text_no_control_call(self, dry_executor: SopExecutor) -> None:
        """dry_run type_text step must NOT call control.type_text."""
        dry_executor.control.type_text = MagicMock()
        step = {"id": "t", "name": "T", "type": "type_text", "text": "hello"}
        success, msg = dry_executor.run_step(step)
        assert success is True
        assert "[DRY-RUN]" in msg
        dry_executor.control.type_text.assert_not_called()

    def test_dry_run_press_key_no_control_call(self, dry_executor: SopExecutor) -> None:
        """dry_run press_key step must NOT call control.press_key."""
        dry_executor.control.press_key = MagicMock()
        step = {"id": "k", "name": "K", "type": "press_key", "key": "Return"}
        success, msg = dry_executor.run_step(step)
        assert success is True
        assert "[DRY-RUN]" in msg
        dry_executor.control.press_key.assert_not_called()

    def test_dry_run_wait_ms_skipped(self, dry_executor: SopExecutor) -> None:
        """dry_run wait_ms must not actually sleep (returns immediately)."""
        import time as _time

        step = {"id": "w", "name": "W", "type": "wait_ms", "ms": 5000}
        t0 = _time.monotonic()
        success, msg = dry_executor.run_step(step)
        elapsed = _time.monotonic() - t0
        assert success is True
        assert "[DRY-RUN]" in msg
        assert elapsed < 1.0  # must not have slept 5 seconds

    def test_dry_run_validate_pins_skipped(self, dry_executor: SopExecutor) -> None:
        """dry_run validate_pins must not call vision.capture_screen."""
        dry_executor.vision.capture_screen = MagicMock()
        step = {"id": "v", "name": "V", "type": "validate_pins"}
        success, msg = dry_executor.run_step(step)
        assert success is True
        assert "[DRY-RUN]" in msg
        dry_executor.vision.capture_screen.assert_not_called()

    def test_dry_run_auth_sequence_no_real_calls(
        self, dry_executor: SopExecutor
    ) -> None:
        """dry_run auth_sequence must not call any control methods."""
        dry_executor.control.click_target = MagicMock()
        dry_executor.control.type_text = MagicMock()
        dry_executor.control.press_key = MagicMock()
        step = {
            "id": "login",
            "name": "Login",
            "type": "auth_sequence",
            "login_button": "login_button",
            "password_field": "password_field",
            "ok_button": "ok_button",
        }
        success, msg = dry_executor.run_step(step)
        assert success is True
        dry_executor.control.click_target.assert_not_called()
        dry_executor.control.type_text.assert_not_called()
        dry_executor.control.press_key.assert_not_called()

    def test_dry_run_input_text_no_real_calls(self, dry_executor: SopExecutor) -> None:
        """dry_run input_text must not call control methods."""
        dry_executor.control.click_target = MagicMock()
        dry_executor.control.type_text = MagicMock()
        dry_executor.control.press_key = MagicMock()
        step = {
            "id": "ax",
            "name": "Axis-X",
            "type": "input_text",
            "target": "axis_x_field",
            "text": "123",
        }
        success, _ = dry_executor.run_step(step)
        assert success is True
        dry_executor.control.click_target.assert_not_called()
        dry_executor.control.type_text.assert_not_called()
        dry_executor.control.press_key.assert_not_called()

    def test_dry_run_mold_setup_no_real_calls(self, dry_executor: SopExecutor) -> None:
        """dry_run mold_setup must not call control methods."""
        dry_executor.control.click_target = MagicMock()
        dry_executor.control.drag_roi = MagicMock()
        step = {
            "id": "ml",
            "name": "Mold Left",
            "type": "mold_setup",
            "label_target": "mold_left_label",
            "drag_start": [100, 200],
            "drag_end": [800, 350],
        }
        success, _ = dry_executor.run_step(step)
        assert success is True
        dry_executor.control.click_target.assert_not_called()
        dry_executor.control.drag_roi.assert_not_called()
