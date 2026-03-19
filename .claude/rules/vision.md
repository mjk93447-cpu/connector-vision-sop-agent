# Vision 관련 규칙 (src/vision_engine.py, assets/models/ 작업 시 참조)

## MANDATORY: yolo26x.pt 단독 사용
- `from ultralytics import YOLO; YOLO("yolo26x.pt")` 만 허용
- YOLOv8/v9/v10/v11 호출 절대 금지

## 핵심 파일
- `src/vision_engine.py` — YOLO26x 단일 클래스
- `assets/models/yolo26x.pt` — 베이스 모델 (수정 금지)
- `assets/models/yolo26x_pretrained.pt` — GUI 프리트레인 결과 (CI 빌드)

## confidence threshold
- 기본값: 0.6 (`assets/config.json` vision.confidence_threshold)
- 변경 시 → `assets/config.proposed.json`만 수정
