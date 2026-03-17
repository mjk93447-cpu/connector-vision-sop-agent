# YOLO26x Pretrain Report

생성일: 2026-03-17 11:19:04
베이스 모델: `yolo26x.pt` (COCO pretrained)
출력 가중치: `assets\models\yolo26x_pretrained.pt`

## 데이터셋 요약

| 구분 | 이미지 수 |
|------|-----------|
| 학습 | 48 |
| 검증 | 12 |
| 합계 | 60 |

## 평가 지표 (검증 세트)

| 지표 | 값 |
|------|-----|
| **mAP50** | **0.1534** |
| mAP50-95 | 0.1483 |
| Precision | 0.1368 |
| Recall | 0.3487 |
| Epochs | 3 |
| 학습 시간 | 254.9s (4.2분) |

## 클래스별 mAP50

| 클래스 | mAP50 |
|--------|-------|
| button | 0.2754 |
| checkbox | 0.2124 |
| icon | 0.1559 |
| connector | 0.1513 |
| label | 0.1122 |
| input_field | 0.1042 |
| dropdown | 0.0627 |

## 프리트레인 클래스 어휘 → OLED 파인튜닝 매핑

| 프리트레인 클래스 | OLED 12클래스 매핑 |
|-------------------|---------------------|
| button | login_button, apply_button, save_button, register_button, recipe_button |
| icon | open_icon, axis_mark |
| label | mold_left_label, mold_right_label |
| connector | connector_pin, pin_cluster |
| input_field | (파인튜닝 시 조정) |
| checkbox | (파인튜닝 시 조정) |
| dropdown | (파인튜닝 시 조정) |

## 다음 단계

1. `assets/models/yolo26x_pretrained.pt` → OLED 라인 파인튜닝 시작 가중치로 사용
2. GUI Tab7 Training Panel에서 `기반 모델: yolo26x_pretrained.pt` 선택
3. OLED 스크린샷 + 어노테이션 수집 후 로컬 파인튜닝 실행