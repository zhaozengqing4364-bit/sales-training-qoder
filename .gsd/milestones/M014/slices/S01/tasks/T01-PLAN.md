---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 清点首页空壳动作并确定收口策略

逐项清点 dashboard 首页按钮、版本弹窗、筛选弹窗、分享/设定目标类 CTA，按“实现 / 深链 / disabled 文案 / 删除”形成动作收口策略表。优先确认 report export 继续保持缺失。

## Inputs

- `web/src/app/(dashboard)/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- `.gsd/KNOWLEDGE.md`

## Expected Output

- `web/src/app/(dashboard)/page.tsx`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

## Verification

rg -n "导出报告|设定目标|分享分析|筛选" web/src/app/\(dashboard\)/page.tsx

## Observability Impact

none
