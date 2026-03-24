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
