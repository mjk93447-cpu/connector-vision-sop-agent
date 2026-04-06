from __future__ import annotations

import sys
import types

import pytest

from src.runtime_compat import ensure_numpy_compatibility, ensure_torch_cuda_wheel


def test_ensure_numpy_compatibility_accepts_numpy_1_26(monkeypatch) -> None:
    fake_numpy = types.SimpleNamespace(__version__="1.26.4")
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    ensure_numpy_compatibility()


def test_ensure_numpy_compatibility_rejects_numpy_2(monkeypatch) -> None:
    fake_numpy = types.SimpleNamespace(__version__="2.4.3")
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    with pytest.raises(RuntimeError, match="NumPy 1.26.x"):
        ensure_numpy_compatibility()


def test_ensure_torch_cuda_wheel_accepts_cuda_build(monkeypatch) -> None:
    fake_torch = types.SimpleNamespace(version=types.SimpleNamespace(cuda="12.1"))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    ensure_torch_cuda_wheel(require_cuda_wheel=True)


def test_ensure_torch_cuda_wheel_rejects_cpu_build(monkeypatch) -> None:
    fake_torch = types.SimpleNamespace(version=types.SimpleNamespace(cuda=None))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    with pytest.raises(RuntimeError, match="CUDA-enabled torch wheel"):
        ensure_torch_cuda_wheel(require_cuda_wheel=True)
