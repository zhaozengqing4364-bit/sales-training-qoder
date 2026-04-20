---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T01: 定位 learner shell 帮助与导航缺口

Why: 先找到 learner shell 里真正缺的是 shared seam 还是散页按钮，避免后续把帮助入口补成到处乱放的临时卡片。

Do:
1. 盘点 sidebar、dashboard 首页、profile、history 当前可见的导航与帮助入口。
2. 确认支持/反馈信息是否已经存在但不可发现，还是根本缺失。
3. 标出最适合承载统一入口的 shared shell seam。

Done when: 后续实现能围绕一个稳定入口收口，而不是在多个页面临时塞按钮。

## Inputs

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`

## Expected Output

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/*`

## Verification

rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)

## Observability Impact

形成 learner shell 导航/帮助缺口清单。
