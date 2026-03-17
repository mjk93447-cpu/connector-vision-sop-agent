"""
Unit tests for src/ocr_engine.py.

Uses mocks for WinRT and PaddleOCR — no external dependencies required.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

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

    def test_auto_falls_back_to_paddleocr_when_winrt_unavailable(self) -> None:
        with patch("src.ocr_engine._check_winrt", return_value=False):
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
    def test_parse_paddle_output_format(self) -> None:
        """Verify _scan_paddleocr converts PaddleOCR raw output to TextRegion list."""
        engine = OCREngine(backend="paddleocr")
        mock_paddle = MagicMock()
        # PaddleOCR returns: [[ [[[x1,y1],[x2,y1],[x2,y2],[x1,y2]], ("TEXT", 0.99)], ... ]]
        mock_paddle.ocr.return_value = [
            [
                [[[10, 10], [90, 10], [90, 30], [10, 30]], ("LOGIN", 0.99)],
                [[[10, 50], [80, 50], [80, 70], [10, 70]], ("SAVE", 0.95)],
            ]
        ]
        engine._paddle = mock_paddle
        img = _make_bgr()
        results = engine._scan_paddleocr(img)
        assert len(results) == 2
        assert results[0].text == "LOGIN"
        assert results[0].confidence == pytest.approx(0.99)
        assert results[0].source == "paddleocr"
        assert results[1].text == "SAVE"

    def test_handles_empty_paddle_output(self) -> None:
        engine = OCREngine(backend="paddleocr")
        mock_paddle = MagicMock()
        mock_paddle.ocr.return_value = [[]]
        engine._paddle = mock_paddle
        results = engine._scan_paddleocr(_make_bgr())
        assert results == []

    def test_handles_none_paddle_output(self) -> None:
        engine = OCREngine(backend="paddleocr")
        mock_paddle = MagicMock()
        mock_paddle.ocr.return_value = None
        engine._paddle = mock_paddle
        results = engine._scan_paddleocr(_make_bgr())
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
