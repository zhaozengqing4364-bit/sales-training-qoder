# S01: Methodology-aware sales rubric 收口 — UAT

**Milestone:** M022
**Written:** 2026-04-14T05:43:17.667Z

# UAT — M022 / S01 Methodology-aware sales rubric 收口

## Preconditions
- Backend dependencies are installed and the repo-root backend command works: `backend/venv/bin/python -m pytest -c backend/pyproject.toml ...`.
- Web dependencies are installed and `npm --prefix web test -- --run ...` works.
- There is at least one sales practice session fixture or reproducible test session that produces realtime score updates and a completed canonical report/replay/history payload.
- The tester can inspect API payloads or page-rendered data for sales realtime/report/replay/history/admin surfaces.

## Test Case 1 — Realtime sales scoring exposes the shared methodology summary
1. Start or replay a sales practice session that produces a `score_update` / realtime scoring snapshot.
2. Inspect the sales scoring payload emitted by the backend/runtime contract.
3. Confirm the payload still includes the existing score fields (`overall_score`, dimension scores, existing sales score context) and now also carries the additive methodology block.

**Expected outcomes**
- A sales-only methodology summary is present under the shared canonical kernel contract rather than a new ad-hoc top-level score schema.
- The summary exposes the five first-round rubric ids: `discovery_qualification`, `value_story`, `evidence_proof`, `objection_reframe`, `next_step_commitment`.
- The same summary is mirrored through `compatibility_readers.sales_methodology_rubric_v1` for transition consumers.
- The payload does **not** claim an independent `qualification` stage; qualification remains part of `opening + discovery`.

## Test Case 2 — Completed-session read surfaces agree on the same rubric semantics
1. Complete a sales session that has enough evidence to produce canonical report/replay/history data.
2. Inspect the completed-session report payload.
3. Inspect the replay payload for the same session.
4. Inspect a history/admin/session summary surface for the same session.

**Expected outcomes**
- All inspected sales surfaces expose methodology semantics derived from the same shared builder rather than each surface inventing its own rubric health.
- `main_issue` and `next_goal` remain the outward conclusion handles, but they line up with the same rubric gap/next-action interpretation across report/replay/history/admin.
- The rubric ids and health/degraded states are consistent across surfaces for the same session.
- No surface introduces a manager-only or report-only methodology taxonomy.

## Test Case 3 — Learner report explains the rubric contract without breaking the existing report headline
1. Open `/practice/{sessionId}/report` for a completed sales session.
2. Locate the new rubric explainer section on the report page.
3. Read the explainer copy and compare it with the top-line report summary.

**Expected outcomes**
- The report page shows a dedicated sales rubric explainer card describing the five first-round lenses: `discovery / qualification`, `value`, `evidence`, `objection`, `next-step`.
- The existing top-line learner report summary/headline still renders normally; methodology semantics are additive, not a second competing summary block.
- The explainer makes it clear that `main_issue`, `next_goal`, and claim/evidence status come from the same canonical evidence line.

## Test Case 4 — Boundary honesty for qualification remains visible
1. Use the learner report page and docs/api-contract/effectiveness references for the slice.
2. Look specifically for qualification-related wording.
3. Verify that the same wording is present in both docs and the learner-facing report explanation.

**Expected outcomes**
- Qualification is explicitly described as currently merged into `opening + discovery`.
- Neither docs nor page copy claim that the product already ships a standalone qualification stage or complete methodology coverage.
- If the tester only reads the learner report page, they still see the current first-round boundary rather than inflated product claims.

## Test Case 5 — Regression guard on the shared report UI
1. Run `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`.
2. Review the report test result.

**Expected outcomes**
- The report page suite passes green.
- Existing sales report rendering behavior remains intact after the methodology explainer addition.
- The new methodology explanation does not force unrelated report contract churn.

## Edge cases to confirm
- Discovery-only sessions still map qualification evidence through the `discovery_qualification` rubric instead of inventing a separate `qualification` runtime stage.
- Consumers that still rely on compatibility readers can read `sales_methodology_rubric_v1` without losing parity with the canonical methodology payload.
- If a future surface omits the methodology block but still shows canonical sales scores, treat that as a parity regression and recover by reusing the shared methodology builder rather than adding local fallback heuristics.
