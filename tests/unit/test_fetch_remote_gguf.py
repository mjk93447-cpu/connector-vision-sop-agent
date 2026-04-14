from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.fetch_remote_gguf import fetch_remote_gguf


def _url(path: Path) -> str:
    return path.resolve().as_uri()


def test_fetch_remote_gguf_from_direct_url(tmp_path: Path) -> None:
    source = tmp_path / "model.gguf"
    source.write_bytes(b"hello")
    output = tmp_path / "out.gguf"
    result = fetch_remote_gguf(output_file=output, gguf_url=_url(source))
    assert output.read_bytes() == b"hello"
    assert result["mode"] == "direct-url"
    assert result["size_bytes"] == 5
    assert result["output_sha256"] == hashlib.sha256(b"hello").hexdigest()


def test_fetch_remote_gguf_from_split_manifest(tmp_path: Path) -> None:
    part1 = tmp_path / "part1.bin"
    part2 = tmp_path / "part2.bin"
    part1.write_bytes(b"abc")
    part2.write_bytes(b"def")
    combined = b"abcdef"
    manifest = {
        "schema_version": "1",
        "merge_strategy": "concat",
        "sha256": hashlib.sha256(combined).hexdigest(),
        "parts": [
            {"url": _url(part1), "sha256": hashlib.sha256(b"abc").hexdigest()},
            {"url": _url(part2), "sha256": hashlib.sha256(b"def").hexdigest()},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "out.gguf"
    result = fetch_remote_gguf(output_file=output, gguf_manifest_url=_url(manifest_path))
    assert output.read_bytes() == combined
    assert result["mode"] == "manifest-url"
    assert result["size_bytes"] == len(combined)
    assert result["output_sha256"] == hashlib.sha256(combined).hexdigest()
