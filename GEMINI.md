# Connector Vision SOP Agent — GEMINI.md

> Gemini CLI 프로젝트 설정 (gemini-2.5-flash, 1M 컨텍스트)

## 이 프로젝트 개요
Python 3.11 기반 YOLO26x Vision + Ollama LLM SOP 에이전트.
소스: `src/`, 테스트: `tests/unit/` (336 pass, 92% coverage), GUI: PyQt6 7탭.

## ⚠️ 절대 수정 금지 파일
```
assets/models/     assets/config.json     /config/secrets.yaml
```

## Gemini 역할 (토큰 절약 전략)

Gemini CLI는 **탐색·분석·리뷰** 전담. 코드 편집은 Claude Code.

| 작업 | 도구 |
|------|------|
| 코드 탐색·요약 | **Gemini** |
| diff 리뷰·사이드이펙트 분석 | **Gemini** |
| 테스트 실패 원인 분석 | **Gemini** |
| 대형 파일 요약 (500줄+) | **Gemini** |
| 실제 코드 수정·편집 | Claude Code |
| 테스트 작성·실행 | Claude Code |
| 커밋·PR | Claude Code |

## 핵심 커맨드 레퍼런스

```bash
# diff 사이드이펙트 분석
git diff HEAD | gemini -p "이 변경의 잠재적 사이드이펙트와 위험 요소를 나열해줘"

# 테스트 실패 원인 분석
bash run_tests.sh 2>&1 | tail -50 | gemini -p "실패 원인 분석 후 수정 방향 제안해줘"

# 대형 파일 요약
cat src/gui/main_window.py | gemini -p "이 파일의 클래스·메서드 구조를 요약해줘"

# 커밋 전 리뷰
git diff --staged | gemini -p "코드 품질 리뷰: 버그, 스타일 이슈, 누락된 예외처리 확인"

# 의존성 체인 분석
grep -r "from src\." src/ tests/ --include="*.py" -l | gemini -p "의존성 그래프 요약"

# PR 설명 초안 생성
git log main..HEAD --oneline | gemini -p "이 커밋들로 PR 설명 초안 작성해줘 (한국어)"

# config 변경 제안 검토
cat assets/config.proposed.json | gemini -p "이 config 변경이 안전한지 검토해줘"
```

## 프로젝트 스택
- YOLO: `yolo26x.pt` 단독 (YOLOv8/v9/v10/v11 금지)
- LLM: phi4-mini-reasoning via Ollama (http://localhost:11434)
- OCR: WinRT primary → PaddleOCR fallback
- GUI: PyQt6 7탭, 완전 영어 UI
- 테스트: pytest, 336 pass, `bash run_tests.sh`

## 파일 구조 요약
```
src/
  main.py              # 진입점 (--console 플래그)
  vision_engine.py     # YOLO26x 단일 클래스
  ocr_engine.py        # OCR 엔진 (WinRT/PaddleOCR)
  sop_executor.py      # 12단계 SOP
  llm_offline.py       # Ollama HTTP 백엔드
  gui/
    main_window.py     # PyQt6 7탭 메인 윈도우
    panels/            # 각 탭 패널
  training/
    training_manager.py
    dataset_manager.py
tests/unit/            # 336 pass
assets/
  config.json          # v2.0.0 (수정 금지)
  sop_steps.json       # 12단계 SOP 정의
  models/yolo26x.pt    # 베이스 모델 (수정 금지)
```

## 커밋 컨벤션
`[feat/fix/refactor/chore/test] 한국어 설명`
