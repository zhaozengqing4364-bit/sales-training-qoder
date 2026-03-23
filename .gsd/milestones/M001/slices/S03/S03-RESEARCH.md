# M001/S03 — Research

**Date:** 2026-03-23

## Summary

S03 直接承接 R005 / R006，核心不是再发明一套评分或事实逻辑，而是把 S02 已经收稳的统一 evidence contract 翻译成“学员能立刻知道该怎么练、主管能立刻知道该怎么带”的单次报告。现有代码已经有足够可信的底座：`overall_result`、`main_issue`、`next_goal`、`pass_flags`、`stage_summary`、`evaluable`、`not_evaluable_reason`、bad highlights 都已经可稳定读取；真正缺的是信息排序、文案翻译、以及主管从管理面进入单次报告的入口。

当前最大可见缺口有三类。第一，`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 已经能读统一事实，但页面把 verdict、技术诊断、可选增强层、知识库命中检测、高光、策略快照混在一起，学员/主管打开后第一屏并不能直接回答“这次练得好不好、卡在哪、下次练什么”。第二，`backend/src/common/api/practice.py` 的 `get_session_report()` 仍返回硬编码 `suggestions=["Review your performance and practice again!"]`，这会把报告底部建议区降成占位文案。第三，主管侧现有入口并不顺：`/practice/{sessionId}/report` API 已支持 admin 读取，但 `web/src/app/admin/users/[id]/page.tsx` 和 `web/src/components/admin/manager-lite-panel.tsx` 都没有直接 drill-in 到报告的入口，且 `backend/src/admin/api/users.py` 仍在用 legacy 0.4/0.3/0.3 公式组装 admin session 列表，不能当主管事实基线。

## Recommendation

建议把 S03 明确收敛成“**统一事实之上的 deterministic 报告翻译层 + 主管 drill-in 入口**”。按 `safe-grow` 的最小安全改动原则，不要在 S03 再做一套 supervisor-specific scoring pipeline，也不要让前端本地重算 overall / issue / next goal。核心报告继续只信 S02 的 unified evidence contract；`ComprehensiveReport`、highlights、knowledge check 只做增强层，且必须继续允许缺失。

前端报告页的主结构建议围绕四个问题重排：**结论**（overall_result + overall_score + pass_flags）、**卡点**（main_issue + 最弱阶段）、**证据**（bad highlights / objection-stage highlights / stage facts）、**下一轮动作**（next_goal + retry CTA）。这符合 `baseline-ui` 的“一屏一个清晰主动作”和 `accessibility` / `fixing-accessibility` 的“错误与动作就近呈现”规则，也避免把 technical diagnostics 摆在主要阅读路径上。`react-best-practices` / `vercel-react-best-practices` 在这里的落点是：不要引入新的 client-side 评分派生和多套事实拼接，所有 top-line 判断都只消费后端 projection。

主管侧优先走最小闭环：复用同一个 `/practice/{sessionId}/report` 页面作为主管单次判断面，在 admin 入口补 drill-in，而不是先新建主管专属报告页。优先在 `admin/users/[id]` 的 session table 和 manager-lite 的 `not_passed` 卡片上加“查看报告”；若这些入口需要显示可信 top-line 再决定是否小幅对齐 admin session summary API。除非真被入口阻塞，不建议在 S03 顺手重构整个 admin analytics / progress 聚合面。

## Implementation Landscape

### Key Files

- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前单次报告主页面，约 770+ 行，已读取 unified report evidence、optional comprehensive report、knowledge check、highlights；当前问题是信息层级不对，且 `suggestions` 区仍依赖 generic backend placeholder。
- `web/src/lib/session-evidence.ts` — 统一 evidence 的文案翻译层；当前 `STAGE_LABELS` 缺少 `presentation`，`MISSING_FIELD_LABELS` 缺少 `message_scores` / `stage_evidence`，会把机器字段直接暴露给用户。
- `web/src/components/highlights/HighlightList.tsx`
- `web/src/components/highlights/HighlightCard.tsx`
- `web/src/components/highlights/HighlightDetailModal.tsx` — 已有成熟的“好/坏片段 + AI 反馈 + 建议改法 + 上下文”展示能力，是 S03 做“说虚 / 说错 / 没接住”证据区的现成材料，不需要手搓新控件。
- `backend/src/common/api/practice.py` — `/practice/sessions/{session_id}/report` 读取 `SessionEvidenceService` projection，是单次报告基线 API；同时这里仍硬编码 `suggestions=["Review your performance and practice again!"]`，如果 S03 保留“练习建议”区，最好在这里替换成基于 `main_issue` / `next_goal` 的 deterministic copy。
- `backend/src/common/effectiveness/evaluator.py` — `overall_result`、`main_issue`、`next_goal`、`pass_flags` 的唯一规则来源；S03 不应在前端再复制这套判断逻辑。
- `backend/src/common/conversation/session_evidence.py` — unified projection 的装配点；如果 S03 发现前端真缺“可读结论”字段，优先在这里或 `practice.py` 做只读增强，不要绕开 projection。
- `web/src/lib/api/types.ts` — `PracticeSessionReport`、`SessionEvidenceContract`、`HistorySessionSummary`、`ManagerLiteListsResponse`、`UserSessionItem` 的共享类型定义；若 S03 增加 supervisor drill-in 或 report summary 字段，需要先在这里锁合同。
- `web/src/app/admin/users/[id]/page.tsx` — 主管/管理员查看某学员 sessions 的现有入口；现在只有时间、场景、agent/persona、status、duration、legacy score，没有 report CTA。
- `web/src/components/admin/manager-lite-panel.tsx` — 主管最小干预面板；`not_passed` 行已带 `session_id`，是最小成本加“查看报告”入口的位置。
- `backend/src/admin/api/users.py` — `get_user_sessions()` 仍用 legacy 0.4/0.3/0.3 公式算 `scores.overall`，且不返回 `evaluable` / `main_issue` / `next_goal`；如果主管入口需要可信列表态，这是 S03 里最可能需要追加 contract 对齐的 backend 点。
- `web/src/app/(dashboard)/page.tsx` — 学员首页最近练习卡片仍消费旧 `/practice/history` 轻量 summary，弹窗里的“查看详情”按钮当前是死按钮；这是可选的 learner re-entry seam，但不应先于 report 核心重排。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 现有测试只锁“统一 evidence contract 优先于 enhanced conflict / enhanced 缺失时不崩”；S03 需要在这里补“结论 / 卡点 / 下一轮 / 证据区”的 rendering contract。
- `backend/tests/unit/common/test_api_users.py`
- `backend/tests/integration/test_admin_users_api.py` — 如果触碰 admin user session summary contract，这里是最直接的 backend 验证面。

### Build Order

1. **先确认 S03 只做 evidence translation，不做新评分逻辑。**
   - 明确哪些现有字段分别回答：练得好不好、卡在哪、证据是什么、下一轮练什么。
   - 结论应优先使用：`overall_result` + `overall_score` + `pass_flags`。
   - 卡点应优先使用：`main_issue` + `stage_summary`。
   - 证据应优先使用：`bad highlights`（必要时按 `stage_name` / `sales_stage` 过滤）。
   - 下一轮动作应优先使用：`next_goal` + `retry_entry`。

2. **重排 learner report 主视图。**
   - 在 `report/page.tsx` 先把 above-the-fold 收口成“结论 / 主问题 / 下一轮目标 / 关键证据”。
   - knowledge check、voice policy snapshot、legacy score key、evidence completeness diagnostics 下降为 secondary diagnostics（可折叠或下移）。
   - 如果继续保留 `report.suggestions`，先解决 backend placeholder；否则移除这一块，避免假建议。

3. **补 supervisor drill-in，而不是先重做主管专属报告页。**
   - `admin/users/[id]/page.tsx`：在 session row 加 report action。
   - `manager-lite-panel.tsx`：至少在 `not_passed` 项补 `session_id -> /practice/{sessionId}/report` 跳转。
   - 只有当列表前置判断必须可信时，才去对齐 `backend/src/admin/api/users.py` 的 session summary contract；否则让主管一律以 report page 为事实判断面。

4. **最后再考虑 learner 首页 re-entry。**
   - `web/src/app/(dashboard)/page.tsx` 的“查看详情”现在是死按钮；若时间允许，可直接跳到 report page。
   - 这一步不应阻塞核心 R005/R006 交付。

5. **补测试。**
   - 先补 report page focused tests。
   - 再补 admin user detail / manager-lite component tests（当前前端无现成覆盖）。
   - backend 只在 contract 变化时加 tests，避免为 UI-only slice 扩 blast radius。

### Verification Approach

- **Web focused tests**
  - `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
  - 若触碰主管入口，再加：
    - 新增 `web/src/app/admin/users/[id]/page.test.tsx`
    - 或 `web/src/components/admin/manager-lite-panel.test.tsx`
