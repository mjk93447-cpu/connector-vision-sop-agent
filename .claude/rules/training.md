# 학습/파인튜닝 규칙 (src/training/, Tab7 작업 시 참조)

## 학습 파이프라인
- `src/training/dataset_manager.py` — YOLO 포맷 데이터셋 (images/ + labels/ + dataset.yaml)
- `src/training/training_manager.py` — ultralytics YOLO.train() 래퍼, best.pt → assets/models/yolo26x.pt
- `src/training/pretrain_pipeline.py` — 합성 데이터 프리트레인

## Tab7 파인튜닝 우선순위
1. `assets/models/yolo26x.pt` 파인튜닝됨 → 그대로 사용
2. `assets/models/yolo26x_pretrained.pt` 존재 → 이 모델로 파인튜닝 시작
3. 둘 다 없음 → `yolo26x.pt` (ultralytics 자동 다운로드)

## CI 프리트레인
- 워크플로우: `YOLO26x GUI Pretrain` (`.github/workflows/gui-pretrain.yml`)
- 기본 epochs: 20, 데이터: Rico 500장 또는 합성 500장
