# Connector Vision SOP Agent – Offline LLM Roadmap

Last updated: 2026-03-12

This roadmap focuses on making the agent fully usable on an **offline Windows line PC** with a **local LLM** (e.g. Qwen2.5-VL or a distilled variant) for SOP guidance, log diagnosis, and config auto-tuning.

We assume a typical line PC profile based on current industrial offerings:

- Windows 10/11 Pro
- Intel Core i7 class CPU (e.g. 12세대 Alder Lake)
- 16–32 GB RAM
- 보통 전용 GPU가 없거나, 중급 RTX 3060/3070급 1장 이하
- 512 GB SSD 이상 (모델 + 로그 + EXE 보관)

Target LLM profile (2026 기준, **결정사항**):

- **주요 백엔드 (A안 선택)**: `llama-cpp-python` + **Qwen2.5-VL-7B-Instruct GGUF Q4_K_M (~4.7 GB)**
  - 이유:
    - 라인 PC는 별도 서버/서비스를 띄우기 어려운 오프라인 환경인 경우가 많음.
    - EXE와 같은 프로세스 안에서 직접 GGUF를 로드하면 **의존 컴포넌트 수가 줄어들고** 장애 지점을 최소화할 수 있음.
    - Q4_K_M 7B 모델은 i7 + 16–32GB RAM 환경에서 “수 초~수십 초” 지연이지만,
      SOP 실패 진단/튜닝 같은 **저빈도 질의**에는 현실적으로 수용 가능.
- **보조 백엔드 (B안은 옵션)**: HTTP 로컬 서버 (LM Studio / Ollama)
  - LM Studio/Ollama 등을 이미 사용하는 환경에서는 `backend: "http"` + `http_url` 로 연동.
  - 단, **라인 PC에서 상주 서비스 관리가 필요**하므로 기본 배포 시에는 사용하지 않고, 고급 옵션으로 문서화만 한다.
- Fallback: Smaller instruct-only text model (1.5–3B, e.g. Qwen2.5-1.5B-Instruct GGUF) when VL가 과한 경우
- Latency 목표: 일반 질의 응답 5–20초 이내 (CPU-only 기준)

---

## Phase 1 – Console UX & Logging (완료)

- [x] **Hybrid console UI** (`src/main.py` → `run_console()`):
  - First-run banner with usage.
  - Start/stop SOP run.
  - Speed presets: slow / normal / fast.
- [x] **Structured logging pipeline** (`src/log_manager.py`):
  - JSONL events (`events.jsonl`), `summary.json`, screenshot storage.
  - `build_llm_payload()` for LLM-ready context.

Status: merged into `env-2026-stack` branch and validated in CI.

---

## Phase 2 – Offline LLM Integration (진행 예정)

Goal: Run a **fully local LLM** on the line PC without internet.

### Target deliverables (Phase 2)

- `src/llm_offline.py`
  - `LLMConfig`:
    - `backend`: `"llama_cpp"` | `"http"`
    - `model_path`: `str`
    - `ctx_size`: `int` (default 4096)
    - `gpu_layers`: `int` (default 0)
    - `http_url`: `str | None`
    - `max_input_tokens`, `max_output_tokens`
  - `OfflineLLM`:
    - `from_config(cls, cfg: dict) -> OfflineLLM`
    - `chat(system: str, history: list[dict]) -> str`
    - `analyze_logs(payload: dict) -> dict`  
      → `{"config_patch": {...}, "sop_recommendations": [...], "raw_text": "..."}` 형식
- `LogManager.analyze_with_llm()`:
  - `config["llm"]` 블록을 읽어 `OfflineLLM` 인스턴스를 생성.
  - 실패 시:
    - `enabled=false` 처리 or 친절한 에러 메시지 반환.
  - 성공 시:
    - `OfflineLLM.analyze_logs(payload)` 호출해 결과 전달.

### Planned steps:

1. **Choose a local backend** (PC 환경에 따라 선택):
   - **Recommended for typical line PC (i7 + 16–32 GB RAM, no GPU)**  
     - `llama-cpp-python` + **Qwen2.5-VL-7B-Instruct GGUF (Q4_K_M, ~4.7 GB)**  
       - CPU-only 가능하나 응답 속도는 수 초~수십 초 수준으로 예상.
       - SOP 진단/설정 추천 정도의 저빈도 요청에는 충분.
   - **If a strong GPU is available (예: RTX 4090 / 24 GB VRAM)**  
     - vLLM/Transformers + FP16/BF16 Qwen2.5-VL 7B/14B (고성능 모드).
   - **Alternative**: Local HTTP server (예: LM Studio / Ollama)에서 Qwen2.5-VL 호환 모델을 서빙하고, 에이전트는 HTTP만 호출.
