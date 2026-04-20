---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M015

## Success Criteria Checklist
- [x] **S01 — 前端业务页面中的 console 输出被统一收口到共享 debug/observability seam。** Evidence: S01 summary reports raw console reduced to `web/src/lib/debug.ts` plus `web/src/instrumentation*.ts`, `console-boundary.test.ts` added as the regression gate, `debug.durableError(...)` adopted by route/error surfaces, and focused proof passed `5 files / 27 tests`.
- [x] **S02 — 业务页面中的原生弹窗和直接浏览器跳转被替换为 toast/dialog/router/auth-handler seam。** Evidence: S02 summary reports destructive admin flows moved to `ConfirmDialog + toast`, auth redirects moved to `authHandler` + router registration, raw `alert/confirm/window.location` grep reduced to documented exceptions only, and focused/expanded proof passed `7/7` plus `14/14`.
- [x] **S03 — learner 核心路由都有 error/loading fallback，且 baseline responsive/a11y/timezone 风险有记录和低风险修复。** Evidence: S03 summary reports shared learner loading state plus `(dashboard)` / `(auth)` / live-practice loaders, added `(auth)/error.tsx` on the shared learner error seam, baseline matrix recorded in `T01-RESEARCH.md`, and focused learner-shell proof passed `41/41` plus `8/8`.
- [x] **Milestone execution status is structurally complete.** Evidence: `gsd_milestone_status(M015)` shows S01, S02, and S03 all `complete` with all 9/9 tasks done.

## Slice Delivery Audit
| Slice | Planned / Claimed Output | Delivered Evidence | Audit |
|---|---|---|---|
| S01 | Shared frontend debug/observability seam; raw console boundary; durable route-error reporting | Summary documents `web/src/lib/debug.ts`, `web/src/lib/console-boundary.test.ts`, migration of learner/admin/dashboard error surfaces to `debug.durableError(...)`, and passing seam/grep verification | PASS |
| S02 | Replace native dialogs and hard navigation with ConfirmDialog/toast/router/auth-handler seams | Summary documents `web/src/lib/auth-handler.ts`, router bridge in `AppProviders`, auth expiry handling in dashboard/admin shells, admin records/rag-profiles/persona flows moved off native dialog/alert patterns, and passing grep/focused tests | PASS |
| S03 | Add learner-shell loading/error fallbacks and lock responsive/a11y/timezone baseline | Summary documents shared learner loading state, new route-group loaders, auth error boundary, baseline proof file `web/src/app/learner-shell-baseline.test.ts`, and passing learner-shell regression suites | PASS |

## Cross-Slice Integration
## Reviewer B — Cross-Slice Integration

| Boundary | Producer Summary | Consumer Summary | Status |
|---|---|---|---|
| **S01 → S02** shared frontend debug / observability seam | **S01** `provides` a single frontend debug/observability seam and explicitly says downstream work should reuse it while replacing native dialogs and `window.location`. | **S02** `requires` S01’s shared frontend debug/observability seam and its verification notes shared `debug/error` logging on mocked failure paths instead of raw console. | **PASS** |
| **S01 → S03** durable learner route-error seam via `debug.durableError(...)` / `LearnerRouteErrorState` | **S01** `provides` durable route-error reporting and explicitly tells S03 to reuse the learner route/error seam. | **S03** `requires` that seam and states `(auth)/error.tsx` was added on the existing `LearnerRouteErrorState` + `debug.durableError(...)` path; focused proof confirms the durable seam still holds. | **PASS** |
| **S02 → S03** router-aware auth redirect seam + interruptive UI cleanup boundary | **S02** `provides` the router-aware auth redirect seam, reusable `ConfirmDialog + toast` pattern, and strict interruptive-UI proof boundary. | **S03** `requires` S02’s frontend hygiene boundary and proceeds on the cleaned learner/auth shell baseline without reopening dialog/navigation regressions. | **PASS** |

**Reviewer B verdict: PASS**

## Requirement Coverage
## Reviewer A — Requirements Coverage

M015 declared no requirements advanced, validated, or invalidated in the slice summaries, so the review focused on requirements materially touched by the milestone’s frontend-shell work.

| Requirement | Status | Evidence |
|---|---|---|
| **R002 — 当关键训练链路失败时，系统必须提供恢复、降级或可诊断路径** | **PARTIAL** | S01 moved route/error surfaces to `debug.durableError(...)`; S02 routed auth-expiry redirects through `authHandler`; S03 added explicit dashboard/auth/practice loading/error fallbacks. This improves frontend failure visibility and recovery paths, but the summaries do not prove the full end-to-end R002 contract across all training subsystems. |
| **R029 — 忘记密码必须能自助完成（后端 token + 前端 forgot/reset 页面）** | **PARTIAL** | S03 confirms login/forgot/reset forms gained labels plus auth loading/error handling, and S02 includes auth/login regression proof. The milestone summaries do not explicitly prove the full self-service reset token lifecycle. |
| **R031 — 登录页必须提供忘记密码入口** | **PARTIAL** | S03 covers auth-route fallback and mentions login/forgot/reset forms; S02 records login-page regression proof. The milestone summaries do not explicitly state the login page still renders the forgot-password entry. |
| **R032 — 侧边栏必须包含历史记录入口** | **PARTIAL** | S03 defines learner-core scope as sidebar learner routes plus auth/practice flows and verifies history/report/replay behavior, but does not explicitly prove the sidebar entry itself in the milestone-close evidence. |

**Reviewer A verdict: NEEDS-ATTENTION**

Validation note: this is a traceability/documentation gap rather than a demonstrated functional regression. The milestone evidence is strong for its planned frontend-hygiene scope, but requirement mapping remains partial in the close-out artifacts.

## Verification Class Compliance
- **Contract:** PASS — slice-close evidence includes the planned repo-root `rg` scans for raw console and interruptive UI usage plus focused Vitest suites for history, practice report/replay, persona admin, login, auth-handler, dashboard/admin shells, learner-shell baseline, and error-reporting seams.
- **Integration:** PASS — verification did not stop at grep; S02 and S03 both cite focused shell and page tests across learner/admin/auth/practice route families, confirming the shared seams behave in integrated route contexts.
- **Operational:** PASS — no deploy/runtime operations were required; S01 and S02 explicitly preserved documented instrumentation / diagnostics exceptions while keeping browser-side diagnostics visible through the shared debug seam and allowlists.
- **UAT:** PASS with documentation-based evidence — reviewer C found matching slice UAT coverage for a delete confirmation flow, an auth-expiry redirect flow, and learner-shell fallback behavior. The evidence is sufficient for validation, though the milestone-level acceptance/context artifact was not present as a separate file.


## Verdict Rationale
M015’s planned slice outcomes are all delivered and cross-slice contracts are honored: all slices are complete, the focused proof surfaces cited in the summaries passed, and the milestone’s contract/integration/operational/UAT classes all have evidence. The only substantive gap is requirements traceability: reviewer A found that the milestone-close artifacts materially touch several existing requirements but do not map them to explicit covered/validated outcomes, so the milestone merits `needs-attention` rather than `pass`.
