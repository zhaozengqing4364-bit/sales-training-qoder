---
estimated_steps: 2
estimated_files: 4
skills_used: []
---

# T01: 识别 manager/admin 的 fake stats 与漂移 summary

- 盘点 admin 首页、manager-lite、analytics/user detail 当前哪些数字或 summary 是 demo/placeholder/漂移口径。
- 定义 truth surface 优先级：哪些必须接真实 evidence/stats，哪些应降级为说明文案或移除。

## Inputs

- `current admin home`
- `manager-lite`
- `analytics surfaces`

## Expected Output

- `web/src/app/admin/page.tsx`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "2543|84|placeholder|demo|mock|dummy|manager-lite|analytics" web/src/app/admin web/src/components/admin backend/src/common/analytics backend/src/admin/api
