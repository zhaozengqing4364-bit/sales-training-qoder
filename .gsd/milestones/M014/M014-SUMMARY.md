---
id: M014
title: "Learner 入口与体验闭环补齐"
status: complete
completed_at: 2026-04-11T16:58:16.633Z
key_decisions:
  - D175 — Keep dashboard home limited to the real learner loop: recommendation-driven training CTA, history deep links, direct report links only for genuinely completed supported sessions, and otherwise honest disabled/absent affordances.
  - D176 — Keep password reset as one formal lifecycle seam with explicit invalidation and delivery metadata while leaving console email as the default transport seam.
  - D177 — Treat `DashboardShell` + `LearnerHelpEntry` as the single learner help seam and improve discoverability there instead of adding page-local help buttons.
  - D178 — Extend S04 on the existing practice page/right-panel/help seams and keep `/app/test-mic` off the learner route path.
  - D179 — Keep runtime-lock metadata authoritative for IDs/focus intent, but hydrate learner-readable preflight labels from agent/presentation detail APIs.
key_files:
  - web/src/app/(dashboard)/page.tsx
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - web/src/components/dashboard/learner-help-card.tsx
  - web/src/components/layout/dashboard-shell.test.tsx
  - web/src/app/(auth)/forgot-password/page.tsx
  - web/src/app/(auth)/reset-password/page.tsx
  - web/src/hooks/use-voice-speed-preference.ts
  - backend/src/common/services/password_reset.py
  - backend/src/common/rate_limit/api_limiter.py
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
  - web/src/app/test-mic/page.tsx
lessons_learned:
  - For learner-loop repair milestones, the trustworthy close-out bundle is a combined backend auth gate plus an explicit multi-surface web gate; a single page-local suite is not enough to prove the assembled flow.
  - Truthful discoverability often beats new surface area: M014 closed several gaps by reusing homepage/history/profile/practice shell seams instead of inventing second centers for onboarding, help, password change, or preflight.
  - The practice page can absorb meaningful UX upgrades without route sprawl when IDs/focus remain on runtime-lock authority and learner-readable labels are hydrated from existing detail APIs.
---

# M014: Learner 入口与体验闭环补齐

**M014 closed the learner-facing entry gaps across dashboard, auth/profile, shared help discovery, and practice preflight/recovery so the first-use loop is now truthful end to end instead of demo-like or partially hidden.**

## What Happened

M014 finished the learner-facing repair work that sat between the already-validated training/report foundations and a believable first-use experience. S01 turned the dashboard home into a thin learner-loop surface with truthful onboarding, recommendation-driven training CTA routing, history deep links, and report shortcuts only when a completed supported session genuinely exists. S02 formalized the password-reset backend lifecycle, kept profile password changes on the real forgot/reset path, and made voice-speed persistence refresh-safe through the shared browser-local seam instead of pretending there was a backend settings contract. S03 then closed discoverability on top of the existing learner-help shell seam by adding the reusable LearnerHelpCard to home/profile/history rather than inventing duplicate page-local support buttons. Finally, S04 extended the existing practice page with learner-readable preflight context plus structured pause/resume/end recovery guidance, while explicitly keeping `/app/test-mic` outside the learner route path.

Fresh milestone-close verification confirmed that the assembled surfaces still work together. The branch-level diff against the repository’s real integration branch (`001-ai-practice-system`) showed substantial non-`.gsd` code changes. `gsd_milestone_status` confirmed all four slices and all twelve tasks are complete. A fresh backend auth gate passed 20/20 tests across login and password-reset integration coverage, while a fresh web learner-loop gate passed 53/53 tests across login, forgot/reset, dashboard home, profile, history, shared dashboard shell help, voice-speed persistence, and practice preflight/interruption UX. LSP diagnostics were clean on the key dashboard, help, auth, and practice authority files. The result is a coherent learner entry loop: the user can log in or recover access, understand what the homepage wants them to do, find help from the main dashboard pages, enter practice with clear expectations, recover from interruption failures with actionable guidance, and stay on truthful paths instead of dead buttons or debug-only detours.

## Success Criteria Results

## Success criteria verification

- ✅ **首页不再有“点了没反应”的主按钮/CTA，首屏有最小 onboarding 指引**  
  Verified by S01 evidence plus fresh milestone-close web proof. `src/app/(dashboard)/page.test.tsx` and `src/app/(dashboard)/history/page.test.tsx` remain green inside the fresh 53/53 web gate, and S01’s close-out grep confirmed `导出报告` / `设定目标` / `分享分析` were not reintroduced while homepage CTAs stay recommendation/history/report truthful only.
