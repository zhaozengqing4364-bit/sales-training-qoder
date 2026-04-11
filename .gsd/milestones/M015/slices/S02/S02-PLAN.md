# S02: 原生弹窗与 window.location 跳转清理

**Goal:** 消除 admin/learner 中断式交互与直接浏览器跳转，统一到 toast/dialog/router/auth-handler seam。
**Demo:** 业务页面中的原生弹窗和直接浏览器跳转被替换为 toast/dialog/router/auth-handler seam。

## Must-Haves

- 业务页面中的 `alert()` / `confirm()` 被替换为共享 dialog/toast 模式。
- `window.location.assign/href` 从业务跳转中移除，只保留明确允许的少数例外。
- focused proof 能锁定删除确认与 auth redirect 仍然真实可用，而不是靠浏览器原生行为兜底。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 在 S01 的 debug seam 之上收口删除确认、auth redirect 与业务跳转模式，供 S03 的 learner route fallback 与壳层行为直接复用。

## Verification

- future agents 可通过统一 router/auth-handler seam、focused UI tests 和剩余 grep gate 快速判断哪些跳转/确认仍是例外。

## Tasks

- [x] **T01: 盘点原生弹窗与直接跳转使用点** `est:25m`
  Why: 先把原生弹窗和直接跳转按场景分类，后续才能统一到正确的 shared seam，而不是机械替换。

Do:
1. 扫描 admin/learner 页面中的 `alert/confirm/window.location` 使用点。
2. 区分删除确认、auth redirect、普通导航三类场景。
3. 确认每类场景应该落到 dialog、toast、router 还是 auth-handler。

Done when: 所有待清理使用点都能映射到一个明确的 shared seam。
  - Files: `web/src/lib/auth-handler.ts`, `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, `web/src/app/admin/personas/[id]/page.tsx`
  - Verify: rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src

- [x] **T02: 收口 confirm/dialog/router/auth-handler 交互模式** `est:1h`
  Why: 真正的收口点在于把删除确认、auth redirect 和业务导航都接到统一模式，而不是只删掉 API 调用字面量。

Do:
1. 删除操作统一走 modal/dialog confirm。
2. auth redirect 统一走 authHandler/router。
3. 普通业务导航改成 router push/replace。
4. 保留 ErrorBoundary reload 等明确允许的例外，不做过度清理。

Done when: 高风险业务页面不再依赖原生弹窗或硬跳转，focused UI proof 通过。
  - Files: `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, `web/src/app/admin/personas/[id]/page.tsx`, `web/src/app/(dashboard)/profile/page.tsx`, `web/src/components/layout/*`, `web/src/lib/auth-handler.ts`
  - Verify: npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"

- [x] **T03: 为非中断式交互模式补 proof** `est:25m`
  Why: 需要一个长期稳定的 proof，防止以后再次引入原生弹窗和硬跳转。

Do:
1. 回归扫描业务代码中的 `alert/confirm/window.location.assign/href`。
2. 补 focused tests，锁定删除确认和 auth redirect 的非中断式行为。
3. 保持测试关注 shared seam 行为，不把实现细节写死。

Done when: grep gate 和 focused tests 同时通过，且剩余例外可被解释。
  - Files: `web/src/**/*.test.tsx`
  - Verify: rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src && npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"

## Files Likely Touched

- web/src/lib/auth-handler.ts
- web/src/app/admin/records/page.tsx
- web/src/app/admin/rag-profiles/page.tsx
- web/src/app/admin/personas/[id]/page.tsx
- web/src/app/(dashboard)/profile/page.tsx
- web/src/components/layout/*
- web/src/**/*.test.tsx
