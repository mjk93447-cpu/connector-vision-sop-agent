#!/usr/bin/env bash
# Gemini CLI 토큰 절약 헬퍼 스크립트
# 사용법: source tools/gemini-helpers.sh  또는  bash tools/gemini-helpers.sh <커맨드>
#
# 커맨드 목록:
#   diff-review       현재 staged 변경 코드 리뷰
#   diff-side-effect  HEAD 대비 전체 diff 사이드이펙트 분석
#   test-fail         테스트 실패 원인 분석
#   file-summary      파일 구조 요약 (인자: 파일명)
#   pr-draft          PR 설명 초안 생성
#   config-review     config.proposed.json 검토
#   yolo-check        YOLO 규칙 위반 확인 (yolov8/9/10/11 잔재)

set -e

CMD=${1:-help}

case "$CMD" in
  diff-review)
    echo "=== [Gemini] staged diff 코드 리뷰 ==="
    git diff --staged | gemini -p \
      "이 코드 변경을 리뷰해줘.
체크 항목:
1. 버그 가능성 (예외처리 누락, 타입 오류)
2. YOLO 규칙 위반: yolov8/yolov9/yolov10/yolov11 사용 여부 (발견 시 즉시 표시)
3. 테스트가 필요한데 없는 로직
4. 스타일 이슈 (black/ruff 기준)
한국어로 출력. 이슈 없으면 '이상 없음' 출력."
    ;;

  diff-side-effect)
    echo "=== [Gemini] HEAD diff 사이드이펙트 분석 ==="
    git diff HEAD | gemini -p \
      "이 변경의 잠재적 사이드이펙트를 분석해줘.
- 깨질 수 있는 기존 기능
- 영향받는 모듈/클래스
- tests/unit/ 에서 실패 가능한 테스트
- YOLO26x 규칙 위반(yolov8/9/10/11) 여부
한국어 불릿 포인트로 출력."
    ;;

  test-fail)
    echo "=== [Gemini] 테스트 실패 원인 분석 ==="
    bash run_tests.sh 2>&1 | tail -100 | gemini -p \
      "pytest 출력이야. 분석해줘:
1. 실패한 테스트 목록과 각 원인 (1줄 요약)
2. 공통 원인이 있으면 묶어서 설명
3. 수정 우선순위 (높음/중간/낮음)
한국어로 출력."
    ;;

  file-summary)
    FILE=${2:-""}
    if [ -z "$FILE" ]; then
      echo "사용법: $0 file-summary <파일경로>"
      exit 1
    fi
    echo "=== [Gemini] $FILE 구조 요약 ==="
    cat "$FILE" | gemini -p \
      "이 Python 파일을 분석해줘:
1. 클래스·함수 목록 (시그니처 포함)
2. 외부 의존성 (import 목록)
3. 핵심 로직 흐름 요약 (3~5줄)
한국어로 출력."
    ;;

  pr-draft)
    echo "=== [Gemini] PR 설명 초안 ==="
    git log main..HEAD --oneline | gemini -p \
      "이 커밋 목록으로 GitHub PR 설명 초안을 작성해줘.
형식:
## Summary
- (변경 사항 불릿)

## Test Plan
- (테스트 방법)

한국어로 작성."
    ;;

  config-review)
    PROPOSED="assets/config.proposed.json"
    if [ ! -f "$PROPOSED" ]; then
      echo "assets/config.proposed.json 없음"
      exit 1
    fi
    echo "=== [Gemini] config.proposed.json 검토 ==="
    diff assets/config.json "$PROPOSED" 2>/dev/null | gemini -p \
      "config.json 변경 diff야. 검토해줘:
1. 변경된 설정 항목과 예상 효과
2. 위험 요소 또는 주의사항
3. 적용 권장 여부 (권장/주의/비권장)
한국어로 출력."
    ;;

  yolo-check)
    echo "=== [Gemini] YOLO 규칙 위반 검사 ==="
    grep -r "yolov8\|yolov9\|yolov10\|yolov11\|YOLOv8\|YOLOv9\|YOLOv10\|YOLOv11" \
      src/ tests/ --include="*.py" -n 2>/dev/null | \
      gemini -p \
        "YOLO 규칙 위반 grep 결과야.
규칙: yolo26x.pt만 허용, yolov8/v9/v10/v11 절대 금지.
결과가 없으면 '위반 없음' 출력.
있으면 파일:라인 형식으로 목록화하고 수정 방법 제안." \
      || echo "[OK] YOLO 규칙 위반 없음"
    ;;

  help|*)
    echo "사용법: bash tools/gemini-helpers.sh <커맨드>"
    echo ""
    echo "커맨드:"
    echo "  diff-review       staged 변경 코드 리뷰"
    echo "  diff-side-effect  HEAD diff 사이드이펙트 분석"
    echo "  test-fail         테스트 실패 원인 분석"
    echo "  file-summary <파일>  파일 구조 요약"
    echo "  pr-draft          PR 설명 초안 생성"
    echo "  config-review     config.proposed.json 검토"
    echo "  yolo-check        YOLO 규칙 위반(v8/9/10/11) 검사"
    ;;
esac
