"""
12-step SOP executor for Connector Vision Agent v1.0.

Coordinates login, recipe loading, Mold Left/Right ROI training, axis marking,
In Pin Up/Down verification, and final save/open/apply actions for line setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

from src.control_engine import ControlEngine, ControlResult
from src.vision_engine import VisionEngine, DEFAULT_MOLD_ROI


@dataclass
class SopStepResult:
    """Structured result for a single SOP step."""

    name: str
    success: bool
    details: str


class SopExecutor:
    """Coordinate the high-level 12-step SOP sequence across vision and control."""

    def __init__(self, vision: VisionEngine, control: ControlEngine) -> None:
        self.vision = vision
        self.control = control

    # --- High-level public API -------------------------------------------------

    def run(self) -> List[str]:
        """Execute the 12-step SOP and return a concise textual trace.

        The actual clicks/drag/OCR/YOLO interactions are handled by
        ``VisionEngine`` and ``ControlEngine``. This method focuses on domain
        sequencing and returns a human-readable trace for logging and tests.
        """

        results: List[SopStepResult] = []

        results.append(self._step_login())
        results.append(self._step_open_recipe())
        results.append(self._step_select_image_source())
        results.append(self._step_mold_left_label())
        results.append(self._step_mold_left_roi())
        results.append(self._step_mold_right_label())
        results.append(self._step_mold_right_roi())
        results.append(self._step_axis_marking())
        results.append(self._step_in_pin_up())
        results.append(self._step_in_pin_down())
        results.append(self._step_save())
        results.append(self._step_apply_and_open())

        # Convert to simple trace strings for backward-compatible callers.
        trace: List[str] = []
        for index, step in enumerate(results, start=1):
            status = "OK" if step.success else "FAIL"
            trace.append(f"{index:02d}:{step.name}:{status}:{step.details}")
        return trace

    # --- Individual SOP step implementations ----------------------------------

    def _click_with_trace(self, target_name: str, step_name: str) -> SopStepResult:
        """Helper to run a click step and convert to ``SopStepResult``."""

        result: ControlResult = self.control.click_target(target_name)
        if result.success:
            coords_repr = f"@{result.coords}" if result.coords else "@?"
            details = f"clicked {target_name}{coords_repr} in {result.duration:.3f}s"
            return SopStepResult(name=step_name, success=True, details=details)

        details = f"click {target_name} failed: {result.error}"
        return SopStepResult(name=step_name, success=False, details=details)

    def _step_login(self) -> SopStepResult:
        return self._click_with_trace("login_button", "login")

    def _step_open_recipe(self) -> SopStepResult:
        return self._click_with_trace("recipe_button", "open_recipe")

    def _step_select_image_source(self) -> SopStepResult:
        # Some UIs expose this as an icon; YOLO label is "image_source".
        return self._click_with_trace("image_source", "select_image_source")

    def _step_mold_left_label(self) -> SopStepResult:
        # Mold Left label may be an explicit button or OCR label.
        return self._click_with_trace("mold_left_label", "select_mold_left")

    def _step_mold_left_roi(self) -> SopStepResult:
        start, end = DEFAULT_MOLD_ROI
        drag_result: ControlResult = self.control.drag_roi(start, end)
        if drag_result.success:
            details = (
                f"dragged mold_left_roi {start}->{end} "
                f"in {drag_result.duration:.3f}s"
            )
            return SopStepResult(
                name="mold_left_roi",
                success=True,
                details=details,
            )
        details = f"drag mold_left_roi failed: {drag_result.error}"
        return SopStepResult(
            name="mold_left_roi",
            success=False,
            details=details,
        )

    def _step_mold_right_label(self) -> SopStepResult:
        return self._click_with_trace("mold_right_label", "select_mold_right")

    def _step_mold_right_roi(self) -> SopStepResult:
        # For now reuse DEFAULT_MOLD_ROI; field deployments can adjust config later.
        start, end = DEFAULT_MOLD_ROI
        drag_result: ControlResult = self.control.drag_roi(start, end)
        if drag_result.success:
            details = (
                f"dragged mold_right_roi {start}->{end} "
                f"in {drag_result.duration:.3f}s"
            )
            return SopStepResult(
                name="mold_right_roi",
                success=True,
                details=details,
            )
        details = f"drag mold_right_roi failed: {drag_result.error}"
        return SopStepResult(
            name="mold_right_roi",
            success=False,
            details=details,
        )

    def _step_axis_marking(self) -> SopStepResult:
        # Axis marking is typically done in the left mold; use generic text label.
        return self._click_with_trace("axis_mark", "axis_marking")

    def _step_in_pin_up(self) -> SopStepResult:
        # Capture ROI and validate pin count via the vision engine.
        image = self.vision.capture_screen()
        validation = self.vision.validate_pin_count(image)
        if validation.get("valid"):
            count = int(validation.get("count", 0))
            pin_min = int(validation.get("pin_count_min", 0))
            details = f"in_pin_up valid: {count} pins (min {pin_min})"
            return SopStepResult(
                name="in_pin_up",
                success=True,
                details=details,
            )

        details = f"in_pin_up invalid: {validation}"
        return SopStepResult(
            name="in_pin_up",
            success=False,
            details=details,
        )

    def _step_in_pin_down(self) -> SopStepResult:
        # For the basic scaffold, reuse the same validation strategy.
        image = self.vision.capture_screen()
        validation = self.vision.validate_pin_count(image)
        if validation.get("valid"):
            count = int(validation.get("count", 0))
            pin_min = int(validation.get("pin_count_min", 0))
            details = f"in_pin_down valid: {count} pins (min {pin_min})"
            return SopStepResult(
                name="in_pin_down",
                success=True,
                details=details,
            )

        details = f"in_pin_down invalid: {validation}"
        return SopStepResult(
            name="in_pin_down",
            success=False,
            details=details,
        )

    def _step_save(self) -> SopStepResult:
        # Use a generic "save" target; YOLO or OCR can back this.
        return self._click_with_trace("save_button", "save")

    def _step_apply_and_open(self) -> SopStepResult:
        # Final apply/open; UIs vary, so we use two attempts with the same helper.
        apply_result = self._click_with_trace("apply_button", "apply")
        if not apply_result.success:
            return apply_result

        # Optionally open/confirm recipe after apply.
        open_result = self._click_with_trace("open_icon", "open_after_apply")
        success = apply_result.success and open_result.success
        details = f"{apply_result.details} | {open_result.details}"
        return SopStepResult(
            name="apply_and_open",
            success=success,
            details=details,
        )
