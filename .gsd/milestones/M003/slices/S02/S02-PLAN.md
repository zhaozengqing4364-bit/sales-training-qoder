# S02: Persona 压力模型 snapshot 化

**Goal:** Normalize and freeze Persona pressure semantics into the current session snapshot and runtime/compiler path.
**Demo:** After this: Different Personas bound to the same knowledge base can consistently change pressure direction and follow-up behavior across turns and reconnects, with that model frozen in the session snapshot.

## Tasks
- [x] **T01: Normalize Persona policies into a structured customer-pressure model with legacy audit coverage.** — Extend the existing Persona policy schema and normalization logic so Persona behavior is described as a structured pressure model instead of only loose sales-focus strings. Add or update focused tests around `persona_policy.py` and Persona service audit behavior, and make sure old records normalize safely rather than silently dropping to generic defaults.
  - Estimate: 90m
  - Files: backend/src/agent/services/persona_policy.py, backend/src/agent/services/persona_service.py, backend/tests/unit/test_persona_policy.py, backend/tests/integration/test_persona_api.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py
- [x] **T02: Freeze Persona pressure contracts into runtime snapshots and StepFun reconnects** — Compile the structured pressure model into the existing runtime authority chain and freeze it into new session snapshots. Reuse `voice_runtime_policy.py`, `voice_instruction_compiler.py`, and current session-create flow so the runtime sees one frozen Persona pressure contract per session instead of reading live admin config at execution time.
  - Estimate: 90m
  - Files: backend/src/sales_bot/services/voice_runtime_policy.py, backend/src/sales_bot/services/voice_instruction_compiler.py, backend/src/common/api/practice.py, backend/tests/unit/test_voice_instruction_compiler.py, backend/tests/integration/test_knowledge_flow.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py
- [x] **T03: Added pressure-model audit/editing to admin Persona pages and restored repo-root knowledge-flow verification.** — Expose and validate the pressure model on the existing admin Persona surfaces so operators can edit, preview, and audit the behavior they are about to ship. Stay on the current admin Persona list/detail pages and API client/types; do not create a new management surface.
  - Estimate: 75m
  - Files: web/src/app/admin/personas/page.tsx, web/src/app/admin/personas/[id]/page.tsx, web/src/lib/api/client.ts, web/src/lib/api/types.ts, web/src/app/admin/personas/[id]/page.test.tsx
  - Verify: cd web && npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'