2. **Create `src/llm_offline.py`**:
   - `LLMConfig` dataclass (model_path, ctx_size, gpu_layers, backend type).
   - `OfflineLLM` class with:
     - `chat(system: str, history: list[dict]) -> str`
     - `analyze_logs(payload: dict) -> dict` (returns `config_patch`, `sop_recommendations`).
   - Attempt to import `llama_cpp` or call localhost HTTP; if unavailable, raise a clear error.
3. **Wire into `LogManager.analyze_with_llm()`**:
   - If local LLM backend is correctly configured → call `OfflineLLM.analyze_logs()`.
   - Otherwise fall back to the current no-op stub with a clear note.
4. **Extend `assets/config.json` schema**:

   ```jsonc
   {
     "version": "1.0.0",
     "password": "1111",
     "ocr_threshold": 0.75,
     "pin_count_min": null,
     "llm": {
       "enabled": true,
       "backend": "llama_cpp",           // or "http"
       "model_path": "C:/models/qwen2_5-vl-7b-q4_k_m.gguf",
       "ctx_size": 4096,
       "gpu_layers": 0,                  // 0 = pure CPU, >0 if GPU available
       "http_url": "http://localhost:8000/v1/chat/completions",
       "max_input_tokens": 4096,
       "max_output_tokens": 512
     }
   }
   ```

Deliverable: `OfflineLLM` that can be called from both console and automation code.

---

## Phase 3 – LLM Chat Mode (계획)

Goal: Let line engineers **chat with the agent** about the latest SOP run and vision issues, fully offline.

### Target deliverables (Phase 3)

- **1차 버전 (라이트 Q&A)**:
  - 콘솔 챗 모드:
    - `run_console()`에 `[C] Chat mode` 추가.
    - 최근 `LogManager` 페이로드(요약 + tail 이벤트)를 LLM 컨텍스트로 사용.
    - `OfflineLLM.chat()` 을 사용해 **단순 Q&A REPL** 제공.
  - 대화 기능 (v1):
    - 최근 SOP 실행 요약/실패 단계 설명.
    - 로그 기반 원인 추정 및 “다음에 시도해볼 만한 조치 3가지” 제안.
- **2차 버전 (Phase 4와 연계)**:
  - ROI/threshold/retry 설정 변경 시뮬레이션 및 `config_patch` 미리보기는 Phase 4 구현 이후 확장.

### Planned steps:

1. **Console integration**:
   - Add `[C] Chat mode` to `run_console()`:
     - Loads latest `LogManager` payload.
     - Opens a REPL:
       - User: 질문 입력
       - LLM: 답변 (SOP 단계 설명, 원인 추정, 수정 제안 등)
2. **Prompt design**:
   - System prompt: “Samsung OLED connector SOP expert + vision engineer”.
   - Inject:
     - Latest `summary.json` (compact).
     - Key events (errors, retries, pin-count validation failures).
     - Paths to any critical screenshots (engineer can open them separately).
3. **Config auto-suggestions**:
   - v1 (Phase 3): 텍스트 설명/제안까지만 제공 (config 파일은 변경하지 않음).
   - v2 (Phase 4 이후): `analyze_logs()` 및 `sop_advisor`를 통해 JSON patch 미리보기와 적용 플로우 추가.

Deliverable: Interactive chat mode in console using offline LLM.

---

## Phase 4 – SOP & Vision Auto-Tuning (계획)

Goal: Use LLM + logs to automatically refine SOP steps and vision parameters over time.

Ideas:

- Detect recurring failure patterns:
  - e.g. “mold_left_label not found 3 times in a row” → suggest adjusting ROI or OCR PSM.
- Suggest new SOP variants:
  - Re-order steps or add intermediate verification when certain errors appear frequently.
- Auto-generate **“field notes”**:
  - Summarize common issues and successful fixes per day/week for engineering review.

Implementation sketch:

- New module `src/sop_advisor.py` to:
  - Consume LLM suggestions.
  - Validate them against constraints (e.g. safe ranges for thresholds).
  - Apply safe changes to config or store them as proposals for human review.

### Target deliverables (Phase 4)

