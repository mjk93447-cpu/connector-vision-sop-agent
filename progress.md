# Progress — Connector Vision SOP Agent

_최종 갱신: 2026-03-17 (yolo26x 단독 확인 + 프리트레인 파이프라인 구축 + mAP50 측정)_

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

## 현재 스택 (v3.0.0)
- YOLO: yolo26x (`assets/models/yolo26x.pt`, 베이스: yolo26x COCO pretrained, ultralytics>=8.4.0)
- LLM: phi4-mini-reasoning via Ollama (`http://localhost:11434`)
- OCR: 완전 제거 / 테스트: 242개
- GUI: PyQt6 7탭 (Vision Canvas 실시간 + LLM 채팅 + 감사 로그 + Tab7 Training)

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

## 빌드 이력 (v3.0)
| 워크플로우 | Run ID | 상태 | 아티팩트 |
|-----------|--------|------|---------|
| Build & Release EXE | 23175357680 | ✅ 완료 | `connector_vision_agent-v3` |
| **Build All-in-One (통팩)** | **23176720634** | 🔄 진행 중 | **`connector-agent-v3-allinone`** |
| Portable Bundle Part2 (phi4-mini) | 23139568715 | ✅ 재활용 | `portable-part2-phi4-mini` (2.7 GB) |

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

## 다음 작업 후보
- [ ] Rico WidgetCaptioning 실 데이터(500+장)로 프리트레인 재실행 (`python scripts/run_pretrain.py --source rico_widget`)
- [ ] `assets/models/yolo26x_pretrained.pt` → Tab7 Training Panel 기반 모델로 선택 후 OLED 파인튜닝
- [ ] phi4-mini 요약 응답 품질 개선 (다국어 혼용 문제)
- [ ] Checkpoint 4 로컬 검증 완결 (TEST_REPORT.md 업데이트)
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
