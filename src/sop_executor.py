"""
12-step SOP executor for Connector Vision Agent v2.1 / v3.0.

Coordinates login, recipe loading, Mold Left/Right ROI training, axis marking,
In Pin Up/Down verification, and final save/open/apply actions for line setup.

v2.1 changes:
- ``pin_count_min`` / ``pin_count_max`` now read from config (not hardcoded).
- ``step_delay`` inserted between every SOP step (configurable via config).
- ``config`` dict passed through from ``main.py`` for full runtime control.

v3.0 additions:
- ``get_steps()`` — returns a list of step dicts from sop_steps.json (or fallback).
- ``run_step(step)`` — execute a single step dict (used by GUI SopWorker).
- ``sop_steps_path`` parameter to load external step definitions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        sop_steps_path: Optional[Path] = None,
    ) -> None:
        self.vision = vision
        self.control = control
        self._config = config or {}
        self._sop_steps_path = sop_steps_path or Path("assets/sop_steps.json")

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
    # GUI-facing API (used by SopWorker)
    # ------------------------------------------------------------------

    def get_steps(self) -> List[Dict[str, Any]]:
        """Return enabled steps from sop_steps.json (or built-in fallback)."""
        if self._sop_steps_path.exists():
            try:
                data = json.loads(self._sop_steps_path.read_text(encoding="utf-8"))
                return [s for s in data.get("steps", []) if s.get("enabled", True)]
            except Exception:  # noqa: BLE001
                pass
        # Fallback: built-in step list
        return [
            {"id": "login", "name": "Login", "type": "click", "target": "login_button"},
            {
                "id": "open_recipe",
                "name": "Open Recipe",
                "type": "click",
                "target": "recipe_button",
            },
            {
                "id": "image_source",
                "name": "Select Source",
                "type": "click",
                "target": "image_source",
            },
            {
                "id": "mold_left_label",
                "name": "Mold Left Label",
                "type": "click",
                "target": "mold_left_label",
            },
            {
                "id": "mold_left_roi",
                "name": "Mold Left ROI",
                "type": "drag",
                "start": [100, 200],
                "end": [800, 350],
            },
            {
                "id": "mold_right_label",
                "name": "Mold Right Label",
                "type": "click",
                "target": "mold_right_label",
            },
            {
                "id": "mold_right_roi",
                "name": "Mold Right ROI",
                "type": "drag",
                "start": [100, 200],
                "end": [800, 350],
            },
            {
                "id": "axis_marking",
                "name": "Axis Marking",
                "type": "click",
                "target": "axis_mark",
            },
            {"id": "in_pin_up", "name": "Pin Up Check", "type": "validate_pins"},
            {"id": "in_pin_down", "name": "Pin Down Check", "type": "validate_pins"},
            {"id": "save", "name": "Save", "type": "click", "target": "save_button"},
            {
                "id": "apply_and_open",
                "name": "Apply & Open",
                "type": "click_sequence",
                "targets": ["apply_button", "open_icon"],
            },
        ]

    def run_step(self, step: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute a single step dict. Returns (success, message)."""
        step_type = step.get("type", "click")
        step_id = step.get("id", "?")
        step_name = step.get("name", step_id)

        # Extract optional ROI and target_type fields added in v3.5.0
        roi: Optional[Tuple[int, int, int, int]] = (
            tuple(step["roi"]) if step.get("roi") else None  # type: ignore[assignment]
        )
        target_type: Optional[str] = step.get("target_type")

        if step_type == "click":
            target = step.get("target", step_id)
            result: SopStepResult = self._click_with_trace(
                target,
                step_name,
                roi=roi,
                step_id=step_id,
                target_type=target_type,
            )
            return result.success, result.details

        elif step_type == "drag":
            start = tuple(step.get("start", [100, 200]))
            end = tuple(step.get("end", [800, 350]))
            drag_result: ControlResult = self.control.drag_roi(start, end)  # type: ignore[arg-type]
            if drag_result.success:
                return True, f"dragged {start}->{end} in {drag_result.duration:.3f}s"
            return False, f"drag failed: {drag_result.error}"

        elif step_type == "validate_pins":
            result2: SopStepResult = self._validate_pins(step_name)
            return result2.success, result2.details

        elif step_type == "click_sequence":
            targets = step.get("targets", [])
            details_parts = []
            for tgt in targets:
                res = self._click_with_trace(
                    tgt,
                    step_name,
                    roi=roi,
                    step_id=step_id,
                    target_type=target_type,
                )
                details_parts.append(res.details)
                if not res.success:
                    return False, " | ".join(details_parts)
            return True, " | ".join(details_parts)

        else:
            return False, f"Unknown step type: {step_type!r}"

    # ------------------------------------------------------------------
    # Individual SOP step implementations
    # ------------------------------------------------------------------

    def _click_with_trace(
        self,
        target_name: str,
        step_name: str,
        roi: Optional[Tuple[int, int, int, int]] = None,
        step_id: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> SopStepResult:
        """Helper to run a click step and convert to ``SopStepResult``."""

        result: ControlResult = self.control.click_target(
            target_name,
            roi=roi,
            step_id=step_id,
            target_type=target_type,
        )
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
