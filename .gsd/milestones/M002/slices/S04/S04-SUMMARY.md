---
id: S04
parent: M002
milestone: M002
provides:
  - Projection-backed completed-sales alignment that keeps report / replay / history / admin on the same `main_issue` / `next_goal` family as the shared realtime coaching rule baseline.
  - A replay conclusion surface and shared sales vocabulary map that make the aligned coach conclusion visible and readable outside the report page.
  - Minimal projection diagnostics that show whether sales alignment applied, which stage/focus drove it, and why fallback was used.
requires:
  - slice: S01
    provides: The standardized sales realtime score/stage payload naming and five-dimension rubric contract that S04 reuses on the completed-session read side.
  - slice: S03
    provides: The shared stage-aware coaching-focus rule family that S04 mirrors on report/replay/history/admin via read-side alignment.
affects:
  - S06
key_files:
  - backend/src/common/effectiveness/evaluator.py
  - backend/src/common/conversation/session_evidence.py
  - backend/tests/unit/test_effectiveness_sales_report_alignment.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/lib/session-evidence.ts
key_decisions:
  - D041 — keep public report keys stable and expose alignment diagnostics only on the internal helper seam.
  - D042 — completed-session alignment must scan backward for the latest message whose persisted stage + score pair can actually align, instead of trusting the newest partial snapshot.
  - Replay/admin read surfaces should render the aligned API conclusion directly and centralize sales issue/goal vocabulary in `web/src/lib/session-evidence.ts` rather than adding client-side heuristics.
patterns_established:
  - Use `resolve_sales_report_alignment(...)` as the single read-side sales alignment seam: it consumes persisted stage + normalized dimension-score evidence, returns existing `main_issue` / `next_goal` payloads, and keeps fallback diagnostics internal.
  - When aligning completed sales projections, scan backward for the latest message that can actually align (`alignment_used=True`) instead of blindly trusting the newest partial snapshot.
  - Render aligned conclusions on web read surfaces directly from the API and keep issue/goal label translation centralized in `web/src/lib/session-evidence.ts` so replay/admin stay readable without client-side rule duplication.
observability_surfaces:
  - `practice_session_evidence_projection_built` structured log with `sales_alignment_used`, `sales_alignment_stage_key`, `sales_alignment_focus_type`, and `sales_alignment_fallback_reason`.
  - `backend/tests/unit/test_session_evidence_service.py` assertions that aligned and insufficient-evidence paths emit the expected diagnostic fields.
  - `backend/tests/contract/test_practice_evidence_contract.py` and `backend/tests/integration/test_practice_evidence_flow.py` proving report/replay keep stable keys while sharing aligned conclusions.
  - Replay conclusion card in `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` plus admin progress badges exercised by `web/src/app/admin/users/[id]/page.test.tsx`.
drill_down_paths:
  - .gsd/milestones/M002/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-24T23:57:40.601Z
blocker_discovered: false
---

# S04: 训练中建议与报告结论一致性

**Completed sales sessions now share one stage-aware sales conclusion baseline across report, replay, history, and admin, and replay visibly shows the aligned coach conclusion that the report summarizes.**

## What Happened

S04 closed the remaining drift between ‘练中怎么教’ and ‘练后怎么总结’ for completed sales sessions without changing the public report/replay/websocket contract. T01 established a shared read-side seam in `common.effectiveness`: `resolve_sales_report_alignment(...)` uses persisted sales stage plus normalized dimension scores to derive the same sales-first `main_issue` / `next_goal` family that S03’s realtime coaching rule family points toward, while still falling back to existing evaluator semantics when sales evidence is insufficient. T02 then moved that alignment into the projection seam that all completed-session readers already trust. `SessionEvidenceService.build_projection(...)` now scans backward for the latest persisted message whose stage + score pair can actually align, overrides stale `main_issue` / `next_goal` only in the projection copy, and emits minimal diagnostics (`sales_alignment_used`, stage key, focus type, fallback reason) on `practice_session_evidence_projection_built`. That kept report, replay, history, and admin on one aligned baseline even when older `effectiveness_snapshot` values were stale or newer messages only carried partial `overall_score` snapshots.

During slice close I finished the missing T03 web carry-forward. Replay now renders a read-only “本场教练结论” block directly from the API’s aligned `main_issue` / `next_goal` before stage evidence, and `web/src/lib/session-evidence.ts` now translates the new S04 vocabulary (`evidence_gap`, `objection_handling_gap`, `next_step_gap`, `evidence_backing`, etc.) so replay and admin progress badges remain readable. The focused report/replay/admin tests were updated to reflect the aligned vocabulary, and a pre-existing report fallback assertion was corrected to wait for the asynchronous enhanced-report/highlights degraded copy instead of misreporting a UI regression. The resulting slice gives downstream S05/S06 a stable completed-session comparison line: realtime coaching can now be checked against report/replay/admin conclusions using one shared sales-first vocabulary and one diagnosable projection seam.

