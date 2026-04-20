---
id: S03
parent: M021
milestone: M021
provides:
  - One canonical evaluation truth line that S04 can attach AI quality/cost/failure events to.
  - A durable migration contract: canonical_evaluation_kernel + compatibility_readers + explicit fallback order.
  - A shared frontend score resolver that future score-bearing pages can reuse instead of recomputing rollups.
requires:
  []
affects:
  - S04
key_files:
  - backend/src/common/effectiveness/canonical.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/services/practice_report_service.py
  - backend/src/common/conversation/replay.py
  - backend/src/agent/capabilities/realtime_scoring.py
  - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - D236 — share one logic/accuracy/completeness rollup contract while allowing scenario-aware canonical dimension catalogs.
  - D237 — expose explicit canonical_evaluation_kernel plus compatibility_readers while preserving legacy top-level rollups during migration.
  - D238 — force all learner web score surfaces through one shared fallback order: canonical_evaluation_kernel -> compatibility_readers -> legacy rollups.
patterns_established:
  - Ship canonical evaluation truth as a nested kernel plus compatibility readers instead of doing a flag-day field replacement.
  - Keep sales and presentation on one shared rollup contract while allowing scenario-specific canonical dimensions.
  - Whenever realtime score payloads gain new fields, extend StepFun snapshot normalization in the same change or persistence will silently drop them.
  - Force learner score surfaces through one shared frontend resolver so canonical -> compat -> legacy retirement stays measurable and intentional.
observability_surfaces:
  - `SessionEvidenceService` structured log field `evaluation_kernel_contract` for the canonical projection contract.
  - Persisted `canonical_evaluation_kernel` + `compatibility_readers` on realtime/message/report/replay/history payloads.
  - Frontend `data-contract-source` / shared `readSessionEvaluationRollups(...)` source resolution on report/replay/history.
  - Architecture-scan retirement-order note documenting canonical -> compat -> legacy fallback expectations.
drill_down_paths:
  - .gsd/milestones/M021/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M021/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M021/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T03:53:40.866Z
blocker_discovered: false
---

# S03: Canonical evaluation kernel 收口

**Completed the shared canonical evaluation kernel cutover so realtime, report, replay, history, and projection-backed admin surfaces now read one scenario-aware score truth line with explicit compatibility readers.**

## What Happened

## Slice Summary

### Goal Delivered
S03 finished the canonical evaluation kernel cutover for the shipped evaluation read path. Realtime scoring, persisted score snapshots, session-evidence projection, learner report/replay/history, and projection-backed admin/history consumers now share one scenario-aware `canonical_evaluation_kernel` plus explicit `compatibility_readers`, instead of each surface inferring score truth from whichever legacy rollup fields happened to be present.

### What Actually Shipped
- Added a code-owned canonical evaluation kernel in `backend/src/common/effectiveness/canonical.py` with:
  - one stable cross-surface rollup contract (`logic` / `accuracy` / `completeness`),
  - scenario-aware dimension catalogs for sales and presentation,
  - surface reader plans that distinguish canonical consumers from compatibility mirrors.
- Wired realtime scoring and StepFun score snapshot normalization to emit and persist `canonical_evaluation_kernel` + `compatibility_readers`, so the canonical payload survives the realtime -> message storage -> read-side projection path instead of existing only in memory.
- Promoted `SessionEvidenceService` into the canonical evaluation authority seam for report/replay/history/admin read-side consumers. It now projects the canonical kernel, exposes compatibility readers, and logs the kernel contract boundary for downstream diagnostics.
- Threaded the same canonical kernel through projection-backed report, replay, history, and admin-facing summaries while keeping old top-level rollup fields as compatibility output instead of letting each consumer keep recomputing scores.
- Updated shared web API types and moved report/replay/history onto one shared frontend resolver (`readSessionEvaluationRollups(...)`) so every learner-facing score surface now uses the same fallback order: `canonical_evaluation_kernel` first, `compatibility_readers` second, legacy top-level rollups last.
- Recovered the partially broken T03 runtime cutover by removing duplicated JSX tails from the report/replay pages before finishing the real shared-resolver migration.
- Wrote the canonical -> compatibility -> legacy retirement order back into durable artifacts (`ARCHITECTURE_SCAN`, `DECISIONS`, `KNOWLEDGE`, `PROJECT`) so future slices do not rediscover or silently bypass the migration rules.

### Patterns Established
1. **Canonical kernel + compatibility readers, not flag-day replacement.** New score truth ships as an explicit nested payload while old rollup fields remain mirrored outputs during migration.
2. **Scenario-aware dimensions under shared rollups.** Sales and presentation do not need one flat dimension vocabulary to share one kernel; they share rollup semantics while keeping distinct canonical dimension catalogs.
3. **Persist new realtime fields end-to-end.** Any new score payload field must be added to StepFun snapshot normalization at the same time or the runtime/write/read paths will drift.
4. **Frontend uses one shared fallback resolver.** Learner pages must not hand-roll fallback math; retirement only becomes measurable when every surface uses the same resolver.

