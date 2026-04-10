from __future__ import annotations

import argparse
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import cv2
import numpy as np
import torch
import torchvision

from src.model_artifacts import resolve_runtime_model
from src.runtime_compat import ensure_numpy_compatibility, ensure_torch_cuda_wheel
from src.training.training_manager import TrainingManager


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast preflight for GUI CUDA fine-tuning")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Base YOLO model path to validate. Defaults to the active runtime "
            "slot used by the 5.0.0 app bundle."
        ),
    )
    parser.add_argument(
        "--require-cuda-wheel",
        action="store_true",
        help="Fail unless the installed torch wheel reports CUDA support.",
    )
    return parser


def _resolve_model_path(model_arg: str | None) -> Path:
    if model_arg is not None:
        return Path(model_arg).expanduser()
    return resolve_runtime_model("assets/models/yolo26x_local_pretrained.pt")


def _write_dummy_dataset(root: Path) -> Path:
    images_dir = root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_path = images_dir / "dummy.png"
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    cv2.imwrite(str(image_path), image)
    yaml_path = root / "dataset.yaml"
    yaml_path.write_text(
        f"path: {str(root).replace(chr(92), '/')}\n"
        "train: images\n"
        "val: images\n"
        "nc: 1\n"
        "names: ['button']\n",
        encoding="utf-8",
    )
    return yaml_path


def _smoke_cuda_tensor() -> None:
    if not torch.cuda.is_available():
        print("[preflight_app] CUDA not available in this environment; skipping device smoke test.")
        return

    x = torch.tensor([1.0], device="cuda")
    y = x + 1.0
    torch.cuda.synchronize()
    print(f"[preflight_app] CUDA tensor smoke OK: {float(y.item())}")


class _FakeYOLO:
    def __init__(self, weights_path: str) -> None:
        self.weights_path = weights_path
        self.callbacks: dict[str, object] = {}

    def add_callback(self, event: str, callback: object) -> None:
        self.callbacks[event] = callback

    def train(self, **kwargs: object) -> types.SimpleNamespace:
        expected_device = 0 if torch.cuda.is_available() else "cpu"
        if kwargs.get("device") != expected_device:
            raise RuntimeError(
                f"TrainingManager passed device={kwargs.get('device')!r}, expected {expected_device!r}"
            )
        save_dir = Path(kwargs.get("data", ".")).parent / "runs" / "exp"
        weights_dir = save_dir / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        (weights_dir / "best.pt").write_bytes(b"fake-best-weights")
        return types.SimpleNamespace(save_dir=save_dir)


def _smoke_training_manager(model_path: Path) -> None:
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with tempfile.TemporaryDirectory(prefix="cuda_app_preflight_") as tmp:
        root = Path(tmp)
        yaml_path = _write_dummy_dataset(root)
        target_weights = root / "assets/models/yolo26x.pt"
        target_weights.parent.mkdir(parents=True, exist_ok=True)
        target_weights.write_bytes(b"seed")

        tm = TrainingManager(base_model=str(model_path), target_weights=target_weights)

        with patch("ultralytics.YOLO", _FakeYOLO), patch.object(
            TrainingManager, "_check_memory_requirements", lambda self: None
        ), patch.object(
            TrainingManager, "_clean_stale_caches", lambda self, dataset_yaml: None
        ), patch.object(
            TrainingManager, "_apply_ultralytics_tqdm_patch", lambda self: None
        ):
            result = tm.train(
                dataset_yaml=yaml_path,
                epochs=1,
                batch=1,
                image_size=64,
                progress_cb=None,
                metrics_cb=None,
            )

        if not result.exists():
            raise RuntimeError(f"TrainingManager did not write target weights: {result}")

        device = tm._resolve_device()
        expected_device = 0 if torch.cuda.is_available() else "cpu"
        if device != expected_device:
            raise RuntimeError(f"TrainingManager resolved device={device!r}, expected {expected_device!r}")

        print(f"[preflight_app] TrainingManager smoke OK: device={device!r}, weights={result}")


def _import_smoke() -> None:
    from PIL import Image  # noqa: PLC0415,F401
    from ultralytics import YOLO  # noqa: PLC0415,F401

    import torch.testing._internal  # noqa: PLC0415,F401

    boxes = torch.tensor([[0.0, 0.0, 10.0, 10.0]], dtype=torch.float32)
    scores = torch.tensor([0.9], dtype=torch.float32)
    torchvision.ops.nms(boxes, scores, 0.5)

    sample = np.zeros((8, 8, 3), dtype=np.uint8)
    _ = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    os.environ.setdefault("YOLO_OFFLINE", "1")
    os.environ.setdefault("ULTRALYTICS_OFFLINE", "1")
    os.environ.setdefault("WANDB_DISABLED", "true")
    os.environ.setdefault("WANDB_MODE", "disabled")
    os.environ.setdefault("COMET_MODE", "disabled")
    os.environ.setdefault("CLEARML_LOG_MODEL", "false")
    os.environ.setdefault("NEPTUNE_MODE", "offline")

    ensure_numpy_compatibility()
    ensure_torch_cuda_wheel(require_cuda_wheel=args.require_cuda_wheel)
    _import_smoke()
    _smoke_cuda_tensor()
    _smoke_training_manager(_resolve_model_path(args.model))
    print("[preflight_app] GUI CUDA fine-tuning smoke checks passed")


if __name__ == "__main__":
    main()
