---
estimated_steps: 2
estimated_files: 4
skills_used: []
---

# T02: 让 manager/admin 决策面只显示真实 evidence 与真实 stats

- 用 canonical evidence/stats 替换关键管理面上的 fake numbers/dummy cards；没有真实数据的项显式降级，不再硬造‘正在运行中’假象。
- 优先锁主管最常用 surfaces：admin home、user detail、manager-lite、not passed / trend / calibration cards。

## Inputs

- `T01 inventory`
- `M021 canonical kernel`

## Expected Output

- `web/src/app/admin/page.tsx`
- `web/src/components/admin/*`
- `backend/src/common/analytics/*`

## Verification

npm --prefix web test -- --run "src/app/admin/page.test.tsx" "src/components/admin/manager-lite-panel.test.tsx" && backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q
