---
id: T01
parent: S08
milestone: M001
provides:
  - evidence-backed support runtime release-health overview and typed anomaly reader
key_files:
  - backend/src/support/services/runtime_status_service.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/support/api/runtime_status.py
  - backend/tests/unit/test_support_runtime_service.py
  - backend/tests/integration/test_support_runtime_api.py
key_decisions:
  - D031
patterns_established:
  - Shared runtime diagnostics now drive both `/practice/sessions/{id}/knowledge-check` and support runtime anomaly classification.
  - Support runtime overview/faults batch-load recent sessions/messages and classify release health from session evidence first, with SystemLog only as supplemental warning input.
observability_surfaces:
  - /api/v1/support/runtime/overview
  - /api/v1/support/runtime/faults
  - support_runtime_release_health_built
  - /api/v1/practice/sessions/{id}/knowledge-check
duration: 1h12m
verification_result: passed
completed_at: 2026-03-24T16:52:43+0800
blocker_discovered: false
---

# T01: 用统一 evidence truth line 重写 support runtime 后端健康读模型

**Rebuilt support/runtime backend health on unified session evidence and shared runtime diagnostics.**

## What Happened

I replaced the old support runtime reader that counted `SystemLog` rows and treated `status="scoring"` as completed. The new backend path extracts the knowledge/runtime diagnostics logic out of `backend/src/common/api/practice.py` into `backend/src/common/conversation/runtime_diagnostics.py`, reuses that helper inside `/practice/sessions/{id}/knowledge-check`, and introduces `backend/src/support/services/runtime_status_service.py` as the evidence-backed aggregator.

That service batch-loads recent sessions plus `ConversationMessage` rows, builds projections with `SessionEvidenceService.build_projection(...)`, pulls presentation degraded reasons from `PresentationReportService`, classifies blocking/warning anomalies, and keeps raw `SystemLog` rows as supplemental warning-only input. The API layer in `backend/src/support/api/runtime_status.py` is now thin RBAC + shaping only.

## Verification

I first wrote the red tests for the new support-runtime contract, watched the task suite fail on the missing `support.services` module, then implemented the shared helper and release-health service. After that, the focused support-runtime unit/contract/integration suite passed, and the knowledge-check regression still passed against the extracted helper.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py` | 0 | ✅ pass | 3.95s |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses` | 0 | ✅ pass | 3.16s |

## Diagnostics

Future agents can inspect `/api/v1/support/runtime/overview` for typed release-health counters and `/api/v1/support/runtime/faults` for severity/kind/session-scoped anomaly items. The backend also emits `support_runtime_release_health_built`, while canonical cross-check surfaces remain `/api/v1/practice/sessions/{id}/knowledge-check` and `/api/v1/practice/sessions/{id}/report`.

## Deviations

None.

## Known Issues

- `web/src/app/(dashboard)/support/runtime/page.tsx` still expects the old coarse completion/log contract until T02 updates the frontend consumer.

## Files Created/Modified

- `backend/src/common/conversation/runtime_diagnostics.py` — extracted the shared runtime diagnostics helper from `practice.py` so knowledge-check and support runtime reuse the same status/kb-lock/upstream semantics.
- `backend/src/support/services/runtime_status_service.py` — added the evidence-backed release-health aggregator and typed anomaly classifier.
- `backend/src/support/services/__init__.py` — created the support services package.
- `backend/src/support/api/runtime_status.py` — rewired the route layer to the new service and switched faults filtering to `severity`.
- `backend/src/common/api/practice.py` — switched knowledge-check to the shared diagnostics helper without changing the canonical knowledge-check semantics.
- `backend/tests/unit/test_support_runtime_service.py` — added unit coverage for scoring separation, anomaly severity, and typed health summaries.
- `backend/tests/contract/test_support_runtime.py` — updated the support runtime contract guardrails to the typed overview/fault payloads.
- `backend/tests/integration/test_support_runtime_api.py` — added integration coverage for evidence-backed overview/faults, severity filtering, and support-role access.
