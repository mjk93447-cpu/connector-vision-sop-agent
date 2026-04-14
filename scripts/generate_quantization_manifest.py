from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_manifest(
    *,
    gguf_path: Path,
    output_path: Path,
    model_name: str,
    base_model: str,
    tool: str,
    command: str,
    notes: str,
) -> dict:
    manifest = {
        "schema_version": "1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_name": model_name,
        "base_model": base_model,
        "tool": tool,
        "quantization_origin": tool,
        "command": command,
        "notes": notes,
        "gguf_file": gguf_path.name,
        "gguf_size_bytes": gguf_path.stat().st_size,
        "gguf_sha256": sha256_file(gguf_path),
    }
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate TurboQuant provenance manifest for a GGUF.")
    parser.add_argument("--gguf-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--tool", default="turboquant")
    parser.add_argument("--command", default="")
    parser.add_argument("--notes", default="")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    manifest = generate_manifest(
        gguf_path=Path(args.gguf_path),
        output_path=Path(args.output),
        model_name=args.model_name,
        base_model=args.base_model,
        tool=args.tool,
        command=args.command,
        notes=args.notes,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
