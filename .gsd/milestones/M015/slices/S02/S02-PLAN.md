# S02: 原生弹窗与 window.location 跳转清理

**Goal:** 消除 admin/learner 中断式交互与直接浏览器跳转，统一到 toast/dialog/router/auth-handler seam
**Demo:** After this: 业务页面中的原生弹窗和直接浏览器跳转被替换为 toast/dialog/router/auth-handler seam

## Tasks
- [ ] **T01: 盘点原生弹窗与直接跳转使用点** — 扫描 admin/learner 页面中的 alert/confirm/window.location 使用点，区分删除确认、auth redirect、普通导航三类场景，确认可复用的 toast/dialog/router/auth-handler seam。
  - Estimate: 25m
  - Files: web/src/lib/auth-handler.ts, web/src/app/admin/records/page.tsx, web/src/app/admin/rag-profiles/page.tsx, web/src/app/admin/personas/[id]/page.tsx
  - Verify: rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src
- [ ] **T02: 收口 confirm/dialog/router/auth-handler 交互模式** — 替换删除确认与业务跳转：删除操作统一走 modal confirm，auth redirect 统一走 authHandler/router，业务导航改成 router push/replace。保留 ErrorBoundary reload 例外。
  - Estimate: 1h
  - Files: web/src/app/admin/records/page.tsx, web/src/app/admin/rag-profiles/page.tsx, web/src/app/admin/personas/[id]/page.tsx, web/src/app/(dashboard)/profile/page.tsx, web/src/components/layout/*, web/src/lib/auth-handler.ts
  - Verify: npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"
- [ ] **T03: 为非中断式交互模式补 proof** — 回归扫描业务代码，确保 alert/confirm/window.location.assign/href 从业务页面消失，并用 focused tests 锁定删除确认和 auth redirect 行为。
  - Estimate: 25m
  - Files: web/src/**/*.test.tsx
  - Verify: rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src && npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"
