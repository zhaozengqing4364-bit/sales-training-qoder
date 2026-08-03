# API 契约文档

> 前后端同步开发的权威参考，确保接口定义一致

## 目录结构

```
docs/api-contract/
├── README.md           # 本文件 - 契约说明
├── agents.md           # Agent 管理 API 契约
├── analytics.md        # 分析与排行榜 API 契约
├── personas.md         # Persona 管理 API 契约
├── knowledge.md        # 知识库管理 API 契约
├── prompt-templates.md # 提示词与场景绑定 API 契约
├── support-runtime.md  # 支持角色运行状态只读 API 契约
├── effectiveness.md    # 销售方法论 / rubric contract
├── sessions.md         # 会话管理 API 契约 (增强)
├── replay.md           # 对话回放 API 契约
├── model-configs.md    # 模型配置 API 契约
├── voice-runtime.md    # 语音运行时策略 API 契约
├── release-verification.md # 发布验收 API 契约
├── learning-content.md     # 学习内容 API 契约
├── test-bank.md            # 题库 API 契约
├── sales-trainer.md        # 销售训练 MVP API 契约
├── newcomer-training-v2.md # 新人基础训练分切片实施 API 合同
├── api-audit-anomaly-report.md  # 全量路由/端点异常清单 (审计基线)
└── websocket.md            # WebSocket 消息契约
```

## 状态标记

| 标记 | 含义 |
|------|------|
| ✅ 已实现 | 后端已实现，可以联调 |
| 🔨 开发中 | 后端正在开发 |
| 📋 计划中 | 设计完成，等待开发 |
| ⚠️ 变更中 | 接口有变更，需要同步 |

## 使用方式

### 前端开发

1. 查看对应模块的契约文件
2. 在 `web/src/lib/api/types.ts` 补充/对齐类型，在 `web/src/lib/api/client.ts`（及 `client-domains.ts`）实现调用与 normalize
3. Mock 数据必须符合契约格式 (使用 snake_case)
4. 后端实现后进行联调；变更时同步 `web/src/lib/api/client-domains.test.ts` 或 contract 测试

### 后端开发

1. 按照契约实现 API
2. 实现完成后更新状态标记
3. 如有变更，更新契约并通知前端

## 字段命名规范

- **后端 API**: 使用 `snake_case`
- **前端 API 类型** (`web/src/lib/api/types.ts`): 与后端一致，使用 `snake_case`
- **响应 normalize**: 在 `web/src/lib/api/client.ts` 与各 domain builder 中统一处理（非独立 `transforms.ts`）

## 响应格式规范

默认 API 使用统一响应格式（历史兼容接口以模块文档为准，如 `analytics.md`）:

```json
// 成功
{
  "success": true,
  "data": {...},
  "trace_id": "abc123"
}

// 失败
{
  "success": false,
  "error": "[ERROR_CODE]",
  "message": "Human readable message",
  "trace_id": "abc123"
}
```

## 认证模型（2026-03-14 收敛）

- 浏览器端 Web 应用默认使用 `HttpOnly` session cookie，并通过服务端边界调用后端接口。
- 脚本、移动端或非浏览器调用仍可使用 `Authorization: Bearer <token>`。
- 契约文档中的 `Authorization` 示例表示“Bearer 示例写法”，不排斥等价的 cookie 会话认证。

## 分页规范

```json
// 请求参数
{
  "page": 1,        // 页码，从 1 开始
  "page_size": 20   // 每页数量，最大 100
}

// 响应格式
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

## 产品说明阅读顺序（M022/S01）

- 面向 learner / manager 的销售方法论说明，统一以 `docs/api-contract/effectiveness.md` 为准。
- 该文档当前描述的是**首轮方法论 / rubric contract**：`discovery / qualification`、`value`、`evidence`、`objection`、`next-step` 五个视角会映射到同一条 canonical evidence。
- 首轮仍是 additive contract：它解释现有 `logic_score / accuracy_score / completeness_score / overall_score`、`main_issue`、`next_goal`，而不是宣布系统已经支持完整的独立方法论评分器。
- 对外话术必须保留边界诚实：当前 `qualification` 仍并入 `opening + discovery`，不能在页面或管理文案里表述成“已经有独立 qualification rubric / stage”。

## 更新日志

| 日期 | 变更 | 影响模块 |
|------|------|----------|
| 2025-01-11 | 初始创建 | 全部 |
| 2026-02-10 | 新增 analytics 契约，补齐排行榜参数归一化与 include_me 能力 | analytics |
| 2026-02-10 | 规范化 agents/personas/knowledge 契约并切换为“已实现”状态 | agents, personas, knowledge |
| 2026-02-11 | 新增 support 运行状态只读契约 | support-runtime |
| 2026-02-11 | 补充 Agent 归档状态会话创建保护说明 | agents |
| 2026-02-11 | 补充 Agent/Persona 增强模式参数配对约束 | agents |
| 2026-02-11 | 新增 sessions 契约并补齐创建会话策略快照、报告/回放快照引用字段 | sessions, replay |
| 2026-02-13 | 补充 model-configs / voice-runtime / release-verification 三类契约文档 | model-configs, voice-runtime, release-verification |
| 2026-02-16 | 收敛角色策略入口并同步弃用写入约束（Persona Centered） | agents, personas, voice-runtime |
| 2026-02-16 | 提示词治理域收敛为 admin-only，补充独立契约文档 | prompt-templates |
| 2026-02-16 | 新增 Persona 策略健康审计接口与 Voice Runtime 旧写入字段移除说明 | personas, voice-runtime |
| 2026-04-14 | 新增销售方法论 / rubric contract，明确 canonical kernel 与 realtime/report/read-side 的首轮映射 | effectiveness |
| 2026-03-14 | 统一契约认证语义为 “Bearer 或 HttpOnly session cookie”，补充训练运行时主语说明 | sessions, replay, agents, personas, analytics, knowledge, support-runtime |
| 2026-05-28 | 新增销售训练 MVP 基础闭环契约，覆盖 learner/admin 做题、录音上传、转写评分、提示词和操作日志接口 | sales-trainer |
| 2026-06-15 | 补充提示词治理台中文化、系统模板只读、默认冲突修复、影响查询和场景绑定唯一性契约 | prompt-templates |
| 2026-07-16 | 冻结新人基础训练 v2 目标命名空间、命令、错误、并发、权限和 ViewModel；明确未实现状态及旧 API 退役点 | newcomer-training-v2 |
| 2026-07-17 | 挂载 EvidenceDossierV1、Readiness 队列、人工决定、补练、申诉、校准、重建、失效与审计导出合同 | newcomer-training-v2 |
