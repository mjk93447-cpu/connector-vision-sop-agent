from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_from_manifest(manifest_url: str, output_file: Path) -> dict[str, Any]:
    manifest_path = output_file.parent / "gguf_download_manifest.json"
    _download(manifest_url, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    direct_url = str(manifest.get("url", "")).strip()
    if direct_url:
        _download(direct_url, output_file)
    else:
        parts = manifest.get("parts", [])
        if not parts:
            raise ValueError("GGUF download manifest must contain either 'url' or 'parts'.")
        with output_file.open("wb") as out_handle:
            for index, part in enumerate(parts):
                part_url = str(part.get("url", "")).strip()
                if not part_url:
                    raise ValueError(f"Manifest part #{index} is missing a url.")
                temp_part = output_file.parent / f"part-{index:03d}.bin"
                _download(part_url, temp_part)
                expected = str(part.get("sha256", "")).strip().lower()
                if expected:
                    actual = _sha256(temp_part)
                    if actual != expected:
                        raise ValueError(
                            f"Part #{index} sha256 mismatch: expected {expected}, got {actual}"
                        )
                with temp_part.open("rb") as in_handle:
                    shutil.copyfileobj(in_handle, out_handle, length=8 * 1024 * 1024)
                temp_part.unlink(missing_ok=True)

    expected_final = str(manifest.get("sha256", "")).strip().lower()
    if expected_final:
        actual_final = _sha256(output_file)
        if actual_final != expected_final:
            raise ValueError(
                f"Combined GGUF sha256 mismatch: expected {expected_final}, got {actual_final}"
            )

    return manifest


def fetch_remote_gguf(
    *,
    output_file: Path,
    gguf_url: str = "",
    gguf_manifest_url: str = "",
) -> dict[str, Any]:
    if bool(gguf_url) == bool(gguf_manifest_url):
        raise ValueError("Provide exactly one of gguf_url or gguf_manifest_url.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    if gguf_url:
        _download(gguf_url, output_file)
        return {"mode": "direct-url", "url": gguf_url, "output": str(output_file)}

    manifest = _download_from_manifest(gguf_manifest_url, output_file)
    return {
        "mode": "manifest-url",
        "manifest_url": gguf_manifest_url,
        "output": str(output_file),
        "manifest": manifest,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch a GGUF from a direct URL or a split-part manifest.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--gguf-url", default="")
    parser.add_argument("--gguf-manifest-url", default="")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    result = fetch_remote_gguf(
        output_file=Path(args.output),
        gguf_url=args.gguf_url,
        gguf_manifest_url=args.gguf_manifest_url,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
