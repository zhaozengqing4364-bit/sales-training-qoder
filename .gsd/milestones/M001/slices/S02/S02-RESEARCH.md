# M001 / S02 — Research

**Date:** 2026-03-23

## Summary

S02 directly supports **R005** and is the factual precondition for downstream **R006 / R007 / R008**; it also advances **R011** even though R011 is formally owned later. Current code already persists part of the sales-training evidence into `conversation_messages` and `practice_sessions`, but the read paths are split: quick report reads `PracticeSession`, replay reads `ConversationMessage`, history summary reads `ComprehensiveReport.overall_score`, trends/statistics recompute from `PracticeSession` with a different weighting formula, and the report page composes multiple endpoints with fallback.

The core problem is not missing UI. It is source-of-truth fragmentation plus legacy payload drift. StepFun realtime writes `score_snapshot.overall_score`, while replay stage summary and several older tests still expect `score_snapshot.overall`. Highlights have a storage model and UI, but no stable production writer. Comprehensive report generation is not a safe fact source because it depends on `staged_evaluation_results` that the StepFun sales path does not reliably produce, so the report page often has to fall back to a thinner quick report. Zero-turn / low-evidence sessions still route through `summary_service.generate_summary()` and can fail with `[SUMMARY_GENERATION_FAILED]`.

Primary recommendation: implement S02 as a **shared session-evidence boundary** on top of existing `ConversationMessage` + `PracticeSession` snapshot fields, not as another parallel report schema. Normalize one per-turn evidence shape (transcript, stage, score snapshot, fuzzy/vagueness, action card / AI feedback, knowledge-grounding crumbs), normalize legacy keys on read (`overall_score` with fallback to `overall`), persist explicit session-level evaluability/result metadata, and make report / replay / history / trends read from the same normalized evidence projection. Treat `ComprehensiveReport` as a derived view/cache, not the baseline truth.

## Recommendation

Take the smallest architecture shift that actually unifies facts:

1. **Keep existing write surfaces**. StepFun realtime already persists per-message evidence via `save_stepfun_message()` / `patch_existing_message_analysis()` and writes session-level scores / `effectiveness_snapshot` on end. Reuse these instead of inventing a second evidence table immediately.
2. **Add one backend read-model service** for “session evidence baseline” that:
   - loads `PracticeSession`
   - loads ordered `ConversationMessage[]`
   - normalizes legacy/new score snapshot keys
   - exposes session-level evidence summary (overall score basis, evaluable flag, main issue / next goal, knowledge grounding summary, stage rollup, evidence completeness)
3. **Move consumers to that read model** incrementally:
   - `/practice/sessions/{id}/report`
   - `/sessions/{id}/replay`
   - `/practice/history` / `/practice/history/trends` / `/users/me/history`
4. **Stop using in-memory context as report truth** for completed sessions. `SummaryService` can remain as a fallback generator, but terminal persistence/report reads should prefer stored evidence and explicit `evaluable=false` over throwing when evidence is thin.
5. **Do not make S02 depend on staged evaluation availability**. `ComprehensiveReport` should become optional derived output from shared evidence, not the prerequisite for “report exists”.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Realtime per-turn evidence persistence | `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` + `backend/src/common/conversation/storage.py` | Already handles message save + duplicate patch flow; extending this is safer than creating a parallel writer. |
| Session-level next goal / main issue / pass flags | `backend/src/common/effectiveness/evaluator.py` | Already produces deterministic, explainable session result metadata; use it for thin/zero-evidence states instead of inventing another result model. |
| Immutable session runtime baseline for report/replay | `voice_policy_snapshot` + `voice_policy_snapshot_ref` flow proven by `backend/tests/integration/test_voice_runtime_session_snapshot.py` | Existing snapshot-baseline pattern already proves “session-created baseline survives later config changes”; S02 should mirror this mindset for training evidence. |
| Replay message retrieval and access control | `backend/src/common/conversation/replay.py` + `backend/src/common/conversation/api.py` | Current replay reader already owns completed-session gating and message shaping; refactor it into shared evidence reads rather than bypassing it from report/trend code. |

