"""
Unit tests for src/ocr_engine.py.

Uses mocks for WinRT and PaddleOCR — no external dependencies required.
"""

from __future__ import annotations

import sys
from typing import List
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from src.ocr_engine import OCREngine, TextRegion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bgr(h: int = 100, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_region(text: str, x: int = 10, y: int = 10, conf: float = 1.0) -> TextRegion:
    return TextRegion(
        text=text,
        bbox=(x, y, 80, 20),
        confidence=conf,
        center=(x + 40, y + 10),
        source="mock",
    )


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------


class TestBackendResolution:
    def test_explicit_winrt(self) -> None:
        engine = OCREngine(backend="winrt")
        assert engine.backend == "winrt"

    def test_explicit_paddleocr(self) -> None:
        engine = OCREngine(backend="paddleocr")
        assert engine.backend == "paddleocr"

    def test_auto_falls_back_to_easyocr_when_winrt_unavailable(self) -> None:
        with patch("src.ocr_engine._check_winrt", return_value=False), patch(
            "src.ocr_engine._check_easyocr", return_value=True
        ):
            engine = OCREngine(backend="auto")
        assert engine.backend == "easyocr"

    def test_auto_falls_back_to_paddleocr_when_both_unavailable(self) -> None:
        with patch("src.ocr_engine._check_winrt", return_value=False), patch(
            "src.ocr_engine._check_easyocr", return_value=False
        ):
            engine = OCREngine(backend="auto")
        assert engine.backend == "paddleocr"

    def test_auto_uses_winrt_when_available(self) -> None:
        with patch("src.ocr_engine._check_winrt", return_value=True):
            engine = OCREngine(backend="auto")
        assert engine.backend == "winrt"


# ---------------------------------------------------------------------------
# scan_all — PaddleOCR mock
# ---------------------------------------------------------------------------


class TestScanAllPaddleOCR:
    def _make_engine_with_mock_paddle(self, regions: List[TextRegion]) -> OCREngine:
        engine = OCREngine(backend="paddleocr")

        def _mock_scan(img: np.ndarray) -> List[TextRegion]:
            return regions

        engine._scan_paddleocr = _mock_scan  # type: ignore[method-assign]
        return engine

    def test_scan_all_returns_list(self) -> None:
        engine = self._make_engine_with_mock_paddle([_make_region("LOGIN")])
        result = engine.scan_all(_make_bgr())
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].text == "LOGIN"

    def test_scan_all_empty_when_no_text(self) -> None:
        engine = self._make_engine_with_mock_paddle([])
        result = engine.scan_all(_make_bgr())
        assert result == []

    def test_scan_all_returns_empty_on_exception(self) -> None:
        engine = OCREngine(backend="paddleocr")
        engine._paddle = None

        def _raise(img: np.ndarray) -> List[TextRegion]:
            raise RuntimeError("paddle unavailable")

        engine._scan_paddleocr = _raise  # type: ignore[method-assign]
        result = engine.scan_all(_make_bgr())
        assert result == []


# ---------------------------------------------------------------------------
# find_text — exact + fuzzy matching
# ---------------------------------------------------------------------------


