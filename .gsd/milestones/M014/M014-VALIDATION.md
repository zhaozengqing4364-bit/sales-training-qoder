---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M014

## Success Criteria Checklist
## Reviewer C — Assessment & Acceptance Criteria
- [x] 首页不再有“点了没反应”的主按钮/CTA，首屏有最小 onboarding 指引 — `M014-CONTEXT.md` absent, so criterion was sourced from `.gsd/milestones/M014/M014-ROADMAP.md`; `.gsd/milestones/M014/slices/S01/S01-SUMMARY.md` records `verification_result: passed` and states the homepage now ships a truthful three-step onboarding path with only real training/history/report actions, while `.gsd/milestones/M014/slices/S01/S01-UAT.md` covers real CTA routing plus explicit absence of `导出报告` / `设定目标` / `分享分析`.
- [x] 用户可从 profile 走到正式修改密码路径，语速偏好刷新后保留，forgot/reset 体验完整 — `.gsd/milestones/M014/slices/S02/S02-SUMMARY.md` records `verification_result: passed` and documents the real `/forgot-password` handoff from profile, refresh-safe `useVoiceSpeedPreference()` persistence, and formal forgot/reset lifecycle; `.gsd/milestones/M014/slices/S02/S02-UAT.md` covers login→forgot handoff, usable reset token flow, superseded/reused token rejection, and profile voice-speed persistence after refresh.
- [x] 从首页/profile/history 任一页都能找到帮助/反馈入口 — `.gsd/milestones/M014/slices/S03/S03-SUMMARY.md` records `verification_result: passed` and states that dashboard home, profile, and history now all mount the shared `LearnerHelpCard` pointing to the existing `DashboardShell` + `LearnerHelpEntry` seam; `.gsd/milestones/M014/slices/S03/S03-UAT.md` explicitly checks help discoverability on `/`, `/profile`, `/history`, and the mobile drawer.
- [x] 用户在开始录音前能理解本次练习目标，暂停/恢复/结束失败时有清晰指引 — `.gsd/milestones/M014/slices/S04/S04-SUMMARY.md` records `verification_result: passed` and states the practice page now shows a preflight card with `训练目标` / `评价标准` / `角色简介`, plus learner-facing pause/resume/end failure banners with retry guidance; `.gsd/milestones/M014/slices/S04/S04-UAT.md` covers sales/presentation preflight visibility, preflight disappearance after conversation starts, and clear recovery actions for pause/continue/end failures.

Verdict: PASS

## Slice Delivery Audit
| Slice | Delivered contract from summary evidence | Validation status |
|---|---|---|
| S01 | Homepage no longer behaves like a demo: truthful recommendation/history/report CTAs, disabled/absent fake affordances, and minimal onboarding flow. | Pass |
| S02 | Formal password-reset lifecycle, truthful profile→forgot-password handoff, reset-token usability, and refresh-safe voice-speed preference persistence. | Pass |
| S03 | Shared learner help discoverability on dashboard home/profile/history pointing to the existing shell help seam. | Pass |
| S04 | Practice preflight goal preview plus clear pause/resume/end failure guidance on the real `/practice/{sessionId}` learner path. | Pass |

Milestone status evidence: `gsd_milestone_status(M014)` reports S01–S04 all `complete`, with all 12/12 planned tasks done.

## Cross-Slice Integration
## Reviewer B — Cross-Slice Integration
| Boundary | Producer Summary | Consumer Summary | Status |
|---|---|---|---|
| S01 → S02 — truthful learner-home entrypoint available before auth/profile closure | **S01-SUMMARY** says it delivered “a truthful learner-home authority seam for primary CTA routing” and that S02 can “build auth/profile work… on top of a truthful homepage entrypoint.” | **S02-SUMMARY** describes forgot/reset, profile password handoff, and voice-speed persistence, but does **not** explicitly say it consumed or relied on the homepage entrypoint from S01. | Needs attention |
| S01 → S03 — homepage CTA truthfulness feeds help-entry discoverability work | **S01-SUMMARY** says homepage actions now come from real recommendation/history/report authority surfaces and provides “a minimal onboarding story future slices can build on.” | **S03-SUMMARY** explicitly lists `requires: S01` and says it consumed: “Dashboard home already truthfully routes training/history/report CTAs through real learner-loop actions.” | Honored |
| S02 → S03 — truthful profile/auth seam feeds shared help discoverability | **S02-SUMMARY** says it delivered “a truthful learner profile entrypoint into forgot/reset recovery” and kept profile/account surfaces honest. | **S03-SUMMARY** explicitly lists `requires: S02` and says it consumed: “Profile/auth seams already provide truthful password reset handoff and shared learner-shell baseline for profile.” | Honored |
| S01 → S04 — learner entry improvements feed practice main-path closure | **S01-SUMMARY** says homepage closure gives later slices “a stable entrypoint” and keeps the learner loop real rather than demo-only. | **S04-SUMMARY** says “M014 前三块 learner 入口、auth/profile、shared help 的补齐，终于能在真正的 `/practice/{sessionId}` 主链路上形成一致体验,” which confirms reliance on the earlier learner-entry work. | Honored |
| S02 → S04 — auth/profile completion feeds practice preflight/interruption UX | **S02-SUMMARY** says it formalized forgot/reset, truthful profile password routing, and stable voice-speed persistence, and that S04 can assume those seams are stable. | **S04-SUMMARY** explicitly says the practice-chain closure now incorporates “auth/profile” from the earlier slices into the real practice path. | Honored |
| S03 → S04 — shared help shell/discoverability feeds practice-chain consistency | **S03-SUMMARY** says it delivered a reusable `LearnerHelpCard` discoverability layer pointing to the shared `DashboardShell` + `LearnerHelpEntry` seam. | **S04-SUMMARY** explicitly says the practice-chain closure now incorporates earlier “shared help” work into a consistent learner experience. | Honored |

