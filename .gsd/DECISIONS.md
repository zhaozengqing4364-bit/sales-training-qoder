# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | M001 | scope | 首发环境优先级 | 先把桌面端稳定性做满 | 用户明确要求第一版先保证桌面端真实可用，不把移动端 / 企业微信首发绑进 M001 | Yes — 当桌面端闭环已证明并计划扩展使用环境时 |
| D002 | M001 | data | 训练材料事实源 | 公司标准 PPT 与产品资料由后台知识库 / 资产管理维护，不写死在 prompt | 训练内容需要持续更新；业务侧必须能自己上传、更新、替换，并在下一次训练生效 | No |
| D003 | M001 | scope | PPT 第一版教练方式 | 第一版先做完整讲完后的统一复盘，实时打断后置 | 用户把会后统一总结定义为硬门槛，把实时纠偏定义为高价值增强项 | Yes — 当实时纠偏在技术与体验上都被证明成立时 |
| D004 | M001 | pattern | 主管第一版使用方式 | 先提供单次报告 + 连续变化供主管线下辅导，不在系统内做任务派发 | 用户明确接受第一版主管先看报告、线下带教；避免把组织化管理复杂度提前注入主链路 | Yes — 当单次报告和趋势视图已可信后 |
| D005 | M001 | scope | 首发集成边界 | 第一版先独立使用，不新增外部系统集成 | 当前最重要的是证明训练闭环成立；过早接 SSO / CRM / 外部文档系统会放大验收复杂度 | Yes — 当独立系统闭环已稳定且明确需要外部接入时 |
| D006 | M001 | arch | 规划顺序原则 | 先证明训练闭环成立，再建设实时教练、知识真实性、复盘增强与规模化治理 | 现有仓库已有大量骨架，真正短板在闭环可靠性与结果可信度，而不是页面数量 | No |
| D007 | M001/S01 | runtime | 销售训练生命周期权威写入口 | 以 `SessionLifecycleService` + `POST /practice/sessions/{id}/lifecycle` 作为销售训练生命周期唯一权威写入口；保留旧 `DELETE /practice/sessions/{id}` 时必须委托同一结束实现 | 当前结束、副作用与 live sync 在多个入口分叉，必须先收口才能稳定多轮与报告跳转 | Yes — 若未来确有外部兼容需求，可保留多入口但仍需共享同一实现 |
| D008 | M001/S01 | websocket | 销售重连恢复边界 | 销售 StepFun runtime 只恢复最小可继续会话状态（`session_status` / `ai_state` / `turn_count` / 最近活动）并复用 `SessionStateService` + `reconnected` 协议，不序列化上游 StepFun 连接内部状态 | 降低恢复复杂度，同时让 sales 与 presentation 共用同一恢复协议和前端消费面 | Yes — 若后续证明必须恢复更多 runtime 字段，再在同一协议上扩展 |
| D009 | M001/S01/T01 | lifecycle | 会话终态单写入口 | `POST /practice/sessions/{id}/lifecycle` 的 `end` 与旧 `DELETE /practice/sessions/{id}` 统一委托 `backend/src/common/api/practice.py` 内同一终态 helper，再由各入口只决定返回 lifecycle payload 还是 report payload | 终态副作用（sales summary、presentation score flush、report trigger、live handler sync、terminal close）必须共享实现，测试和日志才能收敛到一个排查面 | Yes — 若未来新增兼容入口，也必须继续复用同一 helper |
| D010 | M001/S01/T02 | websocket | Sales StepFun 重连快照边界 | Sales StepFun 只持久化 `session_status` / `ai_state` / `turn_count` 与继续训练所需的最小 runtime 字段（`current_request_id`、最近 stage、最新 scoring/action card），重连时主动清空活跃 response / tool call / grounding 缓冲等不可恢复上游状态 | StepFun 上游连接和流式中间态不可安全序列化；把恢复边界收窄到“可继续训练”而不是“继续同一流”，才能保证断线重连与终态清理稳定可测 | Yes — 若后续证明需要恢复更多字段，必须继续沿用最小可恢复 + 显式清理不可恢复态的模式 |
| D011 | M001/S01/T03 | frontend-lifecycle | 训练页前端生命周期权威面 | 训练页只把服务端 `status` / `reconnected` / `session_ended` 作为 `sessionStatus` / `aiState` / 报告跳转的权威来源；本地只做音频清理，结束失败必须留在训练页暴露重试/重连 | 本地乐观改状态会把 pause/resume/end 漂移伪装成报告页问题；把跳转与状态面绑定到服务端终态，失败才能对用户和后续排障可见 | Yes — 若未来扩展新的服务端 lifecycle 事件，客户端可以消费新合约，但仍不能回到本地猜测终态 |
