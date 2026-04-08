from __future__ import annotations

from pathlib import Path


def test_start_agent_launcher_tolerates_missing_ollama() -> None:
    content = Path("assets/launchers/start_agent.bat").read_text(encoding="utf-8")
    assert "ollama.exe not found" in content
    assert "Continuing with GUI smoke / non-LLM mode" in content
    assert "LLM verification skipped" in content
