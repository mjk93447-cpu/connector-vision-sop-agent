# Changelog — Connector Vision SOP Agent

All notable changes to this project will be documented in this file.

---

## [3.10.0] - 2026-03-27

### Added
- **LLM**: SmolLM3-3B → IBM Granite Vision 3.3-2b 전환 (멀티모달, DocVQA 89%, Ollama `/api/chat` 지원)
- **LLM Panel**: 스크린샷 직접 전송 기능 — 📸 버튼으로 현재 화면 캡처 후 LLM에 첨부 전송
- **SopExecutor**: `--dry-run` 모드 추가 — 실제 마우스/키보드 동작 없이 SOP 단계 검증 가능 (CI/테스트 안전)
- **SopAdvisor**: `jsonschema` 기반 config 검증 — `assets/config.schema.json` 자동 생성, 잘못된 config 즉시 감지
- **CI**: `build.yml` — integration test 및 `requires_model` 마커 테스트 스텝 자동화

### Fixed
- **Coverage**: `.coveragerc` omit 제거 — `control_engine`, `sop_executor`, `main` 커버리지 측정 정상화
- **test_main.py**: 신규 22개 단위 테스트 추가 (`tests/unit/test_main.py`)

### Chore
- git worktree 정리 (11개 → 2개)
- 전체 테스트: **638 pass** (기존 621 → +17)

---

## [3.9.1] - 2026-03-26

### Chore
- GitHub Actions: Node.js 24 opt-in (`ACTIONS_RUNNER_FORCED_INTERNAL_NODE_VERSION`) — deprecation 경고 수정

---

## [3.9.0] - 2026-03-26

### Added
- ROI Picker: `exec()` → `open()` 크래시 수정 (앱 종료 방지)
- SOP: `sop_steps.json` v2.0 — 40단계 원자화 (`wait_ms` / `type_text` / `press_key` 신규 타입)
- 전체 테스트: 599 pass

---

## [3.8.0] - 2026-03-26

### Added
- SOP 현장 요구사항 100% 이행: `auth_sequence` (LOGIN+PW+OK) / `input_text` (AXIS-X/Y) / `mold_setup` / `verify_left/right`
- 신규 스텝 타입: `type_text`, `press_key`
- 전체 테스트: 594 pass

---

## [3.7.1] - 2026-03-25

### Fixed
- ROI picker 3종 버그 수정: GC 방지 / ApplicationModal / MainWindow hide

---

## [3.7.0] - 2026-03-25

### Added
- ROI picker: 전체화면 투명 오버레이 (`_RoiOverlayWindow`) + 직접 숫자 입력

---

## [3.6.0] - 2026-03-22

### Fixed
- 필드 테스트 7개 이슈 수정 (ROI/OCR/LLM/색상/Training)
- 전체 테스트: 554 pass, 커버리지 92%+

---

## [3.2.8] - 2026-03-19

### Fixed
- Training tqdm NoneType 수정: `verbose=False→True` (tqdm disable 방지)
- `main_window.py` `set_vision_engine()` 연결

---

## [3.2.7] - 2026-03-19

### Fixed
- 법인 프록시 우회: `session.trust_env=False` + `NO_PROXY` 설정 + `_HEALTH_TIMEOUT 30s`

---

## [3.2.6] - 2026-03-19

### Fixed
- LLM 헬스체크 비치명적 처리 + `_HEALTH_TIMEOUT 1.5→5s`

---

## [3.2.5] - 2026-03-19

### Fixed
- Training 재실행 수정: `_clean_stale_caches()` — `*.cache/*.cache.npy` 사전 삭제

---

## [3.2.4] - 2026-03-19

### Added
- OCR 버튼 인식 개선: 다단어 병합 / 4종 전처리 / IoU NMS dedup
- 전체 테스트: 447 pass

---

## [3.2.3] - 2026-03-19

### Fixed
- Bug2 근본원인: `self.parent()` → `self.window()` — LLM 요청 미발송 해결

---

## [3.2.0] - 2026-03-18

### Added
- OCR: winsdk import 수정 + EasyOCR fallback
- `build.yml` 단일 워크플로우 통합 (8개 yml → 1개)

---

## [3.1.0] - 2026-03-17

### Added
- OCR-first 파이프라인, ExceptionHandler, CycleDetector, LLM 스트리밍, 영어 GUI 전환

---

## [3.0.0] - 2026-03-17

### Added
- PyQt6 7탭 GUI, Training panel, YOLO26x pretrain CI, `get_base_dir()` EXE fix

---

## [2.0.0] - 2026-02

### Added
- SmolLM3-3B LLM, Ollama 백엔드, config v2.0.0

---

## [1.0.0] - 2025-12

Initial release.
