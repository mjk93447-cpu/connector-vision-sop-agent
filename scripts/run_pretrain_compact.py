"""Compact pretrain runner (epochs + batch minimal input)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_loader import suggest_training_profile
from src.training.pretrain_pipeline import PretrainConfig, PretrainPipeline
from src.training.dataset_manifest import DatasetManifest, DatasetManifestError


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact pretrain runner (Tier A real datasets only)")
    parser.add_argument("--epochs", type=int, required=True, help="학습 epoch")
    parser.add_argument("--batch", type=int, required=True, help="배치 크기")
    parser.add_argument(
        "--source",
        choices=["msd", "ssgd", "deeppcb", "roboflow"],
        default="msd",
        help="Tier A 실사 데이터 소스 (synthetic 제거됨)"
    )
    parser.add_argument("--manifest", type=str, default="pretrain_dataset_manifest.yaml", help="dataset manifest path")
    parser.add_argument("--output-dir", type=str, default="pretrain_data", help="output directory")
    parser.add_argument("--device", type=str, default=None, help="트레이닝 디바이스 (cpu/cuda)")
    parser.add_argument("--mode", choices=["pretrain", "finetune"], default="pretrain", help="학습 모드")

    args = parser.parse_args()

    if Path(args.manifest).exists():
        try:
            manifest = DatasetManifest(args.manifest)
            manifest.validate()
            active_sources = manifest.active_sources
            print(f"[run_pretrain_compact] active sources from manifest: {active_sources}")
        except DatasetManifestError as ex:
            raise
    else:
        print(f"[run_pretrain_compact] Manifest not found: {args.manifest}, continuing with source={args.source}")

    profile = suggest_training_profile()
    if args.device:
        device = args.device
    else:
        device = profile.get("device", "cpu")

    cfg = PretrainConfig(
        output_dir=args.output_dir,
        mode=args.mode,
        epochs=args.epochs,
        batch=args.batch,
        device=device,
        manifest_path=Path(args.manifest) if Path(args.manifest).exists() else None,
        gray_ratio=0.85,
        rebalance=True,
    )

    pipeline = PretrainPipeline(output_dir=args.output_dir, config=cfg)

    # Tier A 실사 데이터셋 로더 (Synthetic 제거됨)
    if args.source == "msd":
        print("[run_pretrain_compact] Loading MSD (smartphone surface defects)...")
        pipeline.build_msd_dataset(max_samples=500)
    elif args.source == "ssgd":
        print("[run_pretrain_compact] Loading SSGD (screen glass defects)...")
        pipeline.build_ssgd_dataset(max_samples=500)
    elif args.source == "deeppcb":
        print("[run_pretrain_compact] Loading DeepPCB (PCB defects)...")
        pipeline.build_deeppcb_dataset(max_samples=500)
    elif args.source == "roboflow":
        print("[run_pretrain_compact] Loading Roboflow (PCB/Connector/Fiducial)...")
        import os  # noqa: PLC0415
        pipeline.build_pcb_components_dataset(
            max_samples=500,
            api_key=os.environ.get("ROBOFLOW_API_KEY"),
        )

    metrics = pipeline.train_and_evaluate(epochs=args.epochs, batch=args.batch)
    pipeline.save_report(metrics)

    print(f"[run_pretrain_compact] complete. weights: {metrics.get('weights')}")


if __name__ == "__main__":
    main()



if __name__ == "__main__":
    main()
