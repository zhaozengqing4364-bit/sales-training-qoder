---
estimated_steps: 3
estimated_files: 5
skills_used:
  - agent-browser
  - verification-before-completion
---

# T04: Capture localhost same-session proof on the shipped route family and write back any durable traps

Finish with the real route-family proof bar: one localhost sales session must be followable from active practice into report and replay on the same host. Steps: 1. Start backend and web on the same loopback host and create one real sales session that reaches live coaching on `/practice/{sessionId}`. 2. Confirm the learner route shows the live same-session cue, follow that exact session into `/practice/{sessionId}/report`, then wait for completion before asserting `/practice/{sessionId}/replay` and its family coherence. 3. Save a short proof artifact and append any reusable host/completion-gate lesson to project knowledge only if execution uncovers a durable trap beyond the current documented constraints. Must-haves: use one real session instead of cross-session stitching; keep frontend/backend hosts aligned for auth-cookie continuity; stop any temporary local servers before finishing. Failure modes: mixed `localhost`/`127.0.0.1` hosts fake a 401 regression, an unrelated app on `:3000` is mistaken for this repo, or replay is asserted before completion and misclassified as a bug. Load profile: one end-to-end session only, with no parallel pytest runs that collide on coverage files and no stale dev servers left behind. Negative tests: replay still blocked before completion, report stays available during scoring/completed transition, and optional enhancement noise is recognized as non-blocking unless the canonical family itself drifts.

## Inputs

- ``web/src/app/(user)/practice/[sessionId]/page.tsx``
- ``web/src/app/(user)/practice/[sessionId]/report/page.tsx``
- ``web/src/app/(user)/practice/[sessionId]/replay/page.tsx``
- ``.gsd/KNOWLEDGE.md``

## Expected Output

- ``.artifacts/m007-s02-same-session/session-proof.md``
- ``.gsd/KNOWLEDGE.md``

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py
npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
Use `bg_shell` to run `backend/venv/bin/python -m uvicorn main:app --app-dir backend/src --port 3444` and `pnpm --dir web exec next dev --hostname localhost --port 3445`, then prove the same session through `/practice/{sessionId}` -> `/practice/{sessionId}/report` -> `/practice/{sessionId}/replay` with browser assertions and save `.artifacts/m007-s02-same-session/session-proof.md`.

## Observability Impact

Produces concrete localhost evidence for the active-session cue and the report/replay completion gate, and leaves any new host/runtime trap documented in project knowledge so later slices do not rediscover it by accident.
