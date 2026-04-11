---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T01: Documented the dashboard-home CTA closure strategy, kept export/share/goal affordances absent, and fixed the version-dialog dismiss action.

Why: 先把 dashboard 首页所有 CTA、版本弹窗与筛选类 affordance 分类清楚，才能避免把 deferred/缺失能力重新伪装成“应该补上”。

Do:
1. 逐项清点首页主按钮、版本弹窗、筛选弹窗和分享/设定目标类 CTA。
2. 按“实现、深链、disabled 文案、删除”四类形成收口策略。
3. 明确 report export、分享分析、设定目标等 affordance 继续保持缺失或诚实禁用。
4. 修正已有版本弹窗等明显的无效交互。

Done when: 首页所有关键 CTA 都有明确 disposition，后续实现不需要再次做策略争论。

## Inputs

- `web/src/app/(dashboard)/page.tsx`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

## Expected Output

- `web/src/app/(dashboard)/page.tsx`
- `.gsd/plans/GSD_PLAN_system-audit-repair.md`

## Verification

rg -n "导出报告|设定目标|分享分析|筛选" web/src/app/\(dashboard\)/page.tsx

## Observability Impact

形成首页 CTA 收口策略表与已知缺失 affordance 边界。