### Downstream Guidance
- S04 should attach quality/cost/failure events to this canonical evaluation seam, not to legacy top-level rollup fields.
- Compatibility reader retirement must be driven by consumer usage: once report/replay/history/admin no longer hit compat fallback, those readers can move toward retire status. Until then, they remain intentional transition surfaces.
- If a future slice adds another score-bearing surface, it should either read the canonical kernel directly or reuse the shared compatibility reader strategy; do not create another local score projection.

### Operational Readiness (Q8)
- **Health signal:** completed-session projections and learner surfaces expose `canonical_evaluation_kernel`, `compatibility_readers`, and a consistent score source (`canonical_kernel`, `compatibility_reader`, or `legacy_rollup`) instead of silently drifting.
- **Failure signal:** if realtime emits a new score field but `normalize_score_snapshot()` is not extended, persisted `ConversationMessage.score_snapshot` will drop the canonical payload and read-side consumers will fall back unexpectedly; if a web page bypasses `readSessionEvaluationRollups(...)`, that page can silently remain on compat/legacy behavior.
- **Recovery procedure:** re-run the focused backend parity/history/admin bundle plus the focused web report/replay/history bundle, then inspect `backend/src/common/effectiveness/canonical.py`, `backend/src/common/conversation/session_evidence.py`, `sales_bot/websocket/components/stepfun_message_helpers.py`, and `web/src/lib/session-evidence.ts` together; fixes must land across all four seams or the canonical truth line will only be partially restored.
- **Monitoring gaps:** compat-fallback usage is still inferred from payload/source inspection and focused tests rather than from a dedicated production counter. Downstream observability work should add explicit compat-hit telemetry before retirement decisions rely on ad-hoc log reading.

## Verification

Fresh slice-close verification passed on the assembled bundle: `rg -n "logic_score|accuracy_score|completeness_score|overall_score|dimension_scores|effectiveness_snapshot|leaderboard|history" backend/src/common backend/src/agent web/src/lib/api/types.ts` passed for the inventory/proof grep, `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q` passed 49/49, `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"` passed 44/44, `rg -n 'prefer `canonical_evaluation_kernel`|compatibility_readers|retire 阶段' .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md -S` confirmed the documented canonical -> compat -> legacy retirement order, and LSP diagnostics were clean on `backend/src/common/effectiveness/canonical.py`, `backend/src/common/conversation/session_evidence.py`, `web/src/lib/session-evidence.ts`, and `web/src/app/(dashboard)/history/page.tsx`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Compatibility readers and legacy top-level rollup fields are still intentionally present for the migration window. Projection-backed realtime/report/replay/history/admin surfaces now share the canonical kernel, but broader legacy SQL-only aggregates such as untouched leaderboard/runtime-metrics paths are not retired by this slice and must not be mistaken for canonical authority.

## Follow-ups

S04 should attach AI quality/cost/failure events to this canonical evaluation truth line instead of inventing a second event payload around legacy rollup fields. Compatibility readers remain intentionally exposed until downstream consumers prove they no longer hit compat fallback.

## Files Created/Modified

- `backend/src/common/effectiveness/canonical.py` — Added the scenario-aware canonical evaluation kernel, shared rollup contract, and compatibility reader builders for sales/presentation.
- `backend/src/common/conversation/session_evidence.py` — Projected canonical_evaluation_kernel + compatibility_readers through the shared session evidence authority seam and added kernel contract logging.
- `backend/src/common/analytics/history_service.py` — Switched projection-backed history/admin read models to consume the shared canonical kernel and carry the same rollups downstream.
- `backend/src/common/services/practice_report_service.py` — Threaded canonical kernel payloads through practice report/replay response builders and realtime persistence normalization.
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — Preserved canonical kernel fields in persisted StepFun score snapshots so realtime -> storage -> read-side stays lossless.
- `web/src/lib/api/types.ts` — Declared canonical_evaluation_kernel / compatibility_readers in shared web API types and reused one frontend score resolver across report/replay/history.
- `web/src/lib/session-evidence.ts` — Centralized canonical -> compat -> legacy score resolution for learner surfaces.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Report page now resolves and exposes score source from the shared canonical/compat contract instead of guessing from legacy rollups.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Replay page now resolves the same shared score source and no longer diverges from report/history.
- `web/src/app/(dashboard)/history/page.tsx` — History cards and trend deltas now read the same canonical/compat score source used by report/replay.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Documented the canonical -> compatibility -> legacy retirement order for downstream slices.
- `.gsd/KNOWLEDGE.md` — Recorded the new frontend shared-resolver gotcha so future slices do not reintroduce page-local score fallback math.
- `.gsd/DECISIONS.md` — Recorded the shared web fallback-order decision for the migration.
- `.gsd/PROJECT.md` — Refreshed project state to reflect that M021/S03 is now complete and S04 is the next focus.
