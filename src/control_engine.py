"""
PyAutoGUI control engine for Samsung OLED line SOP automation.

Handles deterministic click, double-click, drag, and retry behavior for the
12-step workflow, with emphasis on Mold ROI dragging and pin inspection setup.

v3.0: OCR-first click strategy.
  - click_target() tries OCR (button_text field from sop_steps.json) first.
  - YOLO26x used as fallback and for visual-only tasks (ROI drag, pin detection).
  - All log messages in English for Indian line engineers.

v2.1: All timing parameters are now read from ``config['control']`` so that
line engineers can tune them via config.json (or LLM suggestion) without
rebuilding the EXE.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import pyautogui
except Exception as exc:  # pragma: no cover - depends on display availability.
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:  # pragma: no cover - environment dependent branch.
    PYAUTOGUI_IMPORT_ERROR = None

from src.class_registry import ClassRegistry
from src.vision_engine import VisionEngine

logger = logging.getLogger(__name__)


@dataclass
class ControlResult:
    """Outcome record for a single control action."""

    success: bool
    coords: Optional[Tuple[int, int]]
    duration: float
    error: str = ""


def _read_control_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the ``control`` sub-dict from a full config, with safe defaults."""

    ctrl = config.get("control", {}) if config else {}
    return {
        "retries": int(ctrl.get("retries", 3)),
        "move_duration": float(ctrl.get("move_duration", 0.30)),
        "click_pause": float(ctrl.get("click_pause", 0.50)),
        "drag_duration": float(ctrl.get("drag_duration", 0.40)),
        "retry_delay": float(ctrl.get("retry_delay", 0.50)),
        "step_delay": float(ctrl.get("step_delay", 1.00)),
    }


