---
id: M012
title: "首登可用性与体验修复"
status: complete
completed_at: 2026-04-09T12:22:03.666Z
key_decisions:
  - Keep account recovery on a real persisted one-time token flow with non-enumerating responses, expiry, invalidation, and rate limiting rather than a fake/manual reset path.
  - Treat user-specific stored passwords as authoritative after reset, while keeping pbkdf2_sha256 as the primary write scheme with bcrypt verify fallback in this environment.
  - Keep unavailable learner/auth affordances visible only when they are explicitly disabled and labeled (for example the coming-soon WeCom button) instead of leaving active-looking dead ends.
  - Keep `SidebarContent` as the learner navigation authority seam and extend learner help/history/profile access through shared shell seams rather than page-local patches.
  - Use one frontend authority seam for voice-speed normalization/persistence and apply the same normalized playback rate to every learner audio playback path.
  - Use shared App Router learner error presenters for practice/report/replay so route failures recover with retry/back affordances instead of white screens.
key_files:
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/src/common/services/password_reset.py
  - backend/src/common/audio/tts_service.py
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260408_1718_026_password_reset_tokens.py
  - backend/tests/integration/test_password_reset_api.py
  - backend/tests/unit/test_tts_import_contract.py
  - web/src/app/(auth)/login/page.tsx
  - web/src/app/(auth)/forgot-password/page.tsx
  - web/src/app/(auth)/reset-password/page.tsx
  - web/src/app/(dashboard)/page.tsx
  - web/src/components/layout/sidebar.tsx
  - web/src/components/layout/dashboard-shell.tsx
  - web/src/components/layout/learner-help-entry.tsx
  - web/src/components/learner/learner-route-error-state.tsx
  - web/src/app/(dashboard)/profile/page.tsx
  - web/src/hooks/use-voice-speed-preference.ts
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-streaming-audio-player.ts
  - web/src/app/(dashboard)/leaderboard/page.tsx
lessons_learned:
  - Milestone close-out in this repo must verify code changes against `origin/001-ai-practice-system`, not `main`, because `main` is not a valid integration reference here.
  - First-run learner trust work should close dead ends by turning them into real routes, explicit disabled states, or shared fallback presenters; hiding or leaving ambiguous actions causes regressions to reappear across shells.
  - Settings that affect multiple learner experiences (like voice speed) need a single normalization/persistence seam threaded into all real consumers, or otherwise page-local fixes silently drift apart.
---

# M012: 首登可用性与体验修复

**M012 closed the first-run learner trust gaps by delivering self-service password recovery, truthful dashboard/profile/leaderboard surfaces, and shared learner navigation/error seams that keep the first practice loop usable instead of dead-ending or white-screening.**

## What Happened

M012 focused on the first-run learner loop: logging in, understanding the homepage, choosing training, surviving the first practice/report path, and wanting to try again. S01 shipped a real forgot/reset-password flow with persisted one-time tokens, non-enumerating responses, rate limiting, post-reset login authority, dynamic dashboard identity/version sourcing, and an explicitly disabled coming-soon WeCom affordance. S02 then stabilized the learner shell by keeping 历史记录 anchored in SidebarContent, adding a shared help/feedback seam across dashboard and practice shells, constraining dashboard CTAs to real history/report routes or explicit disabled states, and giving practice/report/replay routes a shared learner-safe error presenter instead of white screens. S03 finished the learner-facing trust polish by making the sidebar user menu hand off truthfully to /profile, reusing forgot-password rather than inventing a fake password API, centralizing voice-speed persistence in one frontend authority seam that reaches every playback path, and aligning leaderboard copy with the existing evaluable-session scoring contract. Fresh close-out verification re-ran the milestone’s focused backend/frontend gates: backend password-reset pytest passed 6 selected tests, login auth web tests passed 7, combined dashboard suites passed 28, learner shell/history tests passed 8, profile/voice-speed/leaderboard tests passed 16, practice-route error tests passed 2, and diagnostics on the touched backend/frontend authority files were clean. Code-diff verification against this repo’s real integration branch (origin/001-ai-practice-system) showed extensive non-.gsd implementation changes, and the milestone directory contains all three slice summaries plus task close-out artifacts. Cross-slice seams held: S01’s truthful auth/dashboard baseline fed S02’s learner-shell/navigation contracts, and S02’s shared shell/error seams carried cleanly into S03’s profile and leaderboard polish without reintroducing hidden entry points, fake actions, or hardcoded learner-visible copy.

## Success Criteria Results

