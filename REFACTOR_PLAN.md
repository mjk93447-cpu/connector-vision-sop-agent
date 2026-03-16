# 리팩토링 계획: YOLO26x + Llama4 Scout (Ollama) 전환

> 최종 목표: YOLO26n + Tesseract + Qwen GGUF → **YOLO26x + Llama4 Scout via Ollama**
> 핵심 원칙: 에러 감소, 비전 정확도 향상, LLM 성능 향상, 의존성 단순화
> 작성일: 2026-03-16 | 기반: ROADMAP.md "Future Direction" 섹션

---

## 스택 전환 요약

| 구성요소 | 현재 (v1) | 목표 (v2) | 변경 이유 |
|---|---|---|---|
| 비전 모델 | YOLO26n (nano) | YOLO26x (extra-large) | 탐지 정확도 대폭 향상 |
| OCR | Tesseract PSM7 | 제거 (YOLO26x 직접 탐지) | 의존성 단순화, 오류 원인 제거 |
| LLM 백엔드 | Qwen2.5-VL GGUF (미배포) | Llama4 Scout via **Ollama** | GGUF 관리 불필요, 간단한 HTTP API |
| LLM 실행 방식 | llama-cpp-python (무겁다) | Ollama 로컬 서버 (ollama serve) | 설치/업데이트 단순, 라인 PC 친화적 |
| Python 버전 | 3.12(로컬)/3.11(CI) 혼용 | **3.11 완전 통일** | CI 불일치 해소 |
| 클래스 구조 | VisionAgent + VisionEngine | VisionEngine 단일 클래스 | 코드 복잡도 감소 |

### Ollama 선택 이유

```
기존 방식: llama-cpp-python 설치 → GGUF 파일 수동 관리 → config model_path 관리
Ollama 방식: ollama serve + ollama pull llama4:scout → HTTP API 호출

장점:
- 설치: 실행파일 1개 (ollama.exe)
- 모델 관리: ollama pull / ollama list (자동화)
- API: OpenAI 호환 HTTP (기존 backend:"http" 재사용 가능)
- 업데이트: ollama pull 1개 명령
- 라인 PC 오프라인: 사전 pull 후 인터넷 불필요
```

---

## 체크포인트 구조

```
CP-0  ──▶  [검증 게이트 0]  ──▶  CP-1  ──▶  [검증 게이트 1]  ──▶  CP-2
  │                                 │                                 │
개발 환경                        Ollama LLM                      YOLO26x
기반 구축                         전환                           도입

CP-2  ──▶  [검증 게이트 2]  ──▶  CP-3  ──▶  [검증 게이트 3]  ──▶  CP-4
  │                                 │                                 │
YOLO26x                         Tesseract                        최종 통합
도입                            완전 제거                         및 배포
```

각 체크포인트는 **개발 작업 → 테스트 작성 → 검증 게이트 통과** 순서로 진행한다.
검증 게이트를 통과하지 않으면 다음 체크포인트로 진입하지 않는다.

---

## CP-0: 개발 환경 기반 구축

**목표**: 리팩토링 시작 전 안전한 베이스라인 확보 — 개발 환경 통일 + 테스트 인프라 구축

### 개발 작업

- [ ] Python 3.11 가상환경 통일 (로컬 `.venv311/`)
- [ ] `requirements-dev.txt` 분리 (pytest, black, ruff, basedpyright)
- [ ] `pytest.ini` 구성 (testpaths, cov 설정)
- [ ] `tests/` 디렉터리 구조 생성
  ```
  tests/
    conftest.py          ← 공통 픽스처
    unit/
      test_config_loader.py
      test_sop_advisor.py
      test_log_manager.py
      test_llm_offline.py
    integration/         ← 기존 src/test_sop.py 이후 이동 예정
  ```
- [ ] 공통 픽스처 정의 (dummy_screen, sample_config, sample_events)
- [ ] 미커버 모듈 4개 단위 테스트 작성
  - `config_loader`: 유효/누락 파일 로딩
  - `sop_advisor`: apply_config_patch, summarize_failures, propose_actions
  - `log_manager`: log/log_error, save_screenshot, finalize, build_llm_payload, analyze_with_llm
  - `llm_offline`: LLMConfig.from_dict, 백엔드 디스패치, HTTP mock

### 검증 게이트 0 (통과 기준)

```bash
# 모든 조건을 동시에 만족해야 한다

pytest -v                    # 기존 3개 + 신규 테스트 전부 통과
pytest --cov=src --cov-report=term-missing  # 커버리지 60% 이상
black --check .              # 포맷 위반 없음
ruff check .                 # 린트 위반 없음
```

**완료 조건**: 커버리지 ≥ 60%, 기존 3개 테스트 포함 전 테스트 그린, black/ruff 클린

---

## CP-1: Ollama LLM 백엔드 전환

**목표**: Qwen GGUF 설계 → Llama4 Scout + Ollama HTTP 방식으로 전환

### 개발 작업

- [ ] `llm_offline.py`: `BackendType`에 `"ollama"` 추가
  ```python
  BackendType = Literal["llama_cpp", "http", "ollama"]
  ```
