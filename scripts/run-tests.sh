#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# moltkit test runner
# Usage:
#   ./scripts/run-tests.sh              # All tests
#   ./scripts/run-tests.sh test_client   # SDK only
#   ./scripts/run-tests.sh test_cli      # CLI only
#   ./scripts/run-tests.sh test_mcp      # MCP only
#   ./scripts/run-tests.sh --integration # With live API (needs MOLTKIT_API_KEY)
# ──────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

# Install test deps if missing
pip install -e ".[test]" -q 2>/dev/null || true

FILTER="${1:-}"
INTEGRATION=false

if [ "$FILTER" = "--integration" ]; then
    INTEGRATION=true
    FILTER=""
fi

echo "🧪 moltkit test suite"
echo "━━━━━━━━━━━━━━━━━━━"

if [ "$INTEGRATION" = true ]; then
    if [ -z "${MOLTKIT_API_KEY:-}" ]; then
        echo "❌ MOLTKIT_API_KEY not set. Integration tests require a real API key."
        exit 1
    fi
    echo "🔴 Integration tests (live API) — may create test data"
    python -m pytest tests/ -k "integration" -v --tb=short
else
    echo "🟢 Unit tests (mocked, no network)"
    if [ -n "$FILTER" ]; then
        python -m pytest "tests/${FILTER}.py" -v --tb=short
    else
        python -m pytest tests/ -v --tb=short --ignore=tests/test_integration.py 2>/dev/null || \
        python -m pytest tests/ -v --tb=short
    fi
fi
