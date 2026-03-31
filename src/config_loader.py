"""
Config loader for offline Samsung OLED line deployment.

Reads tuning values such as engineer password, ROI coordinates, retry counts,
and model/config paths from assets/config.json for field-side adjustment.

Path resolution order (supports both source-run and PyInstaller EXE):
  1. EXE 옆 경로  — connector_agent/assets/config.json  (사용자 편집 가능)
  2. CWD 상대경로 — 개발 환경 소스 실행 시
  3. _MEIPASS     — PyInstaller 번들 내부 fallback
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _resolve_config_path(config_path: Path) -> Path:
    """EXE/소스 양 환경에서 config 파일을 찾아 반환한다."""

    if config_path.is_absolute() and config_path.exists():
        return config_path

    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        # 1순위: EXE 파일 옆 (라인 PC에서 사용자가 편집하는 config)
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / config_path)
        # 3순위: PyInstaller 번들 내부 (_MEIPASS)
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass.exists():
            candidates.append(meipass / config_path)

    # 2순위: CWD 기준 상대 경로 (소스 실행 / pytest)
    candidates.append(config_path)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # 모든 후보 실패 → 원본 경로를 반환해 open()이 표준 에러를 올리도록 함
    return config_path


def get_base_dir() -> Path:
    """EXE/소스 양 환경에서 프로젝트 루트(base) 경로를 반환한다.

    - PyInstaller EXE: sys.executable 의 부모 디렉터리
    - 소스 실행: 이 파일(src/config_loader.py)의 상위 상위 디렉터리
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resolve_app_path(path: str | Path) -> Path:
    """Resolve a project-relative path against the active runtime layout.

    Search order:
      1. Absolute path, if already absolute
      2. EXE directory when frozen
      3. PyInstaller _MEIPASS when available
      4. Project root returned by get_base_dir()
      5. Current working directory
      6. Repository root (source layout fallback)

    The first existing candidate wins. If none exist, the highest-priority
    candidate is returned so callers can still create the file there.
    """

    candidate_path = Path(path)
    if candidate_path.is_absolute():
        return candidate_path

    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).parent)
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass.exists():
            roots.append(meipass)

    roots.append(get_base_dir())
    cwd = Path.cwd()
    if cwd not in roots:
        roots.append(cwd)

    repo_root = Path(__file__).resolve().parent.parent
    if repo_root not in roots:
        roots.append(repo_root)

    candidates: list[Path] = []
    for root in roots:
        resolved = root / candidate_path
        if resolved not in candidates:
            candidates.append(resolved)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def resolve_existing_app_path(*paths: str | Path) -> Path:
    """Return the first existing path among project-relative candidates."""

    if not paths:
        raise ValueError("At least one path must be provided")
    for path in paths:
        resolved = resolve_app_path(path)
        if resolved.exists():
            return resolved
    return resolve_app_path(paths[0])


def detect_local_accelerator() -> dict[str, Any]:
    """Best-effort local accelerator detection for training defaults.

    Returns a dictionary with:
      - device: "cpu" or CUDA device index as int
      - name: GPU name when available
      - memory_gb: total VRAM in GB when available
      - gpu_present: True when a local NVIDIA GPU is detected
      - cuda_usable: True when torch can actually use CUDA
    """

    device: Any = "cpu"
    name: str | None = None
    memory_gb: float | None = None
    gpu_present = False
    cuda_usable = False

    def _read_nvidia_smi() -> tuple[str | None, float | None]:
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
        except Exception:  # noqa: BLE001
            return None, None

        for line in completed.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 2:
                gpu_name = parts[0] or None
                try:
                    vram_mb = float(parts[1])
                except ValueError:
                    vram_mb = None
                return gpu_name, (vram_mb / 1024.0 if vram_mb is not None else None)
        return None, None

    try:
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            device = 0
            cuda_usable = True
            gpu_present = True
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:  # noqa: BLE001
                name = "CUDA GPU"
            try:
                props = torch.cuda.get_device_properties(0)
                memory_gb = props.total_memory / (1024**3)
            except Exception:  # noqa: BLE001
                memory_gb = None
        else:
            name, memory_gb = _read_nvidia_smi()
            gpu_present = name is not None or memory_gb is not None
    except Exception:  # noqa: BLE001
        name, memory_gb = _read_nvidia_smi()
        gpu_present = name is not None or memory_gb is not None

    if gpu_present and name is None:
        name = "NVIDIA GPU"

    return {
        "device": device,
        "name": name,
        "memory_gb": memory_gb,
        "gpu_present": gpu_present,
        "cuda_usable": cuda_usable,
    }


def suggest_training_profile(image_count: int | None = None) -> dict[str, Any]:
    """Suggest training defaults tuned for the local machine.

    GPU-equipped workstations get a larger batch and the full 640px training
    resolution. CPU-only environments fall back to a lighter schedule.
    """

    accelerator = detect_local_accelerator()
    device = accelerator["device"]
    memory_gb = accelerator["memory_gb"]

    sample_count = image_count or 0

    if device != "cpu":
        if memory_gb is not None and memory_gb >= 20:
            batch = 16
        elif memory_gb is not None and memory_gb >= 12:
            batch = 8
        else:
            batch = 4

        if sample_count <= 30:
            epochs = 60
        elif sample_count <= 80:
            epochs = 40
        else:
            epochs = 24

        image_size = 640
    else:
        batch = 2
        epochs = 8 if sample_count <= 30 else 5 if sample_count <= 120 else 4
        image_size = 320

    return {
        "device": device,
        "gpu_name": accelerator["name"],
        "memory_gb": memory_gb,
        "epochs": epochs,
        "batch": batch,
        "image_size": image_size,
    }


def load_config(config_path: str | Path = "assets/config.json") -> dict[str, Any]:
    """Load and return the project configuration JSON file.

    Args:
        config_path: config 파일 경로 (기본값: ``assets/config.json``).
            절대 경로, 또는 EXE·CWD·_MEIPASS 기준 상대 경로를 모두 지원.

    Returns:
        config 딕셔너리.

    Raises:
        FileNotFoundError: 모든 후보 경로에서 파일을 찾지 못한 경우.
        json.JSONDecodeError: JSON 파싱 실패 시.
    """

    resolved = _resolve_config_path(Path(config_path))
    with resolved.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)
