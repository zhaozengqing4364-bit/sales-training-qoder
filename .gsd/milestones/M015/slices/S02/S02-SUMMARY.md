---
id: S02
parent: M015
milestone: M015
provides:
  - A router-aware auth redirect seam that downstream learner-shell work can reuse without reintroducing browser-level hard redirects.
  - A reusable ConfirmDialog + toast interaction pattern for destructive admin flows.
  - A strict proof boundary (grep allowlist + focused tests) that future slices can reuse to detect regressions in native dialogs or hard navigation.
requires:
  - slice: S01
    provides: Shared frontend debug/observability seam so failure-path proof in auth/persona/records tests stays on one logging boundary instead of raw console.
affects:
  - M015/S03
key_files:
  - web/src/lib/auth-handler.ts
  - web/src/components/providers/app-providers.tsx
  - web/src/components/layout/dashboard-shell.tsx
  - web/src/components/layout/admin-shell.tsx
  - web/src/app/admin/records/page.tsx
  - web/src/app/admin/rag-profiles/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/lib/auth-handler.test.ts
  - web/src/app/admin/records/page.test.tsx
  - web/src/app/admin/rag-profiles/page.test.tsx
  - web/src/app/admin/personas/[id]/page.test.tsx
key_decisions:
  - D183 — keep the native-dialog/hard-navigation inventory in `web/src/lib/auth-handler.ts` as `interruptiveUiInventory`, using tokenized primitive labels and explicit allowed-exception entries so the grep gate stays trustworthy.
  - D184 — register Next router navigation in `AppProviders` through `authHandler.setNavigator`, route auth expiry through `authHandler.sessionExpired`, keep non-auth role fallback on local `router.replace`, and standardize destructive admin actions on `ConfirmDialog` plus toast.
patterns_established:
  - Auth-triggered redirects should flow through `authHandler.setNavigator()` + `sessionExpired()/logout()` instead of raw `window.location.assign` or `window.location.href`.
  - Destructive admin actions should use `ConfirmDialog` for consent and toast for success/failure feedback instead of browser-native `confirm()` / `alert()`.
  - The `interruptiveUiInventory` + allowlist grep gate is the authority seam for future native-dialog/hard-navigation cleanup; keep inventory primitive labels tokenized so the grep rule does not match the documentation itself.
observability_surfaces:
  - `web/src/lib/auth-handler.ts` `interruptiveUiInventory` now classifies cleaned-up vs allowed-exception interruptive UI surfaces.
  - `web/src/lib/auth-handler.test.ts` and the allowlist grep check provide a durable diagnostic boundary for future regressions.
  - Focused shell tests (`dashboard-shell.test.tsx`, `admin-shell.test.tsx`) prove auth-expiry and role-fallback routing stays on the shared seam.
drill_down_paths:
  - .gsd/milestones/M015/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M015/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M015/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T18:19:15.547Z
blocker_discovered: false
---

# S02: 原生弹窗与 window.location 跳转清理

**将高风险 admin/learner 中断式交互与 auth/business 跳转统一收口到 ConfirmDialog、toast、router 和 authHandler seam，并用 focused tests + grep allowlist 锁住非中断式行为。**

## What Happened

