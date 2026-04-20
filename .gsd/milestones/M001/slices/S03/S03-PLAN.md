# S03: 单次报告可读化（学员 + 主管）

**Goal:** 把 S02 已统一的训练事实基线翻译成学员和主管都能直接采取行动的单次报告，并让主管从 admin 入口稳定 drill-in 到同一权威报告页。
**Demo:** 对任一已结束训练会话，`/practice/{sessionId}/report` 首屏先回答“这次练得怎么样 / 卡在哪 / 下一轮练什么 / 证据是什么”，建议文案来自统一 evidence 字段而不是占位文本；主管从 `admin/users/[id]` 和 manager-lite `not_passed` 名单都能直接打开同一报告页，且 completed session 的 admin 列表预览使用 unified evidence summary 而不是 legacy 0.4/0.3/0.3 加权分。
**Requirements:** Owns `R005`, `R006`; supports `R011`.

## Must-Haves

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 的首屏必须围绕统一 evidence contract 重排为“结论 → 主问题 → 下一轮唯一目标 → 关键证据”，而不是继续把知识库诊断、策略快照、增强洞察混在主阅读路径前面。
- `backend/src/common/api/practice.py` 返回的 `report.suggestions` 必须改成基于 `overall_result` / `main_issue` / `next_goal` / evaluability 的 deterministic 建议，不再出现 `Review your performance and practice again!` 这类占位文案。
- 不可评估或证据不完整的会话必须继续显式展示 `not_evaluable_reason` / completeness 语义，不能伪装成正常 coaching 结果；增强层（ComprehensiveReport / highlights / knowledge check）缺失时仍要保持核心报告成立。
- `backend/src/admin/api/users.py`、`web/src/app/admin/users/[id]/page.tsx`、`web/src/components/admin/manager-lite-panel.tsx` 必须把主管入口接到同一 `/practice/{sessionId}/report` 页面，并让 completed session 的列表预览读取 unified evidence summary 字段而不是 legacy-only 加权分。

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd backend && pytest tests/contract/test_practice_evidence_contract.py tests/integration/test_admin_users_api.py`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`
- Manual review — 本地打开 `/practice/<sessionId>/report`、`/admin/users/<id>`、`/admin/analytics`，确认首屏先给出结论/卡点/下一轮/证据，且主管无需手拼 URL 就能进入同一报告页。
- Failure-path inspection — 使用一个 `evaluable=false` 或 evidence incomplete 的已结束会话打开 `/practice/<sessionId>/report`，并检查页面文案与调试/网络面，确认 `suggestions`、`overall_result`、`evaluable`、`main_issue`、`next_goal` 仍显式暴露，且 not-evaluable / completeness 降级原因可见而不是静默回退成占位内容。

## Observability / Diagnostics

- Runtime signals: 继续依赖 `[Report] Loaded unified evidence contract`、`[Report] Highlights unavailable; keeping unified evidence` 等前端调试日志，并让 report payload / admin user sessions payload 显式暴露 `suggestions`、`overall_result`、`evaluable`、`main_issue`、`next_goal`。
- Inspection surfaces: `backend/src/common/api/practice.py` 的 report JSON、`backend/src/admin/api/users.py` 的 sessions JSON、`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 与 admin focused tests。
- Failure visibility: 未来 agent 能快速判断失败发生在 deterministic 建议生成、report 首屏排序、admin session summary contract，还是 supervisor CTA wiring。
- Redaction constraints: 诊断只暴露 session-level 枚举、score、stage、CTA target 等非敏感字段；不得把 transcript/audio 原文、用户邮箱或密钥写进日志。

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/conversation/session_evidence.py`, `backend/src/common/api/practice.py`, `backend/src/admin/api/users.py`, `web/src/lib/session-evidence.ts`, `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/admin/users/[id]/page.tsx`, `web/src/components/admin/manager-lite-panel.tsx`.
- New wiring introduced in this slice: report API 生成 deterministic 建议并继续复用 unified evidence top-line；admin users / manager-lite 入口统一 deep-link 到 `/practice/{sessionId}/report`，completed session 列表 summary 改走 projection-backed 字段。
- What remains before the milestone is truly usable end-to-end: S06 仍需把这些单次判断维度聚合成连续变化视图；单次报告本身完成后，本 slice 范围内无额外 blocker。

## Tasks

- [x] **T01: 重排单次报告首屏并替换占位建议文案** `est:3h`
  - Why: R005 的核心不是再加一堆增强洞察，而是让学员打开报告第一屏就能知道结果、主问题、下一轮动作和证据；当前 backend suggestion 仍是占位文本，页面层级也把主结论淹没了。
  - Files: `backend/src/common/api/practice.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `web/src/lib/api/types.ts`, `web/src/lib/session-evidence.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Do: 在 `practice.py` 中用 unified projection 的 `overall_result` / `main_issue` / `next_goal` / evaluability 生成 deterministic suggestions；补齐 `session-evidence.ts` 中 `presentation`、`message_scores`、`stage_evidence` 等用户标签；重排 report 首屏为“结论 → 主问题 → 下一轮唯一目标 → 关键证据”，保留 highlights / knowledge check / comprehensive report 作为下沉增强层，移除死的“导出报告”假 affordance，并继续禁止 client-side 重算 score/result。
  - Verify: `cd backend && pytest tests/contract/test_practice_evidence_contract.py && cd ../web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
  - Done when: report 首屏不再出现 generic 英文建议或死按钮，能明确展示结论/主问题/下一轮/关键证据，且 not-evaluable / enhanced-missing 两类降级都被 focused tests 锁住。
- [x] **T02: 把主管列表入口接到同一权威报告页** `est:3h`
  - Why: R006 不只要求报告内容可读，还要求主管真的能从管理入口进入这份权威报告；当前 admin user sessions 仍是 legacy 权重 summary，manager-lite 也缺少稳定 drill-in CTA。
  - Files: `backend/src/admin/api/users.py`, `backend/tests/integration/test_admin_users_api.py`, `web/src/lib/api/types.ts`, `web/src/app/admin/users/[id]/page.tsx`, `web/src/app/admin/users/[id]/page.test.tsx`, `web/src/components/admin/manager-lite-panel.tsx`, `web/src/components/admin/manager-lite-panel.test.tsx`
  - Do: 让 `get_user_sessions()` 对 completed rows 读取 unified evidence summary，返回 `scores.overall`、`overall_result`、`evaluable`、`not_evaluable_reason`、`main_issue`、`next_goal` 这类 supervisor preview 字段，而不是继续以 legacy 0.4/0.3/0.3 为权威；更新 admin user detail page 和 manager-lite `not_passed` 卡片，统一 deep-link 到 `/practice/{sessionId}/report`，并在前端只展示 projection-backed preview/CTA，不本地发明另一套判断。
  - Verify: `cd backend && pytest tests/integration/test_admin_users_api.py && cd ../web && npm test -- --run 'src/app/admin/users/[id]/page.test.tsx' 'src/components/admin/manager-lite-panel.test.tsx'`
  - Done when: 主管能从两个 admin 入口直接打开同一报告页，completed session 列表 preview 不再依赖 legacy-only summary，且 backend/frontend tests 能证明 contract 与 CTA wiring 都成立。

## Files Likely Touched

- `backend/src/common/api/practice.py`
- `backend/src/admin/api/users.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_admin_users_api.py`
- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/components/admin/manager-lite-panel.tsx`
- `web/src/components/admin/manager-lite-panel.test.tsx`
