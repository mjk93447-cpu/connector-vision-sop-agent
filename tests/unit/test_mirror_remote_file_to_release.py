from __future__ import annotations

import json
from pathlib import Path


def test_mirror_workflow_exists_and_uses_release_upload() -> None:
    content = Path(".github/workflows/mirror-public-turboquant-to-release.yml").read_text(
        encoding="utf-8"
    )
    assert "mirror_remote_file_to_release.py" in content
    assert "contents: write" in content
    assert "GITHUB_TOKEN" in content


def test_mirror_script_creates_release_manifests() -> None:
    content = Path("scripts/mirror_remote_file_to_release.py").read_text(encoding="utf-8")
    assert "gguf_download_manifest.public.json" in content
    assert "quantization_manifest.json" in content
    assert '"release", "upload"' in content