- `src/sop_advisor.py`:
  - `apply_config_patch(config: dict, patch: dict) -> dict`
  - `summarize_failures(events: list[dict]) -> dict` (통계/패턴 요약)
  - `propose_actions(llm_output: dict) -> list[dict]` (엔지니어 검토용 액션 리스트)
- `assets/config.json` 변경 전략:
  - 직접 덮어쓰기보다:
    - `assets/config.proposed.json` 생성,
    - 콘솔에서 엔지니어가 “적용” 명령을 내릴 때만 본 config에 병합.

---

## Phase 5 – Hardening & Field Validation (계획)

- Benchmarks:
  - Measure EXE startup, SOP runtime, LLM response latency on target line PC.
- Reliability:
  - Make LLM usage optional; core SOP must run even if LLM backend is missing.
  - Graceful fallbacks and clear console error messages.
- Documentation:
  - Add **LLM Setup Guide** (Windows, offline) to README:
    - Model download once (online machine).
    - Copy to line PC.
    - Install `llama-cpp-python` or run local HTTP LLM.
    - Configure `assets/config.json.llm` block.

### Target deliverables (Phase 5)

- 라인 PC 벤치마크 리포트:
  - 평균 SOP 실행 시간 (LLM off / on).
  - LLM 응답 지연(평균/최대).
- 장애/에러 매트릭:
  - LLM 미동작 시에도 SOP가 100% 정상 동작하는지 확인.
  - 콘솔 에러 메시지/로그 품질 검증.

---

This roadmap should be kept up to date as we iterate. When a phase is completed, mark its checklist items as done and add any lessons learned for future maintainers.

---

## Mid/Long-Term Development Plan (요약)

이 프로젝트의 중장기 개발은 다음 순서로 진행한다. 각 단계는 이전 단계의 산출물을 전제로 하며, 필요 시 피드백에 따라 반복/보완할 수 있다.

1. **Phase 2 – Offline LLM Integration**
   - `src/llm_offline.py` 구현 및 `LogManager.analyze_with_llm()` 연동.
   - `assets/config.json.llm` 블록 정의 및 라인 PC에서의 최소 설정값 합의.
   - 로컬 개발 PC에서 GGUF 모델을 사용한 end-to-end 테스트 (인터넷 차단 상태).
2. **Phase 3 – LLM Chat Mode**
   - 콘솔 `[C] Chat mode` 구현.
   - 기본 프롬프트/역할 설계 및 로그/스크린샷 컨텍스트 주입.
   - 라인 엔지니어와의 파일럿 세션을 통해 UX 피드백 수집.
3. **Phase 4 – SOP & Vision Auto-Tuning**
   - `sop_advisor` 모듈로 LLM 추천을 안전하게 구조화.
   - `config.proposed.json` 기반의 “제안 → 검토 → 적용” 워크플로우 구현.
   - 반복적인 실패 패턴(예: 특정 버튼 미검출, 핀 카운트 부족 등)에 대한 자동 제안 템플릿 작성.
4. **Phase 5 – Hardening & Field Validation**
   - 실제 라인 PC에 배포하여 장시간 테스트.
   - 성능/신뢰성/사용성 지표 수집 및 필요 시 모델/프롬프트/UX 튜닝.
   - README/운영 매뉴얼/장애 대응 가이드 최종 정리.

---

## Future Direction – Minimal Offline Computer-Use Agent (Llama4-Scout-8B-Q4 + YOLO26x)

장기적으로는 Tesseract OCR 의존성을 제거하고, 보다 단순한 **오프라인 컴퓨터-유즈 에이전트** 아키텍처로 전환한다. 목표 스택:

- **Vision**: YOLO26x (또는 동급 커스텀 YOLO) 단일 스택으로 버튼/핵심 UI 요소 인식.
- **LLM**: `Llama4-Scout-8B-Q4` (가칭, 8B Q4 양자화) 오프라인 CPU+경량 GPU 구동.
- **OCR**: 별도 Tesseract 엔진을 제거하고, 필요 시:
  - YOLO26x 기반 텍스트 박스 검출 + LLM post-hoc reasoning,
  - 혹은 라인에서 요구하는 텍스트 수를 최소화하는 UX 재설계.

### Planned large-scale refactor (모델 체인지 플랜)

