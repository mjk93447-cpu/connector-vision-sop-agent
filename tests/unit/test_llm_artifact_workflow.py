from __future__ import annotations

from pathlib import Path


def test_llm_artifact_workflow_uses_chunked_ollama_packaging() -> None:
    content = Path(".github/workflows/build-llm-artifact.yml").read_text(encoding="utf-8")
    assert "scripts/package_ollama_models.py stage" in content
    assert "2147483648" in content
    assert "actions/upload-artifact@v4" in content
    assert "quantization_manifest_url" in content
    assert "This workflow only accepts TurboQuant GGUF imports" in content


def test_verify_workflow_downloads_prepare_artifact_and_runs_metadata_check() -> None:
    content = Path(".github/workflows/verify-llm-artifact.yml").read_text(
        encoding="utf-8"
    )
    assert "actions/download-artifact@v4" in content
    assert "scripts/verify_ollama_artifact.py" in content
    assert "package_ollama_models.py restore" in content


def test_publish_workflow_consumes_verification_report_and_republishes_bundle() -> None:
    content = Path(".github/workflows/publish-llm-artifact.yml").read_text(
        encoding="utf-8"
    )
    assert "verification_report.json" in content
    assert "connector-agent-llm-verified-cache" in content
    assert "published_bundle" in content