- ✅ **用户可从 profile 走到正式修改密码路径，语速偏好刷新后保留，forgot/reset 体验完整**  
  Verified by S02 evidence plus fresh milestone-close gates: backend auth/password-reset integration proof passed 20/20; the fresh web learner-loop gate included `src/app/(auth)/login/page.test.tsx`, `src/app/(auth)/forgot-password/login-recovery.test.tsx`, `src/app/(auth)/reset-password/login-reset.test.tsx`, `src/app/(dashboard)/profile/page.test.tsx`, and `src/hooks/use-voice-speed-preference.test.ts`, all green.
- ✅ **从首页/profile/history 任一页都能找到帮助/反馈入口**  
  Verified by S03 evidence plus fresh milestone-close web proof. The fresh 53/53 gate reran `src/app/(dashboard)/page.test.tsx`, `src/app/(dashboard)/profile/page.test.tsx`, `src/app/(dashboard)/history/page.test.tsx`, and `src/components/layout/dashboard-shell.test.tsx`, confirming discoverability on the three entry pages and the shared shell seam.
- ✅ **用户在开始录音前能理解本次练习目标，暂停/恢复/结束失败时有清晰指引**  
  Verified by S04 evidence plus fresh milestone-close web proof. The fresh 53/53 gate reran `src/app/(user)/practice/[sessionId]/page.test.tsx` and `src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`, locking the preflight contract and learner-facing interruption recovery copy.

## Horizontal checklist

- No explicit `Horizontal Checklist` section exists in `.gsd/milestones/M014/M014-ROADMAP.md`; no additional checklist items were left unverified beyond the slice-level outcome checks above.

## Definition of Done Results

## Definition of done verification

- ✅ **All slices complete** — `gsd_milestone_status({ milestoneId: "M014" })` returned S01/S02/S03/S04 all `complete`, with task counts 3/3 done in every slice (12/12 tasks complete total).
- ✅ **All slice summaries exist** — `find .gsd/milestones/M014 -maxdepth 3 \( -name '*-SUMMARY.md' -o -name '*-UAT.md' -o -name '*-PLAN.md' -o -name '*-ROADMAP.md' \)` returned `M014-ROADMAP.md` plus `S01`-`S04` PLAN/SUMMARY/UAT files.
- ✅ **Cross-slice integration points still work together** — fresh verification reran the backend auth/password-reset integration gate (20/20) and the cross-surface web learner-loop gate (53/53) spanning auth login/reset, dashboard home/profile/history, shared help shell, voice-speed persistence, and practice preflight/interruption behavior. These tests cover the actual handoff boundaries M014 assembled rather than isolated slice-local code only.
- ✅ **Code changes exist outside planning artifacts** — `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` returned a large non-`.gsd` diff, so the branch clearly contains real implementation work.

## Decision re-evaluation

| Decision | Re-evaluation | Still valid? | Revisit next milestone? |
|---|---|---|---|
| D175 | The shipped homepage stayed a thin learner-loop surface and fresh dashboard tests still prove truthful CTA behavior without fake export/share/goal actions. | Yes | No |
| D176 | Explicit password-reset invalidation and delivery metadata remained the right backend seam; fresh auth integration tests still pass, though a future real email provider can extend this seam without undoing it. | Yes | No |
| D177 | Reusing `DashboardShell` + `LearnerHelpEntry` as the single learner help seam held up; discoverability was solved without duplicate page-local support buttons. | Yes | No |
| D178 | Extending the existing practice page/right-panel/error-banner seams produced the intended preflight and interruption UX while keeping `/app/test-mic` outside learner flow. | Yes | No |
| D179 | Runtime-lock for IDs/focus plus detail APIs for learner-readable preflight labels remains the correct authority split; S04 shipped exactly on that boundary. | Yes | No |

## Requirement Outcomes

## Requirement outcomes

- No requirement status transitions were made during M014.
- The auto-mode context for this close-out reported no requirements advanced, validated, invalidated, or re-scoped in this milestone.
- M014 delivered learner-loop closure evidence on top of already-validated launchability foundations (notably R029-R032 from M012), but it did not create a new requirement transition that needed `gsd_requirement_update`.
- Therefore no requirement records were modified during milestone close-out.

## Deviations

M014 stayed aligned with the roadmap’s learner-loop repair scope, but two slice-level execution facts are worth carrying forward: (1) S03 discovered the learner help entry seam already existed in `DashboardShell`, so the real work became discoverability/proof rather than a new help center; (2) S04 close-out relied on focused practice tests and clean diagnostics because local Next browser smoke remained environment-blocked by a dev-server instrumentation compile hang. Neither deviation invalidated the shipped milestone outcome.

## Follow-ups

- If product later wants cross-device voice-speed sync or an authenticated in-profile change-password flow, introduce a real backend user-settings contract instead of retroactively pretending M014 already shipped one.
- If learner help evolves beyond contextual guidance, extend the shared shell seam rather than adding page-local support affordances.
- If practice interruption telemetry or localhost browser proof becomes operationally important, add dedicated instrumentation/server-readiness work in a future milestone rather than overloading this UX milestone.
