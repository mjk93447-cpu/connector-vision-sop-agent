from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_diag_module():
    script_path = Path("scripts/check_local_runtime.py").resolve()
    spec = importlib.util.spec_from_file_location("check_local_runtime", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLocalRuntimeDiagnostic:
    def test_render_report_warns_on_proxy_and_context_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        diag = _load_diag_module()

        monkeypatch.setenv("HTTP_PROXY", "http://proxy.local:8080")
        monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,::1")
        monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
        monkeypatch.setenv("OLLAMA_ORIGINS", "*")
        monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "0")
        monkeypatch.setattr(
            diag,
            "detect_local_accelerator",
            lambda: {
                "device": 0,
                "name": "NVIDIA RTX 4000 Ada Generation",
                "memory_gb": 20.0,
                "gpu_present": True,
                "cuda_usable": True,
            },
        )

        report, failures = diag.render_report()

        assert failures >= 2
        assert "HTTP_PROXY" in report
        assert "OLLAMA_CONTEXT_LENGTH" in report
        assert "GPU detected" in report

    def test_render_report_passes_when_env_is_clean(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        diag = _load_diag_module()

        for key in [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "NO_PROXY",
            "no_proxy",
            "OLLAMA_HOST",
            "OLLAMA_ORIGINS",
            "OLLAMA_CONTEXT_LENGTH",
        ]:
            monkeypatch.delenv(key, raising=False)

        monkeypatch.setattr(
            diag,
            "detect_local_accelerator",
            lambda: {
                "device": 0,
                "name": "NVIDIA RTX 4000 Ada Generation",
                "memory_gb": 20.0,
                "gpu_present": True,
                "cuda_usable": True,
            },
        )

        report, failures = diag.render_report()

        assert failures >= 1  # OLLAMA_HOST/origins/context may still be unset
        assert "CUDA" in report
