from __future__ import annotations

from pathlib import Path


def test_llm_artifact_workflow_uses_chunked_ollama_packaging() -> None:
    content = Path(".github/workflows/build-llm-artifact.yml").read_text(encoding="utf-8")
    assert "scripts/package_ollama_models.py stage" in content
    assert "2147483648" in content
    assert "actions/upload-artifact@v4" in content