- [x] **S01 / 首次登录可信度修复** — Fresh backend close-out gate `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` passed **6 selected tests** (1 skipped, 1494 deselected), re-proving persisted reset tokens, non-enumeration, rate limiting, one-time use, and reset-password login authority. Fresh frontend auth gate `npm --prefix web test -- --run login` passed **7 tests**, re-proving the forgot-password entry point plus forgot/reset UI behavior. Fresh dashboard gate `npm --prefix web test -- --run dashboard` passed **28 tests**, including homepage real-user identity fallback, dynamic version badge, and the learner dashboard shell surfaces.
- [x] **S02 / learner 导航与首练闭环基础** — Fresh learner-shell gate `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx" "src/app/(user)/practice/layout.test.tsx"` passed **8 tests**, confirming `历史记录` remains anchored in the shared learner sidebar and the shared help/feedback seam appears across dashboard/practice shells. Fresh route-fallback gate `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/error.test.tsx"` passed **2 tests**, confirming retry/back behavior and learner-safe error fallback on the live practice route.
- [x] **S03 / 个人中心与排行榜体验收敛** — Fresh learner-profile/audio/leaderboard gate `npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts" "src/hooks/use-streaming-audio-player.test.ts" "src/app/(dashboard)/leaderboard/page.test.tsx"` passed **16 tests**, confirming truthful /profile routing and password handoff, persisted/normalized voice-speed behavior across playback paths, and leaderboard evaluable-session explanation copy.
- [x] **Milestone vision closure** — Taken together, S01-S03 retire the milestone vision’s core first-run blockers: login recovery is self-service, the homepage no longer shows hardcoded demo identity/version/date, learner navigation/history is visible, learner routes fail with friendly recovery instead of white screens, profile settings are reachable and truthful, and leaderboard/profile copy no longer sends mixed signals. Fresh diagnostics on `backend/src/common/auth/api.py`, `backend/src/common/services/password_reset.py`, `backend/src/common/audio/tts_service.py`, `web/src/app/(auth)/*`, `web/src/app/(dashboard)/page.tsx`, `web/src/components/layout/sidebar.tsx`, `web/src/components/layout/dashboard-shell.tsx`, `web/src/app/(user)/practice/layout.tsx`, `web/src/app/(dashboard)/profile/page.tsx`, `web/src/hooks/use-voice-speed-preference.ts`, and `web/src/app/(dashboard)/leaderboard/page.tsx` all returned **No diagnostics**.

## Definition of Done Results

- [x] **All planned slices complete** — S01, S02, and S03 are all marked complete in the milestone packet and have completed slice summaries/UAT artifacts under `.gsd/milestones/M012/slices/`.
- [x] **All slice summaries exist** — `find .gsd/milestones/M012/slices -maxdepth 4 -type f | sort` confirmed `S01-SUMMARY.md`, `S02-SUMMARY.md`, `S03-SUMMARY.md`, plus task-level summary artifacts for every planned task.
- [x] **Real code, not planning-only output** — `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` returned extensive non-`.gsd/` implementation changes across backend auth/services/tests and web auth/dashboard/layout/profile/leaderboard/audio files.
- [x] **Cross-slice integration works** — S01’s truthful auth/dashboard baseline is consumed by S02’s learner-shell/navigation contracts, and S02’s shared learner shell/error seams support S03’s profile and leaderboard polish without seam mismatch. Fresh combined gates stayed green across auth, dashboard, learner shell/history, practice route fallback, profile, voice-speed, and leaderboard surfaces.
- [x] **Requirement-backed milestone outcomes are evidenced** — R029-R032 each have milestone-close verification evidence tied to fresh backend/web gates and clean diagnostics, with no invalidated or re-scoped milestone requirements.

## Requirement Outcomes

- **R029 → validated** — Supported by fresh milestone-close backend proof `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/ -k password_reset -x -q` (**6 selected tests passed**) covering token creation, local recovery visibility, non-enumeration, rate limiting, one-time use, and reset-password login authority.
- **R030 → validated** — Supported by fresh milestone-close dashboard proof `npm --prefix web test -- --run dashboard` (**28 tests passed**), including assertions that the dashboard renders real current-user identity fallback and the dynamic `package.json` version instead of hardcoded placeholders.
- **R031 → validated** — Supported by fresh milestone-close auth proof `npm --prefix web test -- --run login` (**7 tests passed**), confirming the login page exposes the forgot-password route and the forgot/reset flow behaves correctly end-to-end on the frontend.
- **R032 → validated** — Supported by fresh milestone-close learner-shell proof `npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx" "src/app/(user)/practice/layout.test.tsx"` (**8 tests passed**), confirming `历史记录` remains anchored in the shared learner navigation seam across dashboard and practice shells.

## Deviations

No roadmap-level scope deviation was required. The milestone closed within the planned S01-S03 scope; the only notable validation attention item was that prior milestone validation lacked explicit live app-boot/page-load operational proof, which remains a follow-up for future close-out rigor rather than a delivered-scope miss.

## Follow-ups

- Add a small milestone-level live runtime smoke/UAT proof bundle for future close-outs (app boot + key learner pages load without white screen) so validation does not have to rely almost entirely on contract/integration gates.
- Keep future auth/profile work on truthful routes: replace the disabled WeCom affordance only when the real end-to-end auth path exists, and only add an in-profile authenticated password API if it becomes a genuine supported product contract.
- If learner help/feedback becomes a real support workflow, extend the shared `LearnerHelpEntry` seam instead of scattering new entry points across dashboard/practice pages.
