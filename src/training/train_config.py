"""
OLED 라인 특화 YOLO 학습 파라미터 (detection 전용).

흑백 이미지(hsv_h/s=0), 핀 방향 고정(fliplr=0),
소량 데이터 과적합 방지(freeze=15), Early Stopping(patience=20).

주의: overlap_mask / mask_ratio 는 segmentation 전용 — 여기서 사용 안 함.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Fine-tuning (현장 PC, 200+ 장)
# ---------------------------------------------------------------------------
OLED_TRAIN_PARAMS: dict = {
    # Learning Rate — COCO 사전학습 → 산업 도메인 갭 고려
    "lr0": 0.001,
    "lrf": 0.01,
    "warmup_epochs": 5,
    # 소량 데이터 과적합 방지: backbone 15레이어 freeze
    "freeze": 15,
    # Early Stopping
    "patience": 20,
    # Augmentation — OLED 흑백 라인 특화
    "hsv_h": 0.0,  # 흑백: 색상(Hue) augment 비활성
    "hsv_s": 0.0,  # 흑백: 채도(Saturation) 비활성
    "hsv_v": 0.3,  # 밝기(Value)만 ±30% 허용
    "fliplr": 0.0,  # 핀 방향 고정 → 좌우 flip 비활성
    "mosaic": 0.5,  # mosaic 50% 확률 (다양한 레이아웃 학습)
    # v4.1.1: Geometric augmentation — 카메라 기울기/거리/위치 변동 내성
    "degrees": 5.0,  # ±5° rotation (카메라 미세 기울기)
    "translate": 0.1,  # ±10% translation (객체 위치 변동)
    "scale": 0.3,  # ±30% scale variation (카메라 거리)
    "shear": 0.0,  # shear 없음 (고정 마운트)
    "perspective": 0.0,  # perspective 없음 (고정 각도)
    "erasing": 0.1,  # 10% random erasing (가림 내성)
    # 저장 주기 및 출력
    "save_period": 10,
    "plots": True,
}

# ---------------------------------------------------------------------------
# Pretrain (CI 환경 — 합성 데이터, 배치/메모리 제약)
# ---------------------------------------------------------------------------
OLED_PRETRAIN_PARAMS: dict = {
    **OLED_TRAIN_PARAMS,
    "freeze": 10,  # pretrain: backbone freeze 완화 (합성 이미지 포함)
    "plots": False,  # CI에서 matplotlib 렌더링 오류 방지
    "save_period": 5,
    "degrees": 3.0,  # 합성 데이터는 더 보수적인 rotation
    "erasing": 0.0,  # 합성 데이터는 이미 다양 → erasing 불필요
}