- [ ] `OfflineLLM._chat_ollama()` 구현
  - 기본 URL: `http://localhost:11434/v1/chat/completions`
  - 모델명: `llm.model_path` → Ollama 모델 태그 (`"llama4:scout"`)
  - 기존 `_chat_http()` 로직 재사용 (Ollama는 OpenAI 호환)
- [ ] `LLMConfig` 확장
  ```python
  @dataclass
  class LLMConfig:
      backend: BackendType = "ollama"           # 기본값 변경
      model_path: str = "llama4:scout"           # Ollama 모델 태그
      ctx_size: int = 8192
      gpu_layers: int = 0
      http_url: str = "http://localhost:11434/v1/chat/completions"
      max_input_tokens: int = 6144
      max_output_tokens: int = 1024
  ```
- [ ] `assets/config.json` LLM 블록 갱신
  ```jsonc
  "llm": {
    "enabled": true,
    "backend": "ollama",
    "model_path": "llama4:scout",
    "http_url": "http://localhost:11434/v1/chat/completions",
    "ctx_size": 8192,
    "max_input_tokens": 6144,
    "max_output_tokens": 1024
  }
  ```
- [ ] `tools/dummy_ollama_server.py` 작성 (개발 중 빠른 반복용)
- [ ] Ollama 설치 가이드 문서 추가 (README.md 섹션)

### 테스트 작성

- [ ] `tests/unit/test_llm_offline.py` 확장
  - `test_ollama_backend_uses_http_call()`
  - `test_ollama_default_url_set_correctly()`
  - `test_chat_ollama_returns_response(monkeypatch)`
  - `test_analyze_logs_with_ollama_backend(monkeypatch)`
- [ ] `tests/integration/test_llm_analysis_flow.py`
  - `[L]` 전체 흐름 mock 테스트

### 검증 게이트 1 (통과 기준)

```bash
pytest -v                    # 전 테스트 그린
pytest --cov=src --cov-report=term-missing  # 커버리지 65% 이상

# Ollama 실환경 검증 (개발 PC에서 1회)
ollama serve &
ollama pull llama4:scout
python -c "
from src.llm_offline import OfflineLLM, LLMConfig
llm = OfflineLLM(LLMConfig())
print(llm.chat('test', [{'role':'user','content':'안녕'}]))
"
```

**완료 조건**: 커버리지 ≥ 65%, Ollama 실연동 응답 확인, [L] 분석 흐름 mock 테스트 통과

---

## CP-2: YOLO26x 도입 및 VisionEngine 정리

**목표**: YOLO26n → YOLO26x 교체, VisionAgent/VisionEngine 이중 클래스 → 단일 VisionEngine

### 개발 작업

- [ ] `assets/models/yolo26x.pt` 준비 (Git LFS 등록)
- [ ] `VisionAgent` 클래스 → `VisionEngine`으로 완전 통합 (상속 제거)
- [ ] `DetectionConfig` 확장
  ```python
  @dataclass
  class DetectionConfig:
      confidence_threshold: float = 0.55   # 26x는 더 정확 → 낮춰도 됨
      ocr_psm: int = 7                     # DEPRECATED
      use_ocr_fallback: bool = False       # 기본값 OFF
      nms_iou_threshold: float = 0.45
  ```
- [ ] `VisionEngine._load_model()`: `yolo26x.pt` 우선, `yolo26n.pt` 폴백
- [ ] `config.json` `vision` 블록 추가
  ```jsonc
  "vision": {
    "model_path": "assets/models/yolo26x.pt",
    "confidence_threshold": 0.55,
    "nms_iou_threshold": 0.45,
    "use_ocr_fallback": false
  }
  ```
- [ ] CI `release.yml` YOLO 검증 스텝 `yolo26x.pt`로 수정
- [ ] OCR 메서드 `# DEPRECATED` 주석 추가 (제거는 CP-3)

### 테스트 작성

- [ ] `tests/unit/test_vision_engine.py` (신규)
  - `test_detection_config_defaults()`
  - `test_vision_engine_no_ocr_fallback(monkeypatch)`
  - `test_detect_objects_returns_list(monkeypatch)`
  - `test_model_fallback_to_yolo26n_when_26x_missing(tmp_path, monkeypatch)`
  - `test_normalize_roi()`
  - `test_extract_pin_centers_blank_image()`
  - `test_validate_pin_count()`

### 검증 게이트 2 (통과 기준)

```bash
pytest -v --cov=src          # 커버리지 70% 이상
# yolo26x.pt 로드 확인
python -c "from ultralytics import YOLO; m=YOLO('assets/models/yolo26x.pt'); print('OK:', len(m.names), 'classes')"
# EXE 빌드 성공
build.bat
```

**완료 조건**: 커버리지 ≥ 70%, YOLO26x 로드 확인, EXE 빌드 성공

---

## CP-3: Tesseract 완전 제거

**목표**: pytesseract 의존성 완전 제거 — YOLO26x 단독 탐지 체제로 전환

### 개발 작업

