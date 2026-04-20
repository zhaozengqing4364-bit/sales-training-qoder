---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M012

## Success Criteria Checklist
- [x] **S01 / 首次登录可信度修复** — Slice roadmap promised self-service login recovery, real homepage identity/version, and a clearly unavailable WeCom affordance. S01 summary + UAT substantiate all three: persisted one-time reset tokens, forgot/reset UI flow, old-password rejection after reset, dashboard greeting sourced from real user data, dynamic `package.json` version badge, and disabled "即将支持" WeCom copy. Evidence: backend password-reset pytest gates (6 passed), auth web gate (7 passed), dashboard web gate (14 passed).
- [x] **S02 / learner 导航与首练闭环基础** — Slice roadmap promised a visible history entry, learner-shell help/feedback seam, real learner CTA behavior, and friendly route fallbacks instead of white screens. S02 summary substantiates shared `SidebarContent` history visibility, shared `LearnerHelpEntry`, dashboard CTA contraction to `/history` and `/practice/{sessionId}/report`, and shared `LearnerRouteErrorState` across practice/report/replay. Evidence: focused Vitest gates for sidebar/dashboard-shell/practice layout, dashboard/history CTA routing, and practice error boundary all passed; close-out diagnostics clean.
- [x] **S03 / 个人中心与排行榜体验收敛** — The roadmap promised profile speech-rate persistence, removal of the dead notification toggle, leaderboard scoring explanation, and profile password-change support. The milestone close-out packet marks S03 complete and delivered with no invalidated scope or unresolved dependency mismatch; no roadmap demo promise remains unclaimed at milestone level.
- [x] **Milestone vision closure** — The combined slice outputs remove the major first-run blockers in the vision statement: login recovery is self-service, homepage identity is no longer demo/hardcoded, learner navigation/history is present, first-practice routes have friendly error fallbacks, and downstream profile/leaderboard polish is marked complete. The only notable validation gap is missing explicit milestone-level operational runtime proof (app boot + manual page-load/no-white-screen evidence) in the supplied packet.

## Slice Delivery Audit
| Slice | Planned demo / deliverable | Evidence in close-out packet | Verdict |
|---|---|---|---|
| S01 | 用户可自助登录、重置密码；首页显示真实用户名和动态版本号；企业微信按钮已标注即将支持 | S01 summary and UAT show persisted reset-token backend, forgot/reset pages, one-time token behavior, reset-password login authority, real dashboard greeting/version sourcing, and explicit disabled WeCom affordance. | ✅ Delivered |
| S02 | 侧边栏有历史入口；所有 learner 页面有 error boundary；首页空壳按钮已处理；有反馈入口 | S02 summary shows `SidebarContent` still owns learner nav with `历史记录`, help/feedback entry shared across learner shells, homepage CTA constrained to real routes or explicit disabled states, and shared learner route error presenter used by practice/report/replay. | ✅ Delivered |
| S03 | Profile 语速设置持久化；通知开关移除；排行榜有评分说明；个人中心可修改密码 | Milestone packet marks S03 complete and includes no contradiction, re-scope, or downstream dependency failure against this demo claim. | ✅ Delivered |

**Deferred work inventory / attention items**
- Planned operational verification class asked for "app starts without crash; all pages load without white screen," but the packet primarily contains contract/integration/UAT-style automated evidence rather than explicit runtime boot/page-load proof. This is a validation gap to document, not a delivered-scope failure.

## Cross-Slice Integration
- **S01 → S02 seam alignment:** S01 established the trustworthy auth/dashboard baseline (`useCurrentUser()` identity, dynamic version, real password-reset flow, explicit disabled-state pattern for unavailable auth affordances). S02 explicitly consumed that baseline instead of reintroducing hardcoded copy: learner CTA behavior stayed on real routes, and the shared-shell learner navigation/help seam sits on top of the S01 dashboard/auth foundation. No seam mismatch is reported.
- **S02 → S03 seam alignment:** S02 centralized learner navigation/help/error-fallback seams for learner shells, which is the correct boundary for S03 profile/leaderboard polish to build on. The milestone packet shows no evidence that S03 had to fork or bypass those seams.
- **Boundary consistency:** Across the milestone, user-facing dead ends were consistently converted into either real routed behavior, explicit disabled states, or friendly fallback presenters. No slice summary reports a regression against an upstream seam, no invalidated requirement was recorded, and no follow-up cites a cross-slice contract break.
- **Gap noted:** cross-slice integration evidence is strong at the UI seam/route-contract level, but the packet does not include a full end-to-end runtime walkthrough proving the entire "login → homepage → training → report" loop under a live running app instance.

## Requirement Coverage
- **R029** — Covered and validated by S01. Evidence: backend password-reset pytest gate plus auth web tests proving self-service forgot/reset flow, non-enumeration, rate limiting, one-time token use, and login with the new password.
- **R030** — Covered and validated by S01. Evidence: dashboard web tests proving real current-user display/fallback and dynamic package version in place of hardcoded copy/date.
- **R031** — Covered and validated by S01. Evidence: login web tests proving the login page exposes the forgot-password entry point and the reset flow is reachable/validated.
- **R032** — Covered and validated by S02. Evidence: learner-shell/sidebar/dashboard/practice layout tests proving `历史记录` remains anchored in the shared learner navigation seam.

All active requirements referenced in the milestone packet (R029–R032) are addressed by at least one slice and have fresh close-out validation evidence. No active requirement is left uncovered, and no requirement was invalidated or re-scoped during milestone execution.

## Verification Class Compliance
## Verification Class Compliance

### Contract — ✅ Addressed
- Backend API contract evidence exists via `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` and the broader `backend/tests/ -k password_reset` planner gate.
- Frontend contract evidence exists via focused Vitest suites for login/forgot/reset, dashboard, sidebar/dashboard-shell/practice layout, dashboard/history routing, and practice error boundaries.

### Integration — ✅ Addressed
- S01 packet states frontend auth/dashboard behavior was verified against the real API client contract (`web/src/lib/api/client.ts`) and backend routes via pytest.
- S02 packet verifies shared learner shell, dashboard CTA routing, and route fallback integration across dashboard/practice/report/replay seams.

### Operational — ⚠️ Partially evidenced / gap documented
- Planned class required proof that the app starts without crash and pages load without white screen.
- The milestone packet does show indirect runtime-hardening evidence (guarded optional `edge_tts` import to avoid unrelated backend startup/test collection crashes; learner route error boundaries to prevent white-screen failures on route errors).
- However, it does **not** include explicit milestone-level operational proof such as a fresh app boot, navigation of key pages in a live runtime, or browser-based no-white-screen verification.
- This is the main validation attention item.

### UAT — ✅ Addressed
- S01 includes a detailed UAT document covering login recovery, non-enumeration, token validation, one-time use, new-password login authority, real dashboard identity/version, and disabled WeCom affordance.
- Milestone packet also includes learner-shell/history validation for R032 and route-fallback/user-facing behavior evidence for S02.
- Together these support the milestone’s intended first-run learner experience improvements.


## Verdict Rationale
M012 delivered the planned scope and all referenced requirements (R029–R032) have concrete close-out evidence. S01 and S02 are strongly substantiated by focused backend/frontend gates and UAT, and the milestone packet records S03 as delivered without any contradictory scope drift or unresolved integration issue. The only meaningful gap is verification-class completeness: the roadmap asked for explicit operational runtime proof (app boot + no-white-screen page loads), but the supplied packet is dominated by contract/integration/UAT evidence rather than live operational verification. That gap is important to document but does not currently indicate a shipped-scope failure, so the milestone should be marked needs-attention rather than needs-remediation.
