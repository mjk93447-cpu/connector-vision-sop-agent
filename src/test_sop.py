"""
Pytest suite for the 12-step SOP automation path and vision engine.

These tests focus on wiring and basic invariants without requiring a real
display, PyAutoGUI backend, or YOLO weights. Where necessary, we monkeypatch
the control/vision layers to behave deterministically.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from src.main import main
from src.sop_executor import SopExecutor
from src.control_engine import ControlEngine, ControlResult
from src.vision_engine import VisionEngine, DetectionConfig


def test_full_sop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the full SOP with faked control/vision to ensure 12 steps succeed."""

    # Arrange: build real vision/controls but monkeypatch side effects.
    vision = VisionEngine(DetectionConfig())
    control = ControlEngine(vision_agent=vision, retries=1)
    executor = SopExecutor(vision=vision, control=control)

    # Fake control so that all clicks/drag operations succeed without PyAutoGUI.
    def _fake_click_target(self: ControlEngine, target_name: str) -> ControlResult:
        return ControlResult(success=True, coords=(100, 100), duration=0.01)

    def _fake_drag_roi(
        self: ControlEngine,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> ControlResult:
        return ControlResult(success=True, coords=end, duration=0.02)

    monkeypatch.setattr(ControlEngine, "click_target", _fake_click_target, raising=True)
    monkeypatch.setattr(ControlEngine, "drag_roi", _fake_drag_roi, raising=True)

    # Fake screen capture so tests do not require a real display or pyautogui.
    def _fake_capture_screen(
        self: VisionEngine, region: tuple[int, int, int, int] | None = None
    ) -> np.ndarray:
        return np.zeros((480, 640, 3), dtype=np.uint8)

    monkeypatch.setattr(
        VisionEngine,
        "capture_screen",
        _fake_capture_screen,
        raising=True,
    )

    # Fake pin validation so in_pin_up/in_pin_down both pass.
    def _fake_validate_pin_count(self: VisionEngine, image: Any) -> dict[str, Any]:
        return {"count": 40, "pin_count_min": 20, "valid": True, "centers": []}

    monkeypatch.setattr(
        VisionEngine,
        "validate_pin_count",
        _fake_validate_pin_count,
        raising=True,
    )

    # Act
    result = executor.run()

    # Assert
    assert len(result) == 12
    # 마지막 3단계는 저장/적용/열기 관련이므로 모두 성공 상태여야 한다.
    assert all("OK" in step for step in result[-3:])


def test_main_integration_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure main() wiring returns a 12-step trace even in headless mode.

    We mock control/vision in the same way as the full SOP test so that
    ``src/main.py`` can be validated without a GUI.
    """

    # Monkeypatch the collaborators used inside main().
    from src import main as main_module

    original_vision_engine = main_module.VisionEngine
    original_control_engine = main_module.ControlEngine

    class _TestVision(VisionEngine):
        def validate_pin_count(self, image: Any) -> dict[str, Any]:  # type: ignore[override]
            return {"count": 40, "pin_count_min": 20, "valid": True, "centers": []}

    class _TestControl(ControlEngine):
        def click_target(self, target_name: str) -> ControlResult:  # type: ignore[override]
            return ControlResult(success=True, coords=(100, 100), duration=0.01)

        def drag_roi(  # type: ignore[override]
            self,
            start: tuple[int, int],
            end: tuple[int, int],
        ) -> ControlResult:
            return ControlResult(success=True, coords=end, duration=0.02)

    # Ensure screen capture does not depend on pyautogui in headless tests.
    def _fake_capture_screen(
        self: VisionEngine, region: tuple[int, int, int, int] | None = None
    ) -> np.ndarray:
        return np.zeros((480, 640, 3), dtype=np.uint8)

    monkeypatch.setattr(
        VisionEngine,
        "capture_screen",
        _fake_capture_screen,
        raising=True,
    )

    monkeypatch.setattr(main_module, "VisionEngine", _TestVision, raising=True)
    monkeypatch.setattr(main_module, "ControlEngine", _TestControl, raising=True)

    try:
        trace = main()
    finally:
        # Restore originals for safety in interactive runs.
        main_module.VisionEngine = original_vision_engine
        main_module.ControlEngine = original_control_engine

    assert len(trace) == 12
    assert all("OK" in step for step in trace[-3:])


def test_vision_smoke() -> None:
    """Basic smoke test for the vision engine with a synthetic image."""

    vision = VisionEngine(DetectionConfig())

    # Synthetic blank grayscale image; detect_ui_targets(None) uses defaults.
    dummy_image = np.zeros((480, 640), dtype=np.uint8)

    # Pin validation should run and return a structured dict.
    validation = vision.validate_pin_count(dummy_image)
    assert "count" in validation
    assert "valid" in validation

    # Default UI target labels should be surfaced when no image is provided.
    labels = vision.detect_ui_targets()
    assert isinstance(labels, list)
    assert len(labels) >= 1