- [ ] `vision_engine.py`: `read_text()`, `locate_text()`, `preprocess_for_ocr()`, `similarity()` 삭제
- [ ] `control_engine.py`: OCR 폴백 블록 제거
  ```python
  # 삭제 대상
  text_match = self.vision.locate_text(image, target_text=target_name)
  if text_match is not None:
      return self._center_of_bbox(text_match["bbox"])
  ```
- [ ] `requirements.txt`: `pytesseract==0.3.13` 제거
- [ ] `build_exe.spec`: `'pytesseract'` hiddenimport 제거
- [ ] `config.json`: `ocr_threshold`, `ocr_psm` 키 제거 (v2 스키마 확정)
- [ ] `sop_advisor.py` `SAFE_NUMERIC_RANGES`: `"ocr_threshold"` 항목 제거
- [ ] `main.py` `_resolve_confidence_threshold()`, `_resolve_ocr_psm()` 정리
- [ ] `DEFAULT_MOLD_ROI` 하드코딩 제거 → `config.json.mold` 블록으로 이동

### 테스트 작성

- [ ] OCR 관련 import/call이 코드에 없는지 자동 검사
  ```python
  # tests/unit/test_no_ocr_dependency.py
  def test_no_pytesseract_import_in_src():
      """pytesseract가 src/ 코드에서 import되지 않아야 한다."""
  ```
- [ ] `tests/unit/test_control_engine.py` (신규)
  - YOLO 단독 탐지 경로만 활성화 확인

### 검증 게이트 3 (통과 기준)

```bash
pytest -v --cov=src          # 커버리지 80% 이상
grep -rn "pytesseract\|import tesseract" src/  # 결과 없어야 함
pip show pytesseract          # 설치 안 된 상태에서도 pytest 통과
build.bat                     # EXE 크기 감소 확인 (pytesseract 제거 효과)
```

**완료 조건**: 커버리지 ≥ 80%, pytesseract 흔적 없음, EXE 빌드 성공

---

## CP-4: 최종 통합 및 배포 검증

**목표**: 전체 시스템 정합성 확인, CI 갱신, 라인 PC 배포 준비 완료

### 개발 작업

- [ ] `config.json` v2 스키마 최종 확정 및 `README.md` 갱신
- [ ] `ROADMAP.md` Checkpoints 섹션 업데이트
- [ ] `CLAUDE.md` 기술 스택 섹션 갱신 (YOLO26x, Ollama)
- [ ] `.github/workflows/release.yml` 전면 갱신
  - YOLO26x 검증 스텝
  - `pytest --cov-fail-under=80` 게이트
  - `requirements-dev.txt` 분리 설치
- [ ] `TEST_REPORT.md` 작성 (CP-0 ~ CP-4 검증 결과 문서화)
- [ ] `src/test_sop.py` → `tests/integration/test_sop_flow.py` 이동

### 검증 게이트 4 (최종 완료 기준)

```bash
# 전체 테스트
pytest -v --cov=src --cov-fail-under=80

# 정적 분석
black --check .
ruff check .

# 빌드
build.bat

# 라인 PC 배포 전 수동 시나리오 (콘솔)
python -m src.main
# [1] SOP 실행 → OK
# [L] LLM 분석 → enabled:false 시 안내 메시지
# [C] Chat mode → LLM 없을 때 안내 메시지
# [Q] 종료
```

**완료 조건**: 모든 자동 게이트 통과, 수동 시나리오 확인, TEST_REPORT.md 완성
→ `develop` → `main` 머지, `v2.0.0` 태그 생성

---

## 개발 환경 요구사항 (전 체크포인트 공통)

### Python

```bash
python --version  # 3.11.x 이어야 함
```

### 의존성 구조

| 파일 | 용도 |
|---|---|
| `requirements.txt` | 라인 PC 런타임 (최소) |
| `requirements-dev.txt` | 개발/테스트 전용 |

### Ollama 설치 (개발 PC & 라인 PC)

```bash
# 1. 설치 (Windows)
winget install Ollama.Ollama
# 또는 https://ollama.com/download

# 2. 서버 시작
ollama serve

# 3. Llama4 Scout 모델 다운로드 (온라인 머신에서 1회)
ollama pull llama4:scout

# 4. 오프라인 라인 PC에는 모델 파일 복사
# Windows: %USERPROFILE%\.ollama\models\
```

### 브랜치 전략

```bash
git checkout -b feature/v2-yolo26x-llama4 develop

# 서브 작업
git checkout -b feature/v2/cp0-test-infra feature/v2-yolo26x-llama4
git checkout -b feature/v2/cp1-ollama      feature/v2-yolo26x-llama4
git checkout -b feature/v2/cp2-yolo26x     feature/v2-yolo26x-llama4
git checkout -b feature/v2/cp3-remove-ocr  feature/v2-yolo26x-llama4
```

### 커밋 메시지 형식

```
[feat] Ollama 백엔드 타입 추가 및 LLMConfig 기본값 변경
[refactor] VisionAgent/VisionEngine 이중 클래스 단일화
[remove] pytesseract 의존성 및 OCR 메서드 완전 제거
[test] test_log_manager.py — finalize/build_llm_payload 커버리지 추가
[chore] requirements-dev.txt 분리, pytest.ini 구성
```
