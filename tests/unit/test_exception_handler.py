"""
Unit tests for src/exception_handler.py.

Uses mocks for OCREngine and OfflineLLM — no external dependencies required.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import numpy as np

from src.exception_handler import (
    DISMISS_PRIORITY,
    KNOWN_POPUP_TEXTS,
    ExceptionContext,
    ExceptionHandler,
    PopupInfo,
)
from src.ocr_engine import TextRegion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bgr(h: int = 100, w: int = 200) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_region(text: str, x: int = 10, y: int = 10) -> TextRegion:
    return TextRegion(
        text=text,
        bbox=(x, y, 80, 20),
        confidence=0.95,
        center=(x + 40, y + 10),
        source="mock",
    )


def _make_context(
    step_id: str = "login",
    target: str = "LOGIN",
    error_type: str = "button_not_found",
) -> ExceptionContext:
    return ExceptionContext(
        sop_step_id=step_id,
        target_button=target,
        ocr_text_on_screen="some text on screen",
        error_type=error_type,
        recent_history=["step1 ok", "step2 ok"],
    )


def _make_handler(regions: List[TextRegion], llm: object = None) -> ExceptionHandler:
    ocr = MagicMock()
    ocr.scan_all.return_value = regions
    return ExceptionHandler(ocr=ocr, llm=llm)


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


class TestConstants:
    def test_known_popup_texts_nonempty(self) -> None:
        assert len(KNOWN_POPUP_TEXTS) > 10

    def test_dismiss_priority_nonempty(self) -> None:
        assert len(DISMISS_PRIORITY) > 5

    def test_dismiss_priority_starts_with_safe_options(self) -> None:
        # "Remind me later" should be higher priority than "Restart"
        assert "Remind me later" in DISMISS_PRIORITY
        assert DISMISS_PRIORITY.index("Remind me later") < DISMISS_PRIORITY.index("OK")


# ---------------------------------------------------------------------------
# detect_popup
# ---------------------------------------------------------------------------


class TestDetectPopup:
    def test_returns_none_when_no_text(self) -> None:
        handler = _make_handler([])
        result = handler.detect_popup(_make_bgr())
        assert result is None

    def test_returns_none_when_no_popup_text(self) -> None:
        # Use text strings that do not appear as substrings of any KNOWN_POPUP_TEXTS entry
        handler = _make_handler([_make_region("RECIPE"), _make_region("APPLY")])
        result = handler.detect_popup(_make_bgr())
        assert result is None

    def test_detects_windows_update_popup(self) -> None:
        handler = _make_handler(
            [
                _make_region("Windows Update"),
                _make_region("Remind me later", x=50),
                _make_region("Update and restart", x=100),
            ]
        )
        result = handler.detect_popup(_make_bgr())
        assert result is not None
        assert isinstance(result, PopupInfo)
        assert (
            "Windows Update" in result.title or "WINDOWS UPDATE" in result.title.upper()
        )
        assert result.dismiss_text.upper() in [d.upper() for d in DISMISS_PRIORITY]

    def test_prefer_remind_me_later_over_restart(self) -> None:
        """Dismiss priority: 'Remind me later' should be chosen over 'Restart now'."""
        handler = _make_handler(
            [
                _make_region("Windows Update"),
                _make_region("Restart now"),
                _make_region("Remind me later"),
            ]
        )
        result = handler.detect_popup(_make_bgr())
        assert result is not None
        assert (
            "remind" in result.dismiss_text.lower()
            or "later" in result.dismiss_text.lower()
        )

    def test_detects_activation_popup(self) -> None:
        handler = _make_handler(
            [
                _make_region("Activate Windows"),
                _make_region("Close"),
            ]
        )
        result = handler.detect_popup(_make_bgr())
        assert result is not None

    def test_popup_with_no_known_dismiss_uses_close_fallback(self) -> None:
        """If popup detected but no dismiss button found, return fallback PopupInfo."""
        handler = _make_handler(
            [
                _make_region("Windows Update"),
                # No dismiss button present
            ]
        )
        result = handler.detect_popup(_make_bgr())
        assert result is not None
        assert result.dismiss_text == "Close"

    def test_case_insensitive_popup_detection(self) -> None:
        handler = _make_handler(
            [
                _make_region("WINDOWS UPDATE"),  # all-caps
                _make_region("remind me later"),  # lowercase
            ]
        )
        result = handler.detect_popup(_make_bgr())
        assert result is not None

    def test_uac_popup_detected(self) -> None:
        handler = _make_handler(
            [
                _make_region("User Account Control"),
                _make_region("Cancel"),
            ]
        )
        result = handler.detect_popup(_make_bgr())
        assert result is not None


# ---------------------------------------------------------------------------
# is_screen_frozen
# ---------------------------------------------------------------------------


class TestIsScreenFrozen:
    def test_returns_false_with_no_history(self) -> None:
        handler = _make_handler([])
        assert handler.is_screen_frozen() is False

    def test_returns_false_with_single_screenshot(self) -> None:
        handler = _make_handler([])
        handler.record_screenshot(_make_bgr())
        assert handler.is_screen_frozen() is False

    def test_returns_true_for_identical_screenshots(self) -> None:
        handler = _make_handler([])
        img = _make_bgr()
        handler.record_screenshot(img)
        handler.record_screenshot(img)
        assert handler.is_screen_frozen() is True

    def test_returns_false_for_different_screenshots(self) -> None:
        handler = _make_handler([])
        img_a = np.zeros((100, 200, 3), dtype=np.uint8)
        img_b = np.full((100, 200, 3), 128, dtype=np.uint8)
        handler.record_screenshot(img_a)
        handler.record_screenshot(img_b)
        assert handler.is_screen_frozen() is False

    def test_explicit_screenshots_param(self) -> None:
        handler = _make_handler([])
        img = _make_bgr()
        assert handler.is_screen_frozen([img, img, img]) is True

    def test_mismatched_shapes_returns_false(self) -> None:
        handler = _make_handler([])
        img_a = np.zeros((100, 200, 3), dtype=np.uint8)
        img_b = np.zeros((50, 100, 3), dtype=np.uint8)
        assert handler.is_screen_frozen([img_a, img_b]) is False

    def test_keeps_only_last_three(self) -> None:
        handler = _make_handler([])
        different = np.full((100, 200, 3), 200, dtype=np.uint8)
        same = np.zeros((100, 200, 3), dtype=np.uint8)
        # Record 3 different + 3 same — history should keep last 3 (the same ones)
        for _ in range(3):
            handler.record_screenshot(different)
        for _ in range(3):
            handler.record_screenshot(same)
        assert handler.is_screen_frozen() is True


# ---------------------------------------------------------------------------
# handle_exception — chain
# ---------------------------------------------------------------------------


class TestHandleException:
    def test_returns_dismiss_popup_when_popup_detected(self) -> None:
        handler = _make_handler(
            [
                _make_region("Windows Update"),
                _make_region("Close"),
            ]
        )
        ctx = _make_context()
        result = handler.handle_exception(ctx, img_np=_make_bgr())
        assert result.action == "dismiss_popup"
        assert result.source == "popup_heuristic"
        assert result.target_text is not None

    def test_returns_wait_when_screen_frozen(self) -> None:
        handler = _make_handler([])  # OCR returns empty → no popup
        # Pre-load identical screenshots
        img = _make_bgr()
        handler.record_screenshot(img)
        handler.record_screenshot(img)
        ctx = _make_context()
        with patch("src.exception_handler.time.sleep"):
            result = handler.handle_exception(ctx)
        assert result.action == "wait"
        assert result.source == "screen_frozen"

    def test_calls_llm_when_available(self) -> None:
        handler = _make_handler([])  # no popup, no freeze
        mock_llm = MagicMock()
        mock_llm.recovery_action.return_value = {
            "action": "restart_step",
            "target_text": None,
            "reason": "LLM says retry",
        }
        handler._llm = mock_llm
        ctx = _make_context()
        result = handler.handle_exception(ctx)
        assert result.source == "llm"
        assert result.action == "restart_step"
        mock_llm.recovery_action.assert_called_once()

    def test_falls_back_when_llm_raises(self) -> None:
        mock_llm = MagicMock()
        mock_llm.recovery_action.side_effect = RuntimeError("LLM unavailable")
        handler = _make_handler([])
        handler._llm = mock_llm
        ctx = _make_context()
        result = handler.handle_exception(ctx)
        assert result.source == "fallback"
        assert result.action == "restart_step"

    def test_no_llm_returns_fallback(self) -> None:
        handler = _make_handler([])
        ctx = _make_context()
        result = handler.handle_exception(ctx)
        assert result.source == "fallback"

    def test_llm_context_includes_step_id(self) -> None:
        mock_llm = MagicMock()
        mock_llm.recovery_action.return_value = {
            "action": "wait",
            "target_text": None,
            "reason": "ok",
        }
        handler = _make_handler([])
        handler._llm = mock_llm
        ctx = _make_context(step_id="mold_left_roi")
        handler.handle_exception(ctx)
        call_args = mock_llm.recovery_action.call_args[0][0]
        assert call_args["sop_step"] == "mold_left_roi"

    def test_recovery_action_dataclass_fields(self) -> None:
        handler = _make_handler([])
        ctx = _make_context()
        result = handler.handle_exception(ctx)
        assert hasattr(result, "action")
        assert hasattr(result, "target_text")
        assert hasattr(result, "reason")
        assert hasattr(result, "source")


# ---------------------------------------------------------------------------
# compress_ocr_text
# ---------------------------------------------------------------------------


class TestCompressOcrText:
    def test_empty_regions(self) -> None:
        result = ExceptionHandler.compress_ocr_text([])
        assert result == ""

    def test_returns_joined_text(self) -> None:
        regions = [_make_region("LOGIN"), _make_region("SAVE")]
        result = ExceptionHandler.compress_ocr_text(regions)
        assert "LOGIN" in result
        assert "SAVE" in result

    def test_truncates_to_max_chars(self) -> None:
        long_texts = [_make_region("A" * 50) for _ in range(20)]
        result = ExceptionHandler.compress_ocr_text(long_texts, max_chars=100)
        assert len(result) <= 101  # 100 + ellipsis

    def test_skips_empty_text(self) -> None:
        regions = [_make_region(""), _make_region("   "), _make_region("LOGIN")]
        result = ExceptionHandler.compress_ocr_text(regions)
        assert "LOGIN" in result
        assert result.count("|") == 0  # only one text → no separator