class TestFindText:
    def _make_engine(self, regions: List[TextRegion]) -> OCREngine:
        engine = OCREngine(backend="paddleocr")
        engine.scan_all = lambda img: regions  # type: ignore[method-assign]
        return engine

    def test_exact_match(self) -> None:
        regions = [_make_region("LOGIN")]
        engine = self._make_engine(regions)
        result = engine.find_text(_make_bgr(), "LOGIN")
        assert result is not None
        assert result.text == "LOGIN"

    def test_case_insensitive_match(self) -> None:
        regions = [_make_region("LOGIN")]
        engine = self._make_engine(regions)
        result = engine.find_text(_make_bgr(), "login")
        assert result is not None

    def test_fuzzy_match_typo(self) -> None:
        # "LOGON" vs "LOGIN" — fuzzy match should find it at low threshold
        regions = [_make_region("LOGON")]
        engine = self._make_engine(regions)
        result = engine.find_text(_make_bgr(), "LOGIN", fuzzy=True, threshold=0.60)
        assert result is not None

    def test_fuzzy_match_too_different(self) -> None:
        regions = [_make_region("SAVE")]
        engine = self._make_engine(regions)
        result = engine.find_text(_make_bgr(), "LOGIN", fuzzy=True, threshold=0.80)
        assert result is None

    def test_no_match_returns_none(self) -> None:
        engine = self._make_engine([])
        result = engine.find_text(_make_bgr(), "LOGIN")
        assert result is None

    def test_returns_best_match(self) -> None:
        regions = [
            _make_region("LGN", x=10),  # poor match
            _make_region("LOGIN", x=50),  # perfect match
        ]
        engine = self._make_engine(regions)
        result = engine.find_text(_make_bgr(), "LOGIN")
        assert result is not None
        assert result.text == "LOGIN"

    def test_exact_mode_no_fuzzy(self) -> None:
        regions = [_make_region("LOGI")]
        engine = self._make_engine(regions)
        result = engine.find_text(_make_bgr(), "LOGIN", fuzzy=False)
        assert result is None

    def test_custom_threshold(self) -> None:
        regions = [_make_region("LOGN")]
        engine = self._make_engine(regions)
        # High threshold — "LOGN" vs "LOGIN" should fail
        result = engine.find_text(_make_bgr(), "LOGIN", threshold=0.99)
        assert result is None
        # Low threshold — should pass
        result = engine.find_text(_make_bgr(), "LOGIN", threshold=0.50)
        assert result is not None


# ---------------------------------------------------------------------------
# PaddleOCR raw output parsing
# ---------------------------------------------------------------------------


class TestPaddleOCRParsing:
    """Tests for _scan_paddleocr raw-output parsing.

    _scan_paddleocr now iterates _preprocess_variants (4 variants) internally.
    We patch _preprocess_variants to return a single variant equal to the input
    image so the mock paddle is called exactly once and assertions remain simple.
    """

    def test_parse_paddle_output_format(self) -> None:
        """Verify _scan_paddleocr converts PaddleOCR raw output to TextRegion list.
        Uses spec=['ocr'] so hasattr(mock, 'predict') is False → 2.x code path taken.
        """
        engine = OCREngine(backend="paddleocr")
        # Use spec to prevent MagicMock from synthesising a 'predict' attribute
        mock_paddle = MagicMock(spec=["ocr"])
        # PaddleOCR returns: [[ [[[x1,y1],[x2,y1],[x2,y2],[x1,y2]], ("TEXT", 0.99)], ... ]]
        mock_paddle.ocr.return_value = [
            [
                [[[10, 10], [90, 10], [90, 30], [10, 30]], ("LOGIN", 0.99)],
                [[[10, 50], [80, 50], [80, 70], [10, 70]], ("SAVE", 0.95)],
            ]
        ]
        engine._paddle = mock_paddle
        img = _make_bgr()
        # Patch _preprocess_variants to return a single variant so mock is called once
        with patch.object(OCREngine, "_preprocess_variants", return_value=[img]):
            results = engine._scan_paddleocr(img)
        assert len(results) == 2
        assert results[0].text == "LOGIN"
        assert results[0].confidence == pytest.approx(0.99)
        assert results[0].source == "paddleocr"
        assert results[1].text == "SAVE"

    def test_handles_empty_paddle_output(self) -> None:
        engine = OCREngine(backend="paddleocr")
        mock_paddle = MagicMock(spec=["ocr"])
        mock_paddle.ocr.return_value = [[]]
        engine._paddle = mock_paddle
        img = _make_bgr()
        with patch.object(OCREngine, "_preprocess_variants", return_value=[img]):
            results = engine._scan_paddleocr(img)
        assert results == []

    def test_handles_none_paddle_output(self) -> None:
        engine = OCREngine(backend="paddleocr")
        mock_paddle = MagicMock(spec=["ocr"])
        mock_paddle.ocr.return_value = None
        engine._paddle = mock_paddle
        img = _make_bgr()
        with patch.object(OCREngine, "_preprocess_variants", return_value=[img]):
            results = engine._scan_paddleocr(img)
        assert results == []


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


