---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T01: 定位 learner shell 帮助与导航缺口

盘点 learner shell、首页、profile、history 当前可见导航与帮助入口，确认缺口集中在哪个 shared shell seam，而不是散页缺按钮。

## Inputs

- `web/src/components/layout/sidebar.tsx`
- `web/src/app/(dashboard)/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`

## Expected Output

- `web/src/components/layout/sidebar.tsx`

## Verification

rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)

## Observability Impact

none
