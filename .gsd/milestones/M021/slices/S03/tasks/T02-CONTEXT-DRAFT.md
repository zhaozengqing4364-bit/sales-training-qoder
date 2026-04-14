# M021 / S03 / T02 wrap-up context draft

## Status
- Task **not implemented yet** in this unit.
- No product code changed.
- Wrap-up was triggered by context budget before the planned red→green implementation loop started.

## What was verified
- Read task/slice plans, prior T01 summary, and safe-grow continuity files.
- Read the current implementation seams in:
  - `backend/src/common/effectiveness/canonical.py`
  - `backend/src/common/conversation/session_evidence.py`
  - `backend/src/common/services/practice_report_service.py`
  - `backend/src/common/conversation/replay.py`
  - `backend/src/common/analytics/history_service.py`
  - `backend/src/common/analytics/admin_analytics_service.py`
  - `backend/src/agent/capabilities/realtime_scoring.py`
  - `backend/src/presentation_coach/services/presentation_report_service.py`
  - `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`
  - `backend/src/common/services/practice_session_service.py`
  - `backend/src/common/api/practice.py`
  - `backend/src/common/db/schemas.py`
  - `backend/src/common/conversation/schemas.py`
- Ran the exact task-plan verification command before edits:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q`
  - Result: **47 passed**.
- Ran a focused grep inventory confirming the current state:
  - canonical schema constants exist in `common/effectiveness/canonical.py`
  - read-side consumers already centralize around `SessionEvidenceService`
  - realtime write path and API/read-model schemas still expose mostly legacy rollup fields (`logic_score`, `accuracy_score`, `completeness_score`, `overall_score`, `dimension_scores`) instead of a shipped canonical evaluation kernel payload.

## Concrete findings to resume from
1. **Canonical schema exists, runtime kernel does not.**
   - `backend/src/common/effectiveness/canonical.py` currently declares dimension catalogs + surface reader plans only.
   - It does **not** yet provide a runtime `build_*kernel*` function or compatibility-reader registry implementation that downstream code can call.

2. **Read-side projection still derives legacy rollups directly.**
   - `SessionEvidenceService.build_projection()` still resolves `logic/accuracy/completeness` via `_resolve_score_triplet()` and presentation-specific ad hoc mapping.
   - This is the strongest place to introduce one canonical evaluation object and then derive legacy fields from compatibility readers.

3. **Realtime snapshots are still legacy-shaped.**
   - `RealtimeScoringCapability.execute()` emits `overall/overall_score/dimensions/dimension_scores/feedback`.
   - `normalize_score_snapshot()` only preserves `overall_score`, `dimension_scores`, `stage_name`, and `suggestions`.
   - `_apply_sales_realtime_score_snapshot_to_session()` in both `common/services/practice_session_service.py` and `common/api/practice.py` still calls `build_sales_rollup_scores(...)` directly.

4. **Report/replay/history/admin are already close to a single authority seam.**
   - `PracticeReportService.build_session_report()` and `ReplayService.get_replay_data()` already read from `SessionEvidenceService`.
   - `HistoryService.build_history_entries()` and `AdminAnalyticsService` already aggregate from the same projection summaries.
   - The likely minimal change is to attach one canonical evaluation payload to the projection/report/replay/history/admin summaries while keeping existing top-level legacy fields for compatibility.

5. **Presentation path needs the same kernel, not a separate contract.**
   - `PresentationReportService.build_presentation_review()` returns the six-dimension review payload, but not a shared canonical kernel object.
   - `SessionEvidenceService._attach_presentation_review()` then remaps those scores into the three legacy rollups ad hoc.
   - This is the second main seam to unify under the same kernel builder with scenario-aware dimensions.

## Recommended next move (do this first)
Use TDD and add **fail-first** focused tests before code edits. Suggested test targets:

1. `backend/tests/contract/test_practice_evidence_contract.py`
   - Add assertions that report/replay responses expose a new `canonical_evaluation` (or similarly named) payload with:
     - `schema_version == "evaluation_kernel_v1"`
     - `scenario_type`
     - canonical dimension entries
     - canonical rollups
   - Keep asserting current legacy fields remain present and match compatibility-reader output.

2. `backend/tests/unit/test_history_service_evidence_projection.py`
   - Add assertions that `HistorySessionSummary` carries the same canonical evaluation payload from projection, while legacy summary fields remain unchanged.

3. `backend/tests/unit/common/test_admin_analytics_service.py`
   - Add a small assertion proving admin aggregates still compute from the projection-backed compatibility output while source summaries expose the canonical payload.

4. Add a new focused realtime unit test if feasible (likely under `backend/tests/unit/`)
   - Assert `RealtimeScoringCapability` emits the canonical payload and that score snapshot normalization preserves it.

## Recommended implementation order after tests fail
1. Add runtime kernel builder + compatibility reader registry/helpers in `backend/src/common/effectiveness/canonical.py`.
2. Export them from `backend/src/common/effectiveness/__init__.py`.
3. Update `SessionEvidenceProjection` / `SessionEvidenceService` to build and carry canonical evaluation, then derive legacy rollups from compatibility readers.
4. Update `PresentationReportService` to emit/build the same canonical kernel for presentation dimensions.
5. Update `PracticeReportService`, `ReplayService`, `HistoryService`, and schemas (`common/db/schemas.py`, `common/conversation/schemas.py`) to expose the canonical payload while preserving legacy fields.
6. Update realtime scoring + score snapshot normalization + terminal sync helpers to emit/preserve the canonical payload and use compatibility readers when projecting session rollups.

## Verification to rerun after implementation
- Exact task-plan bundle:
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q`
- Plus any new focused realtime/canonical unit tests you add.

## Important constraints
- Keep changes minimal and preserve current stack.
- Do **not** batch unrelated analytics/dashboard/training cleanup just because grep showed more legacy score math elsewhere.
- The most relevant untouched legacy surfaces discovered but **not** yet in scope for this unit are broader analytics/training/dashboard helpers that still read direct session rollups.