1. **Vision 레이어 정리 (YOLO26x 중심)**
   - `src/vision_engine.py`에서:
     - Tesseract 관련 전처리/`read_text`/`locate_text` 로직을 점진적으로 제거 또는 비활성화.
     - Mold ROI, 버튼/아이콘 검출 등을 YOLO26x 한 계열로 통합.
   - `assets/config.json`:
     - `ocr_threshold`, `ocr_psm` 등 OCR 전용 파라미터를 deprecated로 표시하고,
     - YOLO confidence/ROI 설정 위주로 재구성.

2. **LLM 백엔드 교체 (Llama4-Scout-8B-Q4)**
   - `src/llm_offline.py`:
     - Qwen2.5-VL 중심 설계를 유지하되, `backend: "llama4_scout"` 와 같은 신규 백엔드 타입을 추가.
     - GGUF 형식의 `Llama4-Scout-8B-Q4` 모델을 기본값으로 가정하고, CPU-only + 저용량 GPU 환경에서의 튜닝 파라미터 정의.
   - `assets/config.json.llm`:
     - `model_path`를 `C:/models/llama4-scout-8b-q4.gguf` 와 같은 경로로 업데이트.
     - 컨텍스트/출력 토큰 수를 실제 응답 지연과 메모리 사용량 기준으로 재조정.

3. **SOP/에이전트 동작 단순화**
   - Tesseract 제거 이후, 버튼/단계 인식은 모두:
     - YOLO26x → UI 요소/영역 인식,
     - LLM (Llama4-Scout) → 로그 해석, 튜닝 제안, 예외 상황 설명,
     로 역할을 분리.
   - `sop_executor` 및 `control_engine`에서 OCR 기반 분기를 줄이고,
     - “탐지 실패 시 LLM에게 진단 요청”과 같은 고수준 처리 패턴으로 통합.

4. **테스트/마이그레이션 전략**
   - 기존 Tesseract 기반 코드와 YOLO+LLM-only 경로를 **일시적으로 공존**시켜, 라인 테스트 중 비교 가능하게 유지.
   - Checkpoint 4 이후, 충분한 라인 테스트/벤치마크가 끝나면:
     - Tesseract 의존 패키지를 `requirements.txt`에서 제거,
     - 코드/문서에서 OCR 관련 설명을 정리.

이 모델 체인지 계획은 Phase 2~5를 모두 관통하는 장기 리팩터링으로, 실제 라인 PC에 배포되는 최종 버전은 “Llama4-Scout-8B-Q4 + YOLO26x” 조합의 **미니멀 오프라인 컴퓨터-유즈 에이전트** 형태로 귀결되는 것을 목표로 한다.

개발자는 새로운 기능을 설계하거나 수정할 때마다 이 ROADMAP을 우선 검토하고, 현재 단계와 일치하는지 확인한 뒤 작업을 진행해야 한다.

---

## Pre-deployment Local Validation Strategy (라인 PC 배포 전 로컬 검증 전략)

EXE 파일의 예상 용량(수백 MB)과 GitHub Actions 빌드/아티팩트 업로드·다운로드 시간이 매우 크기 때문에, **라인 PC 배포 전에 로컬에서 최대한 많은 검증을 완료**하는 것을 원칙으로 한다.

- **원칙 1 – 로컬 기능 검증 우선**  
  - 가능한 모든 오류는 로컬 개발 환경(또는 경량 VM)에서:
    - Python 단위 테스트/통합 테스트 (`src/test_sop.py` 및 추가 테스트),
    - `run_console()`를 직접 실행한 CLI 시나리오 테스트,
    - LLM 비활성화/활성화 시나리오 (llm.enabled true/false, 잘못된 model_path/http_url 등),
    - [L] / [C] 명령 흐름의 예외 처리,
  를 통해 먼저 발견·해결한다.

- **원칙 2 – CI 빌드는 체크포인트 단위로**  
  - GitHub Actions를 통한 PyInstaller EXE 빌드는:
    - Phase / Checkpoint 단위의 의미 있는 단계가 완료되었을 때만 수행한다.
    - 단순한 콘솔 메시지 변경, 사소한 UX 수정 등은 CI 빌드를 즉시 트리거하지 않는다.
  - 이렇게 해서, **무거운 Torch/YOLO 의존성 설치와 EXE 아티팩트 생성에 드는 시간을 최소화**한다.

- **원칙 3 – LLM 없이도 동작 가능한 경로 유지**  
  - 라인 PC에 배포하기 전에:
    - LLM 관련 의존성이 전혀 없는 환경에서도 `[1]/[2]/[3]` SOP 실행과 기본 로그 수집이 100% 정상 동작해야 한다.
    - LLM 모듈/설정이 잘못되어도, 콘솔에는 **친절한 가이드가 포함된 오류 메시지**만 출력되고, EXE가 비정상 종료되지 않아야 한다.

