"""Optional manual pretrain dataset builder for developer work only.

This script is not used by the GitHub pretrain artifact build.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.training.compact_pretrain_pipeline import (  # noqa: E402
    CompactPretrainPipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare compact PCB electronics pretrain data")
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
    parser.add_argument(
        "--sources",
        default=None,
        help="Optional comma-separated source names to include in the bundle.",
    )
    args = parser.parse_args()

    source_names = None
    if args.sources:
        source_names = [item.strip() for item in args.sources.split(",") if item.strip()]

    pipeline = CompactPretrainPipeline(output_dir=args.output_dir)
    manifest = pipeline.build_bundle(
        max_samples_per_source=args.max_samples_per_source,
        grayscale=not args.no_grayscale,
        reset=True,
        source_names=source_names,
    )
    print("[prepare_pretrain_data] bundle ready")
    print(manifest)


if __name__ == "__main__":
    main()

