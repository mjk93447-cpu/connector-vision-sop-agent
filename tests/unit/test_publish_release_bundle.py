from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.publish_release_bundle import MAX_ASSET_BYTES, publish_release_bundle


def test_publish_release_bundle_rejects_oversized_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bundle"
    source.mkdir()
    (source / "huge.bin").write_bytes(b"abc")
    monkeypatch.setenv("GH_TOKEN", "test-token")

    with pytest.raises(ValueError, match="exceeds max asset size"):
        publish_release_bundle(
            source_dir=source,
            repo="owner/name",
            tag="demo",
            title="Demo",
            notes="",
            asset_prefix="demo",
            max_asset_bytes=2,
        )


def test_publish_release_bundle_builds_flattened_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bundle"
    nested = source / "llm_stage"
    nested.mkdir(parents=True)
    (nested / "blob.part000").write_bytes(b"hello")
    (source / "verification").mkdir()
    (source / "verification" / "report.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GH_TOKEN", "test-token")

    uploads: list[str] = []

    def fake_run(cmd: list[str], check: bool = False, capture_output: bool = False, text: bool = False):
        if cmd[:3] == ["gh", "release", "view"]:
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()
        if cmd[:3] == ["gh", "release", "upload"]:
            uploads.append(Path(cmd[4]).name)
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("scripts.publish_release_bundle.subprocess.run", fake_run)

    manifest = publish_release_bundle(
        source_dir=source,
        repo="owner/name",
        tag="demo",
        title="Demo",
        notes="",
        asset_prefix="demo-bundle",
        max_asset_bytes=MAX_ASSET_BYTES,
    )

    assert {item["relative_path"] for item in manifest["files"]} == {
        "llm_stage/blob.part000",
        "verification/report.json",
    }
    assert any(name.endswith("release_bundle_manifest.json") for name in uploads)
    assert "demo-bundle__llm_stage__blob.part000" in uploads
    assert "demo-bundle__verification__report.json" in uploads