class ControlEngine:
    """Controller for UI interactions with retry-aware execution.

    OCR-first strategy (v3.0):
      1. OCR: find button by text (button_text field in sop_steps.json)
      2. YOLO26x fallback: detect by class label
      3. Exception handler: popup / freeze / LLM recovery

    All timing parameters are configurable via ``config['control']``.
    Legacy keyword arguments (``retries``, ``move_duration``, ``click_pause``)
    are still accepted for backward compatibility, but values from ``config``
    take precedence when both are supplied.
    """

    def __init__(
        self,
        vision_agent: VisionEngine,
        config: Optional[Dict[str, Any]] = None,
        ocr_engine: Optional[Any] = None,  # OCREngine instance
        exception_handler: Optional[Any] = None,  # ExceptionHandler instance
        sop_steps: Optional[List[Dict[str, Any]]] = None,  # full sop_steps list
        # Legacy kwargs (kept for backward compat / tests).
        retries: int = 3,
        move_duration: float = 0.30,
        click_pause: float = 0.50,
    ) -> None:
        self.vision = vision_agent
        self._ocr = ocr_engine
        self._exception_handler = exception_handler
        # Build button_text lookup: target → button_text
        self._button_text_map: Dict[str, str] = {}
        if sop_steps:
            for step in sop_steps:
                tgt = step.get("target", "")
                btn_txt = step.get("button_text", "")
                if tgt and btn_txt:
                    self._button_text_map[tgt] = btn_txt
                # Also index by step id
                sid = step.get("id", "")
                if sid and btn_txt:
                    self._button_text_map[sid] = btn_txt

        self._registry = ClassRegistry.load()
        self._trace_cb: Optional[Callable[[dict], None]] = None

        if config is not None:
            cfg = _read_control_cfg(config)
            self.retries = cfg["retries"]
            self.move_duration = cfg["move_duration"]
            self.click_pause = cfg["click_pause"]
            self.drag_duration = cfg["drag_duration"]
            self.retry_delay = cfg["retry_delay"]
            self.step_delay = cfg["step_delay"]
        else:
            # Fallback to legacy kwargs (used by older tests / callers).
            self.retries = retries
            self.move_duration = move_duration
            self.click_pause = click_pause
            self.drag_duration = 0.40
            self.retry_delay = 0.50
            self.step_delay = 1.00

    @staticmethod
    def _ensure_pyautogui_available() -> None:
        if pyautogui is None:
            raise RuntimeError(
                "pyautogui is unavailable in this environment."
            ) from PYAUTOGUI_IMPORT_ERROR

    @staticmethod
    def _center_of_bbox(bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x1, y1, x2, y2 = bbox
        return (x1 + x2) // 2, (y1 + y2) // 2

    def _get_button_text(self, target_name: str) -> Optional[str]:
        """Look up button_text for a target name from sop_steps.json."""
        return self._button_text_map.get(target_name)

    @staticmethod
    def _normalize_target_name(target_name: str) -> List[str]:
        """Convert a snake_case target name into OCR search candidates.

        Examples
        --------
        "login_button"    → ["login", "login button"]
        "submit_btn"      → ["submit", "submit button"]
        "password_field"  → ["password"]
        "recipe_button"   → ["recipe", "recipe button"]
        "save_button"     → ["save", "save button"]
        """
        # Remove known suffixes that represent widget type rather than label text
        _WIDGET_SUFFIXES = ("_button", "_btn", "_field", "_label", "_icon", "_box")
        stripped = target_name
        for suffix in _WIDGET_SUFFIXES:
            if target_name.endswith(suffix):
                stripped = target_name[: -len(suffix)]
                break

        # Replace remaining underscores with spaces for multi-word labels
        readable = stripped.replace("_", " ")

        candidates: List[str] = [readable]
        # For _button / _btn suffixes also try "word button" phrasing
        if target_name.endswith(("_button", "_btn")):
            candidates.append(readable + " button")

        return candidates

    def _emit_trace(
        self,
        step_id: Optional[str],
        target: str,
        class_type: str,
        method: str,
        success: bool,
        coord: Optional[Tuple[int, int]],
        conf: Optional[float],
        roi: Optional[Tuple[int, int, int, int]],
    ) -> None:
        """Fire the trace callback if registered."""
        if self._trace_cb is not None:
            self._trace_cb(
                {
                    "step_id": step_id,
                    "target": target,
                    "class_type": class_type,
                    "method": method,
                    "success": success,
                    "coord": coord,
                    "conf": conf,
                    "roi": roi,
                }
            )

    def _resolve_target_coordinates(
        self,
        target_name: str,
        image: Optional[Any] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
        step_id: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> Optional[Tuple[int, int]]:
        """OCR-first target resolution.

        1. NON_TEXT classes → skip OCR, go directly to YOLO26x (with roi)
        2. OCR via button_text_map (explicit label from sop_steps.json)
        3. OCR via normalized target_name (e.g. "login_button" → "login")
        4. YOLO26x: detect by class label (fallback / visual targets)

        Parameters
        ----------
        target_name:
            UI target class name.
        image:
            BGR screenshot to search within. Captured from screen if None.
        roi:
            Optional (x, y, w, h) region to restrict detection.
        step_id:
            Step identifier passed through to trace callback.
        target_type:
            Override class type: "TEXT", "NON_TEXT", or None (auto-detect via registry).
        """
        if image is None:
            image = self.vision.capture_screen()

        # Determine if NON_TEXT
        is_non_text = (target_type == "NON_TEXT") or (
            target_type is None and self._registry.is_non_text(target_name)
        )

        if is_non_text:
            # Skip OCR entirely — go directly to YOLO26x
            detection = self.vision.find_detection(image, label=target_name, roi=roi)
            if detection is not None:
                coord = self._center_of_bbox(detection.bbox)
                self._emit_trace(
                    step_id,
                    target_name,
                    "NON_TEXT",
                    "YOLO",
                    True,
                    coord,
                    detection.confidence,
                    roi,
                )
                return coord
            else:
                self._emit_trace(
                    step_id, target_name, "NON_TEXT", "YOLO", False, None, None, roi
                )
                return None

        # TEXT path: OCR-first, then YOLO fallback
        # --- Priority 1: OCR with explicit button_text from sop_steps.json ---
        if self._ocr is not None:
            button_text = self._get_button_text(target_name)
            if button_text:
                region = self._ocr.find_text(image, button_text, fuzzy=True, roi=roi)
                if region is not None:
                    logger.debug("OCR found '%s' at %s", button_text, region.center)
                    self._emit_trace(
                        step_id,
                        target_name,
                        "TEXT",
                        "OCR",
                        True,
                        region.center,
                        region.confidence,
                        roi,
                    )
                    return region.center

            # --- Priority 2: OCR with normalized target_name candidates ---
            for candidate in self._normalize_target_name(target_name):
                region = self._ocr.find_text(image, candidate, fuzzy=True, roi=roi)
                if region is not None:
                    logger.debug(
                        "OCR found '%s' (normalized from '%s') at %s",
                        candidate,
                        target_name,
                        region.center,
                    )
                    self._emit_trace(
                        step_id,
                        target_name,
                        "TEXT",
                        "OCR",
                        True,
                        region.center,
                        region.confidence,
                        roi,
                    )
                    return region.center

        # OCR が存在したが全候補で失敗した場合の診断ログ
        if self._ocr is not None:
            try:
                all_regions = self._ocr.scan_all(image, roi=roi)
                detected = [r.text for r in all_regions[:10]]
                logger.warning(
                    "[OCR] '%s' not found. scan_all=%d region(s): %s",
                    target_name,
                    len(all_regions),
                    detected if detected else "(empty — OCR may be non-functional)",
                )
            except Exception as _diag_exc:
                logger.debug("[OCR] diagnostic scan failed: %s", _diag_exc)

        # --- Priority 3: YOLO26x (fallback / visual targets) ---
        detection = self.vision.find_detection(image, label=target_name, roi=roi)
        if detection is not None:
            coord = self._center_of_bbox(detection.bbox)
            self._emit_trace(
                step_id,
                target_name,
                "TEXT",
                "YOLO_fallback",
                True,
                coord,
                detection.confidence,
                roi,
            )
            return coord

        self._emit_trace(
            step_id, target_name, "TEXT", "YOLO_fallback", False, None, None, roi
        )
        return None

    def click_at(self, x: int, y: int) -> ControlResult:
        """Click a specific coordinate without any vision lookup."""

        start = time.perf_counter()
        try:
            self._ensure_pyautogui_available()
            pyautogui.moveTo(x, y, duration=self.move_duration)
            pyautogui.click()
            time.sleep(self.click_pause)
            duration = time.perf_counter() - start
            return ControlResult(success=True, coords=(x, y), duration=duration)
        except Exception as exc:  # pragma: no cover - defensive guard.
            duration = time.perf_counter() - start
            return ControlResult(
                success=False,
                coords=(x, y),
                duration=duration,
                error=str(exc),
            )

    def click_target(
        self,
        target_name: str,
        roi: Optional[Tuple[int, int, int, int]] = None,
        step_id: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> ControlResult:
        """Locate a named UI target and click it with retries.

        After each failed attempt the engine waits ``retry_delay`` seconds
        before trying again (configurable via ``config.control.retry_delay``).

        Parameters
        ----------
        target_name:
            UI target class name.
        roi:
            Optional (x, y, w, h) region to restrict detection.
        step_id:
            Step identifier passed through to trace callback.
        target_type:
            Override class type: "TEXT", "NON_TEXT", or None (auto-detect).
        """

        start = time.perf_counter()
        last_error = ""
        coords: Optional[Tuple[int, int]] = None
        _recent_history: list = []

        for attempt in range(1, self.retries + 1):
            try:
                screenshot = self.vision.capture_screen()

                # Record for freeze detection
                if self._exception_handler is not None:
                    self._exception_handler.record_screenshot(screenshot)

                coords = self._resolve_target_coordinates(
                    target_name,
                    image=screenshot,
                    roi=roi,
                    step_id=step_id,
                    target_type=target_type,
                )
                if coords is None:
                    last_error = (
                        f"Target '{target_name}' not found "
                        f"(attempt {attempt}/{self.retries})"
                    )
                    logger.warning(last_error)

                    # Try exception handler
                    if self._exception_handler is not None:
                        try:
                            from src.exception_handler import (
                                ExceptionContext,
                            )  # noqa: PLC0415

                            ocr_text = ""
                            if self._ocr is not None:
                                regions = self._ocr.scan_all(screenshot)
                                from src.exception_handler import (
                                    ExceptionHandler,
                                )  # noqa: PLC0415

                                ocr_text = ExceptionHandler.compress_ocr_text(regions)

                            context = ExceptionContext(
                                sop_step_id=target_name,
                                target_button=self._get_button_text(target_name)
                                or target_name,
                                ocr_text_on_screen=ocr_text,
                                error_type="button_not_found",
                                recent_history=_recent_history[-3:],
                            )
                            recovery = self._exception_handler.handle_exception(
                                context, img_np=screenshot
                            )
                            _recent_history.append(
                                f"attempt {attempt}: recovery={recovery.action}"
                            )
                            logger.info(
                                "Exception recovery: action=%s reason=%s",
                                recovery.action,
                                recovery.reason,
                            )
                            if recovery.action == "abort":
                                break
                            if (
                                recovery.action == "dismiss_popup"
                                and recovery.target_text
                            ):
                                # Try to click the dismiss button
                                if self._ocr is not None:
                                    fresh = self.vision.capture_screen()
                                    dismiss_region = self._ocr.find_text(
                                        fresh, recovery.target_text
                                    )
                                    if dismiss_region:
                                        self._ensure_pyautogui_available()
                                        pyautogui.click(*dismiss_region.center)
                                        time.sleep(1.0)
                        except Exception as exc_inner:
                            logger.warning("Exception handler error: %s", exc_inner)

                    time.sleep(self.retry_delay)
                    continue

                self._ensure_pyautogui_available()
                x, y = coords
                pyautogui.moveTo(x, y, duration=self.move_duration)
                pyautogui.click()
                time.sleep(self.click_pause)

                duration = time.perf_counter() - start
                _recent_history.append(f"attempt {attempt}: success at {coords}")
                return ControlResult(
                    success=True,
                    coords=coords,
                    duration=duration,
                )
            except Exception as exc:  # pragma: no cover - defensive guard.
                last_error = str(exc)
                time.sleep(self.retry_delay)

        duration = time.perf_counter() - start
        return ControlResult(
            success=False,
            coords=coords,
            duration=duration,
            error=last_error,
        )

    def drag_roi(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
    ) -> ControlResult:
        """Drag a region of interest on screen.

        Drag speed is controlled by ``drag_duration``
        (configurable via ``config.control.drag_duration``).
        """

        start_time = time.perf_counter()
        try:
            self._ensure_pyautogui_available()

            (x1, y1), (x2, y2) = VisionEngine.normalize_roi(start=start, end=end)

            pyautogui.moveTo(x1, y1, duration=self.move_duration)
            pyautogui.dragTo(x2, y2, duration=self.drag_duration)
            time.sleep(self.click_pause)

            duration = time.perf_counter() - start_time
            return ControlResult(
                success=True,
                coords=(x2, y2),
                duration=duration,
            )
        except Exception as exc:  # pragma: no cover - defensive guard.
            duration = time.perf_counter() - start_time
            return ControlResult(
                success=False,
                coords=None,
                duration=duration,
                error=str(exc),
            )
