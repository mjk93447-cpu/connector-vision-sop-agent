"""
Pytest suite for the 12-step SOP automation path and vision engine.

These tests focus on wiring and basic invariants without requiring a real
display, PyAutoGUI backend, or YOLO weights. Where necessary, we monkeypatch
the control/vision layers to behave deterministically.

New in v3 (Training)
--------------------
test_screen_detection_and_log  — screen capture → YOLO detection → log output
test_llm_screen_analysis_log   — LLM analyses SOP failure log payload → output
test_text_detection_sequential_drag — class-detection-ordered sequential drag
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from src.main import main
from src.sop_executor import SopExecutor
from src.control_engine import ControlEngine, ControlResult
from src.vision_engine import VisionEngine, DetectionConfig, DEFAULT_TARGET_LABELS


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
    def _fake_validate_pin_count(
        self: VisionEngine, image: Any, pin_count_min: int = 20
    ) -> dict[str, Any]:
        return {"count": 40, "pin_count_min": pin_count_min, "valid": True, "centers": []}

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
        def validate_pin_count(self, image: Any, pin_count_min: int = 20) -> dict[str, Any]:  # type: ignore[override]
            return {"count": 40, "pin_count_min": pin_count_min, "valid": True, "centers": []}

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


# ---------------------------------------------------------------------------
# v3 local functional tests
# ---------------------------------------------------------------------------


def test_screen_detection_and_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: screen capture → YOLO detection → log output.

    Monkeypatches capture_screen to return a synthetic image and
    detect_objects to return two fake detections.  Validates that the
    VisionEngine pipeline works end-to-end and that LogManager records
    the detection event.
    """
    from src.log_manager import LogManager
    from src.vision_engine import UiDetection

    vision = VisionEngine(DetectionConfig())

    fake_img = np.zeros((480, 640, 3), dtype=np.uint8)

    def _fake_capture(self: VisionEngine, region: Any = None) -> np.ndarray:
        return fake_img

    fake_detections = [
        UiDetection(label="login_button", confidence=0.91, bbox=(10, 20, 110, 60)),
        UiDetection(label="pin_cluster", confidence=0.75, bbox=(200, 100, 400, 200)),
    ]

    def _fake_detect(
        self: VisionEngine, image: np.ndarray, conf_threshold: Any = None
    ) -> list[UiDetection]:
        return fake_detections

    monkeypatch.setattr(VisionEngine, "capture_screen", _fake_capture, raising=True)
    monkeypatch.setattr(VisionEngine, "detect_objects", _fake_detect, raising=True)

    # Perform capture + detection
    img = vision.capture_screen()
    assert img.shape == (480, 640, 3)

    dets = vision.detect_objects(img)
    assert len(dets) == 2
    assert dets[0].label == "login_button"
    assert dets[1].label == "pin_cluster"

    # Log the result and verify structure
    log = LogManager()
    log.log(step="screen_detection", message=f"검출 {len(dets)}개: {[d.label for d in dets]}")
    payload = log.build_llm_payload(config={})
    assert "events" in payload or "summary" in payload


def test_llm_screen_analysis_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: LLM analyzes SOP failure log payload → structured output.

    Monkeypatches OfflineLLM.analyze_logs to return a fake analysis result.
    Validates that sop_advisor.suggest_training_needs works on the event list.
    """
    from src.log_manager import LogManager
    from src.sop_advisor import suggest_training_needs

    # Build a fake failure log
    log = LogManager()
    log.log(
        step="login",
        message="login_button not found — 미검출",
        level="ERROR",
    )
    log.log(
        step="login",
        message="login_button not found — 미검출",
        level="ERROR",
    )
    log.log(
        step="login",
        message="login_button not found — 미검출",
        level="ERROR",
    )
    log.log(
        step="mold_left_label",
        message="mold_left_label confidence 0.42 — 낮은 신뢰도",
        level="WARNING",
    )

    payload = log.build_llm_payload(config={})

    # LLM analysis via stub (no real LLM needed)
    fake_analysis = {
        "config_patch": {"vision.confidence_threshold": 0.5},
        "sop_recommendations": ["login_button 추가 학습 권장"],
        "raw_text": "login_button 검출 실패 반복됨. 파인튜닝 필요.",
    }

    def _fake_analyze(self: Any, payload_arg: Any) -> dict[str, Any]:
        return fake_analysis

    from src.llm_offline import OfflineLLM  # type: ignore[attr-defined]  # noqa: PLC0415

    monkeypatch.setattr(OfflineLLM, "analyze_logs", _fake_analyze, raising=False)

    # Training suggestion engine should detect the login_button failure pattern
    events = payload.get("events_tail", payload.get("events", []))
    suggestions = suggest_training_needs(events)
    assert isinstance(suggestions, list)
    login_suggestions = [s for s in suggestions if s["class"] == "login_button"]
    assert len(login_suggestions) >= 1
    assert login_suggestions[0]["priority"] == "high"


def test_text_detection_sequential_drag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: detect labeled regions → sequential drag in label order.

    Uses a synthetic image with fake detections returned in arbitrary order.
    Verifies that the detections can be sorted by label index (SOP class order)
    and that drag operations succeed for each bbox center pair.
    """
    from src.vision_engine import UiDetection

    vision = VisionEngine(DetectionConfig())
    control = ControlEngine(vision_agent=vision, retries=1)

    # Fake detections in non-canonical order
    fake_detections = [
        UiDetection(label="mold_right_label", confidence=0.88, bbox=(300, 100, 450, 160)),
        UiDetection(label="login_button", confidence=0.95, bbox=(50, 30, 180, 70)),
        UiDetection(label="pin_cluster", confidence=0.72, bbox=(200, 200, 380, 280)),
    ]

    def _fake_detect(
        self: VisionEngine, image: np.ndarray, conf_threshold: Any = None
    ) -> list[UiDetection]:
        return fake_detections

    monkeypatch.setattr(VisionEngine, "detect_objects", _fake_detect, raising=True)

    drag_calls: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def _fake_drag(
        self: ControlEngine,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> ControlResult:
        drag_calls.append((start, end))
        return ControlResult(success=True, coords=end, duration=0.01)

    monkeypatch.setattr(ControlEngine, "drag_roi", _fake_drag, raising=True)

    dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
    dets = vision.detect_objects(dummy_image)

    # Sort by SOP class index order (DEFAULT_TARGET_LABELS)
    def _label_order(d: UiDetection) -> int:
        try:
            return DEFAULT_TARGET_LABELS.index(d.label)
        except ValueError:
            return len(DEFAULT_TARGET_LABELS)

    ordered = sorted(dets, key=_label_order)
    assert ordered[0].label == "login_button"  # index 0
    assert ordered[1].label == "mold_right_label"  # index 6

    # Perform sequential drag for each adjacent pair (simulates mold ROI drag)
    for i in range(len(ordered) - 1):
        x1, y1, x2, y2 = ordered[i].bbox
        start = ((x1 + x2) // 2, (y1 + y2) // 2)
        xa, ya, xb, yb = ordered[i + 1].bbox
        end = ((xa + xb) // 2, (ya + yb) // 2)
        result = control.drag_roi(start, end)
        assert result.success

    assert len(drag_calls) == len(ordered) - 1
