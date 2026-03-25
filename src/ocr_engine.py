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
_EASYOCR_AVAILABLE: Optional[bool] = None  # cached after first check


def _check_easyocr() -> bool:
    """Return True if EasyOCR is importable."""
    global _EASYOCR_AVAILABLE  # noqa: PLW0603
    if _EASYOCR_AVAILABLE is not None:
        return _EASYOCR_AVAILABLE
    try:
        import easyocr as _  # noqa: F401

        _EASYOCR_AVAILABLE = True
    except Exception:
        _EASYOCR_AVAILABLE = False
    return _EASYOCR_AVAILABLE


def _check_winrt() -> bool:
    """Return True if Windows.Media.Ocr is accessible."""
    global _WINRT_AVAILABLE  # noqa: PLW0603
    if _WINRT_AVAILABLE is not None:
        return _WINRT_AVAILABLE
    try:
        import winsdk.windows.media.ocr as _  # noqa: F401
        import winsdk.windows.graphics.imaging as _g  # noqa: F401

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

    def scan_all(
        self,
        img_np: np.ndarray,
        roi: Optional[tuple] = None,  # (x, y, w, h)
    ) -> List[TextRegion]:
        """Scan entire image (or ROI crop) and return all detected TextRegion objects.

        Parameters
        ----------
        img_np : BGR numpy array (screen capture).
        roi    : Optional (x, y, w, h) region of interest in screen coordinates.
                 If given, only that crop is scanned and returned bbox/center
                 coordinates are offset back to original screen coordinates.
        """
        try:
            if roi is not None:
                rx, ry, rw, rh = roi
                cropped = img_np[ry : ry + rh, rx : rx + rw]
                scan_img = cropped
            else:
                scan_img = img_np

            if self._backend == "winrt":
                regions = self._scan_winrt(scan_img)
            elif self._backend == "easyocr":
                regions = self._scan_easyocr(scan_img)
            else:
                regions = self._scan_paddleocr(scan_img)

            if roi is not None:
                rx, ry = roi[0], roi[1]
                offset_regions: List[TextRegion] = []
                for r in regions:
                    bx, by, bw, bh = r.bbox
                    new_bbox = (bx + rx, by + ry, bw, bh)
                    new_center = (r.center[0] + rx, r.center[1] + ry)
                    offset_regions.append(
                        TextRegion(
                            text=r.text,
                            bbox=new_bbox,
                            confidence=r.confidence,
                            center=new_center,
                            source=r.source,
                        )
                    )
                return offset_regions

            return regions
        except Exception as exc:
            logger.warning("OCR scan_all error (%s): %s", self._backend, exc)
            return []

    def find_text(
        self,
        img_np: np.ndarray,
        target: str,
        fuzzy: bool = True,
        threshold: Optional[float] = None,
        roi: Optional[tuple] = None,  # (x, y, w, h)
    ) -> Optional[TextRegion]:
        """Find the best-matching TextRegion for ``target``.

        Parameters
        ----------
        img_np : BGR numpy array (screen capture).
        target : Button text to locate (e.g. "LOGIN").
        fuzzy  : Use difflib fuzzy matching (recommended).
        threshold : Override instance threshold for this call.
        roi    : Optional (x, y, w, h) region of interest — passed to scan_all().
        """
        thr = threshold if threshold is not None else self.threshold
        regions = self.scan_all(img_np, roi=roi)
        # Merge adjacent word-level regions so multi-word button labels
        # (e.g. "Image Source") are searchable as a single region.
        regions = self._merge_adjacent_regions(regions)
        best: Optional[TextRegion] = None
        best_score = 0.0

        t_upper = target.upper().strip()
        t_nospace = t_upper.replace(" ", "")  # "LOG IN" → "LOGIN"
        for r in regions:
            r_upper = r.text.upper().strip()
            r_nospace = r_upper.replace(" ", "")
            if fuzzy:
                score = max(
                    difflib.SequenceMatcher(None, t_upper, r_upper).ratio(),
                    difflib.SequenceMatcher(None, t_nospace, r_nospace).ratio(),
                )
            else:
                score = 1.0 if (t_upper == r_upper or t_nospace == r_nospace) else 0.0

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
        if requested in ("winrt", "paddleocr", "easyocr"):
            return requested
        # "auto": winrt → easyocr → paddleocr
        if _check_winrt():
            return "winrt"
        if _check_easyocr():
            return "easyocr"
        return "paddleocr"

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

            import winsdk.windows.graphics.imaging as wgi  # noqa: PLC0415
            import winsdk.windows.media.ocr as wocr  # noqa: PLC0415
            import winsdk.windows.storage.streams as wss  # noqa: PLC0415
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
            dw.write_bytes(raw_bytes)
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
                # Fallback: explicitly request English OCR (available on most Windows 10/11)
                try:
                    import winsdk.windows.globalization as wg  # noqa: PLC0415

                    lang = wg.Language("en-US")
                    ocr_engine = wocr.OcrEngine.try_create_from_language(lang)
                    if ocr_engine is not None:
                        logger.debug("WinRT OCR: using en-US language fallback")
                except Exception as _e:
                    logger.debug("WinRT OCR en-US fallback failed: %s", _e)
                    ocr_engine = None
            if ocr_engine is None:
                raise RuntimeError(
                    "WinRT OcrEngine: no OCR language pack available "
                    "(tried user profile + en-US). "
                    "Install English language pack or enable PaddleOCR."
                )

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
        """Use PaddleOCR PP-OCRv4 for text detection.

        Runs multiple preprocessed variants (V1–V4) and deduplicates results
        with IoU-based NMS so that bold fonts and colored button backgrounds
        are reliably detected regardless of which variant performs best.
        """
        paddle = self._get_paddle()
        if paddle is None:
            logger.warning("PaddleOCR not available — returning empty OCR result")
            return []

        all_regions: List[TextRegion] = []
        for variant in self._preprocess_variants(img_np):
            try:
                # PaddleOCR 3.x uses predict(); 2.x uses ocr()
                if hasattr(paddle, "predict"):
                    result_list = paddle.predict(variant)
                    # 3.x returns list of OCRResult objects; normalize to 2.x format
                    raw = []
                    for ocr_result in result_list or []:
                        page = []
                        rec_texts = getattr(ocr_result, "rec_texts", None)
                        rec_scores = getattr(ocr_result, "rec_scores", None)
                        dt_polys = getattr(ocr_result, "dt_polys", None)
                        if rec_texts and dt_polys:
                            for i, text_val in enumerate(rec_texts):
                                conf_val = rec_scores[i] if rec_scores else 1.0
                                poly = dt_polys[i] if i < len(dt_polys) else None
                                if poly is not None:
                                    page.append(
                                        [poly, (str(text_val), float(conf_val))]
                                    )
                        raw.append(page)
                else:
                    raw = paddle.ocr(variant, cls=True)
            except Exception as exc:
                logger.warning("PaddleOCR inference error: %s", exc)
                continue

            if not raw:
                continue
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
                    all_regions.append(
                        TextRegion(
                            text=str(text),
                            bbox=(x_min, y_min, bw, bh),
                            confidence=float(conf),
                            center=(cx, cy),
                            source="paddleocr",
                        )
                    )

        return self._dedup_regions(all_regions)

    def _get_paddle(self) -> Optional[object]:
        """Lazy-load PaddleOCR instance."""
        if self._paddle is not None:
            return self._paddle
        try:
            from paddleocr import PaddleOCR  # noqa: PLC0415

            # PaddleOCR 3.x removed use_gpu and use_angle_cls args; 2.x still accepts them.
            # Try 3.x-compatible constructor first, fall back to 2.x signature.
            try:
                self._paddle = PaddleOCR(lang="en", show_log=False)
            except TypeError:
                self._paddle = PaddleOCR(
                    use_angle_cls=True, lang="en", show_log=False, use_gpu=False
                )
        except ImportError:
            logger.warning(
                "paddleocr package not installed. "
                "Install with: pip install paddleocr paddlepaddle"
            )
            self._paddle = None
        except Exception as exc:
            logger.warning("PaddleOCR initialization failed: %s", exc)
            self._paddle = None
        return self._paddle

    # ------------------------------------------------------------------
    # EasyOCR backend (PyTorch-based, works without WinRT)
    # ------------------------------------------------------------------

    def _scan_easyocr(self, img_np: np.ndarray) -> List[TextRegion]:
        """Use EasyOCR for text detection with multi-variant preprocessing.

        Runs V1–V4 preprocessing variants and deduplicates results so bold
        fonts and colored button backgrounds are reliably detected.
        """
        reader = self._get_easyocr()
        if reader is None:
            logger.warning("EasyOCR not available — returning empty OCR result")
            return []

        all_regions: List[TextRegion] = []
        for variant in self._preprocess_variants(img_np):
            try:
                raw = reader.readtext(variant)
            except Exception as exc:
                logger.warning("EasyOCR inference error: %s", exc)
                continue

            for bbox_pts, text, conf in raw or []:
                # bbox_pts: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                xs = [int(p[0]) for p in bbox_pts]
                ys = [int(p[1]) for p in bbox_pts]
                x_min, y_min = min(xs), min(ys)
                bw = max(xs) - x_min
                bh = max(ys) - y_min
                cx = x_min + bw // 2
                cy = y_min + bh // 2
                all_regions.append(
                    TextRegion(
                        text=str(text),
                        bbox=(x_min, y_min, bw, bh),
                        confidence=float(conf),
                        center=(cx, cy),
                        source="easyocr",
                    )
                )

        return self._dedup_regions(all_regions)

    def _get_easyocr(self) -> Optional[object]:
        """Lazy-load EasyOCR Reader instance."""
        if self._paddle is not None and hasattr(self._paddle, "readtext"):
            return self._paddle  # reuse slot for easyocr reader
        if self._backend == "easyocr" and self._paddle is None:
            try:
                import easyocr  # noqa: PLC0415

                self._paddle = easyocr.Reader(["en"], gpu=False, verbose=False)
                logger.info("EasyOCR Reader initialized (CPU, en)")
            except ImportError:
                logger.warning(
                    "easyocr package not installed. "
                    "Install with: pip install easyocr"
                )
                self._paddle = None
            except Exception as exc:
                logger.warning("EasyOCR initialization failed: %s", exc)
                self._paddle = None
        return self._paddle

    # ------------------------------------------------------------------
    # Multi-word region merging (WinRT word-level → line-level)
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_adjacent_regions(regions: List[TextRegion]) -> List[TextRegion]:
        """Merge horizontally adjacent word-level regions into line-level regions.

        WinRT returns word-level bounding boxes.  A button labelled "Image Source"
        produces two separate TextRegions: "Image" and "Source".  This method
        groups words on the same horizontal line and merges neighbouring words
        so that multi-word button labels can be matched as a single region.

        Original word regions are preserved in the output alongside the merged
        line regions so that single-word searches still work.

        Parameters
        ----------
        regions : list of TextRegion (may come from any backend)

        Returns
        -------
        list of TextRegion — original regions + merged line regions (no dedup)
        """
        if not regions:
            return []

        # Sort by y_center for line grouping
        sorted_r = sorted(regions, key=lambda r: r.center[1])

        # Group into lines: compare each word against the LAST word already in
        # the line (rolling reference) so slight vertical drift across 3+ words
        # is handled correctly.  Words whose y_center difference is within 70%
        # of the smaller word's height are considered on the same line.
        lines: List[List[TextRegion]] = []
        for reg in sorted_r:
            placed = False
            for line in lines:
                ref = line[-1]  # rolling reference: compare to last word in line
                y_diff = abs(reg.center[1] - ref.center[1])
                height_threshold = min(reg.bbox[3], ref.bbox[3]) * 0.7
                if y_diff <= height_threshold:
                    line.append(reg)
                    placed = True
                    break
            if not placed:
                lines.append([reg])

        merged: List[TextRegion] = []
        for line in lines:
            # Sort words left-to-right within the line
            line_sorted = sorted(line, key=lambda r: r.bbox[0])

            # Greedily merge horizontally close words
            groups: List[List[TextRegion]] = [[line_sorted[0]]]
            for word in line_sorted[1:]:
                last_group = groups[-1]
                last_word = last_group[-1]
                # Gap between end of last word and start of current word
                gap = word.bbox[0] - (last_word.bbox[0] + last_word.bbox[2])
                gap_threshold = max(last_word.bbox[2], word.bbox[2]) * 1.5
                if gap <= gap_threshold:
                    last_group.append(word)
                else:
                    groups.append([word])

            for group in groups:
                if len(group) == 1:
                    # Single-word group — already in original regions
                    continue
                # Build merged region spanning all words in the group
                x_min = min(r.bbox[0] for r in group)
                y_min = min(r.bbox[1] for r in group)
                x_max = max(r.bbox[0] + r.bbox[2] for r in group)
                y_max = max(r.bbox[1] + r.bbox[3] for r in group)
                bw = x_max - x_min
                bh = y_max - y_min
                merged.append(
                    TextRegion(
                        text=" ".join(r.text for r in group),
                        bbox=(x_min, y_min, bw, bh),
                        confidence=sum(r.confidence for r in group) / len(group),
                        center=(x_min + bw // 2, y_min + bh // 2),
                        source=group[0].source + "+merged",
                    )
                )

        return regions + merged

    # ------------------------------------------------------------------
    # IoU-based deduplication (multi-variant scan)
    # ------------------------------------------------------------------

    @staticmethod
    def _bbox_iou(a: tuple, b: tuple) -> float:
        """Intersection-over-Union for two (x, y, w, h) bounding boxes."""
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ix = max(ax, bx)
        iy = max(ay, by)
        ix2 = min(ax + aw, bx + bw)
        iy2 = min(ay + ah, by + bh)
        if ix2 <= ix or iy2 <= iy:
            return 0.0
        inter = (ix2 - ix) * (iy2 - iy)
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _dedup_regions(
        regions: List[TextRegion], iou_threshold: float = 0.5
    ) -> List[TextRegion]:
        """Remove duplicate TextRegions using IoU-based non-maximum suppression.

        When multiple preprocessing variants detect the same text region, only
        the highest-confidence result is kept.

        Parameters
        ----------
        regions       : List of TextRegion from one or more scan passes.
        iou_threshold : Regions with IoU > this value are considered duplicates.
        """
        if not regions:
            return []
        sorted_r = sorted(regions, key=lambda r: r.confidence, reverse=True)
        kept: List[TextRegion] = []
        suppressed = set()
        for i, r in enumerate(sorted_r):
            if i in suppressed:
                continue
            kept.append(r)
            for j in range(i + 1, len(sorted_r)):
                if j in suppressed:
                    continue
                if OCREngine._bbox_iou(r.bbox, sorted_r[j].bbox) > iou_threshold:
                    suppressed.add(j)
        return kept

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

    @staticmethod
    def _preprocess_variants(img_np: np.ndarray) -> List[np.ndarray]:
        """Return multiple preprocessed variants of an image for robust OCR.

        Each variant targets a different visual challenge:
          V1 — CLAHE grayscale  : general text (existing _preprocess logic)
          V2 — OTSU binarize    : bold / thick fonts — clean black-white separation
          V3 — max-channel      : colored button backgrounds (pick highest-contrast channel)
          V4 — inverted OTSU    : white/light text on dark or colored backgrounds

        All variants are 3-channel BGR arrays with border padding so they can
        be fed directly to PaddleOCR / EasyOCR without further conversion.
        """
        pad = 4

        def _to_bgr_padded(gray: np.ndarray) -> np.ndarray:
            bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            return cv2.copyMakeBorder(
                bgr, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255)
            )

        variants: List[np.ndarray] = []

        # V1: CLAHE grayscale (existing _preprocess)
        variants.append(OCREngine._preprocess(img_np))

        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

        # V2: OTSU binarization — best for bold/thick fonts
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(_to_bgr_padded(otsu))

        # V3: Max-channel extraction — best for colored button backgrounds.
        # Pick the channel with highest std-dev (most contrast between text and bg).
        b_ch, g_ch, r_ch = cv2.split(img_np)
        max_chan = max((b_ch, g_ch, r_ch), key=lambda ch: float(ch.std()))
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        chan_enhanced = clahe.apply(max_chan)
        _, chan_bin = cv2.threshold(
            chan_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        variants.append(_to_bgr_padded(chan_bin))

        # V4: Inverted OTSU — for white/light text on dark or colored backgrounds
        inverted = cv2.bitwise_not(otsu)
        variants.append(_to_bgr_padded(inverted))

        # V5: 2× bicubic upscale + OTSU — for large-font / button text (e.g. "LOG IN")
        h, w = gray.shape[:2]
        upscaled = cv2.resize(
            gray, (int(w * 2), int(h * 2)), interpolation=cv2.INTER_CUBIC
        )
        _, v5_bin = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(_to_bgr_padded(v5_bin))

        return variants
