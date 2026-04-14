---
id: T02
parent: S02
milestone: M022
key_files:
  - backend/src/agent/services/industry_pack_contract.py
  - backend/src/common/db/voice_policy_snapshot.py
  - backend/src/common/db/schemas.py
  - backend/src/common/conversation/schemas.py
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/app/admin/agents/[id]/page.tsx
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - backend/tests/contract/test_sessions.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/unit/test_sales_scenarios_api.py
  - web/src/app/admin/personas/[id]/page.test.tsx
  - web/src/app/admin/agents/[id]/page.test.tsx
key_decisions:
  - D245 — Freeze a compact `voice_policy_snapshot_ref.runtime_binding` summary as the inspectable industry-pack/report provenance surface instead of exposing a separate mutable evidence model.
duration: 
verification_result: mixed
completed_at: 2026-04-14T06:36:09.197Z
blocker_discovered: false
---

# T02: Added industry-pack runtime binding evidence to frozen session refs and surfaced the contract in persona/agent admin detail pages.

**Added industry-pack runtime binding evidence to frozen session refs and surfaced the contract in persona/agent admin detail pages.**

## What Happened

I extended the industry-pack helper so runtime bindings are summarized in one compact shape, then wired that summary into `voice_policy_snapshot_ref` via `backend/src/common/db/voice_policy_snapshot.py` and the shared Pydantic schemas used by session detail, report, and replay surfaces. The new `runtime_binding` block now freezes customer-pressure source, sales focus, axes, follow-up behavior, bound knowledge bases, and affected runtime/evidence surfaces alongside the immutable session reference.

On the admin side, I kept the existing entrypoints instead of adding a second content surface. `web/src/app/admin/personas/[id]/page.tsx` now fetches the persona industry-pack contract and shows an `Industry Pack 合同` card that maps owned field groups to the runtime snapshot/report evidence targets while keeping the editable pressure-model preview. `web/src/app/admin/agents/[id]/page.tsx` now fetches the agent industry-pack contract and shows an `Industry Pack 运行合同` card that explains the agent/runtime boundary and the runtime authorities still responsible for composed industry-pack behavior. I also updated the focused backend and web tests to lock the new frozen-ref/report/replay shape and the new admin detail surfaces.

## Verification

Focused backend regression coverage passed for the new frozen `voice_policy_snapshot_ref.runtime_binding` contract across session create/detail/report/replay paths and for the updated scenario runtime binding helper. The persona detail page test from the task plan passed with the new contract card, and I added/passed a focused agent detail page test for the runtime contract card. I also reran the broader slice verification backend command exactly as written; it still fails on an unrelated existing RBAC assertion in `backend/tests/integration/test_rbac_access_control_api.py::test_admin_knowledge_rejects_non_admin_with_trace_id`, where the current API returns `[ROLE_REQUIRED]` instead of the test’s expected `ADMIN_REQUIRED`. LSP diagnostics for the modified backend and shared web API files returned no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_sessions.py backend/tests/unit/test_sales_scenarios_api.py -q` | 0 | ✅ pass | 13210ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q` | 1 | ❌ fail | 16580ms |
| 3 | `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"` | 0 | ✅ pass | 2820ms |
| 4 | `npm --prefix web test -- --run "src/app/admin/agents/[id]/page.test.tsx"` | 0 | ✅ pass | 2130ms |
| 5 | `lsp diagnostics: backend/src/agent/services/industry_pack_contract.py backend/src/common/db/voice_policy_snapshot.py backend/src/common/db/schemas.py backend/src/common/conversation/schemas.py web/src/lib/api/client.ts web/src/lib/api/types.ts` | 0 | ✅ pass | 200ms |

## Deviations

Instead of changing admin list pages or creating new runtime evidence endpoints, I concentrated the task on the existing detail pages plus the immutable `voice_policy_snapshot_ref` contract so the same frozen evidence is reused by session detail, report, and replay surfaces.

## Known Issues

The task-plan backend verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q` still fails on the pre-existing RBAC assertion `backend/tests/integration/test_rbac_access_control_api.py::test_admin_knowledge_rejects_non_admin_with_trace_id`. That failure is outside the industry-pack/runtime/admin surfaces touched in this task; the focused T02 regressions added here passed.

## Files Created/Modified

- `backend/src/agent/services/industry_pack_contract.py`
- `backend/src/common/db/voice_policy_snapshot.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/conversation/schemas.py`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/admin/agents/[id]/page.tsx`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- `backend/tests/contract/test_sessions.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/unit/test_sales_scenarios_api.py`
- `web/src/app/admin/personas/[id]/page.test.tsx`
- `web/src/app/admin/agents/[id]/page.test.tsx`
