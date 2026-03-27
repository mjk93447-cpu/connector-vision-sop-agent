#!/usr/bin/env bash
# scripts/ci_check.sh — 로컬 CI 사전 검증
#
# build.yml의 테스트 단계를 그대로 재현하여 Push 전에 빌드 실패 여부를 확인한다.
#
# 사용법:
#   bash scripts/ci_check.sh          # 전체 (unit + integration)
#   bash scripts/ci_check.sh unit      # unit 테스트만 (빠름, ~30s)
#   bash scripts/ci_check.sh integ     # integration 테스트만 (느림, 90-180s)
#
# 종료 코드:
#   0 — 모든 테스트 통과 (CI 통과 가능성 높음)
#   1 — 하나 이상 실패 (Push 전 수정 필요)

set -euo pipefail

MODE="${1:-all}"
PASS=0
FAIL=0

banner() { echo ""; echo "══════════════════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════════════════"; }
ok()     { echo "[PASS] $*"; ((PASS++)) || true; }
fail()   { echo "[FAIL] $*"; ((FAIL++)) || true; }

# ── Unit tests (mirrors build.yml: --timeout=60) ──────────────────────────
run_unit() {
    banner "Unit Tests  (timeout=60s per test)"
    if python -m pytest tests/unit/ -q --tb=short --no-header --timeout=60; then
        ok "unit tests"
    else
        fail "unit tests"
    fi
}

# ── Integration tests (mirrors build.yml: --timeout=300) ──────────────────
run_integ() {
    banner "Integration Tests  (timeout=300s per test)"
    if python -m pytest tests/integration/ -q --tb=short --no-header --timeout=300; then
        ok "integration tests"
    else
        fail "integration tests"
    fi
}

case "$MODE" in
    unit)  run_unit  ;;
    integ) run_integ ;;
    all)   run_unit; run_integ ;;
    *)
        echo "Usage: $0 [unit|integ|all]"
        exit 1
        ;;
esac

banner "CI Check Summary"
echo "  PASSED : $PASS"
echo "  FAILED : $FAIL"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo "❌  CI check FAILED — fix above errors before pushing."
    exit 1
else
    echo "✅  CI check PASSED — safe to push."
    exit 0
fi
