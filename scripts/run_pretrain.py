"""
YOLO26x 프리트레인 실행 스크립트.

사용법:
  # 합성 데이터로 빠른 테스트 (의존성 없음)
  python scripts/run_pretrain.py --source synthetic --n-images 200 --epochs 20

  # Rico WidgetCaptioning (HuggingFace datasets 필요)
  python scripts/run_pretrain.py --source rico_widget --max-samples 500 --epochs 30

  # 커스텀 설정
  python scripts/run_pretrain.py --source synthetic --n-images 500 --epochs 50 --batch 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (스크립트 직접 실행 시)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.training.pretrain_pipeline import PretrainConfig, PretrainPipeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="YOLO26x 프리트레인 파이프라인")
    parser.add_argument(
        "--source",
        choices=["synthetic", "rico_widget"],
        default="synthetic",
        help="데이터 소스 (기본: synthetic)",
    )
    parser.add_argument(
        "--n-images",
        type=int,
        default=200,
        help="합성 데이터 이미지 수 (source=synthetic 시 사용, 기본: 200)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=500,
        help="Rico 최대 샘플 수 (source=rico_widget 시 사용, 기본: 500)",
    )
    parser.add_argument(
        "--epochs", type=int, default=20, help="학습 에포크 수 (기본: 20)"
    )
    parser.add_argument("--batch", type=int, default=4, help="배치 크기 (기본: 4)")
    parser.add_argument(
        "--imgsz", type=int, default=640, help="이미지 크기 (기본: 640)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="pretrain_data",
        help="출력 디렉터리 (기본: pretrain_data/)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="PRETRAIN_REPORT.md",
        help="결과 리포트 저장 경로 (기본: PRETRAIN_REPORT.md)",
    )
    args = parser.parse_args()

    cfg = PretrainConfig(
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch=args.batch,
        image_size=args.imgsz,
    )
    pipeline = PretrainPipeline(output_dir=args.output_dir, config=cfg)

    # 데이터셋 구축
    if args.source == "synthetic":
        pipeline.build_synthetic_dataset(n_images=args.n_images)
    elif args.source == "rico_widget":
        pipeline.build_rico_dataset(max_samples=args.max_samples)

    # 학습 + 평가
    print(f"\n[run_pretrain] 학습 시작 (epochs={args.epochs}, batch={args.batch})...")
    metrics = pipeline.train_and_evaluate(epochs=args.epochs, batch=args.batch)

    # 결과 출력
    print("\n" + "=" * 50)
    print("  PRETRAIN 결과 요약")
    print("=" * 50)
    print(f"  mAP50     : {metrics['map50']:.4f}")
    print(f"  mAP50-95  : {metrics['map50_95']:.4f}")
    print(f"  Precision : {metrics['precision']:.4f}")
    print(f"  Recall    : {metrics['recall']:.4f}")
    print(f"  학습 시간 : {metrics['elapsed_sec']:.1f}s")
    print(f"  가중치    : {metrics['weights']}")
    print("=" * 50)

    if metrics.get("classes"):
        print("\n  클래스별 mAP50:")
        for cls, v in sorted(metrics["classes"].items(), key=lambda x: -x[1]):
            print(f"    {cls:<15} {v:.4f}")

    # 리포트 저장
    report_path = pipeline.save_report(metrics, path=Path(args.report))
    print(f"\n[run_pretrain] 리포트 저장 완료 → {report_path}")


if __name__ == "__main__":
    main()
