"""
Windows exception handler for Connector Vision SOP Agent.

Handles common Windows line PC interruptions that can block SOP execution:
  1. Known system popups (Windows Update, Activation, UAC, etc.)
  2. Screen freeze detection (MSE < 0.01 across 3 consecutive screenshots)
  3. Unknown situations → phi4-mini LLM recovery_action() (last resort)

Chain:
    detect_popup()         — pattern-match known popup text → dismiss button
    is_screen_frozen()     — compare 3 screenshots, MSE threshold
    OfflineLLM.recovery_action() — LLM JSON: action/target_text/reason
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

import numpy as np

from src.ocr_engine import OCREngine, TextRegion

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known Windows popup patterns (text that appears in popup title/buttons)
# ---------------------------------------------------------------------------

KNOWN_POPUP_TEXTS: List[str] = [
    # Windows Update
    "Windows Update",
    "Restart now",
    "Restart later",
    "Remind me later",
    "Schedule the restart",
    "Update and restart",
    "Download and install",
    # Windows Activation
    "Activate Windows",
    "Activation",
    "Get genuine",
    "Windows isn't activated",
    # UAC / Security
    "Run anyway",
    "More info",
    "This app can't run",
    "User Account Control",
    "Allow this app",
    # Windows Defender / SmartScreen
    "Windows protected your PC",
    "Windows Defender",
    "Scan with",
    # Driver / Hardware
    "A driver can't load",
    "Driver error",
    # Generic OK/Close buttons that appear in blocking popups
    "Don't save",
    "Discard",
    "Ignore",
    "Close",
    "OK",
]

# Dismiss priority order: prefer "Remind me later" / "Close" / "Cancel" over "Restart"
DISMISS_PRIORITY: List[str] = [
    "Remind me later",
    "Schedule the restart",
    "Restart later",
    "Close",
    "Cancel",
    "Ignore",
    "OK",
    "Run anyway",
    "More info",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PopupInfo:
    """Detected Windows popup metadata."""

    title: str  # popup title text (best guess)
    dismiss_text: str  # button text to click to dismiss
    dismiss_region: TextRegion  # OCR region of the dismiss button


@dataclass
class ExceptionContext:
    """Context passed to handle_exception()."""

    sop_step_id: str
    target_button: str
    ocr_text_on_screen: str  # compressed scan_all() result
    error_type: str  # "button_not_found" | "popup" | "frozen"
    recent_history: List[str] = field(default_factory=list)  # last 3 step results


@dataclass
class RecoveryAction:
    """Action returned by handle_exception()."""

    action: str  # "dismiss_popup" | "wait" | "restart_step" | "skip_step" | "abort"
    target_text: Optional[str]  # OCR text to click (for dismiss_popup)
    reason: str
    source: str  # "popup_heuristic" | "screen_frozen" | "llm" | "fallback"


# ---------------------------------------------------------------------------
# ExceptionHandler
# ---------------------------------------------------------------------------


class ExceptionHandler:
    """Detect and recover from common Windows SOP interruptions."""

    def __init__(
        self,
        ocr: OCREngine,
        llm: Optional[Any] = None,  # OfflineLLM instance (optional)
    ) -> None:
        self._ocr = ocr
        self._llm = llm
        self._screenshot_history: List[np.ndarray] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_popup(self, img_np: np.ndarray) -> Optional[PopupInfo]:
        """Scan screen for known Windows popup patterns.

        Returns PopupInfo with the best dismiss button, or None if no popup.
        """
        regions = self._ocr.scan_all(img_np)
        if not regions:
            return None

        # Build a text → region map (case-insensitive)
        text_map: dict[str, TextRegion] = {r.text.upper().strip(): r for r in regions}
        all_texts_upper = list(text_map.keys())

        # Check if any known popup text is visible
        popup_title_region: Optional[TextRegion] = None
        for known in KNOWN_POPUP_TEXTS:
            known_up = known.upper()
            for t in all_texts_upper:
                if known_up in t or t in known_up:
                    popup_title_region = text_map.get(t)
                    break
            if popup_title_region:
                break

        if popup_title_region is None:
            return None

        # Find best dismiss button
        for dismiss_text in DISMISS_PRIORITY:
            dismiss_up = dismiss_text.upper()
            for t, region in text_map.items():
                if dismiss_up in t or t in dismiss_up:
                    logger.info(
                        "Popup detected: %r — dismiss via %r",
                        popup_title_region.text,
                        region.text,
                    )
                    return PopupInfo(
                        title=popup_title_region.text,
                        dismiss_text=region.text,
                        dismiss_region=region,
                    )

        # Found popup but no known dismiss button — return with "Close" as fallback
        return PopupInfo(
            title=popup_title_region.text,
            dismiss_text="Close",
            dismiss_region=popup_title_region,
        )

    def record_screenshot(self, img_np: np.ndarray) -> None:
        """Record screenshot for freeze detection (keep last 3)."""
        self._screenshot_history.append(img_np.copy())
        if len(self._screenshot_history) > 3:
            self._screenshot_history.pop(0)

    def is_screen_frozen(self, screenshots: Optional[List[np.ndarray]] = None) -> bool:
        """Return True if consecutive screenshots are nearly identical (MSE < 0.01).

        Uses provided list or internal history (last 3 captures).
        Requires at least 2 screenshots.
        """
        imgs = screenshots or self._screenshot_history
        if len(imgs) < 2:
            return False

        mse_values = []
        for i in range(len(imgs) - 1):
            a = imgs[i].astype(np.float32)
            b = imgs[i + 1].astype(np.float32)
            if a.shape != b.shape:
                return False
            mse = float(np.mean((a - b) ** 2))
            mse_values.append(mse)

        # All consecutive pairs must be below threshold
        return all(m < 0.5 for m in mse_values)  # 0.5 = near-identical in 0-65536 range

    def handle_exception(
        self,
        context: ExceptionContext,
        img_np: Optional[np.ndarray] = None,
    ) -> RecoveryAction:
        """Main exception handling chain.

        Priority:
          1. detect_popup (no LLM needed)
          2. is_screen_frozen (wait 5s)
          3. LLM recovery_action (last resort)
        """

        # --- Step 1: Popup detection ---
        if img_np is not None:
            popup = self.detect_popup(img_np)
            if popup is not None:
                return RecoveryAction(
                    action="dismiss_popup",
                    target_text=popup.dismiss_text,
                    reason=f"Windows popup detected: '{popup.title}'",
                    source="popup_heuristic",
                )

        # --- Step 2: Screen freeze detection ---
        if self.is_screen_frozen():
            logger.info("Screen freeze detected — waiting 5s")
            time.sleep(5)
            return RecoveryAction(
                action="wait",
                target_text=None,
                reason="Screen appeared frozen — waited 5 seconds",
                source="screen_frozen",
            )

        # --- Step 3: LLM recovery (only when LLM is available) ---
        if self._llm is not None:
            try:
                result = self._llm.recovery_action(
                    {
                        "sop_step": context.sop_step_id,
                        "target_button": context.target_button,
                        "ocr_text": context.ocr_text_on_screen,
                        "error_type": context.error_type,
                        "history": context.recent_history,
                    }
                )
                return RecoveryAction(
                    action=result.get("action", "restart_step"),
                    target_text=result.get("target_text"),
                    reason=result.get("reason", "LLM recovery"),
                    source="llm",
                )
            except Exception as exc:
                logger.warning("LLM recovery_action failed: %s", exc)

        # --- Fallback ---
        return RecoveryAction(
            action="restart_step",
            target_text=None,
            reason=f"Auto-recovery failed for step '{context.sop_step_id}' — retrying",
            source="fallback",
        )

    @staticmethod
    def compress_ocr_text(regions: List[TextRegion], max_chars: int = 400) -> str:
        """Compress OCR scan results to a short string for LLM context."""
        texts = [r.text for r in regions if r.text.strip()]
        combined = " | ".join(texts)
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "…"
        return combined