## Verification

Fresh slice-level verification passed after completing the missing T03 carry-forward and correcting the pre-existing async report fallback assertion. Exact commands run: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py`; `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv`; `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'insufficient_sales_evidence' -vv`; `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv`; `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`; and `cd web && /usr/bin/time -p npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`. All exited 0 on the final run. Observability was confirmed by the projection-diagnostic fields asserted in `backend/tests/unit/test_session_evidence_service.py` and by the replay/admin focused tests that render the aligned conclusion family visibly.

## Requirements Advanced

- R009 — S04 proved that completed sales sessions no longer let stale read-side snapshots drift away from the sales-first coaching focus family established in S03: projection, report, replay, history, and admin now share aligned `main_issue` / `next_goal` conclusions while preserving stable public contract keys.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Adjusted one pre-existing report-page async fallback assertion to wait for post-load degraded copy while finishing T03; otherwise the slice followed the written plan.

## Known Limitations

S04 aligns completed-session read surfaces only. It does not yet prove coach degraded / resume visibility during live training, and it does not itself supply the live end-to-end/UAT proof that one realtime suggestion and the final report stayed aligned inside the same session; those remain for S05 and S06.

## Follow-ups

S05 should reuse the new projection diagnostics when surfacing coach degraded / resume visibility so operators can distinguish ‘no coach issue found’ from ‘coach alignment unavailable’. S06 should run one live sales session that proves the realtime action card and final report/replay conclusion share the same issue/goal family for the same session.

## Files Created/Modified

- `backend/src/common/effectiveness/evaluator.py` — Added the shared `resolve_sales_report_alignment(...)` helper and aligned sales issue/goal vocabulary for completed-session read-side reuse.
- `backend/src/common/effectiveness/schemas.py` — Defined shared schemas for the report-alignment helper diagnostics and payload typing.
- `backend/src/common/effectiveness/__init__.py` — Exported the new sales report-alignment helper from the shared effectiveness boundary.
- `backend/src/common/conversation/session_evidence.py` — Made completed sales projections scan backward for the latest alignable sales evidence, override stale read-side conclusions, and emit alignment diagnostics on `practice_session_evidence_projection_built`.
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py` — Locked discovery/evidence, objection handling, closing/next-step, and insufficient-evidence fallback behavior for the shared alignment helper.
- `backend/tests/unit/test_session_evidence_service.py` — Verified projection-side override/fallback behavior and the new alignment diagnostics fields.
- `backend/tests/unit/test_replay_service.py` — Proved replay reads the aligned sales conclusion instead of stale snapshot data.
- `backend/tests/unit/test_history_service_evidence_projection.py` — Verified history/progress readers reuse the aligned projection baseline for completed sales sessions.
- `backend/tests/contract/test_practice_evidence_contract.py` — Kept report/replay contract keys stable while asserting stale sales snapshots are overridden by aligned conclusions.
- `backend/tests/integration/test_practice_evidence_flow.py` — Proved completed-session report and replay stay aligned through the real API flow.
- `backend/tests/integration/test_sales_value_training_flow.py` — Updated the sales report integration proof to the current aligned-stage baseline.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Added the read-only “本场教练结论” block so replay shows the same aligned `main_issue` / `next_goal` family as report before stage evidence.
- `web/src/lib/session-evidence.ts` — Extended shared issue/goal label maps for S04 alignment vocabulary such as `evidence_gap`, `objection_handling_gap`, and `evidence_backing`.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Asserted replay renders the aligned coach conclusion and does not fall back to legacy `/messages` stitching.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Updated sales fixtures to the aligned issue/goal vocabulary and fixed async degraded-copy assertions for enhanced-report/highlights fallback.
- `web/src/app/admin/users/[id]/page.test.tsx` — Verified admin progress badges remain readable for the new aligned sales issue/goal types.
- `.gsd/REQUIREMENTS.md` — Recorded that R009 is further advanced by S04’s completed-session alignment proof while remaining active pending S05/S06.
- `.gsd/KNOWLEDGE.md` — Captured the async-report-fallback test gotcha so future agents wait for degraded copy instead of misreporting a regression.
- `.gsd/PROJECT.md` — Refreshed project state to note that M002/S04 now aligns completed-session report/replay/admin/history conclusions to the realtime coaching family.
