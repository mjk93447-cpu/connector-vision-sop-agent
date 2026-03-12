"""
PyAutoGUI control engine for Samsung OLED line SOP automation.

Handles deterministic click, double-click, drag, and retry behavior for the
12-step workflow, with emphasis on Mold ROI dragging and pin inspection setup.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    import pyautogui
except Exception as exc:  # pragma: no cover - depends on display availability.
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:  # pragma: no cover - environment dependent branch.
    PYAUTOGUI_IMPORT_ERROR = None

from src.vision_engine import VisionAgent


@dataclass
class ControlResult:
    """Outcome record for a single control action."""

    success: bool
    coords: Optional[Tuple[int, int]]
    duration: float
    error: str = ""


class ControlEngine:
    """Controller for UI interactions with retry-aware execution.

    This class is tightly coupled to ``VisionAgent`` / ``VisionEngine``:

    - Uses YOLO detections (and OCR fallback) to resolve target coordinates.
    - Executes PyAutoGUI interactions with configurable retry behavior.
    - Returns structured ``ControlResult`` objects for logging and validation.
    """

    def __init__(
        self,
        vision_agent: VisionAgent,
        retries: int = 3,
        move_duration: float = 0.1,
        click_pause: float = 0.05,
    ) -> None:
        self.vision = vision_agent
        self.retries = retries
        self.move_duration = move_duration
        self.click_pause = click_pause

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
        """Use YOLO (and optional OCR) to find the target on screen."""

        # Capture the current screen as a BGR image for the vision engine.
        image = self.vision.capture_screen()

        # 1) Try YOLO label-based detection.
        detection = self.vision.find_detection(image, label=target_name)
        if detection is not None:
            return self._center_of_bbox(detection.bbox)

        # 2) Fallback: OCR-based lookup when target_name is a visible text label.
        text_match = self.vision.locate_text(image, target_text=target_name)
        if text_match is not None:
            return self._center_of_bbox(text_match["bbox"])  # type: ignore[arg-type]

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
        """Locate a named UI target and click it with retries."""

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
                    time.sleep(0.1)
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
                time.sleep(0.1)

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
        """Drag a region of interest on screen, using normalized ROI coordinates."""

        from src.vision_engine import VisionAgent as _VA  # local import to avoid cycle

        start_time = time.perf_counter()
        try:
            self._ensure_pyautogui_available()

            # Normalize ROI so callers can pass arbitrary corner order.
            (x1, y1), (x2, y2) = _VA.normalize_roi(start=start, end=end)

            pyautogui.moveTo(x1, y1, duration=self.move_duration)
            pyautogui.dragTo(x2, y2, duration=self.move_duration)
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
