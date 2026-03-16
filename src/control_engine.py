"""
PyAutoGUI control engine for Samsung OLED line SOP automation.

Handles deterministic click, double-click, drag, and retry behavior for the
12-step workflow, with emphasis on Mold ROI dragging and pin inspection setup.

v2.1: All timing parameters are now read from ``config['control']`` so that
line engineers can tune them via config.json (or LLM suggestion) without
rebuilding the EXE.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import pyautogui
except Exception as exc:  # pragma: no cover - depends on display availability.
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:  # pragma: no cover - environment dependent branch.
    PYAUTOGUI_IMPORT_ERROR = None

from src.vision_engine import VisionEngine


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

    All timing parameters are configurable via ``config['control']``.
    Legacy keyword arguments (``retries``, ``move_duration``, ``click_pause``)
    are still accepted for backward compatibility, but values from ``config``
    take precedence when both are supplied.
    """

    def __init__(
        self,
        vision_agent: VisionEngine,
        config: Optional[Dict[str, Any]] = None,
        # Legacy kwargs (kept for backward compat / tests).
        retries: int = 3,
        move_duration: float = 0.30,
        click_pause: float = 0.50,
    ) -> None:
        self.vision = vision_agent

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

    def _resolve_target_coordinates(
        self, target_name: str
    ) -> Optional[Tuple[int, int]]:
        """Use YOLO26x to find the target on screen."""

        image = self.vision.capture_screen()

        # YOLO label-based detection (CP-3: OCR fallback removed).
        detection = self.vision.find_detection(image, label=target_name)
        if detection is not None:
            return self._center_of_bbox(detection.bbox)

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

    def click_target(self, target_name: str) -> ControlResult:
        """Locate a named UI target and click it with retries.

        After each failed attempt the engine waits ``retry_delay`` seconds
        before trying again (configurable via ``config.control.retry_delay``).
        """

        start = time.perf_counter()
        last_error = ""
        coords: Optional[Tuple[int, int]] = None

        for attempt in range(1, self.retries + 1):
            try:
                coords = self._resolve_target_coordinates(target_name)
                if coords is None:
                    last_error = (
                        f"target '{target_name}' not found "
                        f"(attempt {attempt}/{self.retries})"
                    )
                    time.sleep(self.retry_delay)
                    continue

                self._ensure_pyautogui_available()
                x, y = coords
                pyautogui.moveTo(x, y, duration=self.move_duration)
                pyautogui.click()
                time.sleep(self.click_pause)

                duration = time.perf_counter() - start
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
