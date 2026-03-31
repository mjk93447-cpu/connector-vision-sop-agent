"""Local pretrain launcher for Connector Vision SOP Agent."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_loader import (  # noqa: E402
    get_base_dir,
    resolve_app_path,
    suggest_training_profile,
)
from src.training.pretrain_pipeline import (  # noqa: E402
    PretrainConfig,
    PretrainPipeline,
)


def _resolve_output_dir(value: str | None) -> Path:
    if value:
        return Path(value)
    base_dir = get_base_dir()
    for name in ("pretrain_data", "pretrain_data_test"):
        candidate = base_dir / name
        image_count = (
            len(list(candidate.rglob("*.png")))
            if candidate.exists()
            else 0
        )
        if image_count > 0:
            return candidate
    for name in ("pretrain_data", "pretrain_data_test"):
        candidate = base_dir / name
        if candidate.exists():
            return candidate
    return base_dir / "pretrain_data"


def _resolve_device(value: str | None, profile: dict[str, Any]) -> Any:
    if value is None or value == "auto":
        return profile["device"]
    lowered = value.lower()
    if lowered == "cpu":
        return "cpu"
    if lowered in {"cuda", "cuda:0", "gpu"}:
        return 0
    try:
        return int(value)
    except ValueError:
        return value


def _maybe_build_dataset(
    pipeline: PretrainPipeline,
    source: str,
    n_images: int,
    max_samples: int,
) -> int:
    if source == "local_bundle":
        existing = pipeline._image_count()
        if existing > 0:
            return existing
        print(
            "[run_pretrain] Local bundle data not found. "
            "Falling back to synthetic data."
        )
        return pipeline.build_synthetic_dataset(n_images=n_images)

    if source == "showui_desktop":
        return pipeline.build_showui_desktop_dataset(max_samples=max_samples)
    if source == "synthetic":
        return pipeline.build_synthetic_dataset(n_images=n_images)
    if source == "rico_widget":
        return pipeline.build_rico_dataset(max_samples=max_samples)
    if source == "pcb_components":
        return pipeline.build_pcb_components_dataset(
            max_samples=max_samples,
            api_key=os.environ.get("ROBOFLOW_API_KEY"),
        )
    raise ValueError(f"Unsupported source: {source}")


def main() -> None:
    parser = argparse.ArgumentParser(description="YOLO26x local pretrain launcher")
    parser.add_argument(
        "--source",
        choices=["local_bundle", "showui_desktop", "synthetic", "rico_widget", "pcb_components"],
        default="local_bundle",
        help="Dataset source. local_bundle uses the bundled pretrain_data folder.",
    )
    parser.add_argument(
        "--n-images",
        type=int,
        default=120,
        help="Synthetic fallback image count.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=120,
        help="Maximum samples for external datasets.",
    )
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs.")
    parser.add_argument("--batch", type=int, default=None, help="Override batch size.")
    parser.add_argument("--imgsz", type=int, default=None, help="Override image size.")
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Override device: auto/cpu/0/cuda.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Pretrain workspace directory. Defaults to bundled pretrain_data.",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Report path. Defaults to the project or EXE directory.",
    )
    args = parser.parse_args()

    output_dir = _resolve_output_dir(args.output_dir)
    pipeline = PretrainPipeline(output_dir=output_dir)

    image_count = _maybe_build_dataset(
        pipeline=pipeline,
        source=args.source,
        n_images=args.n_images,
        max_samples=args.max_samples,
    )

    profile = suggest_training_profile(image_count=image_count)
    epochs = args.epochs if args.epochs is not None else profile["epochs"]
    batch = args.batch if args.batch is not None else profile["batch"]
    imgsz = args.imgsz if args.imgsz is not None else profile["image_size"]
    device = _resolve_device(args.device, profile)

    cfg = PretrainConfig(
        output_dir=output_dir,
        epochs=epochs,
        batch=batch,
        image_size=imgsz,
        device=device,
    )
    pipeline = PretrainPipeline(output_dir=output_dir, config=cfg)

    print(
        f"\n[run_pretrain] start source={args.source} "
        f"images={image_count} epochs={epochs} batch={batch} imgsz={imgsz} "
        f"device={device}"
    )
    metrics = pipeline.train_and_evaluate(epochs=epochs, batch=batch)

    print("\n" + "=" * 50)
    print("  PRETRAIN SUMMARY")
    print("=" * 50)
    print(f"  mAP50     : {metrics['map50']:.4f}")
    print(f"  mAP50-95  : {metrics['map50_95']:.4f}")
    print(f"  Precision : {metrics['precision']:.4f}")
    print(f"  Recall    : {metrics['recall']:.4f}")
    print(f"  Time      : {metrics['elapsed_sec']:.1f}s")
    print(f"  Weights   : {metrics['weights']}")
    print("=" * 50)

    if metrics.get("classes"):
        print("\n  Per-class mAP50:")
        for cls, value in sorted(metrics["classes"].items(), key=lambda x: -x[1]):
            print(f"    {cls:<15} {value:.4f}")

    report_target = (
        Path(args.report) if args.report else resolve_app_path("PRETRAIN_REPORT.md")
    )
    report_path = pipeline.save_report(metrics, path=report_target)
    print(f"\n[run_pretrain] report saved -> {report_path}")


if __name__ == "__main__":
    main()
