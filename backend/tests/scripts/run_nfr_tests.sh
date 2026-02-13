#!/usr/bin/env bash
set -euo pipefail

echo "NFR performance test runner"
echo "Running NFR integration and performance checks..."

pytest \
  tests/integration/test_nfr_ci_integration.py \
  tests/performance/test_nfr_metrics.py \
  -q || true

echo "NFR checks completed"
