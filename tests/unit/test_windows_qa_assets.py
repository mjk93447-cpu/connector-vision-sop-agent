from __future__ import annotations

import json
from pathlib import Path


_ALLOWED_STEP_TYPES = {
    "click",
    "drag",
    "validate_pins",
    "click_sequence",
    "type_text",
    "press_key",
    "wait_ms",
    "auth_sequence",
}


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_windows_settings_smoke_uses_supported_step_types() -> None:
    scenario = _load("qa/scenarios/windows_settings_smoke.json")
    assert scenario["steps"]
    assert {step["type"] for step in scenario["steps"]}.issubset(_ALLOWED_STEP_TYPES)


def test_windows_settings_colors_toggle_uses_supported_step_types() -> None:
    scenario = _load("qa/scenarios/windows_settings_colors_toggle.json")
    assert scenario["steps"]
    assert {step["type"] for step in scenario["steps"]}.issubset(_ALLOWED_STEP_TYPES)


def test_windows_settings_navigation_deep_is_long_enough_for_complex_run() -> None:
    scenario = _load("qa/scenarios/windows_settings_navigation_deep.json")
    enabled_steps = [step for step in scenario["steps"] if step.get("enabled", True)]
    assert len(enabled_steps) >= 10


def test_gui_smoke_script_checks_for_main_window() -> None:
    content = Path("scripts/run_gui_bundle_smoke.ps1").read_text(encoding="utf-8")
    assert "MainWindowHandle" in content
    assert "gui_window_detected" in content


def test_windows_scenario_qa_script_writes_json_report() -> None:
    content = Path("scripts/run_windows_scenario_qa.py").read_text(encoding="utf-8")
    assert "ScenarioRunSummary" in content
    assert "artifacts/qa" in content


def test_windows_scenario_qa_script_passes_sop_steps_to_control_engine() -> None:
    content = Path("scripts/run_windows_scenario_qa.py").read_text(encoding="utf-8")
    assert "sop_steps=steps" in content


def test_windows_settings_navigation_steps_define_roi_for_sidebar_targets() -> None:
    for rel_path in (
        "qa/scenarios/windows_settings_smoke.json",
        "qa/scenarios/windows_settings_colors_toggle.json",
        "qa/scenarios/windows_settings_navigation_deep.json",
    ):
        scenario = _load(rel_path)
        nav_steps = [
            step for step in scenario["steps"] if step.get("target", "").endswith("_nav")
        ]
        assert nav_steps
        assert all("roi" in step for step in nav_steps)
