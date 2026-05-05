#!/usr/bin/env bash
set -euo pipefail

echo "NFR performance test runner"
MODE="${1:---quick}"

case "${MODE}" in
  --help|-h)
    cat <<'EOF'
Usage: tests/scripts/run_nfr_tests.sh [--quick|--smoke|--full]
  --quick  Print NFR runner info only (default, no test execution)
  --smoke  Run quick NFR sanity checks
  --full   Run full NFR integration + performance suite
EOF
    exit 0
    ;;
  --quick)
    echo "Running NFR quick mode (no sub-tests executed)."
    ;;
  --smoke)
    echo "Running NFR smoke checks..."
    pytest \
      tests/integration/test_nfr_ci_integration.py::TestNFRCIWorkflow::test_ci_workflow_file_exists \
      tests/integration/test_nfr_ci_integration.py::TestNFRCIWorkflow::test_nfr_reporter_module_exists \
      --no-cov -q
    ;;
  --full)
    echo "Running NFR integration and performance checks..."
    pytest \
      tests/integration/test_nfr_ci_integration.py \
      tests/performance/test_nfr_metrics.py \
      --no-cov -q
    ;;
  *)
    echo "Unknown mode: ${MODE}"
    echo "Use --help to see available options."
    exit 2
    ;;
esac

echo "NFR checks completed (${MODE})"
