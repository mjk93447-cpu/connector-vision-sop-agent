from __future__ import annotations

from pathlib import Path

import pytest

import src.pretrain_runtime as pretrain_runtime


class TestResolvePretrainDataRoot:
    def test_prefers_explicit_existing_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        explicit = tmp_path / "custom_pretrain"
        explicit.mkdir()
        monkeypatch.setattr(pretrain_runtime, "get_base_dir", lambda: tmp_path)
        result = pretrain_runtime.resolve_pretrain_data_root(explicit)
        assert result == explicit

    def test_falls_back_to_connector_agent_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        connector_root = tmp_path / "connector_agent" / "pretrain_data"
        connector_root.mkdir(parents=True)
        monkeypatch.setattr(pretrain_runtime, "_EXPLICIT_RUNTIME_ROOT", tmp_path / "connector_agent")
        monkeypatch.setattr(pretrain_runtime, "get_base_dir", lambda: tmp_path / "missing_base")
        monkeypatch.chdir(tmp_path)
        result = pretrain_runtime.resolve_pretrain_data_root()
        assert result == connector_root


class TestSuggestPretrainProfile:
    def test_cuda_profile_uses_larger_batch_and_workers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            pretrain_runtime,
            "detect_pretrain_hardware",
            lambda: {
                "device": 0,
                "name": "NVIDIA RTX 4000 Ada Generation",
                "memory_gb": 20.0,
                "gpu_present": True,
                "cuda_usable": True,
                "logical_cores": 48,
                "physical_cores": 24,
                "ram_gb": 128.0,
            },
        )
        profile = pretrain_runtime.suggest_pretrain_profile(image_count=200)
        assert profile.device == 0
        assert profile.batch >= 16
        assert profile.image_size == 640
        assert profile.workers >= 4

    def test_cpu_profile_scales_down_image_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            pretrain_runtime,
            "detect_pretrain_hardware",
            lambda: {
                "device": "cpu",
                "name": None,
                "memory_gb": None,
                "gpu_present": False,
                "cuda_usable": False,
                "logical_cores": 48,
                "physical_cores": 24,
                "ram_gb": 128.0,
            },
        )
        profile = pretrain_runtime.suggest_pretrain_profile(image_count=50)
        assert profile.device == "cpu"
        assert profile.image_size == 320
        assert profile.batch >= 4
        assert profile.workers > 0
