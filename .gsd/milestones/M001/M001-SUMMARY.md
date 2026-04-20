---
id: M001
provides:
  - Desktop sales/PPT training now closes on one stable lifecycle and evidence line, with governed material updates, readable reports, supervisor trend views, and release-health diagnostics.
key_decisions:
  - D009
  - D013
  - D015
patterns_established:
  - Persist session facts once, project them once, and make learner, supervisor, trend, PPT, and runtime-health surfaces read the same authority line.
  - Model degraded, blocked, and not-evaluable outcomes as explicit business facts with diagnostics instead of hiding them behind generic summary failures.
  - Freeze knowledge and PPT material identity into each new session so next-session behavior stays explainable across runtime, report, and retry flows.
observability_surfaces:
  - GET /api/v1/practice/sessions/{id}/report
  - GET /api/v1/admin/users/{userId}/sessions
  - GET /api/v1/admin/users/{userId}/progress
  - GET /api/v1/presentations
  - GET /api/v1/support/runtime/overview
  - practice_session_lifecycle_transition_applied / practice_session_evidence_projection_built
requirement_outcomes:
  - id: R001
    from_status: active
    to_status: validated
    proof: S01 unified terminal lifecycle and reconnect recovery for sales practice, and S08 rechecked the real practice-page runtime surface in the final localhost release wave.
  - id: R002
    from_status: active
    to_status: validated
    proof: S01 made lifecycle failures retryable and trace-bearing on the practice page, while S08 classified runtime anomalies on /support/runtime instead of leaving them as opaque breakages.
  - id: R003
    from_status: active
    to_status: validated
    proof: S05 re-centered scoring, prompts, knowledge checks, and canonical report output on value articulation, customer benefit translation, evidence use, and objection handling.
  - id: R004
    from_status: active
    to_status: validated
    proof: S04 proved admin-managed knowledge/PPT updates, frozen session material snapshots, live knowledge-check diagnostics, stable presentation versioning, and active-session replace blocking.
  - id: R005
    from_status: active
    to_status: validated
    proof: S02 unified the report fact baseline, S03 made the canonical learner report readable and actionable, and S08 rechecked that the baseline report still works when optional enhancement endpoints degrade.
  - id: R006
    from_status: active
    to_status: validated
    proof: S03 moved supervisor previews and drill-ins onto the same projection-backed evidence line and proved canonical /practice/{sessionId}/report review paths for completed sessions.
  - id: R007
    from_status: active
    to_status: validated
    proof: S06 delivered projection-backed /progress and /stats surfaces plus live browser/API proof that supervisors can judge improvement, repeated blockers, and focus shifts across recent sessions.
  - id: R008
    from_status: active
    to_status: validated
    proof: S07 made the shared report route scenario-aware for PPT reviews, proved happy and degraded presentation paths, and validated a real audio-driven page-turn session; S08 rechecked both PPT report paths in the release wave.
duration: 2026-03-23 → 2026-03-24
verification_result: passed
completed_at: 2026-03-24T18:35:27+08:00
---

# M001: 桌面端销售训练闭环可用化

**Turned the desktop sales/PPT training stack into one usable launch loop: stable realtime sessions, one evidence-backed report line, governed material updates, supervisor progress views, and release-health diagnostics.**

## What Happened

M001 started by removing split-brain behavior from the core runtime. S01 put sales practice lifecycle changes behind one backend terminal path, made reconnect recovery restore only the safe runtime snapshot, and forced the practice page to trust only server lifecycle events. S02 then did the same kind of cleanup for facts: session evidence is now persisted and projected once, with explicit evaluability and completeness semantics, so report, replay, history, and trends no longer invent their own versions of the same session.

