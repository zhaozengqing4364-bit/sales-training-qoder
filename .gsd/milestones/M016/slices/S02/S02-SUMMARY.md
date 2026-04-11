---
id: S02
parent: M016
milestone: M016
provides:
  - A stable outward error contract for the audited prompt-template, presentation, and protected-route auth surfaces.
  - One frontend `ApiRequestError` normalization seam that covers top-level envelopes, dependency detail payloads, validation arrays, and segment-audio errors.
  - A reusable proof pattern for S03 admin security hardening so future work can extend the same contract instead of re-inventing page-local parsing.
requires:
  []
affects:
  - M016/S03
key_files:
  - backend/src/prompt_templates/api/routes.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/common/auth/service.py
  - backend/src/common/api/practice.py
  - backend/tests/conftest.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_prompt_templates_api_rbac.py
  - backend/tests/integration/test_presentation_delete_permissions.py
  - web/src/lib/api/client.ts
  - web/src/lib/api/client.auth.test.ts
key_decisions:
  - D191 — reuse the prompt-template error seam plus frontend `normalizeApiErrorPayload`/`ApiRequestError` instead of a broad FastAPI-wide exception rewrite.
  - D192 — audited backend route-local 4xx failures should return `JSONResponse(error_response(...))`, while dependency/auth failures stay on structured `HTTPException.detail={error,message}`.
  - D193 — `get_current_admin_user` and `require_role(...)` must reuse `_raise_auth_http_error(...)` so dependency-level permission failures remain frontend-normalizable without page-local guessing.
patterns_established:
  - Use `JSONResponse(error_response(...))` for audited route-local business/domain 4xx surfaces that need stable top-level `error/message/trace_id`.
  - Use `_raise_auth_http_error(...)` for dependency/auth/RBAC failures so protected-route detail payloads stay structured.
  - Treat `web/src/lib/api/client.ts` `normalizeApiErrorPayload` + `ApiRequestError` as the only frontend normalization seam; do not add page-local payload parsing.
  - Pair backend route-family contract tests with the focused frontend API-client suite whenever the shared error seam changes.
observability_surfaces:
  - Audited route-local failures now expose top-level `error`, `message`, and `trace_id` through `error_response(...)` / `build_server_error(...)`.
  - Dependency-based auth/RBAC failures now preserve structured `detail.error` / `detail.message` plus `trace_id` for support triage.
  - Focused proof lives in `backend/tests/contract/test_presentations.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_presentation_flow.py`, and `web/src/lib/api/client.auth.test.ts`.
drill_down_paths:
  - .gsd/milestones/M016/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M016/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M016/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T20:05:15.718Z
blocker_discovered: false
---

# S02: API 错误契约与异常分类收口

**Unified the audited prompt-template, presentation, and auth failure surfaces onto one stable backend/frontend error contract so high-noise API calls now expose structured errors and the web client no longer relies on page-local guessing.**

## What Happened

## Delivered outcome
S02 closed the highest-noise API error drift points without widening into a global FastAPI exception rewrite. The slice reused the existing prompt-template error seam as the authority model, then applied the same contract to the audited presentation and auth surfaces that were still leaking mixed error shapes.

### What actually shipped
- **Prompt-template audited routes** now keep a stable outward envelope for audited route-local 4xx/5xx failures using the existing `error_response(...)` / `build_server_error(...)` seam.
- **Presentation routes** now return structured top-level 4xx envelopes for the audited not-found and permission branches instead of plain-string `HTTPException` payloads, while preserving the existing blocker `409` and server-error `5xx` Result-style contract.
- **Auth dependency guards** (`get_current_user`, `get_current_admin_user`, `require_role(...)`) now raise structured `detail={error,message}` payloads through `_raise_auth_http_error(...)`, so protected-route auth/permission failures stay machine-readable even when they must propagate through FastAPI dependency handling.
- **Frontend `apiFetch` / `ApiRequestError`** now normalizes top-level envelopes, dependency `detail`, validation arrays, and segment-audio failure payloads through one seam instead of route-local parsing or page-local fallback logic.
- **Focused cross-end proof** now locks the role-guard contract on both `/api/v1/presentations` and `/api/v1/admin/presentations`, and the frontend auth client suite proves those payloads still collapse into one `ApiRequestError` path.

### Patterns established
1. **Route-local business/domain 4xx** on audited high-noise families should return `JSONResponse(error_response(...))` so clients receive stable top-level `error/message/trace_id` fields.
2. **Dependency/auth/RBAC failures** should keep using `_raise_auth_http_error(...)` with `detail={error,message}` because dependencies cannot safely short-circuit with response objects.
3. **Frontend callers** should read all API failures through `normalizeApiErrorPayload` and `ApiRequestError`; adding page-local payload guessing would now be a regression.
4. **Focused contract proof** should pair the backend route-family test with the frontend API-client suite whenever a backend error seam changes.

