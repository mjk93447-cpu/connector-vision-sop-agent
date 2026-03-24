# MCP 서버 관리 (토큰 절약) — v2 (2026-03-24)

## 현황 (설정 완료)

| MCP | 상태 | 용도 |
|-----|------|------|
| Desktop Commander | ✅ 허용 (17개 도구) | 다중 파일 읽기, 비동기 테스트 실행 |
| Windows-MCP | ✅ 허용 (6개 도구) | PyQt6 GUI 자동 테스트 |
| HuggingFace | ✅ 허용 (2개 도구) | 모델 검색 시에만 |
| Claude_Preview | ⛔ deny 등록 | Python 개발에 불필요 |
| Claude_in_Chrome | ⛔ deny 등록 | 불필요 |

## 핵심 규칙

### Desktop Commander — 다중 파일 읽기 (Claude Read 대체)
```
# 나쁨 (3번 호출)
Read(llm_offline.py) → Read(workers.py) → Read(llm_panel.py)

# 좋음 (1번 호출) — DC read_multiple_files
read_multiple_files([llm_offline.py, workers.py, llm_panel.py])
```

### Desktop Commander — 비동기 테스트 실행
```
# 나쁨 (블로킹)
Bash("bash run_tests.sh")  ← 테스트 끝날 때까지 대기

# 좋음 (비동기)
start_process("bash run_tests.sh")  → 다른 파일 작업 병행
read_process_output(pid)            → 완료 후 결과 확인
```

### Gemini 2.5 Pro — 대규모 분석 위임
```bash
# 500줄+ 파일 → Gemini에 위임 (Claude 토큰 0 소모)
bash tools/gemini-helpers.sh file-summary src/vision_engine.py

# 다중 파일 동시 분석
bash tools/gemini-helpers.sh multi-file-summary src/llm_offline.py src/gui/workers.py

# 대형 작업 전 전체 분석
bash tools/gemini-helpers.sh preflight src/
```

### Windows-MCP — GUI 테스트
가이드: `tools/gui-test-mcp.md`
- Bug2 LLM 응답 검증
- Training tqdm 검증
- Vision YOLO overlay 검증
- OCR 다단어 인식 검증

## 사용 금지
- `mcp__Claude_Preview__*` — deny 등록됨
- `mcp__Claude_in_Chrome__*` — deny 등록됨

## scheduled-tasks 등록 목록
| 태스크 | 주기 | 용도 |
|--------|------|------|
| daily-morning-init | 매일 09:00 | 환경 점검 + 커밋 분석 + progress.md 업데이트 |
| pre-commit-check | ad-hoc | 커밋 전 YOLO 위반 + 테스트 검증 + Gemini 리뷰 |
| weekly-build-trigger | 매주 월 09:00 | 빌드 상태 점검 + 자동 트리거 판단 |
