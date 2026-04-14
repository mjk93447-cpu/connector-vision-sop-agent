from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.package_ollama_models import MANIFEST_NAME


def _str_to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def build_verification_report(
    *,
    stage_root: Path,
    expected_model: str,
    source_run_id: str,
    require_turboquant: bool,
) -> dict[str, Any]:
    manifest_path = stage_root / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing staged manifest: {manifest_path}")

    prepare_metadata_path = stage_root / "prepare_metadata.json"
    if not prepare_metadata_path.exists():
        raise FileNotFoundError(f"Missing prepare metadata: {prepare_metadata_path}")

    show_json_path = stage_root / "ollama_show.json"
    show_text_path = stage_root / "ollama_show.txt"
    if not show_json_path.exists() or not show_text_path.exists():
        raise FileNotFoundError("Prepared artifact is missing ollama_show evidence files.")
    quant_manifest_path = stage_root / "quantization_manifest.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prepare_metadata = json.loads(prepare_metadata_path.read_text(encoding="utf-8"))
    show_json = json.loads(show_json_path.read_text(encoding="utf-8"))
    prepared_model = str(prepare_metadata.get("model_name", "")).strip()
    if prepared_model != expected_model:
        raise ValueError(
            f"Prepared model mismatch: expected {expected_model!r}, got {prepared_model!r}"
        )

    source_mode = str(prepare_metadata.get("source_mode", "")).strip()
    quantization_origin = str(prepare_metadata.get("quantization_origin", "")).strip()
    turboquant_claimed = "turbo" in quantization_origin.lower()

    if require_turboquant:
        if source_mode != "gguf-import":
            raise ValueError(
                "TurboQuant verification requires source_mode=gguf-import. "
                "official-pull cannot prove a custom TurboQuant quantization path."
            )
        if not turboquant_claimed:
            raise ValueError(
                "TurboQuant verification requires quantization_origin to include "
                "'turbo' so the artifact chain documents its quantization source."
            )
        if not quant_manifest_path.exists():
            raise FileNotFoundError(
                "TurboQuant verification requires quantization_manifest.json in the prepared artifact."
            )
        quant_manifest = json.loads(quant_manifest_path.read_text(encoding="utf-8"))
        manifest_origin = str(quant_manifest.get("quantization_origin", "")).strip()
        manifest_tool = str(quant_manifest.get("tool", "")).strip()
        if "turbo" not in manifest_origin.lower() and "turbo" not in manifest_tool.lower():
            raise ValueError(
                "TurboQuant verification requires quantization_manifest.json to identify "
                "a TurboQuant tool or quantization_origin."
            )
    else:
        quant_manifest = (
            json.loads(quant_manifest_path.read_text(encoding="utf-8"))
            if quant_manifest_path.exists()
            else {}
        )

    details = show_json.get("details", {})
    if str(details.get("format", "")).strip().lower() != "gguf":
        raise ValueError("Prepared model is not reported as GGUF by ollama show.")

    return {
        "schema_version": "1",
        "status": "prepared",
        "model_name": expected_model,
        "source_run_id": source_run_id,
        "prepared_artifact_name": str(prepare_metadata.get("prepared_artifact_name", "")),
        "source_mode": source_mode,
        "quantization_origin": quantization_origin,
        "require_turboquant": require_turboquant,
        "prepare_metadata_path": prepare_metadata_path.name,
        "prepared_manifest_path": manifest_path.name,
        "prepared_files": {
            "copied_files": len(manifest.get("copied_files", [])),
            "split_files": len(manifest.get("split_files", [])),
        },
        "prepare_show_files": {
            "text": show_text_path.name,
            "json": show_json_path.name,
        },
        "quantization_manifest_path": quant_manifest_path.name if quant_manifest_path.exists() else "",
        "quantization_manifest_summary": quant_manifest,
        "ollama_details": details,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify prepared Ollama artifact metadata.")
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--require-turboquant", default="true")
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_verification_report(
        stage_root=Path(args.stage_root),
        expected_model=args.expected_model,
        source_run_id=args.source_run_id,
        require_turboquant=_str_to_bool(args.require_turboquant),
    )
    output = Path(args.output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