class TestPreprocess:
    def test_preprocess_returns_bgr_array(self) -> None:
        img = _make_bgr(100, 200)
        out = OCREngine._preprocess(img)
        assert out.ndim == 3
        assert out.shape[2] == 3

    def test_preprocess_adds_border(self) -> None:
        img = _make_bgr(100, 200)
        out = OCREngine._preprocess(img)
        # Should be larger (border added)
        assert out.shape[0] > 100
        assert out.shape[1] > 200


# ---------------------------------------------------------------------------
# WinRT en-US fallback logic
# ---------------------------------------------------------------------------
#
# Strategy: instead of mocking the deep WinRT call chain, we patch the
# internal helper that wraps the WinRT import block.  Specifically, we
# monkey-patch OCREngine._scan_winrt at a higher level to exercise only
# the fallback branching logic that was added in commit 7b25dde.
#
# The branching lives *inside* _scan_winrt, so the cleanest approach is
# to patch `winrt.windows.media.ocr.OcrEngine` method return values and
# ensure recognize_async is a coroutine (AsyncMock).


class TestWinRTEnglishFallback:
    def _build_winrt_sys_modules(
        self,
        profile_engine: object,
        lang_engine: object,
    ) -> dict:
        """Build a sys.modules patch dict whose attribute hierarchy mirrors the real WinRT tree.

        Python resolves `import winrt.windows.media.ocr as wocr` by following the attribute
        chain on the top-level `winrt` object, not by direct sys.modules key lookup.  We must
        therefore wire each level so attribute traversal reaches our configured mock.
        """
        from unittest.mock import AsyncMock

        mock_wocr = MagicMock()
        mock_wocr.OcrEngine.try_create_from_user_profile_languages.return_value = (
            profile_engine
        )
        mock_wocr.OcrEngine.try_create_from_language.return_value = lang_engine

        if lang_engine is not None:
            mock_ocr_result = MagicMock()
            mock_ocr_result.lines = []
            lang_engine.recognize_async = AsyncMock(return_value=mock_ocr_result)

        if profile_engine is not None:
            mock_ocr_result2 = MagicMock()
            mock_ocr_result2.lines = []
            profile_engine.recognize_async = AsyncMock(return_value=mock_ocr_result2)

        mock_wg = MagicMock()
        mock_wgi = MagicMock()
        mock_wss = MagicMock()

        # Build the object attribute hierarchy
        mock_media = MagicMock()
        mock_media.ocr = mock_wocr
        mock_graphics = MagicMock()
        mock_graphics.imaging = mock_wgi
        mock_storage = MagicMock()
        mock_storage.streams = mock_wss
        mock_windows = MagicMock()
        mock_windows.media = mock_media
        mock_windows.globalization = mock_wg
        mock_windows.graphics = mock_graphics
        mock_windows.storage = mock_storage
        mock_winrt = MagicMock()
        mock_winrt.windows = mock_windows

        return {
            "winsdk": mock_winrt,
            "winsdk.windows": mock_windows,
            "winsdk.windows.media": mock_media,
            "winsdk.windows.media.ocr": mock_wocr,
            "winsdk.windows.globalization": mock_wg,
            "winsdk.windows.graphics": mock_graphics,
            "winsdk.windows.graphics.imaging": mock_wgi,
            "winsdk.windows.storage": mock_storage,
            "winsdk.windows.storage.streams": mock_wss,
        }

    def _clear_winrt_imports(self) -> None:
        """Remove any cached winsdk sub-modules so patch.dict takes effect."""
        for key in list(sys.modules.keys()):
            if key.startswith("winsdk"):
                del sys.modules[key]

    def test_tries_en_us_when_profile_returns_none(self) -> None:
        """profile returns None → try_create_from_language called once → result list returned."""
        mock_lang_engine = MagicMock()
        self._clear_winrt_imports()
        mods = self._build_winrt_sys_modules(
            profile_engine=None,
            lang_engine=mock_lang_engine,
        )
        engine = OCREngine(backend="winrt")
        with patch.dict(sys.modules, mods):
            result = engine._scan_winrt(_make_bgr())
        assert isinstance(result, list)
        mods[
            "winsdk.windows.media.ocr"
        ].OcrEngine.try_create_from_language.assert_called_once()

    def test_raises_when_both_winrt_none(self) -> None:
        """Both profile and en-US return None → RuntimeError caught → PaddleOCR fallback → []."""
        self._clear_winrt_imports()
        mods = self._build_winrt_sys_modules(profile_engine=None, lang_engine=None)
        engine = OCREngine(backend="winrt")
        engine._scan_paddleocr = lambda img: []  # type: ignore[method-assign]
        with patch.dict(sys.modules, mods):
            result = engine._scan_winrt(_make_bgr())
        # RuntimeError raised, caught by outer except → paddleocr fallback
        assert result == []
        assert engine._backend == "paddleocr"


