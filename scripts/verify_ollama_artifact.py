from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.package_ollama_models import MANIFEST_NAME

MAX_CHUNK_BYTES = 2_000_000_000


def _str_to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _expected_family(model_name: str) -> str:
    return model_name.split(":", 1)[0].strip().lower()


def _expected_quantization_level(model_name: str) -> str:
    suffix = model_name.rsplit("-", 1)[-1].strip()
    if not suffix:
        raise ValueError(f"Unable to derive expected quantization level from {model_name!r}")
    return suffix[:1].upper() + suffix[1:]


def _normalize_token(value: str) -> str:
    return str(value).strip().lower()


def _validate_stage_chunking(stage_root: Path, manifest: dict[str, Any]) -> None:
    chunk_size = int(manifest.get("chunk_size", 0) or 0)
    if chunk_size <= 0:
        raise ValueError("Prepared artifact manifest is missing a positive chunk_size.")
    if chunk_size > MAX_CHUNK_BYTES:
        raise ValueError(
            f"Prepared artifact chunk_size exceeds 2 GiB limit: {chunk_size} > {MAX_CHUNK_BYTES}"
        )

    for rel_path in manifest.get("copied_files", []):
        path = stage_root / rel_path
        if not path.exists():
            raise FileNotFoundError(f"Prepared artifact copied file is missing: {rel_path}")
        if path.stat().st_size > MAX_CHUNK_BYTES:
            raise ValueError(f"Prepared artifact copied file exceeds 2 GiB limit: {rel_path}")

    for item in manifest.get("split_files", []):
        rel_path = str(item.get("path", "")).strip()
        if not rel_path:
            raise ValueError("Prepared artifact split_files item is missing path.")
        split_chunk_size = int(item.get("chunk_size", 0) or 0)
        if split_chunk_size <= 0 or split_chunk_size > MAX_CHUNK_BYTES:
            raise ValueError(
                f"Prepared artifact split file chunk_size is invalid for {rel_path}: {split_chunk_size}"
            )
        parts = item.get("parts", [])
        if not parts:
            raise ValueError(f"Prepared artifact split file is missing parts for {rel_path}.")
        combined_size = 0
        for part_rel in parts:
            part_path = stage_root / str(part_rel)
            if not part_path.exists():
                raise FileNotFoundError(f"Prepared artifact part is missing: {part_rel}")
            part_size = part_path.stat().st_size
            if part_size > MAX_CHUNK_BYTES:
                raise ValueError(f"Prepared artifact part exceeds 2 GiB limit: {part_rel}")
            combined_size += part_size
        expected_size = int(item.get("size", 0) or 0)
        if expected_size <= 0:
            raise ValueError(f"Prepared artifact split file has invalid size metadata: {rel_path}")
        if combined_size != expected_size:
            raise ValueError(
                f"Prepared artifact split file size mismatch for {rel_path}: "
                f"expected {expected_size}, got {combined_size}"
            )


def _validate_quantization_contract(
    *,
    expected_model: str,
    quant_manifest: dict[str, Any],
    fetch_result: dict[str, Any],
    gguf_download_manifest: dict[str, Any],
) -> None:
    required_keys = [
        "schema_version",
        "model_name",
        "base_model",
        "tool",
        "quantization_origin",
        "expected_family",
        "expected_quantization_level",
        "gguf_file",
        "gguf_size_bytes",
        "gguf_sha256",
        "source_url",
        "reference_url",
    ]
    missing = [key for key in required_keys if not str(quant_manifest.get(key, "")).strip()]
    if missing:
        raise ValueError(
            "TurboQuant quantization_manifest.json is missing required fields: "
            + ", ".join(missing)
        )

    if str(quant_manifest.get("schema_version")) != "1":
        raise ValueError("TurboQuant quantization_manifest.json must use schema_version '1'.")
    if str(quant_manifest.get("model_name")).strip() != expected_model:
        raise ValueError("TurboQuant quantization_manifest.json model_name does not match.")

    expected_family = _expected_family(expected_model)
    expected_quant = _expected_quantization_level(expected_model)
    if _normalize_token(str(quant_manifest.get("expected_family"))) != expected_family:
        raise ValueError("TurboQuant quantization manifest expected_family does not match.")
    if _normalize_token(str(quant_manifest.get("expected_quantization_level"))) != _normalize_token(
        expected_quant
    ):
        raise ValueError(
            "TurboQuant quantization manifest expected_quantization_level does not match."
        )

    gguf_sha256 = _normalize_token(str(quant_manifest.get("gguf_sha256")))
    if len(gguf_sha256) != 64:
        raise ValueError("TurboQuant quantization manifest gguf_sha256 must be a 64-char hex digest.")
    gguf_size = int(quant_manifest.get("gguf_size_bytes", 0) or 0)
    if gguf_size <= 0:
        raise ValueError("TurboQuant quantization manifest gguf_size_bytes must be positive.")

    fetch_sha = _normalize_token(str(fetch_result.get("output_sha256", "")))
    fetch_size = int(fetch_result.get("size_bytes", 0) or 0)
    if fetch_sha != gguf_sha256:
        raise ValueError("Fetched GGUF sha256 does not match quantization manifest.")
    if fetch_size != gguf_size:
        raise ValueError("Fetched GGUF size does not match quantization manifest.")

    fetch_mode = str(fetch_result.get("mode", "")).strip()
    if fetch_mode not in {"direct-url", "manifest-url"}:
        raise ValueError(f"Unexpected GGUF fetch mode: {fetch_mode!r}")

    if gguf_download_manifest:
        download_sha = _normalize_token(str(gguf_download_manifest.get("sha256", "")))
        download_size = int(gguf_download_manifest.get("size_bytes", 0) or 0)
        if download_sha != gguf_sha256:
            raise ValueError("GGUF download manifest sha256 does not match quantization manifest.")
        if download_size != gguf_size:
            raise ValueError("GGUF download manifest size does not match quantization manifest.")
        for index, part in enumerate(gguf_download_manifest.get("parts", [])):
            part_size = int(part.get("size_bytes", 0) or 0)
            if part_size <= 0 or part_size > MAX_CHUNK_BYTES:
                raise ValueError(
                    f"GGUF download manifest part #{index} exceeds 2 GiB limit or is invalid."
                )


