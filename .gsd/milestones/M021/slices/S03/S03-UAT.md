# S03: Canonical evaluation kernel 收口 — UAT

**Milestone:** M021
**Written:** 2026-04-14T03:53:40.867Z

# UAT — M021 / S03 Canonical evaluation kernel 收口

## Preconditions
1. Backend and web are running on the current branch with the S03 changes.
2. Prepare three sessions for verification:
   - one **completed sales session** created after the S03 change,
   - one **completed presentation session** created after the S03 change,
   - one **older completed session** (or fixture payload) that still relies on compatibility readers / legacy rollups.
3. Tester can access learner report/replay/history and any admin surface that already consumes projection-backed session summaries.

## Test Case 1 — Sales report reads canonical kernel first
1. Open the completed sales session report at `/practice/{sessionId}/report`.
2. Inspect the report header score and dimension summary.
3. Confirm the API payload for the same session includes `canonical_evaluation_kernel` and `compatibility_readers`.
4. Expected outcome:
   - the page renders a score without error,
   - the rendered top-line score matches `canonical_evaluation_kernel.overall_score`,
   - the report identifies the resolved score source as canonical rather than silently falling back,
   - legacy top-level `logic_score` / `accuracy_score` / `completeness_score` remain present only as compatibility mirrors.

## Test Case 2 — Replay matches report on the same session
1. Open `/practice/{sessionId}/replay` for the same completed sales session.
2. Compare the replay headline score with the report headline score.
3. Expected outcome:
   - replay renders successfully without parser/runtime errors,
   - the replay headline score matches the report headline score,
   - replay resolves score source from the same contract order as report (`canonical_evaluation_kernel` -> `compatibility_readers` -> legacy rollups),
   - there is no page-local drift where replay shows a different rollup than report for the same session.

## Test Case 3 — History cards and trend deltas use the same resolver
1. Open `/history` for the learner that owns the completed sales session.
2. Locate the card for that session and inspect any visible trend / summary score.
3. Expected outcome:
   - the session card score matches report/replay for the same session,
   - history does not recalculate from stale local math,
   - if the session is canonical-ready, the resolved source is canonical rather than compat/legacy.

## Test Case 4 — Presentation sessions share the same kernel family
1. Open the completed presentation session report.
2. Inspect the payload for `canonical_evaluation_kernel` and `compatibility_readers`.
3. Expected outcome:
   - presentation sessions still expose shared rollups (`logic` / `accuracy` / `completeness`) through the canonical kernel,
   - presentation-specific canonical dimensions are present instead of being flattened into sales-only dimensions,
   - the learner-facing score remains readable on the shared report/replay/history route family.

## Test Case 5 — Compatibility fallback stays intentional for older sessions
1. Open the older completed session or inject a fixture payload where `canonical_evaluation_kernel` is absent but `compatibility_readers` or legacy top-level rollups still exist.
2. Visit report, replay, and history for that session.
3. Expected outcome:
   - the pages still render instead of breaking,
   - the resolved score source shows compatibility-reader fallback before legacy fallback,
   - numbers remain aligned across report/replay/history even though the session is not fully canonical.

## Edge Case A — Persistence seam regression detection
1. Trigger a realtime scoring update on a fresh practice session.
2. Inspect the persisted `ConversationMessage.score_snapshot` for the new turn.
3. Expected outcome:
   - `score_snapshot` preserves `canonical_evaluation_kernel` and `compatibility_readers`,
   - the completed report/replay/history for that session can read the same canonical payload without reconstructing it heuristically.

## Edge Case B — Frontend shared resolver remains the single fallback authority
1. Compare report, replay, and history for the same session after forcing a compat-only payload.
2. Expected outcome:
   - all three surfaces still agree on logic/accuracy/completeness/overall,
   - no surface drifts onto its own local fallback order,
   - if one page diverges, treat it as a shared-resolver regression rather than a cosmetic UI bug.

