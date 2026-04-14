from __future__ import annotations

from pathlib import Path


def test_start_agent_launcher_tolerates_missing_ollama() -> None:
    content = Path("assets/launchers/start_agent.bat").read_text(encoding="utf-8")
    assert "ollama.exe not found" in content
    assert "Continuing with GUI smoke / non-LLM mode" in content
    assert "LLM verification skipped" in content
    assert "llm_stage" in content
    assert "restore_ollama_stage.ps1" in content


def test_restore_launcher_script_exists() -> None:
    content = Path("assets/launchers/restore_ollama_stage.ps1").read_text(encoding="utf-8")
    assert "ollama_split_manifest.json" in content
    assert "split_files" in content
