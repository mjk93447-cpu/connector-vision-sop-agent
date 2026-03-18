"""
Unit tests for src/control_engine.py.

Focus areas:
- ControlEngine construction (with/without OCR, sop_steps)
- _normalize_target_name() — target_name → OCR search candidates
- _resolve_target_coordinates() — OCR-first strategy
  * button_text_map hit
  * normalized target_name fallback (Bug 1 fix: "login_button" → "login")
  * YOLO26x fallback when OCR returns nothing
  * all-fail returns None

All YOLO / screen / pyautogui interactions are mocked.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.control_engine import ControlEngine
from src.ocr_engine import TextRegion
from src.vision_engine import DetectionConfig, UiDetection, VisionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bgr(h: int = 100, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_region(
    text: str,
    x: int = 50,
    y: int = 50,
    conf: float = 1.0,
) -> TextRegion:
    return TextRegion(
        text=text,
        bbox=(x, y, 80, 20),
        confidence=conf,
        center=(x + 40, y + 10),
        source="mock",
    )


def _make_detection(label: str = "login_button") -> UiDetection:
    return UiDetection(label=label, confidence=0.9, bbox=(10, 10, 100, 50))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vision() -> VisionEngine:
    """VisionEngine without loading actual YOLO weights."""
    with patch.object(VisionEngine, "_load_model", return_value=None):
        v = VisionEngine(DetectionConfig(confidence_threshold=0.5))
    return v


@pytest.fixture
def mock_ocr() -> MagicMock:
    """OCREngine mock that returns no matches by default."""
    ocr = MagicMock()
    ocr.find_text.return_value = None
    return ocr


@pytest.fixture
def sop_steps() -> List[dict]:
    return [
        {
            "id": "login",
            "target": "login_button",
            "button_text": "LOGIN",
            "enabled": True,
        },
        {
            "id": "save",
            "target": "save_button",
            "button_text": "SAVE",
            "enabled": True,
        },
    ]


@pytest.fixture
def engine(
    vision: VisionEngine, mock_ocr: MagicMock, sop_steps: List[dict]
) -> ControlEngine:
    """ControlEngine with mock OCR and sop_steps wired up."""
    return ControlEngine(
        vision_agent=vision,
        ocr_engine=mock_ocr,
        sop_steps=sop_steps,
    )


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_button_text_map_populated(
        self, vision: VisionEngine, sop_steps: List[dict]
    ) -> None:
        ctrl = ControlEngine(vision_agent=vision, sop_steps=sop_steps)
        assert ctrl._button_text_map.get("login_button") == "LOGIN"
        assert ctrl._button_text_map.get("save_button") == "SAVE"

    def test_button_text_map_empty_without_steps(self, vision: VisionEngine) -> None:
        ctrl = ControlEngine(vision_agent=vision)
        assert ctrl._button_text_map == {}

    def test_ocr_none_without_engine(self, vision: VisionEngine) -> None:
        ctrl = ControlEngine(vision_agent=vision)
        assert ctrl._ocr is None

    def test_ocr_stored_when_provided(
        self, vision: VisionEngine, mock_ocr: MagicMock
    ) -> None:
        ctrl = ControlEngine(vision_agent=vision, ocr_engine=mock_ocr)
        assert ctrl._ocr is mock_ocr


# ---------------------------------------------------------------------------
# _normalize_target_name tests
# ---------------------------------------------------------------------------


class TestNormalizeTargetName:
    def test_button_suffix_stripped(self) -> None:
        candidates = ControlEngine._normalize_target_name("login_button")
        assert "login" in candidates

    def test_button_suffix_also_adds_button_phrasing(self) -> None:
        candidates = ControlEngine._normalize_target_name("login_button")
        assert "login button" in candidates

    def test_btn_suffix_stripped(self) -> None:
        candidates = ControlEngine._normalize_target_name("submit_btn")
        assert "submit" in candidates
        assert "submit button" in candidates

    def test_field_suffix_stripped(self) -> None:
        candidates = ControlEngine._normalize_target_name("password_field")
        assert "password" in candidates
        # No "button" variant for _field suffix
        assert "password button" not in candidates

    def test_label_suffix_stripped(self) -> None:
        candidates = ControlEngine._normalize_target_name("mold_left_label")
        assert "mold left" in candidates

    def test_no_suffix_returns_readable_name(self) -> None:
        candidates = ControlEngine._normalize_target_name("save_button")
        assert "save" in candidates

    def test_multi_word_underscores_become_spaces(self) -> None:
        candidates = ControlEngine._normalize_target_name("recipe_button")
        assert "recipe" in candidates

    def test_no_known_suffix(self) -> None:
        candidates = ControlEngine._normalize_target_name("axis_mark")
        assert "axis mark" in candidates


# ---------------------------------------------------------------------------
# _resolve_target_coordinates tests
# ---------------------------------------------------------------------------


class TestResolveTargetCoordinates:
    def test_ocr_button_text_map_hit(
        self,
        engine: ControlEngine,
        mock_ocr: MagicMock,
    ) -> None:
        """When button_text_map has an entry, OCR should be called with that text."""
        expected_region = _make_region("LOGIN", x=200, y=100)
        mock_ocr.find_text.return_value = expected_region

        img = _make_bgr()
        coords = engine._resolve_target_coordinates("login_button", image=img)

        # Should use button_text "LOGIN" from map
        mock_ocr.find_text.assert_called_once_with(img, "LOGIN", fuzzy=True)
        assert coords == expected_region.center

    def test_ocr_normalized_fallback_when_no_map_entry(
        self,
        vision: VisionEngine,
        mock_ocr: MagicMock,
    ) -> None:
        """Bug 1 fix: Even without button_text_map, 'login_button' → 'login' OCR search."""
        # No sop_steps passed — button_text_map is empty
        ctrl = ControlEngine(vision_agent=vision, ocr_engine=mock_ocr)

        # OCR returns a match for "login" candidate
        login_region = _make_region("login", x=300, y=150)

        def find_text_side_effect(img, text, fuzzy=True):
            if text.lower() == "login":
                return login_region
            return None

        mock_ocr.find_text.side_effect = find_text_side_effect

        img = _make_bgr()
        coords = ctrl._resolve_target_coordinates("login_button", image=img)

        assert coords == login_region.center

    def test_ocr_normalized_fallback_tries_all_candidates(
        self,
        vision: VisionEngine,
        mock_ocr: MagicMock,
    ) -> None:
        """If 'login' fails, 'login button' should also be tried."""
        ctrl = ControlEngine(vision_agent=vision, ocr_engine=mock_ocr)

        login_button_region = _make_region("login button", x=400, y=200)

        def find_text_side_effect(img, text, fuzzy=True):
            if text.lower() == "login button":
                return login_button_region
            return None

        mock_ocr.find_text.side_effect = find_text_side_effect

        img = _make_bgr()
        coords = ctrl._resolve_target_coordinates("login_button", image=img)

        assert coords == login_button_region.center

    def test_yolo_fallback_when_ocr_finds_nothing(
        self,
        engine: ControlEngine,
        mock_ocr: MagicMock,
    ) -> None:
        """When all OCR attempts return None, YOLO26x detection is used."""
        mock_ocr.find_text.return_value = None

        yolo_detection = _make_detection("login_button")
        with patch.object(engine.vision, "find_detection", return_value=yolo_detection):
            img = _make_bgr()
            coords = engine._resolve_target_coordinates("login_button", image=img)

        # YOLO center = ((10+100)//2, (10+50)//2)
        assert coords == (55, 30)

    def test_returns_none_when_all_fail(
        self,
        engine: ControlEngine,
        mock_ocr: MagicMock,
    ) -> None:
        """Returns None if neither OCR nor YOLO finds the target."""
        mock_ocr.find_text.return_value = None
        with patch.object(engine.vision, "find_detection", return_value=None):
            img = _make_bgr()
            coords = engine._resolve_target_coordinates("nonexistent_button", image=img)
        assert coords is None

    def test_no_ocr_falls_back_to_yolo_directly(
        self,
        vision: VisionEngine,
    ) -> None:
        """Without OCR engine, resolution goes straight to YOLO26x."""
        ctrl = ControlEngine(vision_agent=vision)  # no ocr_engine

        yolo_detection = _make_detection("login_button")
        with patch.object(ctrl.vision, "find_detection", return_value=yolo_detection):
            img = _make_bgr()
            coords = ctrl._resolve_target_coordinates("login_button", image=img)

        assert coords == (55, 30)

    def test_screenshot_captured_when_image_is_none(
        self,
        engine: ControlEngine,
        mock_ocr: MagicMock,
    ) -> None:
        """When image=None, vision.capture_screen() is called."""
        captured = _make_bgr()
        mock_ocr.find_text.return_value = _make_region("LOGIN")

        with patch.object(
            engine.vision, "capture_screen", return_value=captured
        ) as cap:
            engine._resolve_target_coordinates("login_button", image=None)

        cap.assert_called_once()
