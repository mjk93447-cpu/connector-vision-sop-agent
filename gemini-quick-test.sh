#!/usr/bin/env bash
# Gemini CLI 전체 검증 스크립트
# 사용법: bash gemini-quick-test.sh

set -e

echo "=== [1] Gemini CLI 버전 확인 ==="
gemini --version

echo ""
echo "=== [2] 인증 상태 확인 ==="
echo "ping" | gemini -p "Reply with only: PONG" && echo "✓ 인증 OK" || echo "✗ 인증 실패 — gemini 실행 후 Y 입력 필요"

echo ""
echo "=== [3] 이 프로젝트 컨텍스트 로딩 확인 ==="
echo "이 프로젝트의 YOLO 모델 규칙은?" | gemini -p \
  "GEMINI.md 기준으로 한 문장 답변" 2>&1 | head -5

echo ""
echo "=== [4] diff-side-effect 위임 테스트 ==="
echo "[test] git diff HEAD 시뮬레이션" | gemini -p \
  "사이드이펙트 없다고 한 줄로 답변" 2>&1 | head -3

echo ""
echo "=== [5] YOLO 규칙 위반 검사 ==="
bash tools/gemini-helpers.sh yolo-check 2>&1

echo ""
echo "=== [완료] Gemini CLI 세팅 정상 ==="
echo ""
echo "사용 가능한 헬퍼:"
echo "  bash tools/gemini-helpers.sh diff-review        # staged 코드 리뷰"
echo "  bash tools/gemini-helpers.sh diff-side-effect   # HEAD diff 분석"
echo "  bash tools/gemini-helpers.sh test-fail          # 테스트 실패 분석"
echo "  bash tools/gemini-helpers.sh file-summary <파일> # 파일 구조 요약"
echo "  bash tools/gemini-helpers.sh pr-draft           # PR 설명 초안"
echo "  bash tools/gemini-helpers.sh config-review      # config 변경 검토"
echo "  bash tools/gemini-helpers.sh yolo-check         # YOLO 규칙 위반 검사"
