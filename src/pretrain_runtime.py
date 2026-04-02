"""Runtime helpers for local pretrain execution.

This module centralizes:
- dataset root discovery
- hardware detection
- automatic pretrain hyperparameter suggestions

The goal is to keep the pretrain EXE and the build workflow aligned so that
the same hardware-aware defaults are used everywhere.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config_loader import detect_local_accelerator, get_base_dir

_EXPLICIT_RUNTIME_ROOT = Path(r"C:\tools\connector_agent")
_DATA_ROOT_NAMES = ("pretrain_data", "pretrain_data_test", "training_data")
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


@dataclass(frozen=True)
class PretrainProfile:
    device: object
    epochs: int
    batch: int
    image_size: int
    workers: int


def _system_ram_gb() -> float | None:
    """Return total system RAM in GiB when available."""

    if os.name != "nt":
        return None

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return None
    except Exception:  # noqa: BLE001
        return None
    return status.ullTotalPhys / (1024**3)


def _logical_cpu_count() -> int:
    return max(1, os.cpu_count() or 1)


def _physical_cpu_count(logical_count: int) -> int:
    """Best-effort physical core estimate.

    We prefer psutil when present, but fall back to a conservative estimate.
    """

    try:
        import psutil  # type: ignore[import-not-found]  # noqa: PLC0415

        physical = psutil.cpu_count(logical=False)
        if physical:
            return max(1, int(physical))
    except Exception:  # noqa: BLE001
        pass
    return max(1, logical_count // 2 or 1)


def resolve_pretrain_data_root(explicit_root: str | Path | None = None) -> Path:
    """Resolve the folder that contains pretrain_data and its splits.

    Search order:
    1. explicit_root when provided
    2. C:\\tools\\connector_agent\\pretrain_data
    3. EXE/app base dir + known dataset folder names
    4. CWD + known dataset folder names

    The first existing directory wins. If nothing exists yet, the highest
    priority candidate is returned so callers can create it there.
    """

    candidates: list[Path] = []

    def _add(path: Path) -> None:
        if path not in candidates:
            candidates.append(path)

    if explicit_root is not None:
        explicit = Path(explicit_root)
        if explicit.is_absolute():
            _add(explicit)
        else:
            _add((Path.cwd() / explicit).resolve())
            _add((get_base_dir() / explicit).resolve())

    _add((_EXPLICIT_RUNTIME_ROOT / "pretrain_data").resolve())

    base_dir = get_base_dir()
    for root in (base_dir, Path.cwd()):
        for folder_name in _DATA_ROOT_NAMES:
            _add((root / folder_name).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else (base_dir / "pretrain_data")


def count_prepared_images(data_root: Path) -> int:
    """Count image files under train/val image splits."""

    total = 0
    for split in ("train", "val"):
        split_dir = data_root / split / "images"
        if not split_dir.exists():
            continue
        total += sum(1 for p in split_dir.rglob("*") if p.suffix.lower() in _IMG_EXTS)
    return total


def detect_pretrain_hardware() -> dict[str, Any]:
    """Return a hardware summary tailored for pretrain auto-configuration."""

    accel = detect_local_accelerator()
    logical = _logical_cpu_count()
    physical = _physical_cpu_count(logical)
    ram_gb = _system_ram_gb()

    return {
        **accel,
        "logical_cores": logical,
        "physical_cores": physical,
        "ram_gb": ram_gb,
    }


def suggest_pretrain_profile(
    image_count: int | None = None,
    explicit_device: object | None = None,
) -> PretrainProfile:
    """Return an auto-profile for pretrain execution.

    The profile is intentionally hardware-aware and prefers throughput over
    tiny defaults, while staying conservative enough for Windows multiprocessing.
    """

    hw = detect_pretrain_hardware()
    sample_count = max(0, int(image_count or 0))

    if explicit_device is not None:
        device = explicit_device
    else:
        device = hw["device"] if hw["cuda_usable"] else "cpu"

    logical = int(hw["logical_cores"] or 1)
    physical = int(hw["physical_cores"] or max(1, logical // 2))
    ram_gb = hw.get("ram_gb")
    vram_gb = hw.get("memory_gb")
    is_cuda = device != "cpu" and bool(hw["cuda_usable"])

    if is_cuda:
        batch = 16 if (vram_gb or 0) >= 20 or (ram_gb or 0) >= 64 else 8 if (vram_gb or 0) >= 12 else 4
        epochs = 60 if sample_count <= 30 else 40 if sample_count <= 120 else 30
        image_size = 640
        workers = min(max(4, physical // 2), 8)
    else:
        batch = 16 if physical >= 16 and (ram_gb or 0) >= 64 else 8 if physical >= 12 else 4
        epochs = 8 if sample_count <= 30 else 5 if sample_count <= 120 else 3
        image_size = 320
        workers = min(max(4, physical - 2), 12)

    return PretrainProfile(
        device=device,
        epochs=epochs,
        batch=batch,
        image_size=image_size,
        workers=workers,
    )