# ---------------------------------------------------------------------------
# OCR health check (_check_ocr_health in src/main.py)
# ---------------------------------------------------------------------------


class TestOcrHealthCheck:
    def test_health_check_ok_when_scan_returns_regions(self) -> None:
        from src.main import _check_ocr_health

        mock_ocr = MagicMock()
        mock_ocr.scan_all.return_value = [MagicMock(text="Login")]
        mock_ocr._backend = "winrt"
        result = _check_ocr_health(mock_ocr)
        assert "OK" in result

    def test_health_check_warn_when_scan_returns_empty(self) -> None:
        from src.main import _check_ocr_health

        mock_ocr = MagicMock()
        mock_ocr.scan_all.return_value = []
        mock_ocr._backend = "paddleocr"
        result = _check_ocr_health(mock_ocr)
        assert "WARN" in result


# ---------------------------------------------------------------------------
# _merge_adjacent_regions — multi-word button label merging
# ---------------------------------------------------------------------------


class TestMergeAdjacentRegions:
    def _r(self, text: str, x: int, y: int, w: int = 60, h: int = 20) -> TextRegion:
        return TextRegion(
            text=text,
            bbox=(x, y, w, h),
            confidence=1.0,
            center=(x + w // 2, y + h // 2),
            source="winrt",
        )

    def test_two_words_same_line_merged(self) -> None:
        """'Image'(x=10) + 'Source'(x=80) on same y → produces 'Image Source' region."""
        regions = [self._r("Image", x=10, y=10), self._r("Source", x=80, y=12)]
        result = OCREngine._merge_adjacent_regions(regions)
        texts = [r.text for r in result]
        assert "Image Source" in texts

    def test_words_different_lines_not_merged(self) -> None:
        """Words on very different y lines must NOT be merged."""
        regions = [self._r("Save", x=10, y=10), self._r("Cancel", x=10, y=60)]
        result = OCREngine._merge_adjacent_regions(regions)
        texts = [r.text for r in result]
        assert "Save Cancel" not in texts
        assert any(t == "Save" for t in texts)
        assert any(t == "Cancel" for t in texts)

    def test_three_words_same_line(self) -> None:
        """'Image' + 'Source' + 'Path' on same line → 'Image Source Path' merged."""
        regions = [
            self._r("Image", x=10, y=10),
            self._r("Source", x=80, y=10),
            self._r("Path", x=150, y=10),
        ]
        result = OCREngine._merge_adjacent_regions(regions)
        texts = [r.text for r in result]
        assert "Image Source Path" in texts

    def test_wide_gap_words_not_merged(self) -> None:
        """Words separated by very large gap (> 1.5 * word_width) not merged."""
        regions = [
            self._r("Save", x=10, y=10, w=50),
            self._r("Cancel", x=300, y=10, w=60),
        ]
        result = OCREngine._merge_adjacent_regions(regions)
        texts = [r.text for r in result]
        assert "Save Cancel" not in texts

    def test_empty_input(self) -> None:
        assert OCREngine._merge_adjacent_regions([]) == []

    def test_single_region_unchanged(self) -> None:
        regions = [self._r("Login", x=10, y=10)]
        result = OCREngine._merge_adjacent_regions(regions)
        assert any(r.text == "Login" for r in result)

    def test_merged_bbox_covers_both_words(self) -> None:
        r1 = self._r("Image", x=10, y=10, w=50, h=20)
        r2 = self._r("Source", x=70, y=10, w=60, h=20)
        result = OCREngine._merge_adjacent_regions([r1, r2])
        merged = next(r for r in result if r.text == "Image Source")
        mx, my, mw, mh = merged.bbox
        assert mx <= 10
        assert mx + mw >= 70 + 60  # covers rightmost word

    def test_original_regions_preserved(self) -> None:
        """Original word-level regions must still appear in the output."""
        regions = [self._r("Save", x=10, y=10), self._r("As", x=80, y=10)]
        result = OCREngine._merge_adjacent_regions(regions)
        texts = [r.text for r in result]
        assert "Save" in texts
        assert "As" in texts
        assert "Save As" in texts  # merged version also present


# ---------------------------------------------------------------------------
# _bbox_iou + _dedup_regions
# ---------------------------------------------------------------------------


class TestBboxIou:
    def test_identical_boxes_iou_one(self) -> None:
        iou = OCREngine._bbox_iou((0, 0, 100, 50), (0, 0, 100, 50))
        assert iou == pytest.approx(1.0)

    def test_non_overlapping_iou_zero(self) -> None:
        iou = OCREngine._bbox_iou((0, 0, 50, 50), (100, 100, 50, 50))
        assert iou == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        # A=(0,0,100,100) area=10000, B=(50,50,100,100) area=10000
        # intersection=(50,50,50,50)=2500, union=17500 → IoU≈0.143
        iou = OCREngine._bbox_iou((0, 0, 100, 100), (50, 50, 100, 100))
        assert 0.13 < iou < 0.16

    def test_fully_contained_high_iou(self) -> None:
        # small box inside big box: IoU = small_area / big_area
        iou = OCREngine._bbox_iou((0, 0, 100, 100), (25, 25, 50, 50))
        # intersection=2500, union=10000+2500-2500=10000 → IoU=0.25
        assert iou == pytest.approx(0.25)


class TestDedup:
    def _r(
        self, text: str, x: int, y: int, w: int = 80, h: int = 20, conf: float = 1.0
    ) -> TextRegion:
        return TextRegion(
            text=text,
            bbox=(x, y, w, h),
            confidence=conf,
            center=(x + w // 2, y + h // 2),
            source="mock",
        )

    def test_identical_bbox_deduped(self) -> None:
        """Two regions with identical bbox → keep higher confidence one."""
        regions = [
            self._r("LOGIN", 10, 10, conf=0.9),
            self._r("LOGIN", 10, 10, conf=0.7),
        ]
        result = OCREngine._dedup_regions(regions)
        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.9)

    def test_high_iou_deduped(self) -> None:
        """Regions with IoU > 0.5 → keep highest confidence."""
        regions = [
            self._r("LOGIN", 10, 10, w=80, h=20, conf=0.8),
            self._r("L0GIN", 11, 10, w=80, h=20, conf=0.6),  # near-identical bbox
        ]
        result = OCREngine._dedup_regions(regions)
        assert len(result) == 1
        assert result[0].text == "LOGIN"  # higher confidence kept

    def test_low_iou_both_kept(self) -> None:
        """Non-overlapping regions → both kept."""
        regions = [
            self._r("LOGIN", 10, 10, w=80, h=20),
            self._r("SAVE", 200, 150, w=80, h=20),
        ]
        result = OCREngine._dedup_regions(regions)
        assert len(result) == 2

    def test_empty_input(self) -> None:
        assert OCREngine._dedup_regions([]) == []

    def test_single_region_unchanged(self) -> None:
        r = self._r("OK", 5, 5)
        result = OCREngine._dedup_regions([r])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _preprocess_variants
# ---------------------------------------------------------------------------


class TestPreprocessVariants:
    def test_returns_list_of_arrays(self) -> None:
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        variants = OCREngine._preprocess_variants(img)
        assert isinstance(variants, list)
        assert len(variants) >= 4

    def test_all_variants_are_bgr(self) -> None:
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        variants = OCREngine._preprocess_variants(img)
        for v in variants:
            assert v.ndim == 3, "Each variant must be a 3-channel BGR array"
            assert v.shape[2] == 3

    def test_variants_have_same_or_larger_size(self) -> None:
        """Variants may have border padding but must not shrink."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        variants = OCREngine._preprocess_variants(img)
        for v in variants:
            assert v.shape[0] >= 100
            assert v.shape[1] >= 200

    def test_colored_button_variant_differs_from_gray(self) -> None:
        """Blue background with white text: max-channel should differ from gray variant."""
        img = np.full((100, 200, 3), (200, 100, 30), dtype=np.uint8)
        img[40:60, 60:140] = (255, 255, 255)  # white text area
        variants = OCREngine._preprocess_variants(img)
        gray_simple = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        differs = any(
            not np.array_equal(cv2.cvtColor(v, cv2.COLOR_BGR2GRAY), gray_simple)
            for v in variants
        )
        assert differs, "At least one variant must differ from plain grayscale"

    def test_has_both_bright_and_dark_variants(self) -> None:
        """V2 (OTSU) and V4 (inverted OTSU) should span different brightness ranges.

        Uses a large image (gray area = 25 % of total) so that the 4 px white
        border padding does not dominate the mean calculation.
        V2: mostly-black image → low mean.
        V4: bitwise_not(V2) → mostly-white image → high mean.
        """
        # 200×400 image; gray block covers 100×200 = 25 % of pixels
        img = np.zeros((200, 400, 3), dtype=np.uint8)
        img[50:150, 100:300] = (200, 200, 200)
        variants = OCREngine._preprocess_variants(img)
        means = [float(v.mean()) for v in variants]
        # The brightest variant (V4 inverted) and darkest (V2 OTSU) must differ
        # by at least 30 gray levels — confirming both dark and bright paths exist.
        spread = max(means) - min(means)
        assert (
            spread > 30
        ), f"Variants must span diverse brightness levels; means={means}"


# ---------------------------------------------------------------------------
# find_text — multi-word integration
# ---------------------------------------------------------------------------


class TestFindTextMultiword:
    """Integration: find_text() with multi-word targets via merged regions."""

    def _make_engine(self, regions: List[TextRegion]) -> OCREngine:
        engine = OCREngine(backend="paddleocr")
        engine.scan_all = lambda img: regions  # type: ignore[method-assign]
        return engine

    def test_find_multiword_via_merge(self) -> None:
        """'Image Source' split into two word regions → find_text('Image Source') succeeds."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        regions = [
            TextRegion("Image", (10, 10, 55, 20), 1.0, (37, 20), "winrt"),
            TextRegion("Source", (72, 10, 60, 20), 1.0, (102, 20), "winrt"),
        ]
        engine = self._make_engine(regions)
        result = engine.find_text(img, "Image Source")
        assert result is not None, "Should find 'Image Source' via merged region"
        assert "Image Source" in result.text

    def test_find_single_word_still_works(self) -> None:
        """Single-word search still works after merging."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        regions = [TextRegion("Login", (10, 10, 60, 20), 1.0, (40, 20), "winrt")]
        engine = self._make_engine(regions)
        result = engine.find_text(img, "Login")
        assert result is not None

    def test_find_text_case_insensitive_multiword(self) -> None:
        """Case-insensitive match for merged multi-word region."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        regions = [
            TextRegion("image", (10, 10, 55, 20), 1.0, (37, 20), "winrt"),
            TextRegion("source", (72, 10, 60, 20), 1.0, (102, 20), "winrt"),
        ]
        engine = self._make_engine(regions)
        result = engine.find_text(img, "IMAGE SOURCE")
        assert result is not None
