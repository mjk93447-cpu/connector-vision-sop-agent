from __future__ import annotations

from pathlib import Path


def test_build_workflow_emits_cpu_and_gpu_full_packs() -> None:
    content = Path(".github/workflows/build.yml").read_text(encoding="utf-8")

    assert "connector-agent-app-cpu" in content
    assert "connector-agent-app-gpu" in content
    assert "connector_agent_app_cpu" in content
    assert "connector_agent_app_gpu" in content
    assert "runtime_flavor.txt" in content
    assert "dist\\connector_vision_agent.exe" in content
    assert 'Copy-Item "dist\\connector_vision_agent.exe"' in content

    assert "connector-agent-app-core" not in content
    assert "connector-agent-runtime-cpu" not in content
    assert "connector-agent-runtime-gpu" not in content
    assert "dist\\connector_vision_agent\\connector_vision_agent.exe" not in content
    assert "https://download.pytorch.org/whl/cpu" in content
    assert "https://download.pytorch.org/whl/cu121" in content
    assert "CONNECTOR_AGENT_RUNTIME_FLAVOR=${{ matrix.runtime_flavor }}" in content
    assert "Install Ollama runtime" in content
    assert 'Copy-Item "assets\\launchers\\restore_ollama_stage.ps1"' in content
    assert 'Copy-Item $env:OLLAMA_EXE "$pkg\\ollama.exe" -Force' in content
