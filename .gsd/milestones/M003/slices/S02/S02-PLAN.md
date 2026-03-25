# S02: Persona 压力模型 snapshot 化

**Goal:** Promote Persona from prompt flavor to a snapshot-backed customer pressure model that the runtime can actually enforce and later audit.
**Demo:** Different Personas bound to the same knowledge base can consistently change pressure direction and follow-up behavior across turns and reconnects, with that model frozen in the session snapshot.

## Must-Haves

- Different Personas bound to the same knowledge base can consistently change pressure direction and follow-up behavior across turns and reconnects, with that model frozen in the session snapshot and visible to admin/runtime inspection surfaces.

## Proof Level

- This slice proves: integration

## Integration Closure

Reuse the current Persona authority chain only: `backend/src/agent/services/persona_policy.py`, `backend/src/agent/services/persona_service.py`, `backend/src/agent/api/personas.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, session snapshot fields, and the existing admin Persona pages. No second Persona store and no environment/tooling scope.

## Verification

- Persona policy audits, focused compiler tests, admin Persona CRUD tests, and session snapshot inspection become the drift detectors. Runtime proof should inspect frozen snapshot fields rather than infer Persona behavior from prose alone.

## Tasks

- [x] **T01: Turn Persona policy into a structured customer-pressure model** `est:90m`
  Extend the existing Persona policy schema and normalization logic so Persona behavior is described as a structured pressure model instead of only loose sales-focus strings. Add or update focused tests around `persona_policy.py` and Persona service audit behavior, and make sure old records normalize safely rather than silently dropping to generic defaults.
  - Files: `backend/src/agent/services/persona_policy.py`, `backend/src/agent/services/persona_service.py`, `backend/tests/unit/test_persona_policy.py`, `backend/tests/integration/test_persona_api.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py

- [x] **T02: Freeze the pressure model into the runtime compile and session snapshot chain** `est:90m`
  Compile the structured pressure model into the existing runtime authority chain and freeze it into new session snapshots. Reuse `voice_runtime_policy.py`, `voice_instruction_compiler.py`, and current session-create flow so the runtime sees one frozen Persona pressure contract per session instead of reading live admin config at execution time.
  - Files: `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/common/api/practice.py`, `backend/tests/unit/test_voice_instruction_compiler.py`, `backend/tests/integration/test_knowledge_flow.py`
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py

- [ ] **T03: Let admins edit and inspect the pressure model on current Persona pages** `est:75m`
  Expose and validate the pressure model on the existing admin Persona surfaces so operators can edit, preview, and audit the behavior they are about to ship. Stay on the current admin Persona list/detail pages and API client/types; do not create a new management surface.
  - Files: `web/src/app/admin/personas/page.tsx`, `web/src/app/admin/personas/[id]/page.tsx`, `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, `web/src/app/admin/personas/[id]/page.test.tsx`
  - Verify: cd web && npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'

## Files Likely Touched

- backend/src/agent/services/persona_policy.py
- backend/src/agent/services/persona_service.py
- backend/tests/unit/test_persona_policy.py
- backend/tests/integration/test_persona_api.py
- backend/src/sales_bot/services/voice_runtime_policy.py
- backend/src/sales_bot/services/voice_instruction_compiler.py
- backend/src/common/api/practice.py
- backend/tests/unit/test_voice_instruction_compiler.py
- backend/tests/integration/test_knowledge_flow.py
- web/src/app/admin/personas/page.tsx
- web/src/app/admin/personas/[id]/page.tsx
- web/src/lib/api/client.ts
- web/src/lib/api/types.ts
- web/src/app/admin/personas/[id]/page.test.tsx
