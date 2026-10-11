#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-./venv/bin/python}"
if [ ! -x "$PYTHON" ]; then PYTHON="python3"; fi

echo "=== 1. LINT ==="
"$PYTHON" -m flake8 .

echo "=== 2. UNIT + INTEGRATION TESTS & COVERAGE ==="
"$PYTHON" -m pytest tests/test_unit.py tests/test_integration.py -q \
  --cov=app --cov-branch --cov-report=term-missing --cov-report=json:coverage.json

echo "=== 3. COVERAGE GATE (>=80% строк, >=70% ветвлений) ==="
"$PYTHON" check_coverage.py coverage.json

echo "=== 4. E2E TESTS (Playwright) ==="
"$PYTHON" -m pytest tests/test_e2e.py -q --tracing retain-on-failure

echo "=== 5. SECURITY SCAN ==="
"$PYTHON" -m bandit -r app -q
"$PYTHON" -m pip_audit -r requirements.txt

echo "=== CI/CD PIPELINE PASSED SUCCESSFULLY ==="
