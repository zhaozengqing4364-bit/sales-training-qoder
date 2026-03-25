---
id: T03
parent: S02
milestone: M003
key_files:
  - web/src/app/admin/personas/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/app/admin/personas/[id]/page.test.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
  - backend/src/common/auth/service.py
  - backend/src/main.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Reused `/admin/personas/policy-health` on the existing list page for audit visibility instead of adding a new Persona governance surface.
  - Persisted detail-page edits back into `persona_policy.customer_pressure` while also mirroring the flat legacy sales-focus fields for downstream compatibility.
  - Normalized dev-mode environment checks in the dev-login/auth path so repo-root auto-mode pytest continues to work when backend `.env` is loaded via fallback instead of an exported shell env var.
duration: ""
verification_result: passed
completed_at: 2026-03-25T03:01:07.545Z
blocker_discovered: false
---

# T03: Added pressure-model audit/editing to admin Persona pages and restored repo-root knowledge-flow verification.

**Added pressure-model audit/editing to admin Persona pages and restored repo-root knowledge-flow verification.**

## What Happened

I updated the admin Persona frontend so operators can inspect and edit the snapshot-backed customer pressure model on the existing surfaces instead of relying on prompt prose alone. On the list page, I reused the existing `/admin/personas/policy-health` audit to surface persona-policy drift and pressure-model legacy warnings without introducing a new management screen. On the detail page, I added editable pressure-model fields for focus direction, value axes, objection axes, question strategy, revisit-on-evasion, evidence requirement, and example follow-up questions, plus a local preview/audit card that shows what will be frozen into runtime snapshots. I also strengthened the web API typing/normalization around `AdminPersona` and `persona_policy.customer_pressure`, and added a focused Vitest file that verifies both inspection and the exact nested save payload. During verification, the auto-mode gate still failed before reaching the slice-specific behavior because repo-root pytest could not obtain a dev token; I traced that to raw `os.getenv("ENVIRONMENT")` checks in the dev-login path and switched them to normalized development-mode fallback semantics so repo-root knowledge-flow verification works again.

## Verification

Verified the task-specific admin Persona detail flow with `cd web && npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'`, which passed 2 assertions covering pressure-model inspection and nested save payload persistence. Re-ran the failing verification gate with `venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py`; all 12 backend tests passed, confirming the repo-root dev-login/auth regression was fixed and the pressure-model runtime/session snapshot path still holds. I also ran `cd web && npx tsc --noEmit` as an extra compile check; it still fails on an unrelated pre-existing admin knowledge-page typing drift and is recorded below as a known issue rather than part of the required gate.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'` | 0 | ✅ pass | 19300ms |
| 2 | `venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py` | 0 | ✅ pass | 37400ms |


## Deviations

Fixed repo-root development auth resolution in `backend/src/common/auth/service.py` and `backend/src/main.py` because the verification gate was failing with `/api/v1/auth/dev-login` returning 403/401 before the task-specific assertions could run.

## Known Issues

Optional `cd web && npx tsc --noEmit` still reports `web/src/app/admin/knowledge/[id]/page.tsx(294,29): Property 'reprocessKnowledgeDocument' does not exist on type ...`. This is outside the current Persona pressure-model scope; the task-specific Vitest file and the required backend gate both pass.

## Files Created/Modified

- `web/src/app/admin/personas/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/admin/personas/[id]/page.test.tsx`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `backend/src/common/auth/service.py`
- `backend/src/main.py`
- `.gsd/KNOWLEDGE.md`
