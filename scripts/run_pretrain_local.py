"""Prompt-based local launcher for compact YOLO26x pretraining."""

from __future__ import annotations

import argparse
from multiprocessing import freeze_support
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.pretrain_runtime import (  # noqa: E402
    count_prepared_images,
    detect_pretrain_hardware,
    resolve_pretrain_data_root,
    suggest_pretrain_profile,
)

_PIPELINE_IMPORT_ERROR: ImportError | None = None
try:
    from src.training.compact_pretrain_pipeline import (  # noqa: E402
        CompactPretrainConfig,
        CompactPretrainPipeline,
    )
except ImportError as exc:  # pragma: no cover - exercised in packaged EXE failure cases
    _PIPELINE_IMPORT_ERROR = exc
    CompactPretrainConfig = None  # type: ignore[assignment]
    CompactPretrainPipeline = None  # type: ignore[assignment]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compact YOLO26x local pretrain")
    parser.add_argument("--epochs", type=int, default=None, help="Training epochs.")
    parser.add_argument("--batch", type=int, default=None, help="Training batch size.")
    parser.add_argument("--imgsz", type=int, default=None, help="Training image size.")
    parser.add_argument("--workers", type=int, default=None, help="Data loader workers.")
    parser.add_argument("--data-root", type=str, default=None, help="Pretrain data root.")
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Optional device override: auto/cpu/0",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected profile and exit without training.",
    )
    parser.add_argument(
        "--skip-bundle-prep",
        action="store_true",
        help="Skip auto-building the pretrain dataset bundle when splits are missing.",
    )
    return parser


def main() -> None:
    freeze_support()
    parser = _build_parser()
    args = parser.parse_args()

    if _PIPELINE_IMPORT_ERROR is not None or CompactPretrainPipeline is None:
        print("[run_pretrain] Failed to load the compact pretrain pipeline.")
        print(f"[run_pretrain] Import error: {_PIPELINE_IMPORT_ERROR!r}")
        print(
            "[run_pretrain] This usually means the EXE was built without the full "
            "numpy/cv2/dataset bundle. Rebuild with the updated PyInstaller spec."
        )
        raise SystemExit(1)

    output_dir = resolve_pretrain_data_root(args.data_root)
    cfg = CompactPretrainConfig(output_dir=output_dir)
    pipeline = CompactPretrainPipeline(output_dir=output_dir, config=cfg)

    hardware = detect_pretrain_hardware()
    image_count = count_prepared_images(output_dir)
    profile = suggest_pretrain_profile(image_count=image_count)

    train_device = profile.device
    if args.device is not None:
        if args.device.lower() == "cpu":
            train_device = "cpu"
        elif args.device.lower() == "auto":
            train_device = profile.device
        elif args.device.lower() in {"0", "cuda", "cuda:0", "gpu"}:
            train_device = 0
        else:
            train_device = args.device

    profile = suggest_pretrain_profile(image_count=image_count, explicit_device=train_device)
    train_epochs = args.epochs if args.epochs is not None else profile.epochs
    train_batch = args.batch if args.batch is not None else profile.batch
    train_imgsz = args.imgsz if args.imgsz is not None else profile.image_size
    train_workers = args.workers if args.workers is not None else profile.workers

    train_path = output_dir / "train" / "images"
    val_path = output_dir / "val" / "images"
    if not train_path.exists() or not val_path.exists():
        if args.skip_bundle_prep:
            print("[run_pretrain] Dataset split missing. Bundle prep skipped by flag.")
        else:
            print("[run_pretrain] Dataset split missing. Preparing bundle in place...")
            pipeline.build_bundle(max_samples_per_source=10000, grayscale=True, reset=False)
            image_count = count_prepared_images(output_dir)
            profile = suggest_pretrain_profile(image_count=image_count, explicit_device=train_device)
            if args.epochs is None:
                train_epochs = profile.epochs
            if args.batch is None:
                train_batch = profile.batch
            if args.imgsz is None:
                train_imgsz = profile.image_size
            if args.workers is None:
                train_workers = profile.workers

    pipeline.prepare_dataset_yaml()

    print(
        "[run_pretrain] profile "
        f"device={train_device} gpu={hardware.get('name')} vram={hardware.get('memory_gb')}GB "
        f"ram={hardware.get('ram_gb')}GB cores={hardware.get('physical_cores')} "
        f"epochs={train_epochs} batch={train_batch} imgsz={train_imgsz} "
        f"workers={train_workers} data={output_dir} images={image_count}"
    )

    if args.dry_run:
        return

    weights = pipeline.train_and_save(
        epochs=train_epochs,
        batch=train_batch,
        device=train_device,
        imgsz=train_imgsz,
        workers=train_workers,
    )
    print(f"[run_pretrain] finished -> {weights}")


if __name__ == "__main__":
    main()
