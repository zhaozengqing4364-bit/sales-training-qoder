# S03: 单次报告可读化（学员 + 主管） — UAT

**Milestone:** M001
**Written:** 2026-03-23

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: 本 slice 同时涉及 deterministic 后端 contract、前端阅读顺序、主管 drill-in 入口和 degraded-state 表达。仅靠测试不足以证明“首屏可读”，仅靠人工点点看又不足以证明 contract 未漂移，所以需要自动化 + 本地运行时共同证明。

## Preconditions

- 后端与前端本地环境可访问：Backend `http://localhost:3444`，Frontend `http://localhost:3445`
- 先执行数据库迁移：`cd backend && venv/bin/alembic upgrade head`
- 先完成登录，且当前账号具备 admin 权限
- 至少准备两条已结束销售会话：
  - 一条 **可评估但未通过** 的 completed session
  - 一条 **不可评估 / 证据不足** 的 completed session
- 本次 recovery 本地示例数据：
  - evaluable fail session: `1398bea9-c25a-454f-ad1c-f645edcb3350`
  - not-evaluable session: `eda38292-9b64-4a8a-a271-c8f237477e9c`
  - verification user: `s03.verification@example.com`

## Smoke Test

打开 `/practice/1398bea9-c25a-454f-ad1c-f645edcb3350/report`，确认首屏在不滚动深层增强区的情况下就能看到：**沟通闭环结果 / 本场唯一主问题 / 下一轮唯一目标**。

## Test Cases

### 1. 学员报告首屏先给结论、主问题、下一轮目标和证据

1. 打开一个 completed 且 evaluable=true 的销售会话报告页，例如：`/practice/1398bea9-c25a-454f-ad1c-f645edcb3350/report`
2. 观察首屏主阅读路径，不要先依赖高光、知识检测或综合洞察模块。
3. **Expected:** 首屏先出现 `训练评估报告`、`沟通闭环结果`、`本场唯一主问题`、`下一轮唯一目标`。
4. **Expected:** 页面正文直接显示类似 `关键异议回应不够具体。`、`下一轮先把异议处理说完整。` 这类来自 unified evidence 的文案，而不是泛泛英文占位建议。
5. **Expected:** 页面上不存在死的 `导出报告` 按钮。
6. **Expected:** 即使综合洞察不可用，也只显示“综合洞察暂不可用，当前页面仅展示统一训练证据”，核心报告仍成立。

### 2. 证据不足会话必须显式展示不可评估原因

1. 打开一个 completed 但 evaluable=false 的销售会话报告页，例如：`/practice/eda38292-9b64-4a8a-a271-c8f237477e9c/report`
2. 查看首屏顶部和主内容区。
3. **Expected:** 页面出现 `当前会话暂不可评估` 的显式提示。
4. **Expected:** 页面显示不可评估原因文案，例如 `对话轮次不足，暂无法形成稳定评估。`
5. **Expected:** 页面仍保留 `沟通闭环结果`、`本场唯一主问题`、`下一轮唯一目标` 等统一 evidence 字段，但不会把该会话伪装成正常 coaching 成果。
6. **Expected:** 若 evidence completeness 有缺口，页面会显式提示缺口，而不是静默回退成泛泛建议。

### 3. 主管侧 completed session 预览来自 unified evidence，并能指向同一权威报告页

1. 进入 `/admin/users/<userId>`，定位某个 completed 销售会话行；本地 recovery 示例 userId 为 `0a0af6d4-d7cb-4ec8-be9f-f44288b10be2`。
2. 检查列表预览是否直接显示 unified evidence 字段（例如 overall_result、主问题摘要、下一轮目标），而不是只有旧权重分数。
3. 点击 `查看报告`。
4. **Expected:** 跳转目标为 `/practice/{sessionId}/report`，并进入与学员相同的权威报告页，而不是 supervisor-only 新页面。
5. 打开 `/admin/analytics` 的 `未达标名单` 区域。
6. 对同一用户的 completed 未通过会话点击 `查看报告`。
7. **Expected:** drill-in 目标仍是同一个 `/practice/{sessionId}/report`。

## Edge Cases

### 综合洞察/高光缺失，但核心报告仍成立

1. 打开一个 unified evidence 完整、但综合报告或高光接口不可用的 session report。
2. **Expected:** 页面可以显示 `综合洞察暂不可用` 或 `高光片段暂不可用` 的提示，但不会丢失 `overall_result` / `main_issue` / `next_goal` / `suggestions`。

### 本地数据库未迁移到 transcript_metadata 列

1. 在未执行 `cd backend && venv/bin/alembic upgrade head` 的旧本地库上打开 `/admin/users/<id>` 或请求 `/api/v1/admin/users/{id}/sessions`。
2. **Expected:** 这是环境 blocker，不是 S03 业务回退；后端日志会出现 `conversation_messages.transcript_metadata does not exist`，执行迁移后应恢复正常。

## Failure Signals

- 报告页首屏仍先展示增强洞察、知识检查或其它辅助模块，导致结论/主问题/下一轮目标被淹没
- `report.suggestions` 或页面主文案仍出现泛泛占位文本（例如“Review your performance and practice again!”）
- 报告页重新出现 `导出报告` 这类未实现 affordance
- completed admin session 预览回退到 legacy 0.4/0.3/0.3 风格摘要，缺少 `overall_result` / `main_issue` / `next_goal`
- `/admin/users/<id>` 与 `/admin/analytics` 的 `查看报告` 不再指向 `/practice/{sessionId}/report`
- `evaluable=false` 会话被展示成正常 coaching 结果，或者 `not_evaluable_reason` 不可见
- 后端日志出现 `conversation_messages.transcript_metadata does not exist`，说明本地环境没跟上当前 schema

## Not Proven By This UAT

- 不证明 S06 的连续变化聚合是否正确；本 UAT 只验证单次报告和主管 drill-in 的单会话面
- 不证明 comprehensive report / stage results 本身一定可生成；本 slice 只要求增强层缺失时核心 unified evidence 报告仍成立
- 不证明生产环境 SSO / cookie 域名配置；本地 admin SSR 登录态仍可能受环境影响

## Notes for Tester

- 如果 `/admin/users/<id>` 在本地直开时出现“登录已过期”或“用户不存在/加载失败”，先确认不是 auth-cookie host 对齐问题；本 slice 的权威验证面仍然是：
  - `GET /api/v1/admin/users/{id}/sessions`
  - `GET /api/v1/admin/interventions/lists`
  - focused frontend tests for admin detail + manager-lite CTA wiring
- 如果浏览器控制台里看到 enhanced report 404/500（如 `[NO_STAGE_RESULTS]`），先确认核心 unified evidence 报告是否仍然完整；这类增强层失败不应推翻 S03 已交付的核心阅读路径。