## Existing Code and Patterns

- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — StepFun sales runtime already persists per-turn transcript-derived evidence (`sales_stage`, `fuzzy_words`, `score_snapshot`, `ai_feedback`) and can flush session-level top-line scores + `effectiveness_snapshot` from `_latest_score_snapshot`.
- `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py` — Established dedupe-and-patch pattern for realtime persistence. This is the safest place to normalize future evidence payload changes.
- `backend/src/common/conversation/storage.py` — Canonical message storage API. Supports analysis patching and highlights, but highlight marking is not wired into a stable production path yet.
- `backend/src/common/conversation/replay.py` — Current replay truth reader from `ConversationMessage`. Good candidate to extract a shared read model, but currently has legacy assumptions (`score_snapshot["overall"]`) that drift from StepFun writes (`overall_score`).
- `backend/src/common/api/practice.py` — Contains multiple report/history surfaces (`quick report`, `enhanced-report`, practice history, knowledge-check). This file currently exposes the split-brain more than it resolves it.
- `backend/src/evaluation/services/comprehensive_report.py` — Comprehensive report is a derived layer over `staged_evaluation_results` and DB/in-memory conversation data. Useful as a presentation/cache layer, unsafe as the base truth for S02 because stage results may not exist.
- `backend/src/common/analytics/history_service.py` — History summary reads `ComprehensiveReport.overall_score`; stats/trends recompute from `PracticeSession` top-line scores with a different weighting rule. This is the clearest current contract drift.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Report page currently composes four different backends: comprehensive report, quick report, knowledge-check, highlights. This confirms S02 must unify backend truth before S03 tries to improve readability.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Replay page mixes `/replay`, `/messages`, and `/highlights`, then enriches highlights client-side from message score/audio fields.
- `web/src/app/(dashboard)/history/page.tsx` — History/trend UI assumes one overall score line but currently receives it from different backend formulas/sources.

## Constraints

- S02 must preserve S01’s server-authoritative lifecycle chain. Do not reintroduce client-owned terminal facts or alternate end/write paths.
- Completed-session consumers currently require `session.status == "completed"` for replay/highlights. Any shared evidence reader must keep this contract or explicitly version it.
- Existing data already mixes legacy and new score snapshot shapes (`overall` vs `overall_score`). Reader normalization is required before any “single truth” claim is credible.
- `SummaryService` still relies on in-memory `context_manager`, which is fragile for reconnect / zero-turn / partially recovered sessions. Completed-session truth must move toward persisted evidence, not runtime memory.
- `ComprehensiveReport` generation can legitimately be absent or fail (`[REPORT_NOT_FOUND]`, `[NO_STAGE_RESULTS]`). S02 cannot make “report exists” depend on that pipeline.
- Presentation and sales already diverge in report generation. The shared evidence layer must support both without forcing the presentation-specific deterministic report service into sales or vice versa.

## Common Pitfalls

- **Using `PracticeSession` top-line scores as if they were the full evidence record** — Those fields are useful summary fields, but they drop per-turn stage changes, fuzzy/vague wording, and knowledge-grounding context. Treat them as cached rollups, not primary evidence.
- **Letting each reader recompute “overall score” independently** — Current code already uses both `(logic+accuracy+completeness)/3` and `0.4/0.3/0.3`. S02 should define one normalized overall formula and move all consumers to it.
- **Assuming highlights are already trustworthy evidence** — The UI and storage model exist, but no stable production writer currently calls `mark_highlight()`. Either generate them deterministically from persisted evidence in S02 or keep them explicitly optional.
- **Building new truth on top of `ComprehensiveReport`** — It is an async derived artifact, not a guaranteed baseline. Using it as the only score source would keep history/report drift alive whenever generation lags or fails.
- **Keeping zero-turn handling as a hard failure** — S01 already exposed zero-turn terminal failures. S02 should convert these into explicit “not evaluable / insufficient evidence” records, not another hidden exception path.
- **Forgetting legacy test/data contracts** — Several replay/message tests still use `score_snapshot["overall"]`. Any S02 implementation needs backward-compatible readers or deliberate test/data migration.

