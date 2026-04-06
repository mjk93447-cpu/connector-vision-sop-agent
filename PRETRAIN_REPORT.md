# YOLO26x Pretrain Report

**⚠️ 중요 변경 (2026-04-01)**:  
Pretrain 학습은 이제 **Tier A 실사 데이터셋만** 사용합니다.  
Synthetic 데이터셋은 더 이상 학습에 사용되지 않으며 코드에서 제거되었습니다.

베이스 모델: `yolo26x.pt` (COCO pretrained)
출력 가중치: `assets\models\yolo26x_pretrain.pt`

## Tier A 실사 데이터셋 (현재 사용)

| 출처 | 내용 | 예상 이미지 | 라벨 형식 |
|------|------|-----------|----------|
| **MSD** | 스마트폰 표면 결함 | ~1,000+ | YOLO txt |
| **SSGD** | 스마트폰 스크린 글라스 결함 | ~500+ | YOLO txt |
| **DeepPCB** | PCB 결함 (bbox 완비) | ~1,000+ | YOLO txt |
| **Roboflow** | PCB/Connector/Fiducial | ~5,000+ | YOLO txt |

## 평가 지표 (Tier A 실사 데이터셋 기반)

| 지표 | 값 |
|------|-----|
| **mAP50** | **0.1534** |
| mAP50-95 | 0.1483 |
| Precision | 0.1368 |
| Recall | 0.3487 |
| Epochs | 3 |
| 학습 시간 | 254.9s (4.2분) |

## 클래스별 mAP50

| 클래스 | 설명 | 데이터 출처 |
|--------|------|----------|
| oled_inspection_top_view | OLED 패널 상단 검사 영역 (스마트폰 표면) | MSD, SSGD |
| connector_pin_cluster_upper | 커넥터 핀 클러스터 상단 | DeepPCB, Roboflow |
| connector_pin_cluster_lower | 커넥터 핀 클러스터 하단 | DeepPCB, Roboflow |
| connector_pin_mold_left | 커넥터 핀 틀 좌측 | DeepPCB, Roboflow |
| connector_pin_mold_right | 커넥터 핀 틀 우측 | DeepPCB, Roboflow |
| oled_panel_marker | OLED 패널 마크/결함 (스크린 글라스) | SSGD, Roboflow |

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

1. `assets/models/yolo26x_pretrain.pt` → GitHub/cloud pretrain 시작 가중치로 사용
2. GUI Tab7 Training Panel에서 `기반 모델: yolo26x_pretrain.pt` 선택
3. `assets/models/yolo26x_local_pretrained.pt` → GitHub artifact timeout 시 local/offline pretrain 결과로 사용
4. OLED 스크린샷 + 어노테이션 수집 후 로컬 파인튜닝 실행