With the authority lines in place, the milestone turned those facts into usable product surfaces instead of isolated plumbing. S03 made the learner report lead with result, main issue, next goal, and evidence, while supervisor previews now deep-link to the same canonical `/practice/{sessionId}/report` route. S04 made governed material updates real: admin knowledge and standard PPT changes now carry diagnostics, stable version identity, and next-session effect. S05 re-centered sales training on value articulation, evidence, and objection handling rather than generic conversation labels. S06 extended the same evidence projection into supervisor progress so managers can judge whether someone is improving or repeating the same blocker. S07 made the shared report route scenario-aware for PPT practice, including degraded-but-explicit presentation evidence when page metadata is incomplete.

S08 closed the loop instead of leaving those slices as separate wins. The release wave rechecked sales runtime behavior, canonical learner report behavior, supervisor progress behavior, PPT happy/degraded report behavior, and `/support/runtime` anomaly surfacing on one localhost proof line. The result is a desktop-first training system that now behaves like one product: stable enough to run, explicit enough to diagnose, and coherent enough that learner, supervisor, admin, and support views all point at the same underlying facts.

## Cross-Slice Verification

- **Implementation-backed milestone, not planning-only:** `git diff --stat "$(git merge-base HEAD 001-ai-practice-system)" HEAD -- ':!.gsd/'` showed **71 non-`.gsd/` files changed** with **10816 insertions** and **2052 deletions**.
- **All slices materially delivered and documented:** `find .gsd/milestones/M001/slices -maxdepth 2 -name 'S*-SUMMARY.md'` returned **8 summary files**, matching S01-S08.
- **Criterion 1 — desktop sales practice can complete and recover real sessions:** S01 passed backend/frontend lifecycle suites and live reconnect/error checks on `/practice/{sessionId}`; S05 re-proved a live multi-turn StepFun sales session with value/price/competitor/proof prompts; S08 rechecked the final localhost runtime surface.
- **Criterion 2 — learners get a readable, trustworthy, actionable single-session report:** S02 unified the evidence baseline, S03 made `/practice/{sessionId}/report` lead with result / main issue / next goal / evidence, and S08 rechecked that the canonical report remains usable even when optional enhanced-report endpoints fail.
- **Criterion 3 — supervisors can judge a single session quickly:** S03 moved admin completed-session previews onto the same projection-backed evidence line and proved `查看报告` drill-ins to `/practice/{sessionId}/report` with fields such as `overall_result`, `main_issue`, `next_goal`, `evaluable`, and `suggestions` coming from the same source.
- **Criterion 4 — supervisors can see recent change across sessions:** S06 added projection-backed `/progress` and score-bearing `/stats`, repeated blocker / next-goal buckets, not-evaluable counts, and inline degraded states on `/admin/users/{id}`; backend suites, focused web tests, and live browser/API checks all passed.
- **Criterion 5 — managed material updates affect the next training session:** S04 proved admin knowledge diagnostics, frozen `voice_policy_snapshot.knowledge_base_ids`, live `knowledge-check` diagnostics, stable `presentation_id` with incremented `version_number`, active-session replace blocking, and user-entry material version/status visibility. The live success-swap path for an idle ready deck was not re-run at close-out, but it remained covered by passing contract/integration suites.
- **Criterion 6 — PPT practice v1 produces a usable post-session review:** S07 made `/practice/{sessionId}/report` scenario-aware with canonical `presentation_review`, page-aware summaries, degraded reasons such as `missing_page_metadata`, and retry continuity that preserves `presentation_id`; backend suites, live API checks, a real audio-driven page-turn session, and browser assertions passed. S08 rechecked both happy and degraded PPT report paths.
- **Definition of done:** `M001-VALIDATION.md` records a pass verdict, all 8 planned slices delivered their claimed outcomes, and the cross-slice integration audit found no boundary mismatches. The only thinner proof branch was S04’s destructive live success-swap path not being re-run at close-out, and that remained covered by passing automated contract/integration suites plus live blocker/version/user-entry diagnostics.

## Requirement Changes

