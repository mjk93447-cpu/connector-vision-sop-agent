"""Runtime compatibility guards shared by the shipping app entrypoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

RuntimeFlavor = Literal["cpu", "gpu"]


def detect_runtime_flavor() -> RuntimeFlavor:
    """Return the installed runtime flavor.

    Priority:
    1. `CONNECTOR_AGENT_RUNTIME_FLAVOR` override when explicitly set.
    2. Installed torch wheel type (`torch.version.cuda`).
    3. Safe fallback to `cpu`.
    """

    env_value = str(os.environ.get("CONNECTOR_AGENT_RUNTIME_FLAVOR", "")).strip().lower()
    if env_value in {"cpu", "gpu"}:
        return "gpu" if env_value == "gpu" else "cpu"

    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return "cpu"

    cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
    return "gpu" if cuda_version is not None else "cpu"


def runtime_prefers_gpu() -> bool:
    """Return True only when the installed runtime is the GPU variant."""

    return detect_runtime_flavor() == "gpu"


def ensure_numpy_compatibility() -> None:
    """Require NumPy 1.26.x at runtime.

    The Windows packaged app and pretrain EXE both rely on native extensions
    that are known to be stable with NumPy 1.26.x. NumPy 2.x introduces ABI
    changes that can surface as import-time or runtime crashes inside torch,
    torchvision, OpenCV, or Ultralytics.
    """

    try:
        import numpy as np  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment failure path
        raise RuntimeError(
            "NumPy is missing. Rebuild the application with the pinned runtime "
            "dependencies."
        ) from exc

    version_parts = np.__version__.split(".")
    try:
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Unsupported NumPy version string: {np.__version__!r}") from exc

    if major != 1 or minor != 26:
        raise RuntimeError(
            f"Unsupported NumPy runtime {np.__version__!r}. "
            "This build requires NumPy 1.26.x. Reinstall numpy==1.26.4 and "
            "rebuild the executable."
        )


def ensure_torch_cuda_wheel(require_cuda_wheel: bool = True) -> None:
    """Require a CUDA-enabled torch wheel when the build is meant for GPU use."""

    try:
        import torch  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment failure path
        raise RuntimeError(
            "PyTorch is missing. Rebuild the application with the pinned runtime dependencies."
        ) from exc

    cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
    if require_cuda_wheel and cuda_version is None:
        raise RuntimeError(
            "CUDA-enabled torch wheel is required for this build, but the installed "
            "torch reports no CUDA support. Install the cu121 wheel and rebuild."
        )