- **Backend focused tests**（仅当 API contract 变化）
  - `cd backend && pytest tests/unit/common/test_api_users.py tests/integration/test_admin_users_api.py`
  - 若 `practice.py` 的 report payload 改动，补一条针对 `/practice/sessions/{id}/report` 的 contract test
- **Manual / UAT**
  - 学员：打开 `/practice/{sessionId}/report`，第一屏应能直接回答“这次练得好不好 / 卡在哪 / 下次练什么”，且 bad highlights 可支持“说错/说虚”证据复看。
  - 主管：admin 从 `/admin/users/[id]` 或 `/admin/analytics` manager-lite 能直接进入某次会话报告，不需要手拼 URL。
  - 不可评估会话仍必须明确显示 `not_evaluable_reason`，不能被伪装成正常 coaching 文案。

## Constraints

- S03 直接面向 **R005 / R006**，可复用 **R011** 已稳定沉淀的 `main_issue` / `next_goal` / `stage_summary` / highlights，但不应在 S03 偷做 S06 的趋势聚合。
- `ComprehensiveReport` 与 highlights 在当前代码里都是可缺失增强层；S03 必须延续 S02 的 contract：增强内容缺失时，核心报告仍可读、仍可信。
- `backend/src/admin/api/users.py#get_user_sessions()` 仍是 legacy summary，不在 S02 已证明范围内；如果 S03 触碰 supervisor 列表页，要么明确绕过它、只做 report drill-in，要么把它升级到 projection-backed summary，不能继续把旧 0.4/0.3/0.3 当权威。
- 按 `safe-grow`，优先最小直接改动；除非被 contract 阻塞，不要在 S03 顺手重构整块 admin analytics / dashboard。

