from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

MAX_ASSET_BYTES = 2_000_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _asset_name(asset_prefix: str, relative_path: Path) -> str:
    safe = relative_path.as_posix().replace("/", "__")
    return f"{asset_prefix}__{safe}"


def publish_release_bundle(
    *,
    source_dir: Path,
    repo: str,
    tag: str,
    title: str,
    notes: str,
    asset_prefix: str,
    max_asset_bytes: int = MAX_ASSET_BYTES,
) -> dict:
    if "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ:
        raise RuntimeError("GH_TOKEN or GITHUB_TOKEN must be set for gh release commands.")
    if not source_dir.exists():
        raise FileNotFoundError(f"Bundle source directory not found: {source_dir}")
    if max_asset_bytes <= 0:
        raise ValueError("max_asset_bytes must be positive.")

    source_files = sorted(candidate for candidate in source_dir.rglob("*") if candidate.is_file())
    for path in source_files:
        rel = path.relative_to(source_dir)
        size = path.stat().st_size
        if size > max_asset_bytes:
            raise ValueError(
                f"Bundle file exceeds max asset size of {max_asset_bytes} bytes: {rel.as_posix()}"
            )

    _ensure_release(repo=repo, tag=tag, title=title, notes=notes)
    release_base = f"https://github.com/{repo}/releases/download/{tag}"
    files: list[dict[str, object]] = []

    for path in source_files:
        rel = path.relative_to(source_dir)
        size = path.stat().st_size
        asset_name = _asset_name(asset_prefix, rel)
        with tempfile.TemporaryDirectory(prefix="release-asset-") as asset_dir:
            upload_path = Path(asset_dir) / asset_name
            shutil.copy2(path, upload_path)
            _upload_asset(repo, tag, upload_path)
        files.append(
            {
                "relative_path": rel.as_posix(),
                "asset_name": asset_name,
                "size_bytes": size,
                "sha256": _sha256(path),
                "url": f"{release_base}/{asset_name}",
            }
        )

    manifest = {
        "schema_version": "1",
        "bundle_type": "release-directory-manifest",
        "release_tag": tag,
        "asset_prefix": asset_prefix,
        "max_asset_bytes": max_asset_bytes,
        "files": files,
    }

    with tempfile.TemporaryDirectory(prefix="release-bundle-") as temp_dir:
        manifest_path = Path(temp_dir) / f"{asset_prefix}__release_bundle_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _upload_asset(repo, tag, manifest_path)

    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish a directory bundle to GitHub Release assets.")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--asset-prefix", required=True)
    parser.add_argument("--max-asset-bytes", type=int, default=MAX_ASSET_BYTES)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    manifest = publish_release_bundle(
        source_dir=Path(args.source_dir),
        repo=args.repo,
        tag=args.tag,
        title=args.title,
        notes=args.notes,
        asset_prefix=args.asset_prefix,
        max_asset_bytes=int(args.max_asset_bytes),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
