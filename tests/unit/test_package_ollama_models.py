from __future__ import annotations

import json
from pathlib import Path

from scripts.package_ollama_models import (
    MANIFEST_NAME,
    join_file_parts,
    restore_ollama_models,
    split_file_to_parts,
    stage_ollama_models,
    zip_directory,
)


def test_stage_and_restore_chunked_ollama_models(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "blobs").mkdir(parents=True, exist_ok=True)
    (source / "manifests/registry.ollama.ai/library/demo").mkdir(parents=True, exist_ok=True)

    big_blob = source / "blobs/sha256-big"
    small_blob = source / "blobs/sha256-small"
    manifest_file = source / "manifests/registry.ollama.ai/library/demo/latest"

    big_blob.write_bytes(b"ABCDEFGHIJ")
    small_blob.write_bytes(b"ok")
    manifest_file.write_text("manifest", encoding="utf-8")

    staged = tmp_path / "staged"
    manifest = stage_ollama_models(source, staged, chunk_size=9)

    assert (staged / MANIFEST_NAME).exists()
    assert (staged / "blobs/sha256-small").exists()
    assert not (staged / "blobs/sha256-big").exists()
    assert (staged / "blobs/sha256-big.part000").exists()
    assert (staged / "blobs/sha256-big.part001").exists()
    assert len(manifest["split_files"]) == 1

    restored = restore_ollama_models(staged, remove_parts=True)

    assert "blobs/sha256-big" in restored["restored_files"]
    assert (staged / "blobs/sha256-big").read_bytes() == b"ABCDEFGHIJ"
    assert not (staged / "blobs/sha256-big.part000").exists()


def test_zip_directory_creates_zip64_archive(tmp_path: Path) -> None:
    source = tmp_path / "payload"
    source.mkdir()
    (source / "a.txt").write_text("hello", encoding="utf-8")
    (source / "nested").mkdir()
    (source / "nested/b.txt").write_text("world", encoding="utf-8")

    zip_path = tmp_path / "payload.zip"
    out = zip_directory(source, zip_path)

    assert out.exists()
    assert out == zip_path


def test_split_and_join_large_zip_file(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"ABCDEFGHIJ")

    parts = split_file_to_parts(archive, chunk_size=4, delete_source=True)

    assert [part.name for part in parts] == ["bundle.zip.001", "bundle.zip.002", "bundle.zip.003"]
    assert not archive.exists()

    restored = join_file_parts(parts[0], delete_parts=True)

    assert restored.read_bytes() == b"ABCDEFGHIJ"
    assert not parts[0].exists()
