"""
YOLO26x 프리트레인 실행 스크립트.

사용법:
  # OLED 라인 특화 흑백 커넥터/핀/몰드 합성 데이터 (권장: CI 기본값, API 키 불필요)
  python scripts/run_pretrain.py --source oled_synthetic --n-images 300 --epochs 30

  # Roboflow PCB-Components (실제 커넥터 이미지 — ROBOFLOW_API_KEY 필요)
  ROBOFLOW_API_KEY=<your_key> python scripts/run_pretrain.py --source pcb_components --max-samples 500 --epochs 30

  # ShowUI-Desktop (Windows/Mac/Linux 데스크탑 실제 GUI)
  python scripts/run_pretrain.py --source showui_desktop --max-samples 500 --epochs 20

  # 범용 합성 데이터 (컬러 GUI 버튼/아이콘 — OLED 공정 부적합, 테스트용)
  python scripts/run_pretrain.py --source synthetic --n-images 200 --epochs 20

  # Rico WidgetCaptioning (레거시: Android UI, 구형 Windows에는 부적합)
  python scripts/run_pretrain.py --source rico_widget --max-samples 500 --epochs 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (스크립트 직접 실행 시)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.training.pretrain_pipeline import (  # noqa: E402
    PretrainConfig,
    PretrainPipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="YOLO26x 프리트레인 파이프라인")
    parser.add_argument(
        "--source",
        choices=[
            "oled_synthetic",
            "showui_desktop",
            "synthetic",
            "rico_widget",
            "pcb_components",
        ],
        default="oled_synthetic",
        help="데이터 소스 (기본: oled_synthetic — OLED 라인 흑백 커넥터/핀/몰드)",
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
    if args.source == "oled_synthetic":
        pipeline.build_oled_dataset(n_images=args.n_images)
    elif args.source == "showui_desktop":
        pipeline.build_showui_desktop_dataset(max_samples=args.max_samples)
    elif args.source == "synthetic":
        pipeline.build_synthetic_dataset(n_images=args.n_images)
    elif args.source == "rico_widget":
        pipeline.build_rico_dataset(max_samples=args.max_samples)
    elif args.source == "pcb_components":
        import os  # noqa: PLC0415

        pipeline.build_pcb_components_dataset(
            max_samples=args.max_samples,
            api_key=os.environ.get("ROBOFLOW_API_KEY"),
        )

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
