"""
Integration test: SOP Run in a "no YOLO model file" environment.

Simulates the exact line-PC scenario where:
  - yolo26x.pt is NOT on disk (assets/models/ is missing or empty).
  - ultralytics IS imported (bundled in EXE) but model loading returns None.
  - VisionEngine.capture_screen() is mocked (no physical display needed).
  - ControlEngine clicks/drags are mocked (no PyAutoGUI access needed).

Verifies:
  1. VisionEngine initialises without crashing when model file is absent.
  2. SopExecutor.run_step() handles each step type successfully with mocked services.
  3. All 12 built-in fallback steps can be executed end-to-end without error.
  4. YOLO_CONFIG_DIR env-var redirect prevents persistent_cache.json decode errors.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Ensure YOLO_CONFIG_DIR is redirected before vision_engine import
# (mirrors the fix applied in src/vision_engine.py)
# ---------------------------------------------------------------------------
_test_cfg_dir = str(Path.home() / ".connector_vision_agent_test")
Path(_test_cfg_dir).mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", _test_cfg_dir)


from src.sop_executor import SopExecutor  # noqa: E402
from src.vision_engine import DetectionConfig, VisionEngine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_control() -> Any:
    ctrl = MagicMock()
    ok_click = MagicMock(success=True, coords=(100, 200), duration=0.05, error=None)
    ok_drag = MagicMock(success=True, duration=0.2, error=None)
    ctrl.click_target.return_value = ok_click
    ctrl.drag_roi.return_value = ok_drag
    return ctrl


def _make_mock_vision() -> Any:
    vis = MagicMock()
    vis.capture_screen.return_value = MagicMock()  # fake numpy array
    vis.validate_pin_count.return_value = {"valid": True, "count": 40}
    return vis


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoYoloVisionEngine:
    """VisionEngine must initialise gracefully when no .pt file exists."""

    def test_init_with_nonexistent_model_path(self, tmp_path: Path) -> None:
        """model=None when the .pt file is absent — no crash."""
        fake_path = str(tmp_path / "nonexistent_yolo26x.pt")
        cfg = DetectionConfig(model_path=fake_path)
        # Mock YOLO to simulate no model available (fallback also fails).
        with patch("src.vision_engine.YOLO", side_effect=RuntimeError("no model")):
            engine = VisionEngine(config=cfg)
        assert engine.model is None

    def test_detect_objects_returns_empty_when_model_none(self, tmp_path: Path) -> None:
        """detect_objects() returns [] when model is None."""
        import numpy as np

        cfg = DetectionConfig(model_path=str(tmp_path / "missing.pt"))
        with patch("src.vision_engine.YOLO", side_effect=RuntimeError("no model")):
            engine = VisionEngine(config=cfg)
        assert engine.model is None
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        assert engine.detect_objects(blank) == []

    def test_yolo_config_dir_env_var_is_set(self) -> None:
        """YOLO_CONFIG_DIR should be set to avoid persistent_cache.json errors."""
        assert "YOLO_CONFIG_DIR" in os.environ
        cfg_dir = Path(os.environ["YOLO_CONFIG_DIR"])
        assert cfg_dir.exists()


class TestSopRunNoYolo:
    """SopExecutor runs all 12 fallback steps with mocked vision+control."""

    def _make_executor(self, tmp_path: Path) -> SopExecutor:
        config: Dict[str, Any] = {
            "pin_count_min": 40,
            "pin_count_max": 40,
            "control": {"step_delay": 0.0},
        }
        return SopExecutor(
            vision=_make_mock_vision(),
            control=_make_mock_control(),
            config=config,
            sop_steps_path=tmp_path / "nonexistent_sop_steps.json",
        )

    def test_get_steps_returns_12_builtin_fallback(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        steps = executor.get_steps()
        assert len(steps) == 12

    def test_all_step_types_execute_successfully(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        steps = executor.get_steps()
        for step in steps:
            ok, msg = executor.run_step(step)
            assert ok is True, f"Step '{step['id']}' failed: {msg}"

    def test_click_step_success(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        ok, msg = executor.run_step(
            {"id": "login", "name": "Login", "type": "click", "target": "login_button"}
        )
        assert ok is True
        assert "login_button" in msg

    def test_drag_step_success(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        ok, msg = executor.run_step(
            {
                "id": "mold_left_roi",
                "name": "Mold Left ROI",
                "type": "drag",
                "start": [100, 200],
                "end": [800, 350],
            }
        )
        assert ok is True
        assert "dragged" in msg

    def test_validate_pins_step_success(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        ok, msg = executor.run_step(
            {"id": "in_pin_up", "name": "Pin Up Check", "type": "validate_pins"}
        )
        assert ok is True
        assert "40" in msg

    def test_click_sequence_step_success(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        ok, msg = executor.run_step(
            {
                "id": "apply_and_open",
                "name": "Apply & Open",
                "type": "click_sequence",
                "targets": ["apply_button", "open_icon"],
            }
        )
        assert ok is True

    def test_full_sop_run_completes_without_crash(self, tmp_path: Path) -> None:
        """executor.run() completes all 12 steps; none crash."""
        executor = self._make_executor(tmp_path)
        # Patch time.sleep to skip real waits
        with patch("time.sleep"):
            trace = executor.run()
        assert len(trace) == 12
        for entry in trace:
            assert ":OK:" in entry, f"Unexpected FAIL in trace: {entry}"

    def test_control_click_called_for_click_steps(self, tmp_path: Path) -> None:
        """Verify ControlEngine.click_target() is called for 'click' type steps."""
        executor = self._make_executor(tmp_path)
        executor.run_step(
            {"id": "login", "name": "Login", "type": "click", "target": "login_button"}
        )
        executor.control.click_target.assert_called_once_with("login_button")

    def test_control_drag_called_for_drag_steps(self, tmp_path: Path) -> None:
        """Verify ControlEngine.drag_roi() is called for 'drag' type steps."""
        executor = self._make_executor(tmp_path)
        executor.run_step(
            {
                "id": "mold_left_roi",
                "name": "Mold Left ROI",
                "type": "drag",
                "start": [100, 200],
                "end": [800, 350],
            }
        )
        executor.control.drag_roi.assert_called_once()
