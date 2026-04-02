"""Prepare the bundled compact pretrain dataset for offline training."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.training.compact_pretrain_pipeline import (  # noqa: E402
    CompactPretrainPipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare compact PCB defect pretrain data")
    parser.add_argument(
        "--output-dir",
        default="pretrain_data",
        help="Dataset output directory.",
    )
    parser.add_argument(
        "--max-samples-per-source",
        type=int,
        default=10000,
        help="Maximum usable samples to keep from each source dataset.",
    )
    parser.add_argument(
        "--no-grayscale",
        action="store_true",
        help="Keep the original color images instead of converting to grayscale.",
    )
    args = parser.parse_args()

    pipeline = CompactPretrainPipeline(output_dir=args.output_dir)
    manifest = pipeline.build_bundle(
        max_samples_per_source=args.max_samples_per_source,
        grayscale=not args.no_grayscale,
        reset=True,
    )
    print("[prepare_pretrain_data] bundle ready")
    print(manifest)


if __name__ == "__main__":
    main()
