# Connector Vision SOP Agent — CLAUDE.md

> 진행 상태: @progress.md

## ⚠️ [MANDATORY] YOLO 모델 규칙

```
YOLO 모델: yolo26x.pt 단독 사용 — YOLOv8/v9/v10/v11 절대 금지
```

## 스택 (v3.9.0)
- Python 3.11, PyTorch 2.3 CPU, OpenCV 4.10, PyAutoGUI, PyQt6
- YOLO26x (vision), Ollama HTTP (LLM: phi4-mini-reasoning)
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
| `assets/config.json` | v2.0.0 |
| `tests/unit/` | 413 pass |

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

## ★ 현재 집중 작업: Bug 2 — LLM 응답 무한 대기
- 증상: LLM Chat send 후 800초+ thinking... 무응답
- 파일: `src/llm_offline.py`, `src/gui/workers.py`, `src/gui/panels/llm_panel.py`
- 목표: timeout 처리 + Ollama 미실행/CPU-only 환경 자동 감지