- **원칙 4 – 가짜/경량 LLM으로 빠른 반복**  
  - 실제 Qwen2.5-VL GGUF 로딩이 무겁기 때문에:
    - 개발 단계에서는 경량 테스트 모델 또는 “에코/더미 응답”을 하는 HTTP 서버/모의 객체를 사용해,
    - `[L]` 분석, `sop_advisor` 패치 적용, `[C]` 챗 모드의 프로토콜/UX를 빠르게 반복 검증한다.
  - 라인 PC에 실제 모델을 배포하는 것은 Phase 5의 “Hardening & Field Validation” 단계에서 수행한다.

- **원칙 5 – 배포 전 최종 체크리스트**  
  - 실제 라인 PC 배포 전에는 다음 항목을 최소 1회 이상 확인한다:
    - `build_exe.spec`와 GitHub Actions가 사용하는 Python/requirements 버전이 일치하는지,
    - `assets/models`와 YOLO 가중치 파일이 LFS/Artifacts를 통해 정상 전파되는지,
    - `config.json` / `config.proposed.json`의 스키마가 문서(README/ROADMAP)와 맞는지,
    - `[1]/[2]/[3]/[L]/[C]` 전체 플로우를 로컬 또는 테스트 PC에서 한 번 이상 실행했는지.

이 전략을 통해, EXE 아티팩트 빌드/다운로드 및 라인 PC 설치·테스트에 드는 비용을 최소화하면서도, 기능 완성도와 안정성을 최대한 로컬 단계에서 확보하는 것을 목표로 한다.

---

## Checkpoints (진행 상태)

이 섹션은 실제 코드/문서 구현 상태를 기준으로 한 **체크포인트 기반 진행 상황**을 기록한다.

- **Checkpoint 1 – Phase 2/3 기반 구축 (완료)**  
  - `src/llm_offline.py` 구현 및 `OfflineLLM.chat()/analyze_logs()` 스켈레톤 작성.
  - `LogManager.analyze_with_llm()`에서 LLM 호출 파이프라인 연결.
  - `run_console()`에 `[L]` (LLM 분석) / `[C]` (Chat mode v1) 진입점 추가.

- **Checkpoint 2 – Phase 4 스켈레톤 (완료)**  
  - `src/sop_advisor.py`:
    - `SAFE_NUMERIC_RANGES`, `_set_nested()`, `apply_config_patch()`, `summarize_failures()`, `propose_actions()` 구현.
  - `assets/config.proposed.json` 생성 전략 도입:
    - `[L]` 명령 실행 시, LLM이 제안한 `config_patch`를 안전 범위 내에서 적용한 뒤, `assets/config.proposed.json`으로만 저장.
    - 기존 `assets/config.json`은 **자동으로 덮어쓰지 않음**.
  - 콘솔 `[L]` 흐름에서 최근 실패 이벤트를 요약(`summarize_failures`)하여 엔지니어가 반복 오류 패턴을 빠르게 파악 가능.

- **Checkpoint 3 – LLM UX & 제안 출력 정리 (완료)**  
  - **[C] Chat mode UX 다듬기**:
    - 진입 시 초기 안내 문구와 예시 질문(실패 단계 요약/핀 카운트 튜닝/ROI 실패 원인 추정 등)을 콘솔에 표시하도록 구현됨.
    - LLM/백엔드 오류 발생 시, 단순 예외 문자열 대신 “config.json의 llm.* 설정/로컬 LLM 서버 상태를 확인하라”는 가이드를 포함한 메시지를 출력하도록 구현됨.
  - **`sop_advisor.propose_actions()` 결과를 사람이 읽기 좋은 리스트로 출력**:
    - `[L]` 분석 결과에서 `config_patch`와 `sop_recommendations`를 `propose_actions()`로 정규화한 뒤,
      콘솔에 `[CONFIG]` / `[SOP]` 라벨이 붙은 번호 매겨진 리스트로 출력하도록 구현됨.
  - **`config.proposed.json` 수동 적용 절차 문서화**:
    - `README.md`에 “LLM & config.proposed.json 수동 적용 가이드” 섹션을 추가하여:
      - `[L]` 실행 → `assets/config.proposed.json` 생성,
      - `config.json`과 비교·검토,
      - 승인된 변경만 수동으로 반영하는 절차를 상세히 기술함.
    - 본 ROADMAP Phase 4/Checkpoints 섹션에서도 “자동 적용은 하지 않고, 항상 사람이 검토 후 수동 적용한다”는 원칙을 명시함.

