---
id: T02
parent: S04
milestone: M002
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/integration/test_sales_value_training_flow.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D042: projection-side sales alignment scans backward for the latest message that can actually align (`alignment_used=True`) instead of blindly using the newest partial `score_snapshot`.
  - Expose minimal projection diagnostics (`sales_alignment_used`, `sales_alignment_stage_key`, `sales_alignment_focus_type`, `sales_alignment_fallback_reason`) on `practice_session_evidence_projection_built` while keeping public report/replay/history payload keys unchanged.
duration: ""
verification_result: passed
completed_at: 2026-03-24T23:42:39.176Z
blocker_discovered: false
---

# T02: Align completed sales projections to the latest alignable evidence and log read-side fallback diagnostics

**Align completed sales projections to the latest alignable evidence and log read-side fallback diagnostics**

## What Happened

I verified the existing T02-focused red tests first and confirmed the root cause: `SessionEvidenceService.build_projection(...)` was still copying `ensure_effectiveness_snapshot(...)` verbatim, so completed sales readers reused stale `effectiveness_snapshot.main_issue` / `next_goal`, and the projection log emitted no sales-alignment diagnostics. I implemented the smallest read-side fix in `backend/src/common/conversation/session_evidence.py`: completed sales projections now evaluate persisted message evidence through `resolve_sales_report_alignment(...)`, scan backward for the latest message whose stage + normalized score snapshot can actually align, override only the projection-facing `main_issue` / `next_goal` and `effectiveness_snapshot` copy when alignment applies, and otherwise preserve the existing insufficient-evidence fallback unchanged. I also extended `practice_session_evidence_projection_built` with concise safe diagnostics (`sales_alignment_used`, stage key, focus type, fallback reason). While proving replay coverage, I hit a local test-fixture mismatch rather than a product bug: the replay unit fixture left MagicMock `presentation_id` truthy, which forced `resolve_scenario_type(...)` into the presentation branch and returned `[PRESENTATION_REVIEW_BUILD_FAILED:]`; I corrected the fixture to explicitly clear `presentation_id` / `voice_policy_snapshot`. Finally, I investigated the remaining `test_sales_value_training_flow` failure and confirmed it was a stale assertion, not a regression: `stage_summary` still truthfully reflects per-message `overall_score`, so I updated the outdated discovery-stage expectation from 78 to the seeded 82. The result is that report, replay, history, and contract/integration readers all now share the same aligned completed-sales conclusion baseline, and the projection log directly shows whether alignment applied or why it fell back.

## Verification

Fresh slice verification passed end-to-end. Backend unit coverage proved the shared sales alignment helper, projection override path, replay reader, history projection, and insufficient-evidence fallback behavior. Contract and integration suites proved `/practice/sessions/{id}/report` and `/sessions/{id}/replay` now return the same aligned `main_issue` / `next_goal` for stale completed sales snapshots while preserving stable public keys and explicit evidence-completeness semantics. The refreshed web slice command also passed, confirming the current report/replay/admin focused surfaces still consume the aligned contract without frontend regressions. Observability was verified through the projection log fields emitted during the integration run: `practice_session_evidence_projection_built` now includes `sales_alignment_used=true`, `sales_alignment_stage_key=discovery`, `sales_alignment_focus_type=evidence_gap`, and `sales_alignment_fallback_reason=null` for the aligned sales flow, while the insufficient-evidence unit path asserts the same signal falls back with `sales_alignment_used=false` and `sales_alignment_fallback_reason=missing_dimension_scores`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py` | 0 | ✅ pass | 7783ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv` | 0 | ✅ pass | 5712ms |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'insufficient_sales_evidence' -vv` | 0 | ✅ pass | 6048ms |
| 4 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv` | 0 | ✅ pass | 6118ms |
| 5 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py` | 0 | ✅ pass | 6521ms |
| 6 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1506ms |


## Deviations

Adjusted one stale integration expectation in `backend/tests/integration/test_sales_value_training_flow.py` so `stage_summary` continues to assert the canonical per-message `overall_score` contract (82 for the seeded discovery turn), and hardened the replay unit fixture by explicitly setting `presentation_id=None` / `voice_policy_snapshot=None` to avoid MagicMock truthiness misclassifying sales sessions as presentation sessions.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_sales_value_training_flow.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
