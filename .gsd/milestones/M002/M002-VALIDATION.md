---
verdict: needs-remediation
remediation_round: 0
slices_added:
  - S07
  - S08
---

# Milestone Validation: M002

## Success Criteria Checklist
- [x] Criterion 1 — evidence: S01 substantiates the sales-first realtime rubric boundary. Its summary proves classic + StepFun now emit one canonical five-dimension `score_update` / `stage_update` / `action_card` contract, the practice page preserves same-turn score/stage refinement, and `ScorePanel` / websocket focused tests lock the sales labels instead of the legacy generic dimensions.
- [x] Criterion 2 — evidence: S02 and S03 substantiate the single-primary-direction goal. S02 adds the shared realtime-feedback arbiter, same-turn duplicate suppression, reconnect-safe pacing state, transcript-driven stale-hint clearing, and `action_card` precedence on the right panel; S03 then makes stage context + weakest/declining dimensions converge through one shared next-turn coaching rule instead of parallel hints.
- [ ] Criterion 3 — gap: S04 proves completed-session read-side alignment (`report` / `replay` / `history` / `admin`) and adds projection diagnostics, but its own summary explicitly says it does **not yet** prove one live session where the surviving realtime coaching direction and final `main_issue` / `next_goal` stay aligned end-to-end. The planned closeout proof was not delivered before validation.
- [ ] Criterion 4 — gap: No delivered slice substantiates coach degraded / resumed visibility. The milestone directory contains summaries/UAT only for S01-S04, and there is no shipped evidence for capability failure, StepFun jitter, or reconnect recovery surfacing a clear `coach degraded / data unavailable / resumed` state while keeping training usable.

## Slice Delivery Audit

> Audit note: this table reconciles the slice plan M002 entered validation with (S01-S06) before remediation slices were added.

| Slice | Claimed | Delivered | Status |
|-------|---------|-----------|--------|
| S01 | Align realtime scoring, stage labels, and practice-page wording to the current sales rubric | Delivered one canonical five-dimension sales realtime contract across classic + StepFun, fixed same-turn score-update dedupe, kept the practice page sales-first, and re-ran focused backend/frontend suites | pass |
| S02 | Constrain prompt cadence and keep one primary action card per turn | Delivered a shared arbiter, duplicate/replay suppression, minimal reconnect-safe pacing state, transcript-driven stale-hint clearing, and `action_card`-first right-panel precedence | pass |
| S03 | Make stage progression, score deltas, and action-card generation point to one next-turn rule | Delivered `resolve_sales_coaching_focus(...)`, wired classic + StepFun through the same rich-context coaching resolver, and kept the public websocket contract stable | pass |
| S04 | Keep training-time guidance and report/replay conclusions on the same `main_issue` / `next_goal` family | Delivered projection-backed completed-session alignment across report/replay/history/admin, replay conclusion rendering, shared sales vocabulary mapping, and alignment diagnostics | pass |
| S05 | Make coach degradation / reconnect behavior visible without breaking training | No slice summary or UAT artifact exists under `.gsd/milestones/M002/slices/S05`, and the validation evidence contains no delivered UI/log/runtime proof for degraded or resumed coach state | fail |
| S06 | Prove one real sales path end-to-end: live coaching usable, paced, aligned with report, and degraded path diagnosable | No slice summary or UAT artifact exists under `.gsd/milestones/M002/slices/S06`, so there is no end-to-end live proof closing the milestone | fail |

## Cross-Slice Integration
- **S01 → S02:** matched. S02 explicitly consumes the canonical sales realtime payload stabilized in S01 and builds pacing/precedence rules on that boundary.
- **S02 → S03:** matched. S03 reuses S02’s arbiter/pacing seam rather than inventing a second planner, and the summaries line up on one-primary-action behavior.
- **S01 + S03 → S04:** matched. S04 reuses the shared sales vocabulary and stage-aware coaching-focus family to align completed-session read surfaces without renaming public report keys.
- **Planned degradation boundary missing:** the roadmap’s `S02 + S03 → S05` handoff was never retired in execution. No delivered slice proves the promised degrade/resume UI/log/runtime observability boundary.
- **Planned final closure missing:** the roadmap’s `S04 + S05 → S06` handoff was never retired in execution. No delivered slice proves one real session where live coaching, post-session conclusions, and failure-path diagnosability close the loop together.

## Requirement Coverage
- **R009:** materially advanced by S01-S04, but not fully validated for milestone closure. The shipped evidence proves sales-first realtime scoring semantics, pacing, next-turn coaching focus, and completed-session read-side alignment; it does **not** yet prove degraded/resumed coach visibility or one live end-to-end closure path.
- No additional active requirement became orphaned by the delivered work. `R003` and `R005` remain already-validated earlier requirements that M002 only partially reinforces.

## Verdict Rationale
M002 cannot be sealed yet. S01-S04 delivered the core semantic alignment work: the realtime sales rubric is standardized, prompt cadence is constrained, next-turn coaching is decided by one backend rule, and completed-session read surfaces share the same conclusion family. But the milestone still misses the operational closure that the roadmap explicitly required. There is no delivered evidence for coach degraded / resumed visibility under failure or reconnect conditions, and there is no live end-to-end UAT proving one real sales session stays coherent from realtime coaching through final report/replay review. Those are material gaps against the roadmap success criteria and the milestone definition of done, so the correct verdict is `needs-remediation`.

## Remediation Plan
Validation added two remediation slices to `M002-ROADMAP.md`:

1. **S07 — 教练降级/恢复可观测性补齐**
   - Prove capability failure, upstream jitter, silence, and reconnect recovery only degrade the coach surface, never the training mainline.
   - Surface explicit `coach degraded / data unavailable / resumed` state in UI, logs, and runtime evidence so users and operators can distinguish “no issue found” from “coach chain unavailable”.

2. **S08 — 实时教练终验与闭环 UAT**
   - Run one real sales training path that proves: sales-first realtime dimensions are visible, each turn keeps one primary action direction, final report/replay conclusions stay on the same issue/goal family, and degraded-path evidence is diagnosable.
   - Use S04 alignment + S07 observability as the closure gate before re-running milestone validation.
