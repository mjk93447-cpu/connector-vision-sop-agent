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

개발자는 새로운 기능을 설계하거나 수정할 때마다 이 ROADMAP을 우선 검토하고, 현재 단계와 일치하는지 확인한 뒤 작업을 진행해야 한다.


