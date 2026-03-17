# Test Report — v2.0.0 Refactoring (CP-0 ~ CP-4)

Generated: 2026-03-16
Branch: `feature/v2/cp4-integration`
Stack: YOLO26x + Llama4 Scout (Ollama)

---

## 요약

| 항목 | 값 |
|------|-----|
| 총 테스트 수 | 157 |
| 통과 | 157 |
| 실패 | 0 |
| 활성 모듈 커버리지 | 92% |
| Python | 3.12.6 |

---

## 체크포인트별 결과

### CP-0: 테스트 인프라 구축

| 파일 | 테스트 수 | 결과 |
|------|-----------|------|
| test_config_loader.py | 11 | 통과 |
| test_sop_advisor.py | 22 | 통과 |
| test_log_manager.py | 28 | 통과 |
| test_llm_offline.py (초기) | 11 | 통과 |

**게이트**: pytest 72개 통과, 커버리지 60%+ ✅

---

### CP-1: Ollama LLM 백엔드

| 파일 | 변경 내용 |
|------|-----------|
| `src/llm_offline.py` | `_chat_ollama()` 추가, 기본 백엔드 `ollama`로 변경 |
| `assets/config.json` | v1.1.0 — `backend: ollama, model_path: llama4:scout` |
| `tests/unit/test_llm_offline.py` | `TestOllamaBackend` 10개 신규 테스트 |
| `tools/dummy_ollama_server.py` | 개발용 Mock HTTP 서버 |
| `.coveragerc` | 레거시 모듈 제외 설정 |

**게이트**: 115/115 통과, 활성 모듈 93% ✅

---

### CP-2: YOLO26x 도입 및 VisionEngine 통합

| 파일 | 변경 내용 |
|------|-----------|
| `src/vision_engine.py` | VisionAgent + VisionEngine → `VisionEngine` 단일 클래스 |
| `src/vision_engine.py` | `DetectionConfig.model_path` 필드 추가, 기본값 `yolo26x.pt` |
| `src/control_engine.py` | `VisionAgent` → `VisionEngine` 임포트 갱신 |
| `tests/unit/test_vision_engine.py` | 48개 신규 단위 테스트 |

**게이트**: 163/163 통과, 활성 모듈 87% ✅

---

### CP-3: Tesseract 완전 제거

| 파일 | 변경 내용 |
|------|-----------|
| `src/vision_engine.py` | `pytesseract` 임포트 삭제, `preprocess_for_ocr`, `read_text`, `locate_text`, `similarity`, `DetectionConfig.ocr_psm` 삭제 |
| `src/control_engine.py` | OCR 폴백 블록 (`locate_text`) 삭제 |
| `requirements.txt` | `pytesseract==0.3.13` 삭제 |
| `build_exe.spec` | `hiddenimports`에서 `pytesseract` 삭제 |

**게이트**: 157/157 통과, 활성 모듈 92% ✅

---

### CP-4: 최종 통합

| 파일 | 변경 내용 |
|------|-----------|
| `assets/config.json` | v2.0.0 — `vision` 블록 신규, `ocr_threshold` 삭제 |
| `TEST_REPORT.md` | 이 파일 |

**게이트**: 157/157 통과, 활성 모듈 92% ✅

---

## 커버리지 상세

```
Name                   Stmts   Miss  Cover   Missing
----------------------------------------------------
src/__init__.py            0      0   100%
src/config_loader.py       7      0   100%
src/init.py                0      0   100%
src/llm_offline.py        94     10    89%   192-213 (llama_cpp backend, legacy)
src/log_manager.py       102      8    92%   75,153,255-271 (pyautogui paths)
src/sop_advisor.py        55      0   100%
src/vision_engine.py     105     11    90%   93,107-114,125-126,225 (pyautogui paths)
----------------------------------------------------
TOTAL                    363     29    92%
```

*제외 모듈 (CP 대상 아님):* `main.py`, `control_engine.py`, `sop_executor.py`, `test_sop.py`

---

## 스택 전환 요약

| 항목 | 이전 (v1.x) | 이후 (v2.0) |
|------|-------------|-------------|
| YOLO 모델 | yolo26n (nano) | yolo26x (extra-large) |
| OCR | Tesseract PSM7 | 제거 (YOLO 단독) |
| LLM 백엔드 | Qwen2.5-VL GGUF (미배포) | Llama4 Scout (Ollama) |
| LLM 통신 | llama-cpp-python | HTTP (OpenAI 호환) |
| VisionEngine | VisionAgent + VisionEngine 이중 계층 | VisionEngine 단일 클래스 |
| Config | v1.0.0 | v2.0.0 (vision 블록 추가) |

---

## 알려진 미진 사항 (향후 작업)

- YOLO26x 실제 가중치: `assets/models/yolo26x.pt` 파인튜닝 후 배치 필요 (현재 COCO pretrained)
- phi4-mini-reasoning: CPU-only 환경 ~109초 지연, 한국어/중국어 혼용 응답 발생

> **완료된 정리 (레거시 삭제)**: Tesseract/OCR, llama_cpp 백엔드, VisionAgent 별칭 전부 삭제 완료 (2026-03-17)
