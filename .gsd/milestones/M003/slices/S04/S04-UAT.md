# S04: unsupported claim / weak evidence truth contract — UAT

**Milestone:** M003
**Written:** 2026-03-25T07:14:07.926Z

# S04: unsupported claim / weak evidence truth contract — UAT

**Milestone:** M003
**Written:** 2026-03-25

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 changed the contract on existing evaluator/runtime/report/replay seams rather than adding a new live surface. The focused backend and web suites exercise the accepted current routes and prove the contract reuse boundary without depending on a separate debug page.

## Preconditions

- Repository is at the S04 close-out state.
- Python deps in `backend/venv` and web deps in `web/node_modules` are installed.
- Run commands from repo root exactly as written below.
- No parallel backend `pytest` jobs are running, to avoid the known coverage-combine collision.

## Smoke Test

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py`.
2. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py`.
3. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`.
4. **Expected:** All three commands exit 0. The backend suites prove the canonical claim-truth mapping and runtime diagnostics contract; the web suite proves learner report/replay render the same truth line.

## Test Cases

### 1. Canonical evaluator and projection mapping

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py`.
2. Inspect the output for the four canonical truth outcomes: unsupported, weak, pending, and verified.
3. **Expected:** 11 tests pass. Open objection ledgers map to `evidence_pending`, `gap_acknowledged` maps to `unsupported_claim`, and `evidence_provided` maps to `weak_evidence` or `evidence_verified` based on follow-up evidence strength, all without changing the stable `main_issue` / `next_goal` keys.

### 2. Runtime diagnostics keep claim truth distinct from chain failure

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py`.
2. Confirm the contract output includes the knowledge-check regression `test_knowledge_check_keeps_claim_truth_distinct_from_kb_lock_chain_failures`.
3. **Expected:** 62 tests pass. Live StepFun `score_update` payloads expose claim truth, reconnect-safe handler state retains it, and `/api/v1/practice/sessions/{id}/knowledge-check` distinguishes evidence-quality states from kb-lock/search failure diagnostics.

### 3. Learner report and replay show the same truth line

1. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'`.
2. Check that both the report and replay suites are included in the Vitest file list.
3. **Expected:** 2 test files and 7 tests pass. Sales report/replay render the `主张证据状态` card with the canonical learner-facing explanations, while presentation routes remain free of this sales-only card.

## Edge Cases

### Closed-ledger truth classification still matters

1. Run the backend evaluator/projection suite from Test Case 1.
2. Inspect the cases covering `gap_acknowledged` and `evidence_provided` closure states.
3. **Expected:** Closed ledgers no longer override `main_issue` / `next_goal`, but they still participate in claim-truth classification so acknowledged gaps become `unsupported_claim` and strong delivered proof becomes `evidence_verified`.

### kb-lock failure does not overwrite learner-facing truth

1. Run the runtime/contract suite from Test Case 2.
2. Inspect the knowledge-check contract case that mixes claim truth with kb-lock failure.
3. **Expected:** Runtime diagnostics can report `kb_lock_chain_failure=true` alongside claim truth, but kb-lock failure never replaces the canonical evidence-quality state.

### Presentation routes stay outside the sales truth card

1. Run the web suite from Test Case 3.
2. Inspect the report/replay expectations for presentation sessions.
3. **Expected:** Presentation report/replay continue to skip the sales-only `主张证据状态` card, confirming S04 did not leak sales semantics into the PPT path.

## Failure Signals

- Any backend suite reports missing or renamed claim-truth statuses.
- `/knowledge-check` contract starts treating kb-lock/search failure as the primary learner-facing claim-truth result.
- Report and replay render different truth states for the same completed-session evidence.
- Presentation report/replay start showing the sales-only truth card.
- Vitest exits 0 but only one targeted file ran; the file list must still show both report and replay suites.

## Requirements Proved By This UAT

- R010 — The current admin/persona-driven realism chain now has one canonical claim-truth contract across evaluator/session evidence, runtime diagnostics, knowledge-check, report, and replay, while keeping kb-lock chain failures in diagnostics rather than learner-facing coaching copy.

## Not Proven By This UAT

- A fresh live objection-heavy runtime/browser session that shows claim-truth transitions on the same real session; S05 still owns that proof.
- Repo-wide web typecheck cleanliness; `cd web && npx tsc --noEmit` still fails on the unrelated pre-existing `api.reprocessKnowledgeDocument` typing gap in `src/app/admin/knowledge/[id]/page.tsx`.

## Notes for Tester

- Keep backend suites sequential. Parallel `pytest` runs in this repo can fail at coverage combine even when the tests themselves are green.
- Treat `blocked_*` / kb-lock/search failures as operational diagnostics only. The learner-facing truth contract for S04 is the canonical `claim_truth` vocabulary.
- If you add more web checks later, remember that Next.js literal paths containing `(user)` and `[sessionId]` must stay quoted in shell commands.
