# S02: 训练证据落库与报告事实源统一 — UAT

**Milestone:** M001
**Written:** 2026-03-23T09:45:31+08:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 的目标是证明 evidence contract 在写入、投影、聚合和 Web 消费面上的一致性；这已经由完整 backend pytest + web vitest + focused browser diagnostics 证明。该 slice 不要求真人体验质量判断，也不要求依赖实时训练跑一整轮。

## Preconditions

- 使用通过 S02 验证命令的代码版本。
- backend / web 依赖已安装。
- 若要做可选浏览器 spot check，本地 app 可启动且测试账号可通过 `/api/v1/auth/dev-login` 建立会话。
- 若要做浏览器 happy-path 数据核对，本地开发数据库必须已经补齐 `conversation_messages.transcript_metadata` 列；否则只验证 failure-state / diagnostics。

## Smoke Test

运行 slice-level 验证命令并确认全部通过：

1. `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`
2. `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
3. `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py`
4. `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'`

## Test Cases

### 1. Completed session returns one baseline fact set everywhere

1. 准备一个 completed sales session，且包含至少一轮 message evidence。
2. 读取同一 session 的 report、replay，以及该用户 history / trends 对应 summary。
3. 对比 `overall_score`、`evaluable`、`not_evaluable_reason`、`stage_summary`、`main_issue`、`next_goal`。
4. **Expected:** 这些字段来自同一 projection baseline，不因为 report cache、有无 comprehensive report、或 replay message 回退而漂移。

### 2. Thin-evidence completed session stays explicit, not broken

1. 准备一个 zero-turn 或 thin-evidence 的 completed sales session。
2. 读取 report、replay、history summary。
3. **Expected:** 返回显式 `evaluable=false` 与 `not_evaluable_reason=INSUFFICIENT_TURN_DATA`（或等价 contract 枚举），不会变成 500、`[SUMMARY_GENERATION_FAILED]`、或模糊“评分中”。

### 3. History/statistics/trends stop using a separate score formula

1. 准备多条 completed sessions，其中至少包含一条 non-evaluable completed session。
2. 查看 history list、statistics、trends。
3. **Expected:** history list 仍显示该 non-evaluable session，但 statistics / trends 只聚合 evaluable completed sessions；平均分和趋势点不再沿用旧 0.4/0.3/0.3 重算公式。

### 4. Web pages degrade cleanly when optional enhancement data is missing

1. 让 report 的 comprehensive report / highlights 不可用，或让 history analytics snapshot 不可用，但保留 unified evidence contract 可用。
2. 打开 report、replay、history 页面。
3. **Expected:** 页面继续展示 unified evidence baseline，只显示明确的增强层缺失提示；不得因为 enhancement 缺失而改分、改 evaluability、或出现空白页。

## Edge Cases

### Local dev database schema drift

1. 在本地未补齐 `conversation_messages.transcript_metadata` 列的环境打开 `/history`。
2. **Expected:** 页面明确显示统一证据加载失败/重试等诊断 UI，且日志/网络层能看出是后端 schema 漂移，不是前端重新拼装事实导致的静默失败。

## Failure Signals

- 同一 session 在 report / replay / history / trends 上出现不同 `overall_score` 或不同 `evaluable`。
- thin-evidence completed session 重新回到 `[SUMMARY_GENERATION_FAILED]`、500、或模糊“评分中”。
- history list 分数被 statistics / trends / comprehensive report 覆盖。
- replay 页面重新依赖 `/messages` 拼接另一套消息或分数来源。
- report 页面在 comprehensive report 缺失时丢失 baseline evidence。
- 缺少 `practice_session_evidence_projection_built` / `practice_history_projection_query` 等核心诊断面时，难以判断漂移发生在哪一层。

## Requirements Proved By This UAT

- R005 — 证明单次报告已建立统一、可信的事实底座；虽然“可读、可执行”的呈现仍待 S03，但 S02 已证明 report 不再建立在漂移事实上。
- R011 — 证明会话 evidence 已能稳定沉淀并被 replay/history/report/trends 复用为同一可复盘数据资产基线。

## Not Proven By This UAT

- S03 级别的报告可读性、主管判断效率、下次训练建议是否足够可执行。
- M004 级别的 richer replay/highlight/逐轮点评体验。
- 在未迁移本地开发数据库前，浏览器 happy-path 的真实数据一致性复验。

## Notes for Tester

- 若你只需要确认 S02 contract 是否成立，优先相信四条 slice-level 验证命令与 focused tests。
- 若浏览器 `/history` 因本地数据库缺列而报错，这在当前已知问题范围内；重点检查页面是否给出明确 failure-state，而不是空白或混乱分数。
- 后续人工评审应把注意力放在“页面是否继续只信 unified evidence contract”，不要被 optional enhancement 区块是否存在混淆。
