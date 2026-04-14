from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from huggingface_hub import HfApi


def publish_to_hf(
    *,
    repo_id: str,
    gguf_path: Path,
    quantization_manifest_path: Path,
    token: str,
    private: bool = False,
) -> dict:
    if not token:
        raise ValueError("A Hugging Face token is required.")

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)

    staging = gguf_path.parent / ".hf_upload_stage"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    target_gguf = staging / gguf_path.name
    target_manifest = staging / quantization_manifest_path.name
    shutil.copy2(gguf_path, target_gguf)
    shutil.copy2(quantization_manifest_path, target_manifest)

    readme = staging / "README.md"
    readme.write_text(
        "# TurboQuant GGUF Artifact\n\n"
        "This repository stores a TurboQuant-built GGUF and its provenance manifest.\n",
        encoding="utf-8",
    )

    api.upload_large_folder(
        repo_id=repo_id,
        repo_type="model",
        folder_path=staging,
        private=private,
        print_report=False,
    )

    base = f"https://huggingface.co/{repo_id}/resolve/main"
    result = {
        "repo_id": repo_id,
        "gguf_url": f"{base}/{gguf_path.name}?download=true",
        "quantization_manifest_url": f"{base}/{quantization_manifest_path.name}?download=true",
    }
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload TurboQuant GGUF + manifest to a Hugging Face model repo.")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--gguf-path", required=True)
    parser.add_argument("--quantization-manifest-path", required=True)
    parser.add_argument("--token", default="")
    parser.add_argument("--private", action="store_true")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    token = args.token or os.environ.get("HF_TOKEN", "")
    result = publish_to_hf(
        repo_id=args.repo_id,
        gguf_path=Path(args.gguf_path),
        quantization_manifest_path=Path(args.quantization_manifest_path),
        token=token,
        private=bool(args.private),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
