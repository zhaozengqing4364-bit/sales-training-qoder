# S04: 训练中建议与报告结论一致性 — UAT

**Milestone:** M002
**Written:** 2026-03-24T23:57:40.602Z

# S04: 训练中建议与报告结论一致性 — UAT

**Milestone:** M002
**Written:** 2026-03-25

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 only changes completed-session read surfaces and shared projection logic. The slice proves consistency through persisted sales evidence, contract/integration suites, and focused report/replay/admin rendering checks; no live runtime mutation or human-experience timing proof is required in this slice.

## Preconditions

- Backend test database/fixtures can create completed sales sessions with persisted `sales_stage`, `score_snapshot.dimension_scores`, and stale `effectiveness_snapshot` data.
- Web test environment can render report/replay/admin pages against mocked aligned report payloads.
- Run all backend verification commands from `backend/` sequentially to avoid the repo’s `pytest-cov` combine race.

## Smoke Test

1. From `backend/`, run `venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`.
2. **Expected:** report and replay contract/integration suites pass, including the stale-snapshot override case for completed sales sessions.

## Test Cases

### 1. Completed sales projection overrides stale snapshot with aligned conclusion

1. In `backend/tests/unit/test_session_evidence_service.py`, use a completed sales session whose persisted `effectiveness_snapshot.main_issue/next_goal` is stale but whose later message still contains alignable `sales_stage + dimension_scores` evidence.
2. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv`.
3. **Expected:** the projection returns aligned `main_issue` / `next_goal`, and the logger call includes `sales_alignment_used=True`, the expected `stage_key`, and the expected `focus_type`.

### 2. Insufficient sales evidence falls back cleanly and exposes why

1. Use the insufficient-evidence fixtures in `tests/unit/test_effectiveness_sales_report_alignment.py` and `tests/unit/test_session_evidence_service.py`.
2. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'insufficient_sales_evidence' -vv` and `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv`.
3. **Expected:** fallback keeps the current evaluator semantics instead of inventing a new conclusion, and diagnostics report `sales_alignment_used=False` with a concrete fallback reason such as `missing_dimension_scores`.

### 3. Report and replay return the same aligned conclusion family

1. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`.
2. Inspect the stale-snapshot override assertions in the contract/integration output.
3. **Expected:** `/practice/sessions/{id}/report` and replay read paths keep the same public keys but now expose the same aligned `main_issue` / `next_goal` family for the same completed sales session.

### 4. Replay page visibly matches the aligned report conclusion and admin badges stay readable

1. Run `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`.
2. In the replay test, confirm the page renders the “本场教练结论” block before stage evidence using aligned `main_issue` / `next_goal` payloads.
3. In the admin test, confirm repeated issue/goal badges render readable labels for aligned vocabulary such as `证据支撑` and `证据补强`.
4. **Expected:** report, replay, and admin focused tests all pass and no client-side heuristic recomputation is introduced.

## Edge Cases

### Partial newer snapshot after a better earlier aligned turn

1. Use the completed-sales fixture where the newest message only carries `overall_score`, but an earlier later-turn message still has the last full `dimension_scores` snapshot.
2. Run `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py`.
3. **Expected:** projection/replay scan backward to the latest alignable message instead of regressing to the stale persisted snapshot.

### Optional enhanced-report/highlights failures on the report page

1. In `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, use the fixture where `getComprehensiveReport`/`generateComprehensiveReport` and `getHighlights` fail.
2. Run the focused web command.
3. **Expected:** the page still renders the unified evidence report and eventually shows the degraded copy (`综合洞察暂不可用…`, `高光片段暂不可用…`) rather than crashing or hiding the base report.

## Failure Signals

- Report/replay/admin show different `main_issue` or `next_goal` families for the same completed sales session.
- `practice_session_evidence_projection_built` logs omit alignment diagnostics or always report fallback unexpectedly.
- Replay page falls back to stage evidence only and does not show the aligned coach conclusion card.
- Admin progress badges render raw enum values or blank chips for new S04 issue/goal types.

## Requirements Proved By This UAT

- R009 — completed-session report/replay/admin/history now stay aligned with the sales-first coaching focus family established during realtime coaching, removing the stale-snapshot read-side drift proved by the backend and web verification artifacts.

## Not Proven By This UAT

- Live runtime degraded / reconnect visibility during training; that remains for S05.
- End-to-end human/live proof that one realtime action card and the final report stayed aligned inside the same real session; that remains for S06.

## Notes for Tester

- Treat backend verification as the authoritative proof for projection alignment and diagnostics; replay/admin web tests only prove the read surfaces faithfully render the aligned API output.
- If the report fallback-copy assertion flakes in future edits, check whether the test is waiting for the post-load enhanced-report/highlights effects instead of using synchronous DOM queries.
