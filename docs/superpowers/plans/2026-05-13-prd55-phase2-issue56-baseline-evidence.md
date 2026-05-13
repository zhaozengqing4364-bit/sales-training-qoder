# PRD #55 Phase 2 / Issue #56 Backend Baseline Evidence

## Scope

Issue #56 establishes the backend baseline gate before Phase 2 feature work. The
baseline verifies pytest collection state, curriculum/runtime regression surfaces,
and the legacy sales handler invariant.

## Backend baseline

- Command: `cd backend && pytest --collect-only --no-cov`
- Result: `1623 tests collected, 34 errors during collection`
- Unexpected collection errors: `0`
- Classification: all 34 collection errors are environment-only blockers caused by
  missing optional/local backend dependencies in this execution environment.

### Env-only blockers

| Missing module | Representative import path | Reason classified env-only |
| --- | --- | --- |
| `chromadb` | `common.knowledge.vector_store` | Optional knowledge-vector-store dependency is imported by API/knowledge tests; failure is a missing local package, not a Phase 2 curriculum import regression. |
| `websockets` | `sales_bot.websocket.stepfun_realtime_handler` | Realtime WebSocket runtime dependency is absent from this local environment; the failing tests import the runtime surface directly. |
| `prometheus_client` | `common.monitoring.metrics` | Monitoring dependency required by app factory / analytics tests is absent locally; collection stops before behavior executes. |
| `oss2` | `common.oss.signing` | OSS signing dependency required by upload/signing-related tests is absent locally; failure is a missing integration dependency. |

## Targeted curriculum/runtime regression surfaces

- Command: `cd backend && pytest tests/unit/test_curriculum_publish_gates.py tests/unit/test_curriculum_runtime_snapshot_service.py tests/unit/test_curriculum_lineage.py -v --no-cov`
- Result: `18 passed`
- Command: `cd backend && pytest tests/integration/test_curriculum_practice_session_snapshot.py tests/integration/test_curriculum_snapshot_immutability.py tests/integration/test_curriculum_report_lineage_immutability.py tests/integration/test_curriculum_lineage_flow.py -v --no-cov`
- Result: `4 passed, 3 errors`
- Integration errors: the three errors are in `test_curriculum_practice_session_snapshot.py` setup and all fail on `ModuleNotFoundError: No module named 'chromadb'` while importing `common.knowledge.vector_store` via `main` / `websocket_routes`.

## Baseline import tracer test

- Command: `cd backend && pytest tests/unit/test_backend_phase2_baseline.py::test_should_import_phase2_baseline_modules_without_side_effects -v --no-cov`
- Result: `1 passed`

## Legacy sales handler invariant

- Command: `grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true`
- Result: existing diagnostics references remain in `backend/src/training_runtime/plugins.py` by design:
  - `sales_bot.websocket.base_sales_handler`
  - `sales_bot.websocket.enhanced_handler`
  - `sales_bot.websocket.simple_handler`
- Classification: these strings are not runtime wiring to legacy handlers. They are the public diagnostic baseline used by `LEGACY_SALES_HANDLER_MODULES` and `legacy_sales_handlers_absent()` to assert those legacy modules are absent.

## Coverage gate note

- Direct targeted pytest commands without `--no-cov` can fail the repository-wide coverage gate (`--cov-fail-under=48`) even when the targeted behavior test passes.
- For issue #56 behavior verification, targeted commands were re-run with `--no-cov` so unrelated coverage aggregation does not mask import/collection behavior.
