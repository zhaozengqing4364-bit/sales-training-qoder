---
estimated_steps: 3
estimated_files: 6
skills_used:
  - fastapi-python
  - react-best-practices
  - verification-before-completion
---

# T03: Lock same-session report and replay parity on the canonical projection

Keep report/replay closure honest on the existing route family instead of papering over drift in page code. Steps: 1. Extend backend contract/integration coverage so the same session's report truth, replay truth, and completion gate are asserted together, with replay only adding anchor/deep-link decoration on top of the canonical family. 2. Tighten report/replay page tests so both surfaces consume the shared issue/goal/claim-truth vocabulary consistently and do not silently fork copy or lifecycle assumptions. 3. Fix any remaining report/replay projection seam that breaks same-session parity, but keep `SessionEvidenceService` as the authority and preserve the existing rule that replay stays blocked until completion. Must-haves: report can still load first on the same session while status is `scoring`/`completed`; replay remains blocked before completion and matches report family after unlock; replay-only `replay_anchor`/learning-evidence decoration does not mutate the underlying issue/goal contract. Failure modes: replay/test code assumes availability during scoring, report and replay pages format family copy differently, or projection logic falls back to stale session snapshot after live/runtime alignment changed. Load profile: stay on the current projection-backed read path with no extra polling or duplicate data fetch layer. Negative tests: same-session replay blocked before completion, replay anchor stripped before parity comparison, and optional enhancement/report noise not being treated as core family drift.

## Inputs

- ``backend/src/common/conversation/session_evidence.py``
- ``backend/src/common/conversation/replay.py``
- ``backend/tests/contract/test_practice_evidence_contract.py``
- ``backend/tests/integration/test_practice_evidence_flow.py``
- ``web/src/app/(user)/practice/[sessionId]/report/page.test.tsx``
- ``web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx``

## Expected Output

- ``backend/tests/contract/test_practice_evidence_contract.py``
- ``backend/tests/integration/test_practice_evidence_flow.py``
- ``web/src/app/(user)/practice/[sessionId]/report/page.test.tsx``
- ``web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx``

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py
npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
