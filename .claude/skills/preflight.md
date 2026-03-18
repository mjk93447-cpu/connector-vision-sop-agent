# Pre-flight 체크리스트 (대형 리팩토링·다수 파일 수정 전 필수)

이 skill은 단일 채팅에서 70K+ 토큰을 소진하는 에러-재시도 루프를 예방한다.
다수 파일 수정(3개 이상) 또는 기존 API 변경 시 반드시 이 체크리스트를 완료한 뒤 구현을 시작한다.

## 1. 작업 범위 명시
수정 대상 파일 목록을 나열하고, 각 파일의 변경 의도를 1줄씩 적는다.

## 2. 테스트 베이스라인 확인
```bash
bash run_tests.sh
```
현재 통과 수(N pass)를 기록한다. 이것이 변경 후 복구 기준이다.

## 3. 의존성 체인 파악
수정 파일을 import하는 파일 목록을 Grep으로 확인한다.
```bash
grep -r "from src.모듈명\|import 모듈명" src/ tests/ --include="*.py" -l
```
영향 범위가 5개 파일 초과 시 → 단계 분할 후 순차 처리 필수.

## 4. 단계별 커밋 분할 계획
전체를 한 번에 변경하지 않는다. 논리적 단위(기능 1개)마다:
1. 변경 → 2. `bash run_tests.sh` 통과 확인 → 3. 커밋

## 5. Rollback 포인트 설정
```bash
git stash        # 작업 전 스냅샷 (또는 임시 브랜치 생성)
```

## 6. Gemini 위임 검토 (필수 — 토큰 절약)
탐색·분석·리뷰 성격 작업 → Gemini CLI로 선위임 후 Claude 구현.
규칙: `.claude/rules/gemini.md` / 헬퍼: `tools/gemini-helpers.sh`

```bash
# 사이드이펙트 분석
bash tools/gemini-helpers.sh diff-side-effect

# 수정 예정 파일 구조 파악
cat src/대상파일.py | gemini -p "클래스·함수 구조 요약"

# 테스트 실패 분석
bash tools/gemini-helpers.sh test-fail

# YOLO 규칙 위반 검사
bash tools/gemini-helpers.sh yolo-check
```

> ⚠️ 500줄+ 파일 분석, diff 리뷰는 반드시 Gemini 위임. Claude 직접 읽기 금지.
