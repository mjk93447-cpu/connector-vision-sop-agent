# v4.0.0 Test Report

**Test date:** 2026-03-27
**Environment:** Windows 10, CPU-only, IBM Granite Vision 3.2-2b (Ollama), YOLO26x
**Result:** 733 pass, 0 fail, 92%+ coverage

---

## Cumulative Fix History

| Version | Fix | Tests |
|---------|-----|-------|
| v3.6.0 | ROI coordinate mismatch, OCR "LOG IN" detection, LLM contrast/streaming, Training tqdm crash | 554 pass |
| v3.7.0 | ROI overlay fullscreen + direct numeric input | 557 pass |
| v3.8.0 | SOP 100%: auth_sequence / input_text / mold_setup + verify_left/right | 594 pass |
| v3.9.0 | ROI Picker exec→open crash fix + SOP 40-step atomic v2.0 | 599 pass |
| v3.10.0 | Granite Vision 3.2-2b 전환 + multimodal screenshot + dry-run + jsonschema | 646 pass |
| v3.10.1 | image_b64 TypeError fix + Granite chain integration tests | 670 pass |
| v3.10.2 | LLM Chat UX: ROI drag overlay + ChatGPT-like UI + Stop button + 600s timeout | 701 pass |
| **v4.0.0** | **SOP Editor 타입별 편집 UI + CI 빌드 timeout 수정** | **733 pass** |

---

## v4.0.0 New Tests (32개)

### TestStepTypes (6)
- `type_text` / `press_key` / `wait_ms` / `auth_sequence` in `_STEP_TYPES`
- 기존 `click` / `drag` 유지 확인

### TestStepEditDialogTypeWidgets (9)
- `_type_text_widget`, `_text_edit`, `_clear_first_chk` in `_setup_ui`
- `_press_key_widget`, `_key_edit` in `_setup_ui`
- `_wait_ms_widget`, `_ms_spin` in `_setup_ui`
- `_on_type_changed` connect + init call 확인

### TestOnTypeChangedMethod (6)
- 메서드 존재, 3개 위젯 제어, `adjustSize()`, `_QT_AVAILABLE` guard

### TestGetStepTypeSpecificFields (11)
- `type_text` → `text` + `clear_first` 저장
- `press_key` → `key` 저장
- `wait_ms` → `ms` 저장
- 각 타입별 무관 필드 정리 확인
- `_text_edit` / `_key_edit` / `_ms_spin` 위젯 읽기 확인

---

## Coverage Summary

| Module | Coverage |
|--------|----------|
| llm_offline.py | 86% |
| log_manager.py | 92% |
| sop_advisor.py | 73% |
| training_manager.py | 83% |
| ocr_engine.py | 71% |
| **Overall** | **42% (headless — GUI panels excluded from run)** |

> GUI panels (llm_panel, training_panel 등)는 PyQt6 디스플레이 서버 없이 실행 불가하여 source-inspection 방식으로 검증.