- R001: active → validated — S01 unified lifecycle end/reconnect handling and live runtime/browser verification proved the desktop sales session can recover without losing the authoritative state surface.
- R002: active → validated — S01 exposed retryable, trace-bearing lifecycle failures on the practice page, and S08 proved support/runtime anomaly classification instead of opaque breakage.
- R003: active → validated — S05 proved sales practice now evaluates value expression, benefit translation, evidence use, and objection handling instead of generic chat quality.
- R004: active → validated — S04 proved admin-managed knowledge/PPT updates reach the next training session with stable versioning and diagnostics.
- R005: active → validated — S02 and S03 turned the single-session report into one readable, evidence-backed authority surface, and S08 rechecked it under degraded optional-enhancement conditions.
- R006: active → validated — S03 proved supervisor previews and report drill-ins read the same completed-session facts as the learner report.
- R007: active → validated — S06 proved supervisors can judge recent improvement, repeated blockers, and focus shifts from projection-backed progress surfaces.
- R008: active → validated — S07 proved the first PPT postmortem is canonical and usable from the shared report route, with S08 rechecking happy and degraded paths.
- R011 remained **active by design**. M001 advanced its evidence substrate materially through S02, S06, S07, and S08, but richer replay/highlight/searchable learning assets still belong to M004.

## Forward Intelligence

### What the next milestone should know
- M001 already sealed the authority line: runtime lifecycle, canonical report, supervisor progress, PPT review, and support/runtime all work best when they read the same persisted session evidence. M002 should layer real-time coaching on top of that line, not fork score/status logic again.

### What's fragile
- Local proof is sensitive to environment drift — missing Alembic head revisions, repo-root verification shims, or mixed `localhost` / `127.0.0.1` hosts can look like product regressions even when the code path is healthy.

### Authoritative diagnostics
- `/api/v1/practice/sessions/{id}/report`, `SessionEvidenceService.build_projection(...)`, `/api/v1/admin/users/{id}/progress`, and `/api/v1/support/runtime/overview` are the fastest way to tell whether a drift is in persisted evidence, a supervisor aggregate, or release-health classification. These surfaces all sit on the same truth line.

### What assumptions changed
- The highest-leverage fix was not “add more product surface.” It was eliminating split authority lines: lifecycle, report, admin preview, trend, PPT review, and runtime health only became trustworthy once they stopped recomputing or hiding the same session in different ways.

## Files Created/Modified

- `backend/src/common/api/practice.py` — unified terminal lifecycle handling and preserved the canonical practice/report authority path.
- `backend/src/common/conversation/session_evidence.py` — established the shared evidence projection used by report, replay, history, trends, and release-health checks.
- `backend/src/common/analytics/history_service.py` — moved supervisor history/progress/statistics onto projection-backed evidence.
- `backend/src/admin/api/users.py` — aligned admin completed-session previews and progress views with the canonical report evidence line.
- `backend/src/agent/capabilities/realtime_scoring.py` — shifted sales scoring semantics toward value articulation, evidence use, and objection handling.
- `backend/src/presentation_coach/api/presentations.py` — delivered the stable PPT replace/version/status contract used by admin and user entry surfaces.
- `backend/src/presentation_coach/services/presentation_report_service.py` — made PPT post-session review scenario-aware and explicit about degraded completeness.
- `backend/src/support/services/runtime_status_service.py` — added typed blocking/warning release-health aggregation from persisted evidence and runtime diagnostics.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — renders the canonical learner/PPT report from the shared evidence contract.
- `web/src/app/admin/users/[id]/page.tsx` — gives supervisors the continuous-change view and canonical report drill-ins.
- `web/src/app/admin/knowledge/[id]/page.tsx` — exposes governed knowledge diagnostics and retry flows for next-session material trust.
- `web/src/app/(dashboard)/support/runtime/page.tsx` — surfaces release-health anomalies without inventing a second truth source.
