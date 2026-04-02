"""Prompt-based local launcher for compact YOLO26x pretraining."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_loader import get_base_dir  # noqa: E402
from src.training.compact_pretrain_pipeline import (  # noqa: E402
    CompactPretrainConfig,
    CompactPretrainPipeline,
)


def _resolve_output_dir() -> Path:
    base_dir = get_base_dir()
    for name in ("pretrain_data", "pretrain_data_test"):
        candidate = base_dir / name
        if candidate.exists():
            return candidate
    return base_dir / "pretrain_data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact YOLO26x local pretrain")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs.")
    parser.add_argument("--batch", type=int, default=16, help="Training batch size.")
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Optional device override: auto/cpu/0",
    )
    args = parser.parse_args()

    output_dir = _resolve_output_dir()
    cfg = CompactPretrainConfig(output_dir=output_dir)
    pipeline = CompactPretrainPipeline(output_dir=output_dir, config=cfg)

    train_path = output_dir / "train" / "images"
    val_path = output_dir / "val" / "images"
    if not train_path.exists() or not val_path.exists():
        print("[run_pretrain] Dataset split missing. Preparing bundle in place...")
        pipeline.build_bundle(max_samples_per_source=10000, grayscale=True, reset=False)

    if args.device is not None:
        if args.device.lower() == "cpu":
            cfg.device = "cpu"
        elif args.device.lower() in {"0", "cuda", "cuda:0", "gpu"}:
            cfg.device = 0
        else:
            cfg.device = args.device

    print(
        f"[run_pretrain] start epochs={args.epochs} batch={args.batch} "
        f"device={cfg.device} data={output_dir}"
    )
    weights = pipeline.train_and_save(
        epochs=args.epochs,
        batch=args.batch,
        device=cfg.device,
    )
    print(f"[run_pretrain] finished -> {weights}")


if __name__ == "__main__":
    main()