- **Checkpoint 4 – 라인 PC 배포 전 로컬 검증 완결 (진행 예정)**  
  - **목표**: EXE와 라인 PC에 실제 배포하기 전에, 로컬(또는 테스트 PC)에서 수행할 수 있는 모든 검증 항목을 정의·실행하고, 그 결과를 문서로 남겨 **배포 준비 상태를 100% 검증**하는 것.
  - **검증 요소 및 테스트 방법 (예정)**:
    - **A. Python 레벨 정적/동적 테스트**
      - `pytest` 기반 단위/통합 테스트:
        - `src/test_sop.py` 및 추가 테스트 케이스 작성.
        - YOLO/화면 의존 부분은 `monkeypatch`와 더블(mock)을 이용해 헤드리스 환경에서도 통과 가능하도록 설계.
      - 정적 검증:
        - `basedpyright`/mypy 등 타입 체커를 통한 주요 모듈(`vision_engine`, `control_engine`, `sop_executor`, `main`, `log_manager`, `llm_offline`, `sop_advisor`) 점검.
        - `python -m compileall src` 등으로 기본 문법 수준 이상 문제 없는지 확인.
    - **B. 콘솔/사용자 플로우 테스트**
      - `run_console()`를 직접 실행해 다음 시나리오를 수동/스크립트로 검증:
        - `[1]/[2]/[3]` SOP 실행: 정상 완료 / 예외 발생 / 사용자 중단(CTRL+C) 각각의 로그 및 요약이 의도대로 기록되는지.
        - `[L]` 실행:
          - `llm.enabled = false` → LLM 미활성 노트가 출력되고 예외 없이 종료되는지.
          - LLM 설정 오류 (잘못된 model_path/backend/http_url 등) → 친절한 에러 메시지와 함께 안전하게 복구되는지.
          - 정상 LLM 백엔드 → `config_patch`/`sop_recommendations`/`proposed actions`/`config.proposed.json` 생성 경로가 모두 정상인지.
        - `[C]` 실행:
          - 로그가 없는 상태에서의 진입 차단 메시지.
          - LLM 비활성/설정 오류 시의 오류 메시지.
          - 정상 LLM과의 짧은 Q&A 세션(요약 1턴 + 추가 질문 몇 개).
    - **C. 파일/경로/자산 검증**
      - `assets/config.json` / `assets/config.proposed.json` 스키마 검증:
        - 필수 키 (`version`, `password`, `ocr_threshold`, `llm.*` 등)가 누락되지 않았는지.
        - `SAFE_NUMERIC_RANGES` 범위를 벗어나는 값이 없는지.
      - `assets/models/yolo26n.pt` 존재 여부, Git LFS/Artifacts 경로 일관성 확인.
      - `logs/` 디렉터리 구조 (`run_id/summary.json`, `events.jsonl`, `screens/`)가 ROADMAP/README 설명과 일치하는지 확인.
    - **D. CI/CD 상호 검증 (로컬 ↔ Actions)**
      - 로컬에서 사용하는 Python 버전/requirements와 `.github/workflows/release.yml`에 정의된 버전이 일관된지 재검토.
      - Actions에서 사용하는 `build_exe.spec` / PyInstaller 옵션이 로컬 빌드와 동일한지 확인.
      - 필요 시, Actions를 “릴리스 전 최종 건강검진” 수준으로만 실행하고, 사소한 코드 변경마다 재빌드하지 않는 전략을 유지.
    - **E. 결과 문서화**
      - 각 테스트 항목에 대해:
        - 실행 환경 (Python 버전, OS, 가상환경, LLM 백엔드 종류),
        - 수행한 명령/시나리오,
        - 기대 결과와 실제 결과,
        - 발견된 이슈와 조치,
      를 간단한 표/리스트로 정리하여 ROADMAP 또는 별도 `TEST_REPORT.md`에 축적.
  - **완료 조건 (Checkpoint 4 Done)**:
    - 위 검증 요소 A~D에 대해 최소 1회 이상 실행/기록이 완료되고,
    - 남아 있는 이슈/위험요소가 문서화된 상태에서 “라인 PC에 배포해도 된다”는 수준의 신뢰도가 확보되었을 때, Checkpoint 4를 완료로 마크한다.

