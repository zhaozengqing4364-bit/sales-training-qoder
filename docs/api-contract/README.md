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
├── support-runtime.md  # 支持角色运行状态只读 API 契约
├── sessions.md         # 会话管理 API 契约 (增强)
├── replay.md           # 对话回放 API 契约
└── websocket.md        # WebSocket 消息契约
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
2. 按照契约定义创建类型 (`frontend/src/types/api-future.ts`)
3. Mock 数据必须符合契约格式 (使用 snake_case)
4. 后端实现后进行联调

### 后端开发

1. 按照契约实现 API
2. 实现完成后更新状态标记
3. 如有变更，更新契约并通知前端

## 字段命名规范

- **后端 API**: 使用 `snake_case`
- **前端类型**: API 层使用 `snake_case`，内部模型使用 `camelCase`
- **字段映射**: 在 `frontend/src/lib/transforms.ts` 中统一处理

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