### Non-obvious execution facts
- Slice verification exposed a pre-existing blocker outside the original four authority files: `backend/src/common/api/practice.py` referenced `live_knowledge_answer_diagnostics` before assignment, and selective metadata bootstrap also needed `agent.models` imported in `backend/tests/conftest.py`. Both were fixed during T02 so the planned slice gate could run truthfully.
- The slice intentionally stayed narrow: it normalized the audited prompt-template/presentation/auth surfaces, not the repo-wide FastAPI exception system.

## Operational Readiness (Q8)
- **Health signal:** the slice-level backend contract/integration gate stays green, the focused frontend auth client suite stays green, and audited 4xx/5xx failures expose stable `error/message` plus `trace_id` (top-level for route-local responses, structured `detail` for dependency failures).
- **Failure signal:** protected routes start returning raw-string 401/403 payloads again, presentation/prompt-template not-found branches lose top-level `error` fields, or frontend pages need to manually inspect `response.detail` / `response.error_code` outside `ApiRequestError`.
- **Recovery procedure:** re-align the failing route family to the established seam — route-local 4xx back to `JSONResponse(error_response(...))`, dependency/auth guards back to `_raise_auth_http_error(...)`, then rerun `backend/tests/contract/test_presentations.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_presentation_flow.py`, and `web/src/lib/api/client.auth.test.ts`.
- **Monitoring gaps:** the repo still lacks a wider contract gate for every backend route family, and FastAPI’s shared `http_exception_handler` still stringifies dict detail at the top level. Future slices must keep using the explicit focused seam until a deliberate framework-wide error-policy change is proven.


## Verification

## Fresh verification run
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q` → **33 passed** in 4.40s. The exact slice-plan backend gate passed fresh on this close-out run.
- `npm --prefix web test -- --run src/lib/api/client.auth.test.ts` → **9 passed** in 642ms. Frontend API-client normalization still proves dependency-detail, validation-array, network, and segment-audio error handling on one `ApiRequestError` seam.
- Fresh LSP diagnostics reported **No diagnostics** on:
  - `backend/src/prompt_templates/api/routes.py`
  - `backend/src/presentation_coach/api/presentations.py`
  - `backend/src/common/auth/service.py`
  - `backend/src/common/api/practice.py`
  - `backend/tests/conftest.py`
  - `backend/tests/contract/test_presentations.py`
  - `web/src/lib/api/client.ts`
  - `web/src/lib/api/client.auth.test.ts`

## Verification notes
- The narrow backend pytest command still emits existing pytest-cov `module-not-imported` / `no-data-collected` warnings on selective runs, but exit code remained 0 and all target tests passed.
- This slice now has fresh proof for three outward contract classes: route-local domain/not-found envelopes, dependency/RBAC structured detail payloads, and frontend normalization of those shapes plus validation-array and segment-audio errors.


## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 had to fix two pre-existing blockers discovered by truthful slice verification: an uninitialized `live_knowledge_answer_diagnostics` reference in `backend/src/common/api/practice.py`, and a missing `agent.models` import in `backend/tests/conftest.py` that broke selective metadata bootstrap after the `voice_runtime_profiles` foreign key landed.

## Known Limitations

The normalization work is intentionally scoped to the audited prompt-template, presentation, and auth dependency surfaces. The repo-wide FastAPI exception policy is unchanged, so unaudited route families may still need the same focused pattern. Narrow backend pytest runs also still emit pytest-cov `module-not-imported` / `no-data-collected` warnings.

## Follow-ups

Carry the same seam into M016/S03 admin high-risk RBAC surfaces and log-redaction exits, and consider whether a future framework-wide exception-policy change is warranted only after those focused security contracts are proven.

## Files Created/Modified

- `backend/src/prompt_templates/api/routes.py` — Kept the prompt-template route family as the reusable backend error seam and returned stable top-level envelopes for audited route-local failures.
- `backend/src/presentation_coach/api/presentations.py` — Collapsed audited presentation permission/not-found branches onto structured top-level error envelopes while preserving blocker and server-error contracts.
- `backend/src/common/auth/service.py` — Moved auth and role-guard dependency failures onto `_raise_auth_http_error(...)` so protected-route responses preserve structured `detail={error,message}`.
- `web/src/lib/api/client.ts` — Extended frontend error normalization so top-level envelopes, dependency detail payloads, validation arrays, and segment-audio payloads all map to `ApiRequestError`.
- `backend/src/common/api/practice.py` — Fixed the pre-existing `live_knowledge_answer_diagnostics` reference exposed by slice verification.
- `backend/tests/conftest.py` — Restored `agent.models` import so selective metadata bootstrap includes the referenced tables needed by contract tests.
- `backend/tests/contract/test_presentations.py` — Added contract proof for missing-presentation envelopes and structured role/admin dependency payloads.
- `web/src/lib/api/client.auth.test.ts` — Locked dependency-detail, validation-array, and segment-audio failure normalization onto one `ApiRequestError` seam.
