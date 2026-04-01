# Connector Vision SOP Agent — CLAUDE.md

> 진행 상태: @progress.md

## ⚠️ [MANDATORY] YOLO 모델 규칙

```
YOLO 모델: yolo26x.pt 단독 사용 — YOLOv8/v9/v10/v11 절대 금지
```

## 스택 (v4.0.0)
- Python 3.11, PyTorch 2.3 CPU, OpenCV 4.10, PyAutoGUI, PyQt6
- YOLO26x (vision), Ollama HTTP (LLM: IBM Granite Vision 3.2-2b)
- OCR: winsdk(WinRT) → easyocr → paddleocr (자동 선택)
- pytest, black + ruff, PyInstaller EXE

## 절대 수정 금지
```
assets/models/
```

## 핵심 파일
| 파일 | 역할 |
|------|------|
| `src/main.py` | 진입점 + OCR 헬스체크 |
| `src/llm_offline.py` | Ollama HTTP 백엔드 (Bug2 대상) |
| `src/ocr_engine.py` | WinRT/EasyOCR/PaddleOCR |
| `src/vision_engine.py` | YOLO26x 단일 클래스 |
| `src/control_engine.py` | PyAutoGUI 제어 |
| `src/sop_executor.py` | SOP 실행 |
| `src/gui/` | PyQt6 7탭 GUI |
| `assets/config.json` | v4.0.0 |
| `tests/unit/` | 733 pass |

## 커맨드
```bash
bash run_tests.sh                          # 테스트 + 커버리지
python -m black src/ tests/ && python -m ruff check src/ tests/ --fix
gh workflow run "Build Connector Vision Agent (All-in-One)" --ref main
```

## 규칙
1. 코드 수정 → `bash run_tests.sh` 통과 → black+ruff → 커밋
2. 커밋: `[feat/fix/refactor/chore/test] 한국어 설명`
3. 테스트 실패 → 원인 분석 후 재시도 (동일 커맨드 반복 금지)

## 세션 습관
시작→@progress.md | 완료→/compact | 전환→/clear | 종료→progress.md커밋

## 참조 규칙
- config 구조 → `.claude/rules/config-schema.md`
- 빌드 → `.claude/rules/build.md`
- Vision/학습/테스트 → `.claude/rules/vision.md`, `training.md`, `testing.md`

## ⚠️ Pretrain 정책 (v4.0.0, 2026-04-01)

**Tier A 실사 데이터셋만 사용 — Synthetic 제거됨**

```
Synthetic 데이터셋: ❌ 더 이상 학습에 사용하지 않음 (코드에서 제거)
Tier A 실사: ✅ MSD / SSGD / DeepPCB / Roboflow
```

### Pretrain 워크플로우
1. **CI 단계** (workflow): Tier A 데이터셋 다운로드 → 아티펙트 번들 생성
2. **로컬 고사양 PC**: 아티펙트 다운로드 → `start_pretrain.bat` 실행 → GPU로 학습
3. **결과**: `assets/models/yolo26x_local_pretrained.pt` 생성

### Tier A 데이터셋 구성
| 출처 | 용도 | 라이선스 | 예상 이미지 |
|------|------|--------|-----------|
| MSD | 스마트폰 표면 결함 | GPL | ~1,000+ |
| SSGD | 스크린 글라스 결함 | MIT | ~500+ |
| DeepPCB | PCB 결함 (bbox) | 학술용 | ~1,000+ |
| Roboflow | PCB/Connector/Fiducial | 프로젝트별 | ~5,000+ |

## ★ 현재 상태: v4.0.0 — SOP Editor 타입별 편집 + Tier A Pretrain

- SOP Editor (Tab 4): type_text/press_key/wait_ms/auth_sequence 타입별 전용 입력 필드
- LLM Chat ROI: 📸 버튼 → 드래그로 영역 선택 → 800px/JPEG q80 압축
- ChatGPT-like UI: 즉시 ETA 표시, token count 실시간, cold/warm 상태 구분
- Stop 버튼 실제 동작: ⏹ Stop → HTTP 즉시 취소 + 부분 버블 제거 + 상태 복구
- CI 빌드 수정: integration test timeout 분리 (unit 60s / integ 300s)
- 733 pass, 92%+ coverage
