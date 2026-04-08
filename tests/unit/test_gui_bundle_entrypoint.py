from __future__ import annotations

from pathlib import Path


def test_build_exe_spec_targets_gui_entrypoint() -> None:
    content = Path("build_exe.spec").read_text(encoding="utf-8")
    assert "src/gui_app.py" in content
    assert "console=False" in content


def test_packaged_launcher_marks_gui_runtime() -> None:
    content = Path("assets/launchers/start_agent.bat").read_text(encoding="utf-8")
    assert "Launching SOP Agent (GUI mode)" in content
    assert "connector_vision_agent.exe" in content


def test_active_paths_mark_pretrain_as_archived() -> None:
    content = Path("docs/ACTIVE_PATHS.md").read_text(encoding="utf-8")
    assert "src/gui_app.py" in content
    assert "Archived pretrain paths" in content
    assert "scripts/run_pretrain_local.py" in content
