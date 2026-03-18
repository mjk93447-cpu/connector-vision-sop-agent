# Progress — Connector Vision SOP Agent

_최종 갱신: 2026-03-18 (워크플로우 8개 → build.yml 단일 통팩 빌드로 통합 완료)_

## 현재 브랜치
`main` (CP-0~CP-4 + GUI Phase 1~2 완료)

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

## 현재 스택 (v3.1.0)
- YOLO: yolo26x (`assets/models/yolo26x.pt`, 베이스: yolo26x COCO pretrained, ultralytics>=8.4.0)
- LLM: phi4-mini-reasoning via Ollama (`http://localhost:11434`) — 스트리밍 출력 + Brief 모드
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

## 빌드 이력 (v3.0~3.1)
| 워크플로우 | Run ID | 상태 | 아티팩트 |
|-----------|--------|------|---------|
| Build & Release EXE | 23175357680 | ✅ 완료 | `connector_vision_agent-v3` |
| Build All-in-One (통팩) | 23176720634 | ❌ dispatch 불가 | GitHub YAML 오류 (히어독) |
| **Build Full v3.1 (OCR-First)** | **23225700565** | ❌ 실패 | — |
| **Build Connector Vision Agent (All-in-One)** | **23237420818** | 🔄 **진행 중** | **`connector-agent-app` + `connector-agent-llm`** |
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

## ★ 다음 작업

### OCR 수정 완료 (2026-03-18)
- `winrt` → `winsdk` 임포트 수정으로 WinRT OCR 정상 동작 확인
- EasyOCR fallback 추가 (WinRT 미지원 환경용)
- 실 테스트: Notepad "Login" 텍스트 → `login_button` 좌표 `(958, 221)` 정상 감지
- **Windows 7 지원 불가**: Python 3.12 + PyQt6 = Win10 최소 요구. Win7은 Python 3.8 + PyQt5 재작성 필요

### 통팩 빌드 (2026-03-18 진행 중)
- run #23237420818: `gh workflow run "Build Connector Vision Agent (All-in-One)"`
- build-app: EXE + Ollama + YOLO26x + OCR(winsdk/easyocr) + config
- build-llm: phi4-mini-reasoning ~2.5 GB 별도 아티팩트

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