Verdict: NEEDS-ATTENTION

## Requirement Coverage
## Reviewer A — Requirements Coverage
| Requirement | Status | Evidence |
|---|---|---|
| 首页不再存在“点了没反应”的主按钮/弹窗 CTA。 | COVERED | `S01-SUMMARY.md`: 首页 CTA 现由推荐与历史真实数据驱动；`导出报告 / 设定目标 / 分享分析` 保持缺席，最近记录只在可用时提供真实 `/report` 深链，其余回退为明确 disabled 文案。 |
| 首页首屏存在最小 onboarding 指引。 | COVERED | `S01-SUMMARY.md`: 首页已提供最小三步 onboarding（开始训练 → 去历史记录 → 打开最新统一报告）。 |
| 用户能从 profile 里走到正式的修改密码路径。 | COVERED | `S02-SUMMARY.md`: profile 的“修改密码”已改为真实 Next `Link` 到 `/forgot-password`，并带当前邮箱 handoff。 |
| forgot/reset 体验得到正式化补强。 | COVERED | `S02-SUMMARY.md`: 后端 formalize 了 password-reset token lifecycle；forgot-password 页支持邮箱 handoff；reset-password 页同时支持 query token 与手动粘贴 token。 |
| 语速偏好刷新后仍保留，且其存储边界真实可说明。 | COVERED | `S02-SUMMARY.md`: `useVoiceSpeedPreference()` 负责 normalize + `localStorage` persistence，profile 明确标注该偏好是 browser-local，而不是伪装成后端 `PATCH /users/me`。 |
| learner 至少有一个稳定的“遇到问题怎么办”入口。 | COVERED | `S03-SUMMARY.md`: `DashboardShell` + `LearnerHelpEntry` 被确认并保留为唯一帮助入口，同时首页 / profile / history 均新增 `LearnerHelpCard` 指向该共享入口。 |
| 不再需要靠隐性文案解释权限或联系管理员方式。 | COVERED | `S03-SUMMARY.md`: shared help copy 明确说明真实入口位于 sidebar footer / mobile drawer，并直接提示出问题时应报告页面路径或 session id，且说明 runtime/admin surface 为 role-gated。 |
| 用户在开始录音前能理解本次练习在练什么。 | COVERED | `S04-SUMMARY.md`: practice 首次开口前会显示 preflight 卡片，明确训练目标、评价标准与角色简介；sales/presentation 文案分别从 agent/presentation detail API hydrate。 |
| 暂停 / 恢复 / 结束失败时页面有清晰指引。 | COVERED | `S04-SUMMARY.md`: `usePracticeSessionLifecycle` 统一产出 `PracticeLifecycleError`，practice 页复用红色错误 banner 展示动作化文案与 `重试暂停 / 重试继续 / 重试结束 / 重新连接` CTA。 |
| `test-mic` 不会再以普通 learner 功能暴露。 | COVERED | `S04-SUMMARY.md`: `test-mic` 页面被明确标注为“开发工具 · 不属于学员训练主流程”，且 focused proof 锁定该 copy 不会泄漏回 learner path。 |

Verdict: PASS

## Verification Class Compliance
- **Contract:** Slice-close evidence is present across the milestone: S01 frontend Vitest proof for dashboard/home-history authority seams; S02 backend pytest (`test_auth_login_api.py`, `test_password_reset_api.py`) plus focused web Vitest and clean diagnostics; S03 focused dashboard + shell Vitest and clean diagnostics; S04 summary/UAT evidence indicates the practice preflight and lifecycle-error surfaces shipped and verified.
- **Integration:** Roadmap-level learner loop is substantively intact: homepage → auth/profile/help → practice surfaces all show evidence, and reviewer B found 5/6 documented boundaries honored. One integration-evidence gap remains: S02’s summary does not explicitly record consumption of the S01 homepage seam even though the roadmap frames S02 as downstream of the truthful learner entrypoint.
- **Operational:** The reviewed slice artifacts collectively describe working auth recovery, dashboard help discoverability, and practice preflight/interruption recovery on real learner routes. No operational failure evidence surfaced during validation, but the strongest fresh proof remains slice-level summaries/UAT rather than a single milestone-level combined backend+web run transcript.
- **UAT:** Reviewer C mapped all four acceptance criteria to passing summary/UAT evidence, including first-use onboarding, profile→reset flow, help discoverability from three entry pages, and practice preflight plus interruption guidance.


## Verdict Rationale
Reviewer A passed all requirement coverage checks, reviewer C passed all acceptance-criteria checks, and `gsd_milestone_status` confirms all four slices and all twelve planned tasks are complete. The only validation concern is reviewer B’s documented cross-slice evidence gap on boundary S01→S02: the roadmap and S01 summary frame S02 as downstream of the truthful homepage seam, but S02’s summary does not explicitly confirm that consumption. This is a documentation / audit-traceability issue rather than a demonstrated product-delivery failure, so the milestone is marked `needs-attention` rather than `needs-remediation`.
