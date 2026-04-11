---
id: T01
parent: S02
milestone: M016
key_files:
  - backend/src/prompt_templates/api/routes.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/common/auth/service.py
  - web/src/lib/api/client.ts
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D191 — reuse the prompt-template error seam (`error_response`/`build_server_error` on the backend plus `normalizeApiErrorPayload`/`ApiRequestError` on the frontend) instead of attempting a broad FastAPI-wide exception rewrite.
duration: 
verification_result: passed
completed_at: 2026-04-11T19:36:26.706Z
blocker_discovered: false
---

# T01: Codified the high-noise API error-contract drift map beside the live prompt, presentation, auth, and frontend client seams.

**Codified the high-noise API error-contract drift map beside the live prompt, presentation, auth, and frontend client seams.**

## What Happened

I audited the four task-authority files against the shared backend/frontend helpers and wrote the findings back next to the live seams instead of changing runtime behavior early. In `backend/src/prompt_templates/api/routes.py` I documented that this route family is already the closest reusable backend model: 4xx branches converge on `{error,message}` inside FastAPI detail payloads, while 5xx/infra failures already go through `build_server_error(...)` and expose the shared Result-style envelope with trace ids. In `backend/src/presentation_coach/api/presentations.py` I recorded the current three-way drift: plain-string 403/404 branches, blocker 409 via `error_response(...)` plus `details`, and Result-style 5xx upload/replace failures. In `backend/src/common/auth/service.py` I marked the dependency-level auth leak where `get_current_user` / `get_current_admin_user` / `require_role` still raise string-detail auth failures even though `common.auth.api` already returns structured `error_response(...)` envelopes. In `web/src/lib/api/client.ts` I documented that `apiFetch`/`apiUpload` already form the frontend normalization seam through `normalizeApiErrorPayload` + `ApiRequestError`, and that `getSegmentAudioBlobUrl()` is the remaining client-local parser that still reads raw payload fields directly. I then persisted the seam choice as decision D191, added the non-obvious drift map to `.gsd/KNOWLEDGE.md`, and updated `.codex/loop/state.json` plus `.codex/loop/log.md` so T02 can continue from this exact collapse target without re-inventorying the same surfaces.

## Verification

Ran the planned inventory command `rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth` after tightening the code-adjacent notes so the proof signal stayed focused on real drift sites. The command exited 0 and still showed the intended hotspots across prompt templates, presentations, and auth. Then ran fresh LSP diagnostics on `backend/src/prompt_templates/api/routes.py`, `backend/src/presentation_coach/api/presentations.py`, `backend/src/common/auth/service.py`, and `web/src/lib/api/client.ts`; all four returned `No diagnostics`, confirming the inventory writeback stayed syntax/type-clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth` | 0 | ✅ pass | 17ms |
| 2 | `lsp diagnostics backend/src/prompt_templates/api/routes.py` | 0 | ✅ pass | 1ms |
| 3 | `lsp diagnostics backend/src/presentation_coach/api/presentations.py` | 0 | ✅ pass | 1ms |
| 4 | `lsp diagnostics backend/src/common/auth/service.py` | 0 | ✅ pass | 1ms |
| 5 | `lsp diagnostics web/src/lib/api/client.ts` | 0 | ✅ pass | 1ms |

## Deviations

None.

## Known Issues

The outward runtime contract is still intentionally mixed until T02: `backend/src/presentation_coach/api/presentations.py` still exposes plain-string 403/404 branches alongside blocker 409 and Result-style 5xx responses, `backend/src/common/auth/service.py` still leaks string auth `detail` payloads through dependency failures, and `web/src/lib/api/client.ts::getSegmentAudioBlobUrl()` still performs manual raw-payload parsing instead of reusing `ApiRequestError`.

## Files Created/Modified

- `backend/src/prompt_templates/api/routes.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/auth/service.py`
- `web/src/lib/api/client.ts`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
