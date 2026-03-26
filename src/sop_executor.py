"""
12-step SOP executor for Connector Vision Agent v3.8.

Coordinates login, recipe loading, Mold Left/Right ROI training, axis marking,
pin scan/count verification, verify left/right, and final save/apply actions
for line setup.

v2.1 changes:
- ``pin_count_min`` / ``pin_count_max`` now read from config (not hardcoded).
- ``step_delay`` inserted between every SOP step (configurable via config).
- ``config`` dict passed through from ``main.py`` for full runtime control.

v3.0 additions:
- ``get_steps()`` — returns a list of step dicts from sop_steps.json (or fallback).
- ``run_step(step)`` — execute a single step dict (used by GUI SopWorker).
- ``sop_steps_path`` parameter to load external step definitions.

v3.8 additions (SOP field requirement 100%):
- ``auth_sequence`` step type — LOGIN button → PW field → type_text → OK/Enter.
- ``input_text`` step type   — click field → type_text → Enter (axis X/Y).
- ``mold_setup``  step type  — click label → drag ROI (combined mold step).
- New steps: ``axis_y``, ``verify_left``, ``verify_right``.
- ``control.type_text()`` / ``control.press_key()`` wired into executor.
- Password read from ``config['password']`` (default ``"1111"``).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.control_engine import ControlEngine, ControlResult
from src.vision_engine import VisionEngine, DEFAULT_MOLD_ROI

logger = logging.getLogger(__name__)


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

    @property
    def _password(self) -> str:
        """Authentication password (from config['password'], default '1111')."""
        return str(self._config.get("password", "1111"))

    # ------------------------------------------------------------------
    # High-level public API
    # ------------------------------------------------------------------

    def run(self) -> List[str]:
        """Execute the 12-step SOP and return a concise textual trace."""

        steps = [
            self._step_login,
            self._step_open_recipe,
            self._step_mold_left,
            self._step_mold_right,
            self._step_axis_x,
            self._step_axis_y,
            self._step_pin_scan,
            self._step_pin_count,
            self._step_verify_left,
            self._step_verify_right,
            self._step_save,
            self._step_apply,
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
        # Fallback: built-in 12-step list (mirrors sop_steps.json v1.3)
        return [
            {
                "id": "login",
                "name": "Login",
                "type": "auth_sequence",
                "login_button": "login_button",
                "password_field": "password_field",
                "ok_button": "ok_button",
            },
            {
                "id": "open_recipe",
                "name": "Recipe Menu",
                "type": "click",
                "target": "recipe_button",
                "button_text": "RECIPE",
            },
            {
                "id": "mold_left",
                "name": "Mold Left",
                "type": "mold_setup",
                "label_target": "mold_left_label",
                "drag_start": [100, 200],
                "drag_end": [800, 350],
                "roi": [0, 0, 960, 1080],
            },
            {
                "id": "mold_right",
                "name": "Mold Right",
                "type": "mold_setup",
                "label_target": "mold_right_label",
                "drag_start": [100, 200],
                "drag_end": [800, 350],
                "roi": [960, 0, 1920, 1080],
            },
            {
                "id": "axis_x",
                "name": "Axis-X",
                "type": "input_text",
                "target": "axis_x_field",
                "text": "0",
                "clear_first": True,
            },
            {
                "id": "axis_y",
                "name": "Axis-Y",
                "type": "input_text",
                "target": "axis_y_field",
                "text": "0",
                "clear_first": True,
            },
            {
                "id": "pin_scan",
                "name": "Pin Array",
                "type": "validate_pins",
                "roi": [400, 300, 1120, 480],
            },
            {
                "id": "pin_count",
                "name": "Pin Count",
                "type": "validate_pins",
                "roi": [400, 600, 1120, 780],
            },
            {
                "id": "verify_left",
                "name": "Verify Left",
                "type": "click",
                "target": "verify_left_button",
                "button_text": "VERIFY L",
            },
            {
                "id": "verify_right",
                "name": "Verify Right",
                "type": "click",
                "target": "verify_right_button",
                "button_text": "VERIFY R",
            },
            {"id": "save", "name": "Save", "type": "click", "target": "save_button"},
            {
                "id": "apply",
                "name": "Apply",
                "type": "click_sequence",
                "targets": ["apply_button", "open_icon"],
            },
        ]

    def run_step(self, step: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute a single step dict. Returns (success, message)."""
        step_type = step.get("type", "click")
        step_id = step.get("id", "?")
        step_name = step.get("name", step_id)

        # Extract optional ROI and target_type fields
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

        elif step_type == "auth_sequence":
            result3: SopStepResult = self._run_auth_sequence(step)
            return result3.success, result3.details

        elif step_type == "input_text":
            result4: SopStepResult = self._run_input_text(step)
            return result4.success, result4.details

        elif step_type == "mold_setup":
            result5: SopStepResult = self._run_mold_setup(step)
            return result5.success, result5.details

        else:
            return False, f"Unknown step type: {step_type!r}"

    # ------------------------------------------------------------------
    # Composite step runners (v3.8 new types)
    # ------------------------------------------------------------------

    def _run_auth_sequence(self, step: Dict[str, Any]) -> SopStepResult:
        """Full authentication: LOGIN button → PW field → type password → OK/Enter.

        Step dict fields:
          login_button   : target name for the LOGIN button (default 'login_button')
          password_field : target name for the password input (default 'password_field')
          ok_button      : target name for the OK/confirm button (default 'ok_button')
        Password is read from ``self._password`` (config['password'] or '1111').
        """
        step_name = step.get("name", "login")
        step_id = step.get("id", "login")

        # 1. Click LOGIN button
        login_btn = step.get("login_button", "login_button")
        res = self._click_with_trace(login_btn, step_name, step_id=step_id)
        if not res.success:
            return SopStepResult(
                name=step_name,
                success=False,
                details=f"auth: LOGIN button not found — {res.details}",
            )
        time.sleep(0.5)

        # 2. Click password field (Tab fallback if field not found)
        pw_field = step.get("password_field", "password_field")
        pw_res = self._click_with_trace(pw_field, step_name, step_id=step_id)
        if not pw_res.success:
            logger.warning(
                "auth: password field '%s' not found, pressing Tab to advance focus",
                pw_field,
            )
            self.control.press_key("tab")
            time.sleep(0.3)

        # 3. Type password
        password = self._password
        type_result = self.control.type_text(password, clear_first=True)
        if not type_result.success:
            return SopStepResult(
                name=step_name,
                success=False,
                details=f"auth: type_text failed — {type_result.error}",
            )
        time.sleep(0.3)

        # 4. Confirm: try OK button, fall back to Enter
        ok_btn = step.get("ok_button", "ok_button")
        ok_res = self._click_with_trace(ok_btn, step_name, step_id=step_id)
        if not ok_res.success:
            logger.info(
                "auth: OK button '%s' not found — pressing Enter as fallback", ok_btn
            )
            self.control.press_key("enter")

        return SopStepResult(
            name=step_name,
            success=True,
            details=(
                f"auth complete: {login_btn}→{pw_field}→"
                f"typed({len(password)} chars)→confirm"
            ),
        )

    def _run_input_text(self, step: Dict[str, Any]) -> SopStepResult:
        """Click a text field, clear it, type a value, then press Enter.

        Step dict fields:
          target      : target name for the input field
          text        : string to type (default '0')
          clear_first : bool — select-all+delete before typing (default True)
        """
        step_name = step.get("name", "input_text")
        step_id = step.get("id", "input_text")
        target = step.get("target", step_id)
        text = str(step.get("text", "0"))
        clear_first = bool(step.get("clear_first", True))
        roi: Optional[Tuple[int, int, int, int]] = (
            tuple(step["roi"]) if step.get("roi") else None  # type: ignore[assignment]
        )
        target_type: Optional[str] = step.get("target_type")

        # 1. Click the input field
        click_res = self._click_with_trace(
            target, step_name, roi=roi, step_id=step_id, target_type=target_type
        )
        if not click_res.success:
            return SopStepResult(
                name=step_name,
                success=False,
                details=f"input_text: field '{target}' not found — {click_res.details}",
            )
        time.sleep(0.2)

        # 2. Type the text
        type_result = self.control.type_text(text, clear_first=clear_first)
        if not type_result.success:
            return SopStepResult(
                name=step_name,
                success=False,
                details=f"input_text: type_text failed — {type_result.error}",
            )

        # 3. Confirm with Enter
        self.control.press_key("enter")

        dur = float(getattr(type_result, "duration", 0.0))
        return SopStepResult(
            name=step_name,
            success=True,
            details=f"typed '{text}' into '{target}' in {dur:.3f}s",
        )

    def _run_mold_setup(self, step: Dict[str, Any]) -> SopStepResult:
        """Click the mold label, then drag to define the inspection ROI.

        Step dict fields:
          label_target : target name for the mold label (e.g. 'mold_left_label')
          drag_start   : [x, y] drag start coordinates
          drag_end     : [x, y] drag end coordinates
          roi          : optional [x, y, w, h] bounding box for detection
        """
        step_name = step.get("name", "mold_setup")
        step_id = step.get("id", "mold_setup")
        label_target = step.get("label_target", "mold_left_label")
        drag_start = tuple(step.get("drag_start", [100, 200]))
        drag_end = tuple(step.get("drag_end", [800, 350]))
        roi: Optional[Tuple[int, int, int, int]] = (
            tuple(step["roi"]) if step.get("roi") else None  # type: ignore[assignment]
        )
        target_type: Optional[str] = step.get("target_type")

        # 1. Click label
        click_res = self._click_with_trace(
            label_target, step_name, roi=roi, step_id=step_id, target_type=target_type
        )
        if not click_res.success:
            return SopStepResult(
                name=step_name,
                success=False,
                details=(
                    f"mold_setup: label '{label_target}' not found"
                    f" — {click_res.details}"
                ),
            )
        time.sleep(0.5)

        # 2. Drag ROI
        drag_result: ControlResult = self.control.drag_roi(  # type: ignore[arg-type]
            drag_start, drag_end
        )
        if not drag_result.success:
            return SopStepResult(
                name=step_name,
                success=False,
                details=f"mold_setup: drag failed — {drag_result.error}",
            )

        dur = float(getattr(drag_result, "duration", 0.0))
        return SopStepResult(
            name=step_name,
            success=True,
            details=(
                f"mold_setup: clicked '{label_target}', "
                f"dragged {drag_start}→{drag_end} in {dur:.3f}s"
            ),
        )

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
        """Full auth: LOGIN → password field → type PW → OK/Enter."""
        step = {
            "id": "login",
            "name": "login",
            "type": "auth_sequence",
            "login_button": "login_button",
            "password_field": "password_field",
            "ok_button": "ok_button",
        }
        return self._run_auth_sequence(step)

    def _step_open_recipe(self) -> SopStepResult:
        return self._click_with_trace("recipe_button", "open_recipe")

    def _step_mold_left(self) -> SopStepResult:
        """Click MOLD LEFT label then drag ROI."""
        step = {
            "id": "mold_left",
            "name": "mold_left",
            "type": "mold_setup",
            "label_target": "mold_left_label",
            "drag_start": list(DEFAULT_MOLD_ROI[0]),
            "drag_end": list(DEFAULT_MOLD_ROI[1]),
            "roi": [0, 0, 960, 1080],
        }
        return self._run_mold_setup(step)

    def _step_mold_right(self) -> SopStepResult:
        """Click MOLD RIGHT label then drag ROI."""
        step = {
            "id": "mold_right",
            "name": "mold_right",
            "type": "mold_setup",
            "label_target": "mold_right_label",
            "drag_start": list(DEFAULT_MOLD_ROI[0]),
            "drag_end": list(DEFAULT_MOLD_ROI[1]),
            "roi": [960, 0, 1920, 1080],
        }
        return self._run_mold_setup(step)

    def _step_axis_x(self) -> SopStepResult:
        """Click AXIS-X field and enter X-axis reference coordinate."""
        step = {
            "id": "axis_x",
            "name": "axis_x",
            "type": "input_text",
            "target": "axis_x_field",
            "text": "0",
            "clear_first": True,
        }
        return self._run_input_text(step)

    def _step_axis_y(self) -> SopStepResult:
        """Click AXIS-Y field and enter Y-axis reference coordinate."""
        step = {
            "id": "axis_y",
            "name": "axis_y",
            "type": "input_text",
            "target": "axis_y_field",
            "text": "0",
            "clear_first": True,
        }
        return self._run_input_text(step)

    def _validate_pins(self, step_name: str) -> SopStepResult:
        """Shared pin-count validation for pin_scan / pin_count steps.

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

    def _step_pin_scan(self) -> SopStepResult:
        """Scan pin array positions (top ROI)."""
        return self._validate_pins("pin_scan")

    def _step_pin_count(self) -> SopStepResult:
        """Validate total pin count (bottom ROI)."""
        return self._validate_pins("pin_count")

    def _step_verify_left(self) -> SopStepResult:
        """Click VERIFY L to confirm left connector positioning."""
        return self._click_with_trace("verify_left_button", "verify_left")

    def _step_verify_right(self) -> SopStepResult:
        """Click VERIFY R to confirm right connector positioning."""
        return self._click_with_trace("verify_right_button", "verify_right")

    def _step_save(self) -> SopStepResult:
        return self._click_with_trace("save_button", "save")

    def _step_apply(self) -> SopStepResult:
        apply_result = self._click_with_trace("apply_button", "apply")
        if not apply_result.success:
            return apply_result

        open_result = self._click_with_trace("open_icon", "open_after_apply")
        success = apply_result.success and open_result.success
        details = f"{apply_result.details} | {open_result.details}"
        return SopStepResult(name="apply", success=success, details=details)

    # ------------------------------------------------------------------
    # Legacy aliases (backward compat — kept so old test fixtures work)
    # ------------------------------------------------------------------

    def _step_select_image_source(self) -> SopStepResult:  # pragma: no cover
        """Removed in v3.8 (not in standard SOP). Kept as no-op alias."""
        return SopStepResult(
            name="image_source",
            success=True,
            details="image_source step skipped (removed in v3.8 standard SOP)",
        )

    def _step_in_pin_up(self) -> SopStepResult:  # pragma: no cover
        """Alias for _step_pin_scan (renamed in v3.8)."""
        return self._step_pin_scan()

    def _step_in_pin_down(self) -> SopStepResult:  # pragma: no cover
        """Alias for _step_pin_count (renamed in v3.8)."""
        return self._step_pin_count()

    def _step_apply_and_open(self) -> SopStepResult:  # pragma: no cover
        """Alias for _step_apply (renamed in v3.8)."""
        return self._step_apply()
