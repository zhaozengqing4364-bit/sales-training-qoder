---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: 盘点原生弹窗与直接跳转使用点

扫描 admin/learner 页面中的 alert/confirm/window.location 使用点，区分删除确认、auth redirect、普通导航三类场景，确认可复用的 toast/dialog/router/auth-handler seam。

## Inputs

- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/lib/auth-handler.ts`

## Expected Output

- `usage inventory`
- `web/src/lib/auth-handler.ts`

## Verification

rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src

## Observability Impact

current blocking interaction inventory
