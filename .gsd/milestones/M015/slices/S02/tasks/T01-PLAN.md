---
estimated_steps: 6
estimated_files: 4
skills_used: []
---

# T01: 盘点原生弹窗与直接跳转使用点

Why: 先把原生弹窗和直接跳转按场景分类，后续才能统一到正确的 shared seam，而不是机械替换。

Do:
1. 扫描 admin/learner 页面中的 `alert/confirm/window.location` 使用点。
2. 区分删除确认、auth redirect、普通导航三类场景。
3. 确认每类场景应该落到 dialog、toast、router 还是 auth-handler。

Done when: 所有待清理使用点都能映射到一个明确的 shared seam。

## Inputs

- `web/src/lib/auth-handler.ts`
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`

## Expected Output

- `web/src/lib/auth-handler.ts`
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`

## Verification

rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src

## Observability Impact

形成原生弹窗/直接跳转使用点分类表。
