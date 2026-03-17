"""
OCR Engine for Connector Vision SOP Agent.

Primary button detection strategy:
  1. Windows.Media.Ocr (WinRT) — built-in Windows 10 1803+, 0 MB overhead, word-level bbox
  2. PaddleOCR PP-OCRv4 Lite   — ~5 MB model, CPU 50-150 ms/scan, fallback

Both backends return a list of TextRegion(text, bbox, confidence, center, source).
OCREngine.find_text() performs fuzzy matching (difflib.SequenceMatcher) so minor
OCR errors don't cause button misses.

Usage:
    engine = OCREngine(backend="auto", threshold=0.80)
    region = engine.find_text(screenshot_bgr, "LOGIN")
    if region:
        pyautogui.click(*region.center)
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_WINRT_AVAILABLE: Optional[bool] = None  # cached after first check


def _check_winrt() -> bool:
    """Return True if Windows.Media.Ocr is accessible."""
    global _WINRT_AVAILABLE  # noqa: PLW0603
    if _WINRT_AVAILABLE is not None:
        return _WINRT_AVAILABLE
    try:
        import winrt.windows.media.ocr as _  # noqa: F401
        import winrt.windows.graphics.imaging as _g  # noqa: F401

        _WINRT_AVAILABLE = True
    except Exception:
        _WINRT_AVAILABLE = False
    return _WINRT_AVAILABLE


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TextRegion:
    """Single OCR-detected text region."""

    text: str
    bbox: tuple[int, int, int, int]  # (x, y, w, h) — absolute screen coords
    confidence: float
    center: tuple[int, int]  # (cx, cy) — click target
    source: str  # "winrt" | "paddleocr" | "mock"


# ---------------------------------------------------------------------------
# OCREngine
# ---------------------------------------------------------------------------


class OCREngine:
    """WinRT OCR (primary) → PaddleOCR (fallback) text detector.

    Parameters
    ----------
    backend : "auto" | "winrt" | "paddleocr"
        "auto" selects WinRT when available, else PaddleOCR.
    threshold : float
        Minimum fuzzy-match ratio (0–1) for find_text().
    """

    def __init__(self, backend: str = "auto", threshold: float = 0.80) -> None:
        self.threshold = threshold
        self._backend = self._resolve_backend(backend)
        self._paddle: Optional[object] = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_all(self, img_np: np.ndarray) -> List[TextRegion]:
        """Scan entire image and return all detected TextRegion objects."""
        try:
            if self._backend == "winrt":
                return self._scan_winrt(img_np)
            return self._scan_paddleocr(img_np)
        except Exception as exc:
            logger.warning("OCR scan_all error (%s): %s", self._backend, exc)
            return []

    def find_text(
        self,
        img_np: np.ndarray,
        target: str,
        fuzzy: bool = True,
        threshold: Optional[float] = None,
    ) -> Optional[TextRegion]:
        """Find the best-matching TextRegion for ``target``.

        Parameters
        ----------
        img_np : BGR numpy array (screen capture).
        target : Button text to locate (e.g. "LOGIN").
        fuzzy  : Use difflib fuzzy matching (recommended).
        threshold : Override instance threshold for this call.
        """
        thr = threshold if threshold is not None else self.threshold
        regions = self.scan_all(img_np)
        best: Optional[TextRegion] = None
        best_score = 0.0

        t_upper = target.upper().strip()
        for r in regions:
            r_upper = r.text.upper().strip()
            if fuzzy:
                score = difflib.SequenceMatcher(None, t_upper, r_upper).ratio()
            else:
                score = 1.0 if t_upper == r_upper else 0.0

            if score >= thr and score > best_score:
                best_score = score
                best = r

        if best:
            logger.debug(
                "OCR found %r → %r (score=%.2f, src=%s, center=%s)",
                target,
                best.text,
                best_score,
                best.source,
                best.center,
            )
        return best

    @property
    def backend(self) -> str:
        return self._backend

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_backend(requested: str) -> str:
        if requested == "winrt":
            return "winrt"
        if requested == "paddleocr":
            return "paddleocr"
        # "auto": prefer WinRT on Windows
        return "winrt" if _check_winrt() else "paddleocr"

    # ------------------------------------------------------------------
    # WinRT backend (Windows 10 1803+ built-in OCR)
    # ------------------------------------------------------------------

    def _scan_winrt(self, img_np: np.ndarray) -> List[TextRegion]:
        """Use Windows.Media.Ocr for text detection.

        Converts BGR numpy array → WinRT SoftwareBitmap → OcrEngine.RecognizeAsync.
        Returns word-level bounding boxes.
        """
        try:
            import asyncio  # noqa: PLC0415

            import winrt.windows.graphics.imaging as wgi  # noqa: PLC0415
            import winrt.windows.media.ocr as wocr  # noqa: PLC0415
            import winrt.windows.storage.streams as wss  # noqa: PLC0415
        except ImportError:
            logger.debug("WinRT OCR unavailable — falling back to PaddleOCR")
            self._backend = "paddleocr"
            return self._scan_paddleocr(img_np)

        try:
            rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]

            # Build SoftwareBitmap from raw BGRA bytes
            bgra = cv2.cvtColor(img_np, cv2.COLOR_BGR2BGRA)
            raw_bytes = bgra.tobytes()

            # Create IBuffer from bytes
            buf = wss.Buffer(len(raw_bytes))
            ibuf = wss.IBuffer._from(buf)  # type: ignore[attr-defined]
            ibuf.length = len(raw_bytes)  # type: ignore[attr-defined]
            # Copy bytes via DataWriter
            dw = wss.DataWriter()
            dw.write_bytes(list(raw_bytes))
            ibuf = dw.detach_buffer()

            bmp = wgi.SoftwareBitmap.create_copy_from_buffer(
                ibuf,
                wgi.BitmapPixelFormat.BGRA8,
                w,
                h,
                wgi.BitmapAlphaMode.PREMULTIPLIED,
            )

            ocr_engine = wocr.OcrEngine.try_create_from_user_profile_languages()
            if ocr_engine is None:
                raise RuntimeError("WinRT OcrEngine returned None")

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(ocr_engine.recognize_async(bmp))
            loop.close()

            regions: List[TextRegion] = []
            for line in result.lines:
                for word in line.words:
                    rect = word.bounding_rect
                    x = int(rect.x)
                    y = int(rect.y)
                    ww = int(rect.width)
                    wh = int(rect.height)
                    cx = x + ww // 2
                    cy = y + wh // 2
                    regions.append(
                        TextRegion(
                            text=word.text,
                            bbox=(x, y, ww, wh),
                            confidence=1.0,  # WinRT does not expose per-word confidence
                            center=(cx, cy),
                            source="winrt",
                        )
                    )
            return regions

        except Exception as exc:
            logger.warning("WinRT OCR failed: %s — falling back to PaddleOCR", exc)
            self._backend = "paddleocr"
            return self._scan_paddleocr(img_np)

    # ------------------------------------------------------------------
    # PaddleOCR backend (PP-OCRv4 Lite)
    # ------------------------------------------------------------------

    def _scan_paddleocr(self, img_np: np.ndarray) -> List[TextRegion]:
        """Use PaddleOCR PP-OCRv4 for text detection."""
        paddle = self._get_paddle()
        if paddle is None:
            logger.warning("PaddleOCR not available — returning empty OCR result")
            return []

        preprocessed = self._preprocess(img_np)
        try:
            raw = paddle.ocr(preprocessed, cls=True)
        except Exception as exc:
            logger.warning("PaddleOCR inference error: %s", exc)
            return []

        regions: List[TextRegion] = []
        if not raw:
            return regions

        for page in raw:
            if not page:
                continue
            for item in page:
                if not item or len(item) < 2:
                    continue
                box_pts, (text, conf) = item
                # box_pts: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                xs = [int(p[0]) for p in box_pts]
                ys = [int(p[1]) for p in box_pts]
                x_min, y_min = min(xs), min(ys)
                bw = max(xs) - x_min
                bh = max(ys) - y_min
                cx = x_min + bw // 2
                cy = y_min + bh // 2
                regions.append(
                    TextRegion(
                        text=str(text),
                        bbox=(x_min, y_min, bw, bh),
                        confidence=float(conf),
                        center=(cx, cy),
                        source="paddleocr",
                    )
                )
        return regions

    def _get_paddle(self) -> Optional[object]:
        """Lazy-load PaddleOCR instance."""
        if self._paddle is not None:
            return self._paddle
        try:
            from paddleocr import PaddleOCR  # noqa: PLC0415

            self._paddle = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
                use_gpu=False,
            )
        except ImportError:
            logger.warning(
                "paddleocr package not installed. "
                "Install with: pip install paddleocr paddlepaddle-cpu"
            )
            self._paddle = None
        except Exception as exc:
            logger.warning("PaddleOCR initialization failed: %s", exc)
            self._paddle = None
        return self._paddle

    # ------------------------------------------------------------------
    # Image pre-processing (improves OCR on industrial UI buttons)
    # ------------------------------------------------------------------

    @staticmethod
    def _preprocess(img_np: np.ndarray) -> np.ndarray:
        """CLAHE contrast enhancement + border padding for edge buttons."""
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        # Convert back to BGR (PaddleOCR accepts both)
        bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        # Add thin border so edge-touching text is detected
        padded = cv2.copyMakeBorder(
            bgr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255)
        )
        return padded
