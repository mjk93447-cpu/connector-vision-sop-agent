from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_CHUNK_BYTES = 2_000_000_000
MANIFEST_NAME = "ollama_split_manifest.json"


def _chunk_name(path: Path, index: int) -> str:
    return f"{path.name}.part{index:03d}"


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _split_file(source: Path, destination_dir: Path, chunk_size: int) -> list[str]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    with source.open("rb") as handle:
        index = 0
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            part_name = _chunk_name(source, index)
            (destination_dir / part_name).write_bytes(chunk)
            parts.append(part_name)
            index += 1
    return parts


def split_file_to_parts(
    source: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_BYTES,
    delete_source: bool = False,
) -> list[Path]:
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    if source.stat().st_size <= chunk_size:
        return [source]

    parts: list[Path] = []
    with source.open("rb") as handle:
        index = 1
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            part_path = source.with_name(f"{source.name}.{index:03d}")
            part_path.write_bytes(chunk)
            parts.append(part_path)
            index += 1
    if delete_source:
        source.unlink()
    return parts


def join_file_parts(
    first_part: Path,
    *,
    output_file: Path | None = None,
    delete_parts: bool = False,
) -> Path:
    if not first_part.exists():
        raise FileNotFoundError(f"Split archive part not found: {first_part}")
    suffix = first_part.suffix
    if not suffix.startswith(".") or not suffix[1:].isdigit():
        raise ValueError("Expected the first part filename to end with a numeric chunk suffix like .001")

    stem_name = first_part.name[: -len(suffix)]
    if output_file is None:
        output_file = first_part.with_name(stem_name)

    parts = sorted(first_part.parent.glob(stem_name + ".[0-9][0-9][0-9]"))
    with output_file.open("wb") as out_handle:
        for part_path in parts:
            with part_path.open("rb") as in_handle:
                shutil.copyfileobj(in_handle, out_handle, length=8 * 1024 * 1024)
            if delete_parts:
                part_path.unlink(missing_ok=True)
    return output_file


def stage_ollama_models(
    source_root: Path,
    output_root: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_BYTES,
) -> dict[str, Any]:
    if not source_root.exists():
        raise FileNotFoundError(f"Ollama models root not found: {source_root}")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    split_files: list[dict[str, Any]] = []
    copied_files: list[str] = []

    for source_file in sorted(path for path in source_root.rglob("*") if path.is_file()):
        rel = source_file.relative_to(source_root)
        target = output_root / rel
        size = source_file.stat().st_size
        if size > chunk_size:
            parts = _split_file(source_file, target.parent, chunk_size)
            split_files.append(
                {
                    "path": rel.as_posix(),
                    "size": size,
                    "chunk_size": chunk_size,
                    "parts": [str((rel.parent / part).as_posix()) for part in parts],
                }
            )
        else:
            _copy_file(source_file, target)
            copied_files.append(rel.as_posix())

    manifest = {
        "format": "ollama-chunked-stage-v1",
        "source_root": str(source_root),
        "chunk_size": chunk_size,
        "copied_files": copied_files,
        "split_files": split_files,
    }
    (output_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def restore_ollama_models(
    staged_root: Path,
    *,
    remove_parts: bool = False,
) -> dict[str, Any]:
    manifest_path = staged_root / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing split manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored: list[str] = []
    for item in manifest.get("split_files", []):
        rel_path = Path(item["path"])
        target = staged_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out_handle:
            for part_rel in item.get("parts", []):
                part_path = staged_root / Path(part_rel)
                with part_path.open("rb") as in_handle:
                    shutil.copyfileobj(in_handle, out_handle, length=8 * 1024 * 1024)
                if remove_parts:
                    part_path.unlink(missing_ok=True)
        restored.append(rel_path.as_posix())
    return {"restored_files": restored, "manifest": manifest}


def zip_directory(source_root: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in sorted(source_root.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(source_root))
    return zip_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage or restore chunked Ollama model caches.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_parser = subparsers.add_parser("stage", help="Copy and chunk an Ollama models directory.")
    stage_parser.add_argument("--source", required=True)
    stage_parser.add_argument("--output", required=True)
    stage_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_BYTES)

    restore_parser = subparsers.add_parser("restore", help="Restore chunked model files from a staged folder.")
    restore_parser.add_argument("--root", required=True)
    restore_parser.add_argument("--remove-parts", action="store_true")

    zip_parser = subparsers.add_parser("zipdir", help="Zip a directory with ZIP64 support.")
    zip_parser.add_argument("--source", required=True)
    zip_parser.add_argument("--output", required=True)

    split_parser = subparsers.add_parser("split-file", help="Split a large file into .001/.002 parts.")
    split_parser.add_argument("--source", required=True)
    split_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_BYTES)
    split_parser.add_argument("--delete-source", action="store_true")

    join_parser = subparsers.add_parser("join-file", help="Join .001/.002 parts back into one file.")
    join_parser.add_argument("--first-part", required=True)
    join_parser.add_argument("--output", default="")
    join_parser.add_argument("--delete-parts", action="store_true")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "stage":
        manifest = stage_ollama_models(
            Path(args.source),
            Path(args.output),
            chunk_size=int(args.chunk_size),
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    elif args.command == "restore":
        result = restore_ollama_models(
            Path(args.root),
            remove_parts=bool(args.remove_parts),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "zipdir":
        path = zip_directory(Path(args.source), Path(args.output))
        print(path)
    elif args.command == "split-file":
        parts = split_file_to_parts(
            Path(args.source),
            chunk_size=int(args.chunk_size),
            delete_source=bool(args.delete_source),
        )
        print(json.dumps([str(part) for part in parts], ensure_ascii=False, indent=2))
    elif args.command == "join-file":
        output = Path(args.output) if args.output else None
        path = join_file_parts(
            Path(args.first_part),
            output_file=output,
            delete_parts=bool(args.delete_parts),
        )
        print(path)


if __name__ == "__main__":
    main()
