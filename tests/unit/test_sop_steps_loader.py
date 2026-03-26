"""
sop_steps.json 로더 및 SopExecutor.get_steps() / run_step() 단위 테스트.

실제 YOLO 가중치·디스플레이 없이 monkeypatch 기반으로 실행.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock


from src.sop_executor import SopExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_executor(tmp_path: Path, steps_data: Dict[str, Any]) -> SopExecutor:
    """Create a SopExecutor with mocked vision/control and a temp sop_steps.json."""
    steps_path = tmp_path / "sop_steps.json"
    steps_path.write_text(json.dumps(steps_data), encoding="utf-8")

    vision = MagicMock()
    control = MagicMock()
    config: Dict[str, Any] = {"pin_count_min": 40, "pin_count_max": 40}

    executor = SopExecutor(
        vision=vision, control=control, config=config, sop_steps_path=steps_path
    )
    return executor


def _make_executor_no_file(tmp_path: Path) -> SopExecutor:
    """Create SopExecutor pointing to a non-existent sop_steps.json."""
    steps_path = tmp_path / "nonexistent_sop_steps.json"
    vision = MagicMock()
    control = MagicMock()
    return SopExecutor(vision=vision, control=control, sop_steps_path=steps_path)


# ---------------------------------------------------------------------------
# TestGetSteps — sop_steps.json 로드
# ---------------------------------------------------------------------------


class TestGetSteps:
    def test_loads_all_enabled_steps(self, tmp_path: Path) -> None:
        data = {
            "version": "1.0",
            "steps": [
                {
                    "id": "login",
                    "name": "Login",
                    "type": "click",
                    "target": "btn",
                    "enabled": True,
                },
                {
                    "id": "save",
                    "name": "Save",
                    "type": "click",
                    "target": "save_btn",
                    "enabled": True,
                },
            ],
        }
        ex = _make_executor(tmp_path, data)
        steps = ex.get_steps()
        assert len(steps) == 2
        assert steps[0]["id"] == "login"
        assert steps[1]["id"] == "save"

    def test_excludes_disabled_steps(self, tmp_path: Path) -> None:
        data = {
            "version": "1.0",
            "steps": [
                {"id": "login", "name": "Login", "type": "click", "enabled": True},
                {"id": "skip_me", "name": "Skip", "type": "click", "enabled": False},
                {"id": "save", "name": "Save", "type": "click", "enabled": True},
            ],
        }
        ex = _make_executor(tmp_path, data)
        steps = ex.get_steps()
        ids = [s["id"] for s in steps]
        assert "skip_me" not in ids
        assert "login" in ids
        assert "save" in ids

    def test_missing_file_returns_builtin_fallback(self, tmp_path: Path) -> None:
        ex = _make_executor_no_file(tmp_path)
        steps = ex.get_steps()
        assert len(steps) == 12  # built-in has 12 steps
        ids = [s["id"] for s in steps]
        assert "login" in ids
        # v3.8: renamed steps
        assert "pin_scan" in ids  # was in_pin_up
        assert "apply" in ids  # was apply_and_open

    def test_corrupted_file_returns_builtin_fallback(self, tmp_path: Path) -> None:
        steps_path = tmp_path / "sop_steps.json"
        steps_path.write_text("NOT_VALID_JSON", encoding="utf-8")
        vision, control = MagicMock(), MagicMock()
        ex = SopExecutor(vision=vision, control=control, sop_steps_path=steps_path)
        steps = ex.get_steps()
        assert len(steps) == 12

    def test_empty_steps_list(self, tmp_path: Path) -> None:
        data = {"version": "1.0", "steps": []}
        ex = _make_executor(tmp_path, data)
        steps = ex.get_steps()
        assert steps == []

    def test_steps_without_enabled_field_are_included(self, tmp_path: Path) -> None:
        data = {
            "version": "1.0",
            "steps": [
                {"id": "login", "name": "Login", "type": "click"},  # no enabled key
            ],
        }
        ex = _make_executor(tmp_path, data)
        steps = ex.get_steps()
        assert len(steps) == 1

    def test_step_fields_preserved(self, tmp_path: Path) -> None:
        data = {
            "version": "1.0",
            "steps": [
                {
                    "id": "mold_roi",
                    "name": "Mold ROI",
                    "type": "drag",
                    "start": [100, 200],
                    "end": [800, 350],
                    "enabled": True,
                }
            ],
        }
        ex = _make_executor(tmp_path, data)
        step = ex.get_steps()[0]
        assert step["start"] == [100, 200]
        assert step["end"] == [800, 350]
        assert step["type"] == "drag"


# ---------------------------------------------------------------------------
# TestRunStep — 개별 단계 실행
# ---------------------------------------------------------------------------


class TestRunStep:
    def _make_ex(self, tmp_path: Path) -> SopExecutor:
        return _make_executor_no_file(tmp_path)

    def test_click_step_success(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        click_result = MagicMock()
        click_result.success = True
        click_result.coords = (100, 200)
        click_result.duration = 0.05
        click_result.error = None
        ex.control.click_target.return_value = click_result

        ok, msg = ex.run_step(
            {"id": "login", "name": "Login", "type": "click", "target": "login_button"}
        )
        assert ok is True
        assert "login_button" in msg

    def test_click_step_failure(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        click_result = MagicMock()
        click_result.success = False
        click_result.error = "not found"
        click_result.coords = None
        click_result.duration = 0.0
        ex.control.click_target.return_value = click_result

        ok, msg = ex.run_step(
            {"id": "login", "name": "Login", "type": "click", "target": "login_button"}
        )
        assert ok is False
        assert "not found" in msg

    def test_drag_step_success(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        drag_result = MagicMock()
        drag_result.success = True
        drag_result.duration = 0.4
        drag_result.error = None
        ex.control.drag_roi.return_value = drag_result

        ok, msg = ex.run_step(
            {
                "id": "mold_left_roi",
                "name": "Mold ROI",
                "type": "drag",
                "start": [100, 200],
                "end": [800, 350],
            }
        )
        assert ok is True
        assert "dragged" in msg

    def test_drag_step_failure(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        drag_result = MagicMock()
        drag_result.success = False
        drag_result.error = "timeout"
        ex.control.drag_roi.return_value = drag_result

        ok, msg = ex.run_step(
            {"id": "roi", "name": "ROI", "type": "drag", "start": [0, 0], "end": [1, 1]}
        )
        assert ok is False
        assert "timeout" in msg

    def test_validate_pins_success(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        # pin_count_min=40, pin_count_max=40 (from default config in _make_executor_no_file)
        ex._config = {"pin_count_min": 40, "pin_count_max": 40}
        ex.vision.capture_screen.return_value = MagicMock()
        ex.vision.validate_pin_count.return_value = {"valid": True, "count": 40}

        ok, msg = ex.run_step(
            {"id": "in_pin_up", "name": "Pin Up", "type": "validate_pins"}
        )
        assert ok is True
        assert "40" in msg

    def test_validate_pins_failure_low_count(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        ex._config = {"pin_count_min": 40, "pin_count_max": 40}
        ex.vision.capture_screen.return_value = MagicMock()
        ex.vision.validate_pin_count.return_value = {"valid": False, "count": 18}

        ok, msg = ex.run_step(
            {"id": "in_pin_up", "name": "Pin Up", "type": "validate_pins"}
        )
        assert ok is False

    def test_click_sequence_all_success(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        click_result = MagicMock()
        click_result.success = True
        click_result.coords = (10, 20)
        click_result.duration = 0.1
        click_result.error = None
        ex.control.click_target.return_value = click_result

        ok, msg = ex.run_step(
            {
                "id": "apply_and_open",
                "name": "Apply & Open",
                "type": "click_sequence",
                "targets": ["apply_button", "open_icon"],
            }
        )
        assert ok is True
        assert ex.control.click_target.call_count == 2

    def test_click_sequence_partial_failure(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)

        success_result = MagicMock(
            success=True, coords=(1, 2), duration=0.1, error=None
        )
        fail_result = MagicMock(
            success=False, coords=None, duration=0.0, error="not found"
        )
        ex.control.click_target.side_effect = [success_result, fail_result]

        ok, msg = ex.run_step(
            {
                "id": "apply_and_open",
                "name": "Apply & Open",
                "type": "click_sequence",
                "targets": ["apply_button", "open_icon"],
            }
        )
        assert ok is False

    def test_unknown_step_type_returns_failure(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        ok, msg = ex.run_step({"id": "weird", "name": "Weird", "type": "teleport"})
        assert ok is False
        assert "Unknown" in msg or "teleport" in msg

    def test_step_without_target_uses_id(self, tmp_path: Path) -> None:
        ex = self._make_ex(tmp_path)
        click_result = MagicMock(success=True, coords=None, duration=0.05, error=None)
        ex.control.click_target.return_value = click_result

        # No "target" key — should fall back to step id
        ok, _ = ex.run_step({"id": "my_btn", "name": "My Btn", "type": "click"})
        assert ok is True


# ---------------------------------------------------------------------------
# sop_steps.json 파일 자체 스키마 검증
# ---------------------------------------------------------------------------


class TestSopStepsJsonSchema:
    """assets/sop_steps.json 파일의 구조가 올바른지 검증."""

    _path = Path("assets/sop_steps.json")

    def test_file_exists(self) -> None:
        assert self._path.exists(), "assets/sop_steps.json가 존재해야 합니다"

    def test_valid_json(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_has_version_and_steps(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        assert "version" in data
        assert "steps" in data
        assert isinstance(data["steps"], list)

    def test_has_12_steps(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        assert len(data["steps"]) == 12

    def test_each_step_has_required_fields(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert "id" in step, f"step missing 'id': {step}"
            assert "name" in step, f"step missing 'name': {step}"
            assert "type" in step, f"step missing 'type': {step}"
            assert "enabled" in step, f"step missing 'enabled': {step}"

    def test_all_steps_enabled_by_default(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert (
                step.get("enabled") is True
            ), f"step {step['id']} not enabled by default"

    def test_step_types_valid(self) -> None:
        # v3.8: auth_sequence / input_text / mold_setup added
        valid_types = {
            "click",
            "drag",
            "validate_pins",
            "click_sequence",
            "auth_sequence",
            "input_text",
            "mold_setup",
        }
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            assert (
                step["type"] in valid_types
            ), f"step {step['id']} has invalid type: {step['type']!r}"

    def test_drag_steps_have_start_end(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            if step["type"] == "drag":
                assert "start" in step, f"drag step {step['id']} missing 'start'"
                assert "end" in step, f"drag step {step['id']} missing 'end'"
                assert len(step["start"]) == 2
                assert len(step["end"]) == 2

    def test_click_sequence_steps_have_targets(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            if step["type"] == "click_sequence":
                assert (
                    "targets" in step
                ), f"click_sequence step {step['id']} missing 'targets'"
                assert isinstance(step["targets"], list)
                assert len(step["targets"]) >= 2

    def test_unique_step_ids(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        ids = [s["id"] for s in data["steps"]]
        assert len(ids) == len(set(ids)), "Duplicate step IDs found"
