---
id: M010
title: "报告证据链收口"
status: complete
completed_at: 2026-03-30T08:24:22.298Z
key_decisions:
  - D125: Keep provenance scoped to the canonical conclusion family (main_issue, next_goal, claim_truth) instead of expanding M010 into per-suggestion provenance.
  - D126/D132/D134/D135: Build conclusion provenance once on SessionEvidenceService.build_projection() and mirror it into knowledge-check diagnostics rather than introducing a second truth source.
  - D127/D133/D136: Make additive `evidence_degradation` the authoritative four-layer degradation contract and keep `evidence_completeness.degraded_reasons` as a compatibility mirror.
  - D128/D139/D140: Keep `web/src/lib/session-evidence.ts` as the only frontend authority seam; report trusts report payload truth and replay trusts replay payload truth.
  - D131: Preserve the original slice order — backend authority seam first, degradation contract second, learner rendering last — to avoid frontend-first drift.
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/db/schemas.py
  - backend/tests/contract/test_conclusion_evidence_parity.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
lessons_learned:
  - For cross-route trust-chain work, build the new field once on the projection authority seam and mirror it outward; route-local rebuilds drift quickly.
  - Replay parity depends on declared response schemas as much as service payload wiring; undeclared fields can look like logic regressions even when the backend service already emits them.
  - Learner-facing evidence vocabulary must stay helper-owned on the frontend; once report and replay start parsing raw fragments locally, stale truth and wording drift return immediately.
  - Milestone-close proof for completed-session evidence work needs three gates, not one: backend route-family parity, compatibility readers, and learner report/replay rendering.
---

# M010: 报告证据链收口

**Projection-backed conclusion provenance and four-layer evidence degradation now stay consistent across report, replay, and knowledge-check, and learners can see that truth directly on the report and replay surfaces instead of relying on page-local heuristics.**

## What Happened

M010 closed the remaining trust gap in completed-session reporting by extending the existing projection authority seam rather than inventing a second proof path. S01 added `conclusion_evidence` to `SessionEvidenceService.build_projection()` so report and replay share one provenance bundle for `main_issue`, `next_goal`, and `claim_truth`, then mirrored that same bundle into knowledge-check through `build_session_runtime_diagnostics()`. Dedicated parity contracts proved the three route families agree on the same conclusion-level provenance for happy-path, degraded, and presentation sessions.

S02 turned that shared seam into an explicit degradation contract. `SessionEvidenceService` now builds one authoritative four-layer `evidence_degradation` payload (`retrieval`, `transcript`, `audio`, `enhanced_report`) for completed sales sessions, replay declares the field in its schema so serialization cannot silently drop it, and admin/history compatibility readers keep receiving mirrored canonical degraded tokens through `evidence_completeness.degraded_reasons`. This kept one route-family truth while preserving older read models.

S03 finished the learner-facing half of the milestone. Report and replay both render provenance and degradation through shared `web/src/lib/session-evidence.ts` helpers, replay explicitly trusts `replayData.conclusion_evidence` and `replayData.evidence_degradation` instead of any stale report snapshot, and paired page tests now lock both vocabulary parity and the page-specific authority boundary. The result is that completed sales sessions no longer just look credible: they expose why key conclusions are believed and which evidence layers are degraded on the same shipped report/replay/knowledge-check route family that users already consume.

Fresh milestone-close verification reran the backend parity gate (47 passed), compatibility gate (7 passed), and learner report/replay gate (33 passed). Code-change verification against `origin/001-ai-practice-system` also confirmed the milestone contains real non-`.gsd` implementation files, including the backend projection/route/schema seams and the learner report/replay/helper files touched by M010.

## Success Criteria Results

- **Cross-route conclusion provenance parity delivered:** Met. Fresh verification `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q` passed **47/47**. This proves report, replay, and knowledge-check all return identical `conclusion_evidence` for the canonical conclusion family.
- **Unified layered degradation taxonomy delivered:** Met. The same fresh backend gate passed **47/47**, covering happy-path, retrieval-missing, audio-missing, enhanced-report-failed, and presentation-null scenarios for the four-layer `evidence_degradation` payload.
- **Learner-facing report/replay rendering delivered through one frontend authority seam:** Met. Fresh verification `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` passed **33/33**. Report and replay both render helper-owned provenance/degradation copy, and replay does not regress into stale report-snapshot truth.
- **Compatibility consumers preserved:** Met. Fresh verification `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q` passed **7/7**, proving mirrored canonical degraded tokens still satisfy admin/history readers.
- **Milestone vision met:** Met. The shipped surface now explains why `main_issue`, `next_goal`, and `claim_truth` are believed and shows which evidence layers are degraded across report, replay, and knowledge-check, then renders that same truth on learner report/replay pages without page-local derivation drift.

## Definition of Done Results

- **All planned slices complete:** Met. The roadmap slice table shows S01, S02, and S03 complete, and `find .gsd/milestones/M010 -maxdepth 4 \( -type d -o -type f \) | sort` confirmed all three slice summary/UAT/plan paths exist under `.gsd/milestones/M010/slices/`.
- **All slice summaries exist:** Met. `S01-SUMMARY.md`, `S02-SUMMARY.md`, and `S03-SUMMARY.md` are present, along with their task summaries and UAT artifacts.
- **Cross-slice integration works correctly:** Met. S01 established the projection-owned `conclusion_evidence` seam, S02 extended the same seam with authoritative `evidence_degradation` plus compatibility mirroring, and S03 consumed both through shared `session-evidence.ts` helpers. Fresh backend, compatibility, and web verification all passed (47 + 7 + 33).
- **Real code landed outside planning artifacts:** Met. `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` reported non-`.gsd` code changes, and the touched-file check confirmed milestone implementation landed in backend projection/route/schema/test files and learner report/replay/helper files.
- **Horizontal checklist:** None present in the current M010 roadmap render, so there were no additional horizontal checklist items to retire.

## Requirement Outcomes

- **R027:** active → validated. Evidence: S01 built one projection-backed `conclusion_evidence` bundle and proved report/replay/knowledge-check parity with dedicated contract tests; S03 completed the learner-facing delivery so report and replay now render the canonical provenance through shared helpers. Fresh milestone-close verification passed **47 backend parity/unit tests** and **33 learner report/replay tests**.
- **R028:** active → validated. Evidence: S02 introduced authoritative four-layer `evidence_degradation` on the projection authority seam, replay schema alignment, and compatibility mirroring for admin/history readers; S03 rendered the same taxonomy on learner report/replay pages. Fresh milestone-close verification passed **47 backend parity/unit tests**, **7 admin/history compatibility tests**, and **33 learner report/replay tests**.

## Deviations

None in milestone scope. The only standing caveat is the pre-existing unrelated repo-wide frontend typecheck baseline outside the files touched by M010, already documented during S02/S03 and excluded from milestone acceptance.

## Follow-ups

No milestone-blocking follow-up was discovered. The main adjacent debt is still the unrelated repo-wide frontend `tsc` baseline outside M010-touched files; future milestones touching broader web seams should treat that as ambient debt, not as a regression in the M010 evidence contract.