## Common Pitfalls

- **重新在前端算一套 overall / issue / next goal** — 这会直接破坏 S02 的单一事实线。S03 只能“翻译”，不能“重判”。
- **继续把 `report.suggestions` 当真建议渲染** — `get_session_report()` 现在是硬编码英文占位文案，不处理就会把报告末尾变成假行动建议。
- **把可选增强层当主结论层** — `ComprehensiveReport` 404/失败是现有常态之一，不能让主管/学员报告依赖它才能成立。
- **暴露机器字段而不是用户文案** — `web/src/lib/session-evidence.ts` 目前漏了 `presentation`、`message_scores`、`stage_evidence` 的人类标签，S03 如果继续用 completeness note，必须先补齐翻译。
- **把技术诊断摆在报告主路径前面** — knowledge hit-rate、voice policy snapshot 更像 support diagnostics，不是学员/主管 first question；按 `baseline-ui`，主视图要先给一个清晰 verdict 和一个清晰 next action。
- **保留死按钮** — report header 里的“导出报告”当前无 handler；如果 header 会被改，最好一并清掉假 affordance，避免继续伤害可信度。

## Open Risks

- 目前没有 first-class 的“未接住的异议列表”字段；若 S03 要显示这类文案，只能基于 `main_issue` + objection-stage bad highlights 做 evidence-backed best effort，不能写得像后台已经有精确归因引擎。
- `manager-lite` 只有 `not_passed` 项携带 `session_id`；`inactive_streak` / `improving` 没有单次报告 drill-in 目标。如果主管希望这两类名单也能直跳单次报告，需要额外 backend contract。
- admin 前端当前几乎没有 focused tests；如果 S03 触碰 `admin/users/[id]` 或 `manager-lite-panel` 但不补测试，回归风险会明显高于 learner report 页面。

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js | `react-best-practices`, `vercel-react-best-practices`, `baseline-ui`, `accessibility` | installed |
| FastAPI | `wshobson/agents@fastapi-templates` | available |
| Recharts | `ansanabria/skills@recharts` | available |
