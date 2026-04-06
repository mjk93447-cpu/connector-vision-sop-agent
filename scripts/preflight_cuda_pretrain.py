from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np

from src.runtime_compat import ensure_numpy_compatibility, ensure_torch_cuda_wheel


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast preflight for CUDA pretrain runtime compatibility")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Base YOLO model to load for the smoke test.",
    )
    parser.add_argument(
        "--skip-model-load",
        action="store_true",
        help="Skip YOLO model loading and run only import / ABI smoke checks.",
    )
    parser.add_argument(
        "--require-cuda-wheel",
        action="store_true",
        help="Fail unless the installed torch wheel reports CUDA support.",
    )
    return parser


def _ensure_imports() -> None:
    import cv2  # noqa: PLC0415
    import torch  # noqa: PLC0415
    import torchvision  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415,F401
    from ultralytics import YOLO  # noqa: PLC0415,F401

    # Catch the exact class of failure seen in the packaged EXE.
    import torch.testing._internal  # noqa: PLC0415,F401

    # Minimal op-kernel smoke test. If the torch/torchvision ABI is broken,
    # this tends to fail before we even reach model loading.
    boxes = torch.tensor([[0.0, 0.0, 10.0, 10.0]], dtype=torch.float32)
    scores = torch.tensor([0.9], dtype=torch.float32)
    torchvision.ops.nms(boxes, scores, 0.5)

    # OpenCV + NumPy ABI smoke.
    sample = np.zeros((8, 8, 3), dtype=np.uint8)
    _ = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)


def _smoke_cuda() -> None:
    import torch  # noqa: PLC0415

    if not torch.cuda.is_available():
        print("[preflight_cuda] CUDA not available in this environment; skipping device smoke test.")
        return

    x = torch.tensor([1.0], device="cuda")
    y = x + 1.0
    torch.cuda.synchronize()
    print(f"[preflight_cuda] CUDA tensor smoke OK: {float(y.item())}")


def _smoke_model_load(model_path: Path) -> None:
    from ultralytics import YOLO  # noqa: PLC0415

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found: {model_path}. Ensure assets/models/yolo26x.pt is bundled before the build."
        )

    model = YOLO(str(model_path))
    print(f"[preflight_cuda] YOLO load OK: {model_path}")

    import torch  # noqa: PLC0415

    device = 0 if torch.cuda.is_available() else "cpu"
    dummy = np.zeros((64, 64, 3), dtype=np.uint8)
    _ = model.predict(source=dummy, imgsz=64, device=device, verbose=False)
    print("[preflight_cuda] YOLO predict smoke OK")


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
    _ensure_imports()
    _smoke_cuda()

    if not args.skip_model_load:
        if args.model is None:
            model_path = Path("assets/models/yolo26x.pt")
            if not model_path.exists():
                model_path = Path("yolo26x.pt")
        else:
            model_path = Path(args.model).expanduser()
        _smoke_model_load(model_path)

    print("[preflight_cuda] pretrain runtime smoke checks passed")


if __name__ == "__main__":
    main()
