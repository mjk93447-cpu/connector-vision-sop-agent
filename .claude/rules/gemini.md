# Gemini CLI 위임 전략 (토큰 절약)

## 핵심 원칙
**탐색·분석·리뷰 → Gemini CLI**
**편집·구현·테스트·커밋 → Claude Code**

Gemini 2.5 Flash: 1M 토큰 컨텍스트, Claude 컨텍스트 소모 없음.

---

## 언제 Gemini에 위임하는가

### 필수 위임 (Claude 토큰 낭비 방지)
| 상황 | Gemini 커맨드 |
|------|--------------|
| 500줄+ 파일 구조 파악 | `cat 파일 \| gemini -p "구조 요약"` |
| 커밋 전 사이드이펙트 확인 | `git diff HEAD \| gemini -p "사이드이펙트 분석"` |
| 테스트 실패 로그 분석 | `bash run_tests.sh 2>&1 \| tail -60 \| gemini -p "실패 원인 분석"` |
| 의존성 그래프 파악 | `grep 결과 \| gemini -p "의존성 요약"` |
| PR 설명 초안 | `git log main..HEAD --oneline \| gemini -p "PR 설명 작성"` |
| config 변경 안전성 검토 | `cat config.proposed.json \| gemini -p "변경 안전성 검토"` |

### 선택적 위임
- 코드 리뷰 요청 (staged 변경): `git diff --staged | gemini -p "코드 리뷰"`
- 에러 메시지 디버깅: `echo "에러 내용" | gemini -p "원인과 해결책"`
- 대용량 로그 분석: `cat logs/*.jsonl | gemini -p "이상 패턴 찾아줘"`

---

## 실전 패턴

### 1. preflight 체크 (대형 작업 전)
```bash
# 수정 예정 파일들 구조 파악
cat src/vision_engine.py src/ocr_engine.py | gemini -p "두 파일 간 인터페이스와 의존성 요약"
```

### 2. 테스트 실패 분석
```bash
bash run_tests.sh 2>&1 | tail -80 | gemini -p \
  "pytest 실패 로그야. 실패 원인 분류하고 수정 우선순위 제안해줘"
```

### 3. 안전한 커밋 리뷰
```bash
git diff --staged | gemini -p \
  "코드 리뷰: 1) 버그 가능성 2) 테스트 누락 3) YOLO26x 규칙 위반(yolov8/v9/v10/v11 사용 여부) 확인"
```

### 4. 대형 리팩토링 사이드이펙트
```bash
git diff HEAD | gemini -p \
  "이 변경이 tests/unit/ 테스트에 영향을 줄 수 있는 부분 찾아줘. 깨질 수 있는 테스트 목록으로 출력"
```

### 5. 비용 없는 코드베이스 탐색
```bash
find src/ -name "*.py" | xargs cat | gemini -p \
  "이 Python 프로젝트에서 OCR 관련 코드 흐름을 요약해줘"
```

---

## 금지 사항
- Gemini에게 파일 직접 편집 요청 금지 (Claude Code 전담)
- `assets/config.json`, `assets/models/` 내용을 Gemini에 전달해 수정 요청 금지
- Gemini 출력을 검토 없이 코드에 바로 적용 금지

---

## 세션 토큰 절약 효과
- 500줄 파일 분석: Claude ~8K 토큰 → Gemini 0 토큰 (Claude 절약)
- diff 리뷰: Claude ~3K 토큰 → Gemini 0 토큰
- 테스트 실패 분석: Claude ~5K 토큰 → Gemini 0 토큰
