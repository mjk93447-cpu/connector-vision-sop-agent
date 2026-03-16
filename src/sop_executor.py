"""
12-step SOP executor for Connector Vision Agent v2.1.

Coordinates login, recipe loading, Mold Left/Right ROI training, axis marking,
In Pin Up/Down verification, and final save/open/apply actions for line setup.

v2.1 changes:
- ``pin_count_min`` / ``pin_count_max`` now read from config (not hardcoded).
- ``step_delay`` inserted between every SOP step (configurable via config).
- ``config`` dict passed through from ``main.py`` for full runtime control.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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

    def __init__(
        self,
        vision: VisionEngine,
        control: ControlEngine,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.vision = vision
        self.control = control
        self._config = config or {}

    # ------------------------------------------------------------------
    # Config convenience helpers
    # ------------------------------------------------------------------

    @property
    def _pin_count_min(self) -> int:
        """Minimum accepted pin count (from config, default 20)."""
        val = self._config.get("pin_count_min")
        return int(val) if val is not None else 20

    @property
    def _pin_count_max(self) -> int:
        """Maximum accepted pin count (from config, default unlimited)."""
        val = self._config.get("pin_count_max")
        if val is None:
            return 9999
        return int(val)

    @property
    def _step_delay(self) -> float:
        """Seconds to wait between SOP steps (from config.control.step_delay)."""
        return float(self._config.get("control", {}).get("step_delay", 1.0))

    # ------------------------------------------------------------------
    # High-level public API
    # ------------------------------------------------------------------

    def run(self) -> List[str]:
        """Execute the 12-step SOP and return a concise textual trace."""

        steps = [
            self._step_login,
            self._step_open_recipe,
            self._step_select_image_source,
            self._step_mold_left_label,
            self._step_mold_left_roi,
            self._step_mold_right_label,
            self._step_mold_right_roi,
            self._step_axis_marking,
            self._step_in_pin_up,
            self._step_in_pin_down,
            self._step_save,
            self._step_apply_and_open,
        ]

        results: List[SopStepResult] = []
        for step_fn in steps:
            result = step_fn()
            results.append(result)
            if self._step_delay > 0:
                time.sleep(self._step_delay)

        trace: List[str] = []
        for index, step in enumerate(results, start=1):
            status = "OK" if step.success else "FAIL"
            trace.append(f"{index:02d}:{step.name}:{status}:{step.details}")
        return trace

    # ------------------------------------------------------------------
    # Individual SOP step implementations
    # ------------------------------------------------------------------

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
        return self._click_with_trace("image_source", "select_image_source")

    def _step_mold_left_label(self) -> SopStepResult:
        return self._click_with_trace("mold_left_label", "select_mold_left")

    def _step_mold_left_roi(self) -> SopStepResult:
        start, end = DEFAULT_MOLD_ROI
        drag_result: ControlResult = self.control.drag_roi(start, end)
        if drag_result.success:
            details = (
                f"dragged mold_left_roi {start}->{end} "
                f"in {drag_result.duration:.3f}s"
            )
            return SopStepResult(name="mold_left_roi", success=True, details=details)
        details = f"drag mold_left_roi failed: {drag_result.error}"
        return SopStepResult(name="mold_left_roi", success=False, details=details)

    def _step_mold_right_label(self) -> SopStepResult:
        return self._click_with_trace("mold_right_label", "select_mold_right")

    def _step_mold_right_roi(self) -> SopStepResult:
        start, end = DEFAULT_MOLD_ROI
        drag_result: ControlResult = self.control.drag_roi(start, end)
        if drag_result.success:
            details = (
                f"dragged mold_right_roi {start}->{end} "
                f"in {drag_result.duration:.3f}s"
            )
            return SopStepResult(name="mold_right_roi", success=True, details=details)
        details = f"drag mold_right_roi failed: {drag_result.error}"
        return SopStepResult(name="mold_right_roi", success=False, details=details)

    def _step_axis_marking(self) -> SopStepResult:
        return self._click_with_trace("axis_mark", "axis_marking")

    def _validate_pins(self, step_name: str) -> SopStepResult:
        """Shared pin-count validation for in_pin_up / in_pin_down steps.

        Uses ``pin_count_min`` and ``pin_count_max`` from config so that
        line engineers can adjust the acceptable range without recompiling.
        """
        image = self.vision.capture_screen()
        validation = self.vision.validate_pin_count(
            image, pin_count_min=self._pin_count_min
        )
        count = int(validation.get("count", 0))

        if not validation.get("valid"):
            details = (
                f"{step_name} invalid: detected {count} pins, "
                f"min required {self._pin_count_min}"
            )
            return SopStepResult(name=step_name, success=False, details=details)

        if count > self._pin_count_max:
            details = (
                f"{step_name} invalid: detected {count} pins, "
                f"max allowed {self._pin_count_max}"
            )
            return SopStepResult(name=step_name, success=False, details=details)

        details = (
            f"{step_name} valid: {count} pins "
            f"(expected {self._pin_count_min}~{self._pin_count_max})"
        )
        return SopStepResult(name=step_name, success=True, details=details)

    def _step_in_pin_up(self) -> SopStepResult:
        return self._validate_pins("in_pin_up")

    def _step_in_pin_down(self) -> SopStepResult:
        return self._validate_pins("in_pin_down")

    def _step_save(self) -> SopStepResult:
        return self._click_with_trace("save_button", "save")

    def _step_apply_and_open(self) -> SopStepResult:
        apply_result = self._click_with_trace("apply_button", "apply")
        if not apply_result.success:
            return apply_result

        open_result = self._click_with_trace("open_icon", "open_after_apply")
        success = apply_result.success and open_result.success
        details = f"{apply_result.details} | {open_result.details}"
        return SopStepResult(name="apply_and_open", success=success, details=details)