def _validate_show_details(details: dict[str, Any], expected_model: str) -> None:
    if _normalize_token(str(details.get("format", ""))) != "gguf":
        raise ValueError("Prepared model is not reported as GGUF by ollama show.")

    expected_family = _expected_family(expected_model)
    reported_family = _normalize_token(str(details.get("family", "")))
    reported_families = {_normalize_token(item) for item in details.get("families", [])}
    if expected_family not in {reported_family, *reported_families}:
        raise ValueError(
            f"Prepared model family mismatch: expected {expected_family!r}, "
            f"got family={reported_family!r}, families={sorted(reported_families)!r}"
        )

    expected_quant = _normalize_token(_expected_quantization_level(expected_model))
    reported_quant = _normalize_token(str(details.get("quantization_level", "")))
    if reported_quant != expected_quant:
        raise ValueError(
            f"Prepared model quantization mismatch: expected {expected_quant!r}, got {reported_quant!r}"
        )


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
    fetch_result_path = stage_root / "fetch_result.json"
    if not fetch_result_path.exists():
        raise FileNotFoundError(f"Missing fetch result metadata: {fetch_result_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prepare_metadata = json.loads(prepare_metadata_path.read_text(encoding="utf-8"))
    show_json = json.loads(show_json_path.read_text(encoding="utf-8"))
    fetch_result = json.loads(fetch_result_path.read_text(encoding="utf-8"))
    prepared_model = str(prepare_metadata.get("model_name", "")).strip()
    if prepared_model != expected_model:
        raise ValueError(
            f"Prepared model mismatch: expected {expected_model!r}, got {prepared_model!r}"
        )

    source_mode = str(prepare_metadata.get("source_mode", "")).strip()
    quantization_origin = str(prepare_metadata.get("quantization_origin", "")).strip()
    turboquant_claimed = "turbo" in quantization_origin.lower()
    _validate_stage_chunking(stage_root, manifest)

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

    gguf_download_manifest = {}
    gguf_download_manifest_path = stage_root / "gguf_download_manifest.json"
    if gguf_download_manifest_path.exists():
        gguf_download_manifest = json.loads(gguf_download_manifest_path.read_text(encoding="utf-8"))

    if require_turboquant:
        _validate_quantization_contract(
            expected_model=expected_model,
            quant_manifest=quant_manifest,
            fetch_result=fetch_result,
            gguf_download_manifest=gguf_download_manifest,
        )

    details = show_json.get("details", {})
    _validate_show_details(details, expected_model)

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
        "chunk_limit_bytes": MAX_CHUNK_BYTES,
        "chunk_size_bytes": int(manifest.get("chunk_size", 0) or 0),
        "prepared_files": {
            "copied_files": len(manifest.get("copied_files", [])),
            "split_files": len(manifest.get("split_files", [])),
        },
        "prepare_show_files": {
            "text": show_text_path.name,
            "json": show_json_path.name,
        },
        "fetch_result_path": fetch_result_path.name,
        "gguf_download_manifest_path": (
            gguf_download_manifest_path.name if gguf_download_manifest_path.exists() else ""
        ),
        "quantization_manifest_path": quant_manifest_path.name if quant_manifest_path.exists() else "",
        "quantization_manifest_summary": quant_manifest,
        "fetch_result_summary": fetch_result,
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
