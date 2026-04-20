---
id: T02
parent: S02
milestone: M016
key_files:
  - backend/src/prompt_templates/api/routes.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/common/auth/service.py
  - web/src/lib/api/client.ts
  - backend/tests/integration/test_prompt_templates_api_rbac.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_delete_permissions.py
  - web/src/lib/api/client.auth.test.ts
  - backend/tests/conftest.py
  - backend/src/common/api/practice.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D192 — normalize focused backend 4xx route families with route-local `JSONResponse(error_response(...))`, while keeping auth dependency failures on structured `HTTPException.detail={error,message}` so clients still see one stable error-contract seam without a global exception rewrite.
duration: 
verification_result: passed
completed_at: 2026-04-11T19:51:58.339Z
blocker_discovered: false
---

# T02: Unified prompt-template, presentation, auth, and frontend client error handling onto one stable error-contract seam.

**Unified prompt-template, presentation, auth, and frontend client error handling onto one stable error-contract seam.**

## What Happened

I collapsed the audited error drift hotspots onto the shared backend/frontend seam instead of attempting a global FastAPI rewrite. In `backend/src/prompt_templates/api/routes.py`, I converted the audited route-local 4xx branches that previously fell through FastAPI’s stringifying HTTPException handler into direct `JSONResponse(error_response(...))` envelopes, so missing prompt/scenario prompt resources and template-id mismatches now surface stable top-level `error/message/trace_id` fields. In `backend/src/presentation_coach/api/presentations.py`, I introduced the same focused 4xx response helper and applied it to missing-presentation, delete-forbidden, missing-page, and missing-thumbnail paths while preserving the existing blocker 409 and 5xx server-error seams. In `backend/src/common/auth/service.py`, I kept dependency-based auth on `HTTPException` but changed `get_current_user` to raise structured `detail={error,message}` payloads for unauthenticated, invalid-token, missing-user, and disabled-user failures so protected routes stop leaking bare strings. In `web/src/lib/api/client.ts`, I upgraded `normalizeApiErrorPayload` to read top-level envelopes, structured `detail`, and FastAPI validation arrays consistently, preserve `trace_id`, and route segment-audio failures through `ApiRequestError` instead of a custom parser. I added focused backend/frontend tests to lock the new envelopes and, during slice verification, fixed an unrelated pre-existing blocker in `backend/src/common/api/practice.py` where `live_knowledge_answer_diagnostics` was referenced before assignment; I also restored the shared test fixture import in `backend/tests/conftest.py` so selective pytest runs can create `voice_runtime_profiles` before hitting the contract tests.

## Verification

Verified the focused contract seam first with `backend/tests/integration/test_prompt_templates_api_rbac.py`, `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_delete_permissions.py`, and `web/src/lib/api/client.auth.test.ts`; all passed after the red→green cycle. Then fixed the pre-existing `knowledge-check` NameError exposed by the slice gate and re-ran the targeted `backend/tests/contract/test_practice_evidence_contract.py -k "kb_lock_chain_failures"` check, which passed. Finally ran the task-plan verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q`; it finished 31/31 green. Fresh LSP diagnostics also reported no issues on the touched backend/frontend authority files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_prompt_templates_api_rbac.py -q` | 0 | ✅ pass | 2770ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_delete_permissions.py -q` | 0 | ✅ pass | 1910ms |
| 3 | `npm --prefix web test -- --run src/lib/api/client.auth.test.ts` | 0 | ✅ pass | 565ms |
| 4 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "kb_lock_chain_failures" -q` | 0 | ✅ pass | 1850ms |
| 5 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q` | 0 | ✅ pass | 4300ms |

## Deviations

During final verification I found a pre-existing blocker outside the original four task-authority files: `backend/src/common/api/practice.py` referenced `live_knowledge_answer_diagnostics` before assignment, and `backend/tests/conftest.py` no longer imported `agent.models`, which broke selective `Base.metadata.create_all()` runs after the `voice_runtime_profiles` foreign key landed. I fixed both so the planned verification command could run truthfully.

## Known Issues

None.

## Files Created/Modified

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`
- `backend/tests/integration/test_prompt_templates_api_rbac.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_delete_permissions.py`
- `web/src/lib/api/client.auth.test.ts`
- `backend/tests/conftest.py`
- `backend/src/common/api/practice.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
