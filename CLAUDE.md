# 프로젝트명: OLED 패널 검사 비전 AI — Connector Vision SOP Agent

## 프로젝트 개요

삼성 OLED 라인 PC에서 12단계 커넥터 SOP를 자동화하는 오프라인 EXE 에이전트.
YOLO26n + Tesseract OCR PSM7 + PyAutoGUI 기반 비전/제어 레이어로 Mold ROI 설정과 핀 검증을 수행한다.

See @README.md for project overview
See @ROADMAP.md for planned milestones

---

## 기술 스택

- **Python 3.11** (PyInstaller EXE 타깃 — 3.12에서는 Torch 호환 문제 발생 가능)
- **PyTorch 2.4 (CPU)** — YOLO26n 추론
- **OpenCV 4.9** — 이미지 전처리 및 ROI 추출
- **Tesseract OCR (PSM 7)** — 단일 라인 텍스트 인식
- **PyAutoGUI** — 마우스/키보드 제어
- **테스트**: `pytest` (커버리지 80% 이상 유지, 모노키패치 기반 — 실 디스플레이 불필요)
- **포맷터**: `black`, `ruff` (코드 수정 후 반드시 실행)
- **기본 모델**: `claude-sonnet-4-6` (Sonnet 4.6 기본 사용)

---

## 절대 수정 금지 경로 (IMPORTANT)

```
assets/models/        # 학습된 YOLO 모델 가중치 (yolo26n.pt 포함)
assets/config.json    # 라인 PC 운영 설정 (비밀번호·ROI·임계값 포함)
/data/models/         # 학습된 모델 가중치 (외부 마운트)
/config/secrets.yaml  # API 키
/data/raw/            # 원본 이미지 데이터
```

> 위 경로는 어떠한 경우에도 자동으로 덮어쓰지 않는다.
> LLM 튜닝 제안은 반드시 `assets/config.proposed.json`으로만 출력하고,
> 엔지니어가 검토 후 수동으로 `config.json`에 반영한다.

---

## 핵심 파일 맵

```
src/main.py           # 진입점 및 콘솔 UI (run_console / main)
src/vision_engine.py  # YOLO26n + OpenCV + Tesseract 비전 레이어
src/control_engine.py # PyAutoGUI 클릭/드래그 제어 레이어
src/sop_executor.py   # 12단계 SOP 오케스트레이션
src/sop_advisor.py    # LLM 분석 결과 → config_patch 제안
src/llm_offline.py    # 오프라인 LLM 래퍼 (llama-cpp / HTTP)
src/log_manager.py    # 실행 로그 기록 및 LLM 페이로드 빌드
src/config_loader.py  # assets/config.json 로더
src/test_sop.py       # pytest 스모크 테스트 스위트
assets/config.json    # 라인 튜닝 파라미터 템플릿
```

---

## 워크플로우 규칙

1. **코드 수정 후 반드시 `pytest` 실행하고 통과 확인**
2. **테스트 실패 시 스스로 원인 분석 후 수정 반복** — 동일 커맨드 재시도 금지
3. **커밋 전 `black . && ruff check .` 실행**
4. **브랜치 전략**: `feature/*` → `develop` → `main`
5. **커밋 메시지 형식**: `[feat/fix/refactor/chore/test] 한국어 설명`
   - 예: `[feat] OCR 임계값 동적 조정 기능 추가`
   - 예: `[fix] ROI 좌표 범위 초과 시 크래시 수정`
6. **config.json 자동 수정 절대 금지** — 제안은 `config.proposed.json`으로만

---

## 자주 쓰는 커맨드

```bash
# 테스트 (커버리지 포함)
pytest tests/ -v --cov=src
# 또는 현재 구조에서
pytest src/test_sop.py -v

# 포맷 & 린트
black .
ruff check .

# EXE 빌드 (라인 PC 배포용)
build.bat

# 배포 패키지 생성
deploy_package.bat

# 개발 서버 (API 레이어 추가 시)
uvicorn main:app --reload --port 8000

# Docker 빌드
docker build -t oled-inspection .
```

---

## 설정 구조 (config.json 주요 키)

```json
{
  "password": "라인비번",
  "ocr_threshold": 0.6,
  "vision": {
    "confidence_threshold": 0.6,
    "ocr_psm": 7
  },
  "control": {
    "retries": 3
  },
  "llm": {
    "enabled": false,
    "model_path": "",
    "backend": "llama_cpp"
  }
}
```

---

## 보안 및 안전 원칙

- `config.json`의 `password` 필드는 로그에 절대 출력하지 않는다.
- `assets/config.proposed.json`은 엔지니어 검토 전 자동 적용 불가.
- 모델 가중치(`assets/models/`) 교체 시 반드시 버전 태그와 함께 커밋.
- 라인 PC는 오프라인 환경 — 외부 네트워크 호출 코드 추가 금지.

---

## 테스트 정책

- 테스트는 모노키패치 기반으로 실 디스플레이·YOLO 가중치 없이 실행 가능해야 한다.
- 새 SOP 단계 추가 시 대응하는 테스트 케이스를 반드시 함께 작성한다.
- 커버리지 80% 미만으로 떨어지면 PR 병합 불가.
