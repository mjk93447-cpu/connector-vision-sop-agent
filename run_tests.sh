#!/usr/bin/env bash
# run_tests.sh — 테스트 + 커버리지 래퍼
set -euo pipefail

echo "=== pytest (unit, coverage) ==="
python -m pytest tests/unit/ -q --cov=src --cov-config=.coveragerc

echo ""
echo "=== black check ==="
python -m black src/ tests/ --check

echo ""
echo "=== ruff check ==="
python -m ruff check src/ tests/

echo "=== ALL PASSED ==="