S02 先把 repo 内仍然存在的原生 alert/confirm 和直接 browser navigation 盘点为一份共享的 `interruptiveUiInventory`，避免后续任务靠 grep 结果猜测哪些命中是真问题、哪些是允许例外。随后在 `web/src/lib/auth-handler.ts` 中引入 router-aware navigator seam，通过 `AppProviders` 注册 Next router，让 auth 过期与 logout 重定向不再依赖 `window.location.assign`，而是统一走 `authHandler.sessionExpired()` / `setNavigator()`；`dashboard-shell` 与 `admin-shell` 也同步改用 auth seam 与本地 `router.replace()` 来处理认证失败和非 auth 的角色回退。业务侧则把高风险中断式交互改到共享 UI seam：`/admin/records` 删除动作改为 `ConfirmDialog + toast`，`/admin/rag-profiles` 删除动作改为 `ConfirmDialog` 且迁移入口改成 `router.push(...)`，`/admin/personas/[id]` 的必填校验、保存失败和 TTS 预览失败反馈都改为 toast，而不是浏览器原生 alert。最后通过 focused regression proof 把关键行为锁定：删除操作必须先经过共享确认框、auth 过期可以在 router bridge 延迟注册后仍然从 shared seam 完成跳转、persona 保存失败必须留在当前编辑页并给出 toast 反馈。当前 repo 内对 `alert/confirm/window.location.assign/href` 的 grep 命中已收缩到三处文档化例外：`web/src/components/ErrorBoundary.tsx` 与 `web/src/lib/performance.ts` 仅做 URL 诊断采样，`web/src/app/admin/error.tsx` 保留明确允许的 home fallback reload 行为。

## Verification

Fresh slice-close verification passed on four fronts. 1) `rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src` now returns only documented exceptions in `web/src/components/ErrorBoundary.tsx`, `web/src/lib/performance.ts`, and `web/src/app/admin/error.tsx`. 2) A stricter allowlist script passed and confirmed no undisclosed native dialog or hard-navigation usages remain in `web/src`. 3) The plan command `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"` passed 7/7, preserving persona toast/auth-login proof. 4) Expanded seam regressions `npm --prefix web test -- --run src/app/admin/records/page.test.tsx src/lib/auth-handler.test.ts src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/rag-profiles/page.test.tsx` passed 14/14, proving delete-confirmation, router handoff, admin/dashboard auth routing, and delayed auth navigator registration. Fresh LSP diagnostics were clean on `web/src/lib/auth-handler.ts`, `web/src/components/providers/app-providers.tsx`, `web/src/components/layout/dashboard-shell.tsx`, `web/src/components/layout/admin-shell.tsx`, `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, and `web/src/app/admin/personas/*/page.tsx`. The only stderr emitted during tests was expected debug/error logging on mocked failure paths while asserting toast fallbacks.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None. The close-out kept the task-level scope: inventory → shared seam migration → durable proof. The only extra verification was a stricter allowlist check and expanded seam regression suite so the slice could prove the remaining grep hits are true exceptions instead of unfinished cleanup.

## Known Limitations

The repo still intentionally references `window.location.href` in `web/src/components/ErrorBoundary.tsx` and `web/src/lib/performance.ts` for diagnostics, and in `web/src/app/admin/error.tsx` for an explicit fallback reload action. These are documented allowlisted exceptions, not business-navigation regressions.

## Follow-ups

S03 can now reuse the router-aware `authHandler` seam, ConfirmDialog + toast pattern, and the strict interruptive-UI grep/test boundary while finishing learner shell error/loading coverage and baseline responsive/a11y/timezone cleanup.

## Files Created/Modified

- `web/src/lib/auth-handler.ts` — Centralized interruptive UI inventory and moved auth/logout redirects onto a router-aware navigator seam.
- `web/src/components/providers/app-providers.tsx` — Registered the Next router bridge so authHandler can navigate without browser hard redirects.
- `web/src/components/layout/dashboard-shell.tsx` — Delegated learner-shell auth expiry handling to authHandler instead of direct browser navigation.
- `web/src/components/layout/admin-shell.tsx` — Delegated admin auth expiry to authHandler and kept non-auth role fallback on local router.replace.
- `web/src/app/admin/records/page.tsx` — Replaced native delete confirmation and failure alert flows with ConfirmDialog plus toast.
- `web/src/app/admin/rag-profiles/page.tsx` — Moved the migration CTA to router.push and replaced deletion confirmation with ConfirmDialog.
- `web/src/app/admin/personas/[id]/page.tsx` — Replaced blocking validation/save/TTS feedback alerts with toast-based feedback and router navigation.
