---
estimated_steps: 3
estimated_files: 6
skills_used:
  - safe-grow
  - verification-before-completion
---

# T02: Lock same-session lifecycle, report, replay, and frontend contract behavior around the persisted completion transition

**Slice:** S04 — 最终集成验证与封板
**Milestone:** M007

## Description

Once persistence is fixed, lock the same-session contract on current APIs and pages rather than trusting ad hoc manual checks. The executor should load `safe-grow` and `verification-before-completion`. This task keeps the current route-family truth explicit: report remains readable during `scoring`, replay and highlights stay completion-gated until the persisted session becomes `completed`, and the frontend must not add a workaround that hides a backend lifecycle regression.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `SessionEvidenceService` projection-backed report/replay reads | fail the focused suite and inspect whether drift lives in persistence or projection logic before changing UI copy | keep the gate truthful and surface the unresolved lifecycle blocker instead of loosening replay | reject parity assumptions that depend on malformed `main_issue` / `next_goal` / `replay_anchor` payloads |
| replay/highlights completion gate | treat any pre-completion 200 as a regression, not a success | keep `[SESSION_NOT_COMPLETED]` visible and investigate persistence first | preserve the gate and fail tests rather than introducing fallback data |
| report/replay page clients | keep the current blocked/unlocked copy explicit and avoid frontend-only mapping fixes | stop on flaky route-family behavior and re-check the API contract before editing page code | do not infer parity from partial payloads or missing `replay_anchor` metadata |

## Load Profile

- **Shared resources**: sequential backend pytest DB usage and repo-root web Vitest shims.
- **Per-operation cost**: current projection-backed reads plus targeted page tests; no extra fetch loop or polling surface.
- **10x breakpoint**: parallel pytest coverage contention or repeated broad suites; keep the pack focused and sequential.

## Negative Tests

- **Malformed inputs**: partial issue/goal payloads, replay-only `replay_anchor` decoration, and report snapshots that should not override canonical replay truth.
- **Error paths**: replay/highlights before completion, report readable during `scoring`, and frontend blocked-state rendering when replay is still locked.
- **Boundary conditions**: same-session parity after persisted completion, optional enhancement noise, and shell-quoted Next.js test paths from repo root.

## Steps

1. Tighten backend contract/integration suites so the route family proves report stays readable during `scoring`, replay/highlights remain blocked before persisted completion, and unlocked replay/highlights match the canonical issue/goal family after background finalization.
2. Extend report/replay page tests only where needed to prove the frontend does not add a workaround or regress its blocked-versus-unlocked copy while backend completion semantics change.
3. Run the focused backend and frontend packs sequentially; if any failure suggests relaxing `ReplayService._check_session_completed()`, treat that as a regression instead of a fix direction.

## Must-Haves

- [ ] No new debug/status API is introduced.
- [ ] No replay-gate relaxation is accepted as part of the fix.
- [ ] Same-session report/replay/highlights semantics stay on `SessionEvidenceService` projection authority, and every Next.js test path stays shell-quoted exactly as written.

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k "report_generation or scoring"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "same_session or knowledge_check or replay"`
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_replay_api.py -k "finalization or scoring or replay_unlock"`
- `npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`

## Observability Impact

- Signals added/changed: route-family proofs around persisted `PracticeSession.status/report_status` and replay `[SESSION_NOT_COMPLETED]` versus post-finalization 200 responses.
- How a future agent inspects this: run the focused backend suites plus the quoted report/replay Vitest command from repo root.
- Failure state exposed: whether the boundary drift lives in backend lifecycle persistence, replay gating, or frontend blocked/unlocked copy.

## Inputs

- `backend/src/evaluation/services/report_generation_trigger.py` — persisted completion behavior from T01
- `backend/src/common/api/practice.py` — report and knowledge-check routes on the shipped family
- `backend/src/common/conversation/replay.py` — replay/highlights completion gate
- `backend/src/common/conversation/session_evidence.py` — canonical projection authority
- `backend/tests/contract/test_practice_evidence_contract.py` — same-session contract coverage
- `backend/tests/integration/test_practice_evidence_flow.py` — report/replay family integration proof
- `backend/tests/integration/test_session_lifecycle_api.py` — lifecycle transition proof
- `backend/tests/integration/test_replay_api.py` — replay/highlights API coverage
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — learner-facing report contract
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — learner-facing replay contract

## Expected Output

- `backend/tests/contract/test_practice_evidence_contract.py` — tightened same-session contract assertions
- `backend/tests/integration/test_practice_evidence_flow.py` — updated integration parity proof
- `backend/tests/integration/test_session_lifecycle_api.py` — lifecycle verification aligned to persisted completion
- `backend/tests/integration/test_replay_api.py` — replay/highlights gate proof aligned to the fix
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — report-page assertions for blocked/unlocked same-session behavior
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — replay-page assertions that keep the current completion gate and parity semantics truthful
