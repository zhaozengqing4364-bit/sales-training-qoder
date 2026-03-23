---
estimated_steps: 4
estimated_files: 7
skills_used:
  - safe-grow
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - accessibility
  - best-practices
  - code-refactoring
  - test-driven-development
  - verification-before-completion
---

# T02: 把主管列表入口接到同一权威报告页

**Slice:** S03 — 单次报告可读化（学员 + 主管）
**Milestone:** M001

## Description

这个任务负责把“主管真的能用起来”闭环补上。原则是复用同一个 `/practice/{sessionId}/report` 页面，不新建 supervisor-only 报告页，也不在 admin 前端本地重算结果。completed session 的 admin 列表 preview 必须改读 unified evidence summary；两个 admin 入口都要能直接 drill-in 到报告页，让主管不用手拼 URL，也不会先被 legacy 0.4/0.3/0.3 分数误导。

## Steps

1. 在 `backend/src/admin/api/users.py` 改造 `get_user_sessions()`：completed rows 通过 unified evidence projection（沿用 `SessionEvidenceService`）补齐 `scores.overall`、`overall_result`、`evaluable`、`not_evaluable_reason`、`main_issue`、`next_goal`；进行中的 rows 保持 honest，不伪装成已评估结果。
2. 在 `backend/tests/integration/test_admin_users_api.py` 先补 failing integration coverage，锁定 admin user sessions 的分页 / 鉴权不变，同时 completed session 返回 projection-backed preview 字段而不是 legacy-only weighted summary。
3. 更新 `web/src/lib/api/types.ts` 与 `web/src/app/admin/users/[id]/page.tsx`，让 sessions table 显示 unified verdict / preview 信息，并对可读报告的 completed rows 渲染“查看报告” CTA，目标始终是 `/practice/{sessionId}/report`。
4. 更新 `web/src/components/admin/manager-lite-panel.tsx`，在 `not_passed` 卡片增加同一路径的 report CTA；新增 `web/src/app/admin/users/[id]/page.test.tsx` 与 `web/src/components/admin/manager-lite-panel.test.tsx`，覆盖 projection-backed preview 与 CTA wiring。

## Must-Haves

- [ ] `backend/src/admin/api/users.py` 对 completed session 不再把 legacy 0.4/0.3/0.3 加权分当主管事实基线，而是显式返回 unified evidence preview 字段。
- [ ] 主管能从 `admin/users/[id]` 和 manager-lite `not_passed` 卡片直接打开 `/practice/{sessionId}/report`，不需要手拼 URL，也不会落到另一套 supervisor-only 页面。

## Verification

- `cd backend && pytest tests/integration/test_admin_users_api.py`
- `cd web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`

## Observability Impact

- Signals added/changed: admin user sessions JSON 需要显式暴露 `overall_result` / `evaluable` / `main_issue` / `next_goal` 等 preview 字段，方便未来排查 supervisor list 与 report page 是否共享一条事实线。
- How a future agent inspects this: 看 `backend/tests/integration/test_admin_users_api.py`、admin page focused tests，以及浏览器里 `admin/users/[id]` / `admin/analytics` 的 CTA 是否都指向 `/practice/{sessionId}/report`。
- Failure state exposed: 若 admin list 重新回退到 legacy weighted score、CTA target 丢失、或 not-passed 卡片没有 session link，integration / component tests 会直接暴露具体失效面。

## Inputs

- `backend/src/admin/api/users.py` — 当前 admin user sessions 仍用 legacy 0.4/0.3/0.3 公式组装 completed row summary。
- `backend/tests/integration/test_admin_users_api.py` — 现有 admin users integration coverage，可扩展来锁定新的 sessions contract。
- `web/src/lib/api/types.ts` — admin user sessions / manager-lite 的共享前端类型。
- `web/src/app/admin/users/[id]/page.tsx` — 当前 sessions table 只有 legacy score，没有 report CTA。
- `web/src/components/admin/manager-lite-panel.tsx` — `not_passed` 列表已有 `session_id`，但还没有 direct drill-in 到报告页。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — T01 完成后的单次报告权威落点，T02 只能复用它，不能再造新页面。

## Expected Output

- `backend/src/admin/api/users.py` — completed session 的 admin summary 改走 unified evidence preview 字段。
- `backend/tests/integration/test_admin_users_api.py` — integration coverage 锁住 projection-backed admin sessions contract。
- `web/src/lib/api/types.ts` — admin user sessions / manager-lite 类型补齐 unified preview 字段。
- `web/src/app/admin/users/[id]/page.tsx` — sessions table 显示 unified preview，并提供“查看报告” CTA。
- `web/src/app/admin/users/[id]/page.test.tsx` — focused tests 覆盖 admin user detail 的 preview/CTA 行为。
- `web/src/components/admin/manager-lite-panel.tsx` — `not_passed` 卡片新增同一报告页 CTA。
- `web/src/components/admin/manager-lite-panel.test.tsx` — focused tests 覆盖 manager-lite report drill-in。
