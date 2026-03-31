# Progress — Connector Vision SOP Agent

_최종 갱신: 2026-03-31 (v4.1.1 개발 완료 — 버전 관리 모듈 + YOLO26x 흑백 인식 성능 개선 + 775 pass)_

## 현재 브랜치
`claude/vigorous-gates` (v4.1.1 커밋 완료, CI 빌드 진행 중)

## 완료 체크포인트
| CP | 내용 | 테스트 | 커버리지 |
|----|------|--------|----------|
| CP-0 | pytest 인프라, conftest | 72 pass | 60%+ |
| CP-1 | Ollama LLM 백엔드 | 115 pass | 93% |
| CP-2 | YOLO26x, VisionEngine 단일 클래스 | 163 pass | 87% |
| CP-3 | Tesseract 완전 제거 | 157 pass | 92% |
| CP-4 | config v2.0.0, TEST_REPORT.md | 157 pass | 92% |
| fix | config_loader EXE 경로, 포터블 번들 구조 | 163 pass | 92% |
| GUI Phase 1 | PyQt6 6탭 MainWindow + sop_steps.json 외부화 | 210 pass | — |
| **GUI Phase 2** | **Vision Canvas 실시간 연결 + LLM 로그 분석 실제 연동** | **210 pass** | — |
| **Training** | **Tab7: BBox 어노테이션+DatasetManager+TrainingManager+YOLO26x 베이스** | **210 pass** | — |
| **레거시 정리** | **llama_cpp/VisionAgent/ocr_threshold 완전 제거 + 시나리오 테스트** | **215 pass** | — |
| **YOLO26x 확정** | **yolo26n/yolov8 잔재 전부 제거, 문서 업데이트** | **242 pass** | — |
| **프리트레인 파이프라인** | **PretrainPipeline+DatasetConverter+run_pretrain.py + mAP50 실측** | **242 pass** | — |
| **YOLO26x 전용 규칙** | **CLAUDE.md MANDATORY 규칙 + GUI Pretrain CI 워크플로우** | **254 pass** | — |
| **OCR-First 파이프라인** | **OCREngine+ExceptionHandler+CycleDetector+LLM 스트리밍+영어 GUI 전환** | **336 pass** | — |
| **통팩 빌드 준비** | **build_exe.spec OCR hidden imports + build-full-v3.yml YAML 수정 + 빌드 트리거** | **336 pass** | — |
| **Gemini CLI 세팅** | **인증 완료 + GEMINI.md + gemini-helpers.sh + preflight 강화** | **337 pass** | — |
| **YOLO26x 위반 수정** | **pretrain_pipeline.py:310 yolov8→yolov5pytorch + 규칙 준수 테스트** | **337 pass** | — |
| **v3.0.0 버그 3건 수정** | **Bug1 OCR연동+Bug2 LLM응답성+Bug3 Training절대경로/오프라인 + get_base_dir()** | **388 pass** | — |
| **OCR winrt→winsdk 수정** | **winsdk 임포트 수정 + EasyOCR fallback 추가 + Login 감지 실 테스트** | **413 pass** | — |
| **워크플로우 통합** | **8개 yml → build.yml 단일 파일 (build-app + build-llm 2-job)** | **413 pass** | — |
| **Bug2 LLM 수정** | **_get_optimized_options (GPU/CPU 자동) + think=False + 120s deadline + timeout=(10,30)** | **399 pass** | — |
| **Bug2 호환성 보강** | **reasoning_content 별도 필드 처리 (Ollama 0.7+ phi4-mini-reasoning)** | **399 pass** | — |
| **Bug2 v2 재수정** | **think=False payload 최상위 이동 + concurrent.futures 실제 타임아웃** | **403 pass** | — |
| **Bug2 근본원인 수정 (v3.2.3)** | **self.parent()→self.window() — LLM 요청 미발송 근본 원인 해결 + 422 pass** | **422 pass** | — |
| **Training 수정 (v3.2.2)** | **NoneType 에러 수정(forward slash) + 완전 오프라인 env + 클래스별 서브폴더 저장/파인튜닝 UI + 422 pass** | **422 pass** | — |
| **OCR 버튼 인식 개선 (v3.2.4)** | **다단어 병합(_merge_adjacent_regions) + 4종 전처리(_preprocess_variants) + IoU NMS(_dedup_regions)** | **447 pass** | — |
| **Training 재실행 수정 (v3.2.5)** | **_clean_stale_caches() — *.cache/*.cache.npy 사전 삭제로 'NoneType write' 수정** | **453 pass** | — |
| **LLM 헬스체크 수정 (v3.2.6)** | **_HEALTH_TIMEOUT 1.5→5s + on_llm_send() 헬스체크 비치명적 처리 (네트워크드라이브/RAM 부족 환경)** | **454 pass** | — |
| **법인 프록시 우회 (v3.2.7)** | **session.trust_env=False + proxies bypass + _HEALTH_TIMEOUT 30s + start_agent.bat NO_PROXY 설정** | **456 pass** | — |
| **Training tqdm NoneType 수정 (v3.2.8)** | **verbose=False→True (tqdm disable 방지) + main_window.py set_vision_engine() 연결** | **458 pass** | — |
| **v3.8.0 SOP 현장 100%** | **auth_sequence/input_text/mold_setup + axis_y/verify_left/verify_right 신규 스텝 타입** | **458 pass** | — |
| **v3.9.0 ROI+SOP 확장** | **ROI Picker exec→open() 크래시 수정 + sop_steps.json v2.0 40단계 원자화 + wait_ms/type_text/press_key 신규 타입** | **599 pass** | — |
| **v3.10.0 Granite Vision 전환** | **Granite Vision 3.3-2b /api/chat (multimodal) + 📸 Screenshot 전송 + dry-run + jsonschema config 검증 + CI integration test** | **646 pass** | **92%+** |
| **v3.10.1 Granite Chat 버그 수정** | **image_b64 TypeError 수정 (on_llm_send+Workers) + config.json 직접 수정 활성화 + Granite 체인 통합 테스트 18개 신규** | **670 pass** | **92%+** |
| **v3.10.2 LLM Chat UX 개선** | **ROI 스크린샷 오버레이+800px JPEG압축 / ChatGPT-like token+ETA / Stop 버튼 실제 취소+버블 복구 / 600s timeout** | **701 pass** | **92%+** |
| **v4.0.0 SOP Editor 편집 + CI 수정** | **type_text/press_key/wait_ms 타입별 전용 입력 필드 + CI unit/integ timeout 분리 + ci_check.sh 로컬 시뮬레이션** | **733 pass** | **92%+** |
| **v4.1.0 OLED 특화 학습 + 기능 개선** | **OLED_TRAIN_PARAMS+OLEDConnectorGenerator+EpochChartWidget+OCR JSONL 로그+LLM 히스토리 저장+config 툴팁+CI pretrain 잡** | **758 pass** | **92%+** |
| **v4.1.1 버전 관리 모듈 + 흑백 인식 개선** | **src/version.py 단일 소스+CLI범프 / CLAHE+IOU+TTA / OLEDConnectorGenerator 노이즈+핀형상+blur / 기하학 증강 6키** | **775 pass** | **92%+** |

## 현재 스택 (v4.0.0)
- YOLO: yolo26x (`assets/models/yolo26x.pt`, 베이스: yolo26x COCO pretrained, ultralytics>=8.4.0)
- LLM: IBM Granite Vision 3.2-2b via Ollama (`http://localhost:11434`) — 멀티모달 + `/api/chat` + Screenshot 첨부 전송
- **OCR: WinRT/winsdk (primary) → EasyOCR fallback → PaddleOCR** / `src/ocr_engine.py` (TextRegion, fuzzy match)
- GUI: PyQt6 7탭 (완전 영어 UI — 인도 엔지니어 대응)
- 예외처리: ExceptionHandler (팝업 감지→freeze→LLM 3단계 체인)
- 주기 분석: CycleDetector (성공 패턴 JSONL 기록+분석)
- 배포 스크립트: `start_agent.bat`, `install_first_time.bat`
- 문서: `README_INSTALL_EN.md`, `QUICK_START_EN.md` (인도 엔지니어 영문 가이드)

## GUI Phase 2 완료 내용
- **SopWorker**: `screenshot_ready` 시그널 — 매 스텝 후 BGR ndarray emit
- **MainWindow**:
  - `_on_screenshot_ready()`: ndarray→QPixmap→VisionPanel + YOLO bbox overlay
  - `_on_worker_log()`: SOP 로그 → LogManager 기록
  - `_on_sop_finished()`: `LogManager.finalize()` 호출
  - `on_llm_analyze()`: 실제 `LogManager.build_llm_payload()` 사용
- **VisionPanel**:
  - `📁 파일 열기` 버튼 (QFileDialog → 이미지 로드 → YOLO 검출)
  - `set_vision_engine()` / `_run_yolo()` API
  - `📷 캡처` 버튼: numpy+QPixmap+YOLO 통합
- **main.py**: `vision` 추출 → `MainWindow` + `VisionPanel.set_vision_engine()` 전달

## 빌드 이력 (v3.0~3.2)
| 워크플로우 | Run ID | 상태 | 아티팩트 |
|-----------|--------|------|---------|
| Build & Release EXE | 23175357680 | ✅ 완료 | `connector_vision_agent-v3` |
| Build All-in-One (통팩) | 23176720634 | ❌ dispatch 불가 | GitHub YAML 오류 (히어독) |
| **Build Full v3.1 (OCR-First)** | **23225700565** | ❌ 실패 | — |
| Build Connector Vision Agent v3.1 | 23237420818 | ❓ 확인 필요 | `connector-agent-app` + `connector-agent-llm` |
| **Build Connector Vision Agent v3.2.0** | **23239456447** | ❓ 확인 필요 | `connector-agent-app` + `connector-agent-llm` |
| **Build Connector Vision Agent v3.2.1** | **23242119709** | ❓ 확인 필요 | `connector-agent-app` + `connector-agent-llm` |
| **Build Connector Vision Agent v3.2.2** | **23243915242** | ✅ 완료 (27m18s) | `connector-agent-app` + `connector-agent-llm` |
| Portable Bundle Part2 (phi4-mini) | 23139568715 | ✅ 재활용 | `portable-part2-phi4-mini` (2.7 GB) |

### 워크플로우 YAML 이슈 근본 원인 (2026-03-18 해결)
- **원인**: PowerShell `@'...'@` 히어독 내 Python 코드(컬럼0 시작)가 YAML 파서 오류 유발 → GitHub이 `workflow_dispatch` 트리거를 인식 못 함
- **해결**: `python -c "..."` 원라이너로 교체 → `build-full-v3.yml` 정상 파싱 및 dispatch 성공
- **영향받는 파일**: `build-allinone.yml`, `build-allinone-v2.yml`, `build-package.yml` (모두 같은 패턴) — 추후 정리 필요

### 통팩 조립 방법 (2단계)
1. `connector-agent-v3-allinone` 압축 해제
2. `portable-part2-phi4-mini`(run 23139568715) blobs/ manifests/ → `connector_agent\ollama_models\` 복사
3. `start_agent.bat` 더블클릭 → GUI 즉시 실행

## 프리트레인 파이프라인 (2026-03-17 실측)
| 항목 | 값 |
|------|-----|
| 데이터 소스 | 합성 GUI 60장 (SyntheticGUIGenerator) |
| 프리트레인 클래스 | 7개 (button/icon/label/connector/input_field/checkbox/dropdown) |
| 베이스 모델 | yolo26x.pt (COCO pretrained, 80cls) |
| 학습 | 3 epoch, imgsz=320, batch=4, CPU |
| **mAP50** | **0.1534** |
| mAP50-95 | 0.1483 |
| Precision | 0.1368 / Recall 0.3487 |
| 학습 시간 | 254.9s (4.2분, CPU) |
| 출력 가중치 | `assets/models/yolo26x_pretrained.pt` |

클래스별 mAP50: button=0.2754, checkbox=0.2124, icon=0.1559, connector=0.1513, label=0.1122, input_field=0.1042, dropdown=0.0627

> GPU 환경(RTX 3060+) + 실 데이터(Rico/OmniAct) + 더 많은 epoch 시 mAP50 0.5+ 목표

## YOLO26x 전용 규칙 (2026-03-17 확정 — 영구 적용)

```
YOLO 모델: yolo26x.pt 단독 사용
YOLOv8 / YOLOv9 / YOLOv10 / YOLOv11 = 절대 금지
```
- CLAUDE.md 최상단에 MANDATORY 규칙 추가
- OmniParser(YOLOv8 기반) 접근법 폐기 — YOLO26x 아키텍처 불일치

## YOLO26x GUI 프리트레인 CI 전략 (2026-03-17)

**로컬 CPU 학습 대신 GitHub Actions에서 YOLO26x 프리트레인 실행**

| 항목 | 내용 |
|------|------|
| 워크플로우 | `YOLO26x GUI Pretrain` (`.github/workflows/gui-pretrain.yml`) |
| 아키텍처 | YOLO26x 단독 (COCO pretrained → GUI 특화 파인튜닝) |
| 데이터 소스 | Rico WidgetCaptioning 500장 또는 합성 500장 |
| 기본 epochs | 20 (조정 가능: 5~50) |
| 출력 | `yolo26x_pretrained.pt` 아티팩트 + `PRETRAIN_REPORT.md` |
| 번들링 | 아티팩트 → `assets/models/yolo26x_pretrained.pt` 배치 시 통팩에 자동 포함 |

**Tab7 파인튜닝 우선순위**:
1. `assets/models/yolo26x.pt` 이미 파인튜닝됨 → 그대로 사용
2. `assets/models/yolo26x_pretrained.pt` 존재 (CI GUI 프리트레인) → 이 모델로 파인튜닝 시작
3. 둘 다 없음 → `yolo26x.pt` (ultralytics hub 자동 다운로드)

## ★ 다음 작업 후보 (v4.0.0 이후)

### 현장 배포 후 발생 가능한 개선 사항
- [ ] **SOP Editor 검색/필터**: 40단계 중 특정 ID/이름 검색 기능 (단계 수 증가 대비)
- [ ] **SOP Editor 일괄 편집**: 여러 단계 한 번에 enable/disable 토글
- [ ] **PW 마스킹**: type_text 편집 시 Text 필드를 password 모드로 표시 (보안 강화)
- [ ] **Training 진행률 실시간 표시**: mAP50 epoch별 그래프 (Training 탭)
- [ ] **LLM Chat 히스토리 저장**: 세션 간 대화 내용 유지 (JSONL 로컬 저장)
- [ ] **OCR 정확도 로그**: 인식 실패한 텍스트 패턴 수집 → 전처리 개선 피드백
- [ ] **yolo26x_pretrained.pt 다운로드**: CI GUI Pretrain 결과 아티팩트 → assets/models/ 배치
- [ ] **Config 항목 설명 툴팁**: Tab 5 각 설정 항목에 hover 설명 추가

### v4.0.0 완료 내용 (2026-03-27) ✅
- SOP Editor 타입별 전용 입력 필드 (type_text/press_key/wait_ms/auth_sequence)
- CI 빌드 unit/integ timeout 분리 (60s/300s) + scripts/ci_check.sh 로컬 시뮬레이션
- 문서 전면 v4.0.0 업데이트 (README, INSTALL_GUIDE, MERGE_GUIDE, start_agent.bat, TEST_REPORT)
- 733 pass, 92%+ coverage

---

### ROI Picker 크래시 + SOP 원자 40단계 확장 완료 (2026-03-26) — v3.9.0 ✅
- **Bug Fix: ROI Picker 크래시 근본 원인**
  - `_on_add()` / `_on_edit()`의 `dlg.exec()` (blocking modal event loop)
  - `_on_pick_roi()` 내 `self.hide()` + `main_window.hide()` → Windows WM_CLOSE → `done(Rejected)` → exec() 종료 → 앱 종료
  - **Fix 1**: `src/main.py` — `app.setQuitOnLastWindowClosed(False)` 추가
  - **Fix 2**: `sop_editor_panel.py` — `exec()` → `open()` + `_on_add_accepted()` / `_on_edit_accepted()` 시그널 패턴
- **SOP 원자 40단계 확장**
  - `assets/sop_steps.json` v1.3(12단계) → v2.0(40 원자 단계)
  - 12개 메인 단계 → 각 세부 액션 분해: click/type_text/press_key/wait_ms/drag/validate_pins
  - 신규 step 타입: `wait_ms` (N ms 대기), `type_text` (standalone 타이핑), `press_key` (단일 키)
  - `src/sop_executor.py` `run_step()` 3개 타입 핸들러 추가 + fallback 40단계 업데이트
- 테스트: `TestWaitMsStep` / `TestTypeTextStep` / `TestPressKeyStep` (15개 신규)
- 파일: test_sop_executor_new_types.py (신규), test_sop_steps_loader.py/test_no_yolo_sop_run.py/test_sop_executor.py 업데이트
- **599 pass, 0 fail**

### Training 재실행 'NoneType write' 수정 완료 (2026-03-19) — v3.2.5 ✅
- **증상**: Training 탭 → Annotation 저장 → Start Training 누르면 두 번째부터 항상 실패
  - `Training error: 'NoneType' object has no attribute 'write'`
  - FileNotFoundError for `labels/image_source.cache`
- **근본 원인** (3단계 체인):
  1. 첫 번째 학습 실행(DOS 창) 중 ultralytics가 `np.save("image_source.cache", x)` → `image_source.cache.npy` 생성
  2. `.cache.npy → .cache` rename 완료 전 중단 → `image_source.cache.npy` 잔류, `image_source.cache` 없음
  3. 두 번째 실행: `load_dataset_cache_file("image_source.cache")` → FileNotFoundError → cache_labels 재빌드 → Windows rename 실패 → `np.save(None, x)` 코드 경로 → AttributeError
- **Fix**: `TrainingManager._clean_stale_caches(dataset_yaml)` 추가
  - `_count_training_images()` 검증 직후, `model.train()` 직전 호출
  - `labels/` 아래 `*.cache`, `*.cache.npy` 전부 삭제 (rglob, OSError 무시)
  - 각 학습 실행이 항상 깨끗한 상태에서 시작 = "첫 번째 실행이 항상 성공하는" 동작 재현
- 테스트: `TestCleanStaleCaches` 6개 신규 추가
- 커밋: 3bbb6e2 / **453 pass**

### OCR 버튼 인식 개선 완료 (2026-03-19) — v3.2.4 ✅
- **문제 1 (다단어 버튼)**: WinRT가 "image source"를 "image"/"source" 2개로 분리 반환
  - **Fix**: `_merge_adjacent_regions()` — y 근접성 + 수평 gap ≤ 1.5배 너비 조건으로 인접 단어 병합
- **문제 2 (두꺼운 폰트)**: CLAHE 그레이스케일만으로 bold 텍스트 인식 불안정
  - **Fix**: `_preprocess_variants()` — V2 OTSU 이진화 추가 (두꺼운 글자 대비 극대화)
- **문제 3 (컬러 배경 버튼)**: 단색 배경에 텍스트가 묻히는 문제
  - **Fix**: V3 max-channel 추출 + V4 반전 OTSU (흰 배경 어두운 글자 / 어두운 배경 흰 글자 모두 대응)
- **IoU NMS**: `_dedup_regions()` — 4종 변형 스캔 후 IoU≥0.5 중복 제거
- `find_text()`, `_scan_easyocr()`, `_scan_paddleocr()`에 통합
- 테스트 25개 신규 (TestMergeAdjacentRegions/TestBboxIou/TestDedup/TestPreprocessVariants/TestFindTextMultiword)
- 커밋: 5b78747 / **447 pass**

### Bug2 LLM 무한 대기 근본 원인 수정 (2026-03-19) — v3.2.3 ✅
- **진짜 근본 원인**: `LlmPanel._on_send()`에서 `self.parent()` → QTabWidget 내부 `QStackedWidget` 반환
  - `hasattr(QStackedWidget, "on_llm_send") = False` → Worker 생성 없음 → HTTP 요청 미발송
  - `set_sending(True)` 만 실행 → 타이머 무한 동작 → "Thinking... 1000s+"
- **이전 Fix1~3 실패 이유**: timeout/think=False/concurrent.futures는 HTTP 레이어 수정이었으나 요청 자체가 없었음
- **수정**: `self.parent()` → `self.window()` (QWidget.window()는 항상 최상위 MainWindow 반환)
- **추가**: `on_llm_send` 없을 때 즉시 `set_sending(False)` 방어 코드
- `_on_analyze()` 동일 버그 동시 수정
- 커밋: 422830d / **422 pass**

### Training 수정 완료 (2026-03-18) — v3.2.2
- **NoneType 에러 근본 원인**: `dataset.yaml` `path:` 필드 Windows 역슬래시 → `\t`/`\n` 오파싱 → `im_files=[]` → `cache_path=None` → `np.save(None, x)` → `AttributeError`
- **Fix 1**: `save_dataset_yaml()` forward slash 강제 변환 (`str(path).replace("\\", "/")`)
- **Fix 2**: `_count_training_images()` 사전 검증 — 이미지 0개 시 명확한 `ValueError` (ultralytics 호출 전)
- **Fix 3**: 완전 오프라인 env 설정 (`ULTRALYTICS_OFFLINE`, `WANDB_DISABLED`, `COMET_MODE`, `CLEARML_LOG_MODEL`, `NEPTUNE_MODE`)
- **Fix 4**: `workers=0` (Windows multiprocessing 방지), `exist_ok=True`, `rect=False`
- **Fix 5**: pretrain_pipeline 3개 메서드 오프라인 가드 + synthetic fallback
- Save Annotation: `{class}_{YYYYMMDD}_{HHMMSS}.png` + `images/{class}/` 서브폴더 자동 생성
- 파인튜닝 UI: 클래스 체크박스 선택 → `save_dataset_yaml(selected_classes=[...])` 연동
- 커밋: 244613a / **422 pass**

### Bug2 LLM 무한 대기 재수정 완료 (2026-03-18) — v3.2.1
- **근본 원인 A**: `think=False` payload 최상위 이동 (options{} → Ollama 레벨)
- **근본 원인 B**: `session.close()` → `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=120)` 교체
- 커밋: 2739899

### OCR 수정 완료 (2026-03-18)
- `winrt` → `winsdk` 임포트 수정, EasyOCR fallback 추가

### 통팩 빌드 완료 (2026-03-18) — v3.2.2 ✅
- run #23243915242 — 전체 성공 (27m18s)
- `connector-agent-app`: EXE + Ollama + YOLO26x + OCR(winsdk/easyocr) + Training fixes
- `connector-agent-llm`: phi4-mini-reasoning ~2.5 GB 별도 아티팩트

## 이전 다음 작업 후보 (홀드)
- [ ] `YOLO26x GUI Pretrain` 결과(yolo26x_pretrained.pt) 아티팩트 다운로드 → `assets/models/` 배치
- [ ] 통팩 빌드 워크플로우 재등록 수정 (dispatch 불가 이슈 해결) → 통팩 재빌드
- [ ] phi4-mini 요약 응답 품질 개선 (다국어 혼용 문제)
- [ ] actions/upload-artifact@v4 → Node.js 24 호환 버전 업그레이드 (2026-06 전)

## 알려진 이슈
- `assets/models/yolo26x.pt`: CI에서 yolo26x COCO pretrained 다운로드 (파인튜닝 전 상태)
- phi4-mini-reasoning: CPU-only 환경에서 ~109초 지연, 한국어+중국어 혼용 응답 발생
- `.coveragerc` 제외: main.py, control_engine.py, sop_executor.py, test_sop.py

## 핵심 커맨드
```bash
bash run_tests.sh                                          # 테스트+lint
python src/main.py                                         # GUI 실행
python src/main.py --console                               # CLI 모드
gh workflow run "Build Portable Offline Bundle (Split)"    # 포터블 빌드
```
