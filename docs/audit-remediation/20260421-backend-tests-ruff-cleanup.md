# 2026-04-21 Backend Tests Ruff Cleanup

## Scope

Ralph cleanup task: make `cd backend && ruff check src tests --quiet` pass by cleaning historical lint debt in backend tests.

Constraints followed:

- Primarily changed `backend/tests/**`.
- No Docker/deploy/ops changes.
- No dependencies added.
- No effective tests deleted.
- Changes were mechanical: import sorting, unused import cleanup, trailing whitespace cleanup, pyupgrade-style `datetime.UTC`, and precise `# noqa: E402/F401` for test-time import ordering / side-effect imports.

## Verification

### Ruff

Command:

```bash
cd backend && ruff check src tests --quiet
```

Result: **PASS**.

### Targeted pytest: manually touched lint-fix files

Command:

```bash
cd backend && .venv-test/bin/python -m pytest \
  tests/integration/test_nfr_ci_integration.py \
  tests/integration/test_release_gate.py \
  tests/performance/test_e2e_latency.py \
  tests/performance/test_interruption_latency.py \
  tests/performance/test_nfr_metrics.py \
  tests/performance/test_vagueness_detection.py \
  tests/unit/evaluation/test_evaluation_schemas.py \
  tests/unit/evaluation/test_realtime_scoring.py \
  -q --no-cov
```

Result: **93 passed, 5 skipped, 8 warnings**.

### Targeted pytest: final-gate regression/focused subsets

Command:

```bash
cd backend && .venv-test/bin/python -m pytest \
  tests/unit/common/test_auth_transport_matrix.py \
  tests/unit/test_history_service_evidence_projection.py \
  tests/unit/test_session_runtime_authority.py \
  tests/unit/test_stepfun_realtime_persistence.py \
  tests/contract/test_audio_audit_contract.py \
  tests/contract/test_presentations.py \
  tests/unit/test_capability_base.py \
  tests/unit/test_presentation_handler_persistence.py \
  tests/unit/test_websocket_handler.py \
  tests/unit/test_knowledge_retrieval.py \
  tests/unit/test_presentation_ai_policy_service.py \
  -q --no-cov
```

Result: **154 passed, 1 warning**.

### Broad changed-file pytest attempt

Command attempted:

```bash
cd backend && .venv-test/bin/python -m pytest $(git -C .. diff --name-only -- 'backend/tests/**/*.py' | sed 's#^backend/##') -q --no-cov
```

Result: interrupted after ~4m19s because it was long-running. Before interruption it reported:

- 235 passed
- 21 skipped
- 5 failed

Failures were in integration presentation flows / report flow and matched active application contract drift from the larger audit-remediation integration (admin-only presentation upload and canonical presentation score contract), not the mechanical ruff cleanup itself. They require a separate contract decision or implementation fix and were not modified semantically by this lint cleanup.

## Remaining risks

- Full backend pytest was not run to completion in this cleanup lane.
- The broad changed-file pytest attempt surfaced non-ruff integration failures in presentation flow/report tests; these should be handled as a separate contract/runtime follow-up, not as lint debt.
