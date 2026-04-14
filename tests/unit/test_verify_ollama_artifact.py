from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.package_ollama_models import MANIFEST_NAME
from scripts.verify_ollama_artifact import build_verification_report


def _write_prepared_stage(
    tmp_path: Path,
    *,
    source_mode: str,
    quantization_origin: str,
    include_quant_manifest: bool = True,
) -> Path:
    stage_root = tmp_path / "prepared_stage"
    stage_root.mkdir()
    (stage_root / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "format": "ollama-chunked-stage-v1",
                "chunk_size": 2_000_000_000,
                "copied_files": ["manifests/example.json"],
                "split_files": [],
            }
        ),
        encoding="utf-8",
    )
    (stage_root / "manifests").mkdir(exist_ok=True)
    (stage_root / "manifests/example.json").write_text("{}", encoding="utf-8")
    (stage_root / "prepare_metadata.json").write_text(
        json.dumps(
            {
                "model_name": "gemma4:26b-a4b-it-q4_K_M",
                "source_mode": source_mode,
                "quantization_origin": quantization_origin,
                "prepared_artifact_name": "connector-agent-llm-prepared",
            }
        ),
        encoding="utf-8",
    )
    (stage_root / "ollama_show.txt").write_text("show output", encoding="utf-8")
    (stage_root / "ollama_show.json").write_text(
        json.dumps(
            {
                "details": {
                    "format": "gguf",
                    "family": "gemma4",
                    "families": ["gemma4"],
                    "quantization_level": "Q4_K_M",
                }
            }
        ),
        encoding="utf-8",
    )
    (stage_root / "fetch_result.json").write_text(
        json.dumps(
            {
                "mode": "manifest-url",
                "output_sha256": "a" * 64,
                "size_bytes": 123,
            }
        ),
        encoding="utf-8",
    )
    if include_quant_manifest:
        (stage_root / "quantization_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "model_name": "gemma4:26b-a4b-it-q4_K_M",
                    "base_model": "google/gemma-4-26B-A4B-it",
                    "tool": "turboquant",
                    "quantization_origin": quantization_origin,
                    "expected_family": "gemma4",
                    "expected_quantization_level": "Q4_K_M",
                    "gguf_file": "model.gguf",
                    "gguf_size_bytes": 123,
                    "gguf_sha256": "a" * 64,
                    "source_url": "https://example.invalid/model.gguf",
                    "reference_url": "https://example.invalid/reference",
                }
            ),
            encoding="utf-8",
        )
    (stage_root / "gguf_download_manifest.json").write_text(
        json.dumps(
            {
                "sha256": "a" * 64,
                "size_bytes": 123,
                "parts": [{"url": "https://example.invalid/part1", "size_bytes": 100}],
            }
        ),
        encoding="utf-8",
    )
    return stage_root


def test_build_verification_report_accepts_turboquant_import_stage(tmp_path: Path) -> None:
    stage_root = _write_prepared_stage(
        tmp_path,
        source_mode="gguf-import",
        quantization_origin="turboquant",
    )
    report = build_verification_report(
        stage_root=stage_root,
        expected_model="gemma4:26b-a4b-it-q4_K_M",
        source_run_id="12345",
        require_turboquant=True,
    )
    assert report["status"] == "prepared"
    assert report["source_mode"] == "gguf-import"
    assert report["quantization_origin"] == "turboquant"
    assert report["quantization_manifest_summary"]["tool"] == "turboquant"
    assert report["ollama_details"]["quantization_level"] == "Q4_K_M"
    assert report["chunk_limit_bytes"] == 2_000_000_000


def test_build_verification_report_rejects_official_pull_when_turboquant_required(
    tmp_path: Path,
) -> None:
    stage_root = _write_prepared_stage(
        tmp_path,
        source_mode="official-pull",
        quantization_origin="stock-ollama",
    )
    with pytest.raises(ValueError, match="source_mode=gguf-import"):
        build_verification_report(
            stage_root=stage_root,
            expected_model="gemma4:26b-a4b-it-q4_K_M",
            source_run_id="12345",
            require_turboquant=True,
        )


def test_build_verification_report_rejects_missing_quant_manifest_for_turboquant(
    tmp_path: Path,
) -> None:
    stage_root = _write_prepared_stage(
        tmp_path,
        source_mode="gguf-import",
        quantization_origin="turboquant",
        include_quant_manifest=False,
    )
    with pytest.raises(FileNotFoundError, match="quantization_manifest.json"):
        build_verification_report(
            stage_root=stage_root,
            expected_model="gemma4:26b-a4b-it-q4_K_M",
            source_run_id="12345",
            require_turboquant=True,
        )


def test_build_verification_report_rejects_quantization_level_mismatch(tmp_path: Path) -> None:
    stage_root = _write_prepared_stage(
        tmp_path,
        source_mode="gguf-import",
        quantization_origin="turboquant",
    )
    (stage_root / "quantization_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "model_name": "gemma4:26b-a4b-it-q4_K_M",
                "base_model": "google/gemma-4-26B-A4B-it",
                "tool": "turboquant",
                "quantization_origin": "turboquant",
                "expected_family": "gemma4",
                "expected_quantization_level": "Q5_K_M",
                "gguf_file": "model.gguf",
                "gguf_size_bytes": 123,
                "gguf_sha256": "a" * 64,
                "source_url": "https://example.invalid/model.gguf",
                "reference_url": "https://example.invalid/reference",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected_quantization_level"):
        build_verification_report(
            stage_root=stage_root,
            expected_model="gemma4:26b-a4b-it-q4_K_M",
            source_run_id="12345",
            require_turboquant=True,
        )
