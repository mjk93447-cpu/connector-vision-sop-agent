from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import requests


def _ensure_release(repo: str, tag: str, title: str, notes: str) -> None:
    view = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        check=False,
        capture_output=True,
        text=True,
    )
    if view.returncode == 0:
        return
    subprocess.run(
        ["gh", "release", "create", tag, "--repo", repo, "--title", title, "--notes", notes],
        check=True,
    )


def _upload_asset(repo: str, tag: str, path: Path) -> None:
    subprocess.run(
        ["gh", "release", "upload", tag, str(path), "--repo", repo, "--clobber"],
        check=True,
    )


def _head(remote_url: str) -> tuple[int, bool]:
    resp = requests.head(remote_url, allow_redirects=True, timeout=120)
    resp.raise_for_status()
    size = int(resp.headers.get("content-length", "0"))
    accept_ranges = str(resp.headers.get("accept-ranges", "")).lower() == "bytes"
    if size <= 0:
        raise ValueError("Remote file did not provide a content-length.")
    return size, accept_ranges


def mirror_remote_file_to_release(
    *,
    remote_url: str,
    repo: str,
    tag: str,
    release_title: str,
    remote_filename: str,
    chunk_size_bytes: int,
    model_name: str,
    base_model: str,
    reference_url: str,
    quantization_notes: str,
    quantization_tool: str,
) -> dict[str, Any]:
    if "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ:
        raise RuntimeError("GH_TOKEN or GITHUB_TOKEN must be set for gh release commands.")

    total_size, accept_ranges = _head(remote_url)
    if not accept_ranges:
        raise ValueError("Remote file does not support Range requests; cannot mirror in split parts.")

    _ensure_release(
        repo=repo,
        tag=tag,
        title=release_title,
        notes=f"Mirrored TurboQuant artifact for {model_name}",
    )

    release_base = f"https://github.com/{repo}/releases/download/{tag}"
    parts: list[dict[str, Any]] = []
    whole_digest = hashlib.sha256()

    with tempfile.TemporaryDirectory(prefix="mirror-gguf-") as temp_dir:
        temp_root = Path(temp_dir)
        offset = 0
        index = 1
        while offset < total_size:
            end = min(offset + chunk_size_bytes - 1, total_size - 1)
            part_name = f"{remote_filename}.{index:03d}"
            part_path = temp_root / part_name
            resp = requests.get(
                remote_url,
                headers={"Range": f"bytes={offset}-{end}"},
                stream=True,
                timeout=(30, 3600),
            )
            resp.raise_for_status()
            part_digest = hashlib.sha256()
            with part_path.open("wb") as handle:
                for chunk in resp.iter_content(8 * 1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    part_digest.update(chunk)
                    whole_digest.update(chunk)

            _upload_asset(repo, tag, part_path)
            parts.append(
                {
                    "name": part_name,
                    "url": f"{release_base}/{part_name}",
                    "sha256": part_digest.hexdigest(),
                    "size_bytes": part_path.stat().st_size,
                    "range_start": offset,
                    "range_end": end,
                }
            )
            part_path.unlink(missing_ok=True)
            offset = end + 1
            index += 1

        download_manifest = {
            "schema_version": "1",
            "merge_strategy": "concat",
            "source_url": remote_url,
            "filename": remote_filename,
            "size_bytes": total_size,
            "sha256": whole_digest.hexdigest(),
            "parts": parts,
        }
        quant_manifest = {
            "schema_version": "1",
            "model_name": model_name,
            "base_model": base_model,
            "tool": quantization_tool,
            "quantization_origin": quantization_tool,
            "reference_url": reference_url,
            "notes": quantization_notes,
            "source_url": remote_url,
            "mirrored_by": "mirror_remote_file_to_release.py",
            "expected_family": model_name.split(":", 1)[0].strip().lower(),
            "expected_quantization_level": (
                model_name.rsplit("-", 1)[-1][:1].upper()
                + model_name.rsplit("-", 1)[-1][1:]
            ),
            "gguf_file": remote_filename,
            "gguf_size_bytes": total_size,
            "gguf_sha256": whole_digest.hexdigest(),
        }

        download_manifest_path = temp_root / "gguf_download_manifest.public.json"
        quant_manifest_path = temp_root / "quantization_manifest.json"
        download_manifest_path.write_text(
            json.dumps(download_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        quant_manifest_path.write_text(
            json.dumps(quant_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _upload_asset(repo, tag, download_manifest_path)
        _upload_asset(repo, tag, quant_manifest_path)

    return {
        "download_manifest_url": f"{release_base}/gguf_download_manifest.public.json",
        "quantization_manifest_url": f"{release_base}/quantization_manifest.json",
        "parts": len(parts),
        "size_bytes": total_size,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mirror a large public GGUF to GitHub Release assets in split parts.")
    parser.add_argument("--remote-url", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--release-title", required=True)
    parser.add_argument("--remote-filename", required=True)
    parser.add_argument("--chunk-size-bytes", type=int, default=1900000000)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--reference-url", required=True)
    parser.add_argument("--quantization-notes", default="")
    parser.add_argument("--quantization-tool", default="turboquant")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    result = mirror_remote_file_to_release(
        remote_url=args.remote_url,
        repo=args.repo,
        tag=args.tag,
        release_title=args.release_title,
        remote_filename=args.remote_filename,
        chunk_size_bytes=args.chunk_size_bytes,
        model_name=args.model_name,
        base_model=args.base_model,
        reference_url=args.reference_url,
        quantization_notes=args.quantization_notes,
        quantization_tool=args.quantization_tool,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
