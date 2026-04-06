"""Runtime compatibility guards shared by app and pretrain entrypoints."""

from __future__ import annotations


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
