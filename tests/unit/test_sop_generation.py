from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock

from src.sop_generation import SOPGenerationService


def test_generate_from_txt_produces_canonical_shape(tmp_path: Path) -> None:
    src = tmp_path / "sample.txt"
    src.write_text("Click LOGIN\nWait 500 ms\nPress Enter", encoding="utf-8")

    service = SOPGenerationService()
    canonical = service.generate_from_document(src)

    assert set(canonical.keys()) >= {
        "metadata",
        "source_document",
        "workflow",
        "questions_asked",
        "answers",
        "automation_profile",
        "portability",
        "compile_result",
    }
    assert canonical["source_document"]["source_type"] == "txt"
    assert canonical["workflow"]["steps"], "workflow steps should not be empty"


def test_finalize_requires_required_answers(tmp_path: Path) -> None:
    src = tmp_path / "sample.txt"
    src.write_text("Click LOGIN", encoding="utf-8")
    service = SOPGenerationService()
    canonical = service.generate_from_document(src)

    try:
        service.finalize_canonical_sop(canonical)
    except ValueError as exc:
        assert "Required SOP generation questions are unanswered" in str(exc)
    else:
        raise AssertionError("finalize_canonical_sop should block when required answers are missing")


def test_package_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "sample.txt"
    src.write_text("Click LOGIN", encoding="utf-8")
    service = SOPGenerationService()
    canonical = service.generate_from_document(src)
    answered = service.answer_generation_questions(canonical, {"workflow_goal": "ui_automation"})
    finalized = service.finalize_canonical_sop(answered)
    compiled = service.compile_to_runtime_json(finalized, service.build_runtime_profile())

    package_path = tmp_path / "bundle.zip"
    service.save_sop_package(finalized, compiled, package_path)
    imported = service.import_sop_package(package_path)

    assert imported["manifest"]["has_compiled_runtime"] is True
    assert imported["canonical"]["metadata"]["title"]
    assert imported["compiled_runtime"]["steps"]


def test_main_window_runtime_apply_source_refreshes_editor_and_runtime_map() -> None:
    import src.gui.main_window as mod

    source = inspect.getsource(mod.MainWindow.apply_generated_runtime)
    assert "reload_sop_steps" in source
    assert "set_runtime_artifact" in source


def test_control_engine_set_sop_steps_refreshes_button_text_map() -> None:
    from src.control_engine import ControlEngine

    vision = MagicMock()
    ctrl = ControlEngine(vision_agent=vision, sop_steps=[])
    ctrl.set_sop_steps(
        [
            {"id": "login_step", "target": "login_button", "button_text": "LOGIN"},
            {"id": "save_step", "target": "save_button", "button_text": "SAVE"},
        ]
    )
    assert ctrl._button_text_map["login_button"] == "LOGIN"
    assert ctrl._button_text_map["save_step"] == "SAVE"


def test_sop_editor_supports_runtime_specific_fields_via_source() -> None:
    import src.gui.panels.sop_editor_panel as mod

    source = inspect.getsource(mod._StepEditDialog.get_step)
    assert "click_sequence" in source
    assert "auth_sequence" in source
    assert "input_text" in source
    assert "mold_setup" in source


def test_generation_readiness_requires_gemma_turboquant_runtime() -> None:
    service = SOPGenerationService()
    try:
        service.generation_readiness()
    except RuntimeError as exc:
        assert "TurboQuant" in str(exc)
        assert "Gemma" in str(exc)
    else:
        raise AssertionError("generation_readiness should require Gemma + TurboQuant runtime")