## Open Risks

- The current `ConversationMessage` schema may still be too thin for S03/S05 needs such as “未接住的异议”“说虚 / 说错内容” and structured evidence chains. S02 may need either richer `transcript_metadata` usage or a session-level evidence JSON attached to `PracticeSession`.
- Backfilling old sessions could be messy: some sessions will have top-level scores but sparse/legacy message evidence, others may have comprehensive reports but no consistent per-turn analysis.
- Highlight generation is still undefined in live paths. If S03 assumes reliable highlights, S02 must either generate them or explicitly mark them non-blocking.
- History list, trends, quick report, replay, and comprehensive report currently all show “score” differently. Migrating them incrementally risks temporary UI inconsistency unless one shared read model ships first.
- Sales StepFun and presentation handlers persist different kinds of analysis. A shared evidence contract needs scenario-specific optional fields rather than one rigid shape that forces null-heavy payloads.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Next.js / React | `vercel-react-best-practices` | installed |
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| FastAPI | `mindrally/skills@fastapi-python` | available — `npx skills add mindrally/skills@fastapi-python` |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |
| SQLAlchemy / Alembic | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` |

## Sources

- S02 directly supports R005 and provides the fact baseline consumed by downstream report/trend slices; S01 forward intelligence explicitly calls out zero-turn / partial-session persistence as the next slice’s job (source: preloaded milestone roadmap, requirements, and S01 summary).
- Quick report reads mostly `PracticeSession` top-level fields plus `effectiveness_snapshot` and `voice_policy_snapshot_ref`, not per-turn evidence (source: `backend/src/common/api/practice.py`).
- Replay reads `ConversationMessage` rows, derives timeline/stage summaries, and currently expects `score_snapshot["overall"]` when calculating replay stage scores (source: `backend/src/common/conversation/replay.py`).
- StepFun realtime sales persistence writes per-message `sales_stage`, `fuzzy_words`, `score_snapshot`, `ai_feedback`, and session-level `_latest_score_snapshot` with `overall_score` / `dimension_scores` (source: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/sales_bot/websocket/components/stepfun_message_helpers.py`).
- Report page currently composes comprehensive report + quick report + knowledge-check + highlights with fallback behavior, proving the frontend already depends on multiple fact sources (source: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`).
- History list reads `ComprehensiveReport.overall_score`, while statistics/trends recompute from `PracticeSession` top-line scores using a different weighting formula (source: `backend/src/common/analytics/history_service.py`, `backend/src/common/api/users.py`, `backend/src/common/api/analytics.py`).
- Immutable session baseline across detail/report/replay is already proven for voice policy snapshots and can serve as the pattern to copy for evidence baselines (source: `backend/tests/integration/test_voice_runtime_session_snapshot.py`).
- Legacy tests still encode mixed score snapshot shapes (`overall` and `overall_score`), confirming compatibility debt is real rather than theoretical (source: `backend/tests/unit/test_replay_service.py`, `backend/tests/unit/test_stepfun_message_helpers.py`, `backend/tests/unit/test_sales_message_persistence.py`).
- No stable production path currently calls `mark_highlight()`, so “highlights as core evidence” is not yet backed by a guaranteed writer (source: repo-wide search across `backend/src` for `mark_highlight(` only finds storage-layer definitions, not runtime usage).
- Comprehensive report generation depends on `staged_evaluation_results` and can return `[NO_STAGE_RESULTS]`, making it unsafe as the only fact source for finished sessions (source: `backend/src/evaluation/services/comprehensive_report.py`, `backend/src/evaluation/api.py`).
- Zero-turn sales terminal handling still falls back to `summary_service.generate_summary()` when top-level scores are absent, which can produce `[SUMMARY_GENERATION_FAILED]` instead of a persisted “not evaluable” fact (source: `backend/src/common/api/practice.py`, S01 slice summary).
