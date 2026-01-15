# AI Practice Platform - 文档索引

> 本文档是 AI 助手的入口点，帮助 AI 快速定位需要的信息

## 文档分类

### 📐 架构文档 (理解系统)

| 文档 | 用途 | 何时阅读 |
|------|------|----------|
| `architecture.md` | 系统整体架构、技术栈、模块划分 | 需要理解系统全貌时 |
| `api.md` | REST API 和 WebSocket 协议 (含状态标注) | 开发 API 或前后端联调时 |

### 🚀 规划文档 (开发新功能)

| 文档 | 用途 | 何时阅读 |
|------|------|----------|
| `roadmap/sales-coach-upgrade.md` | 销售教练升级技术方案 | 开发销售相关功能时 |
| `roadmap/frontend-pages-spec.md` | 前端页面需求规格 | 开发新页面时 |
| `roadmap/backend-gap-analysis.md` | 后端能力差距分析 | 开发后端新功能时 |

### 📋 API 契约 (前后端协作)

| 文档 | 用途 | 状态 |
|------|------|------|
| `api-contract/README.md` | 契约说明和规范 | - |
| `api-contract/agents.md` | Agent 管理 API | ✅ 已实现 |
| `api-contract/personas.md` | Persona 管理 API | ✅ 已实现 |
| `api-contract/knowledge.md` | 知识库管理 API | ✅ 已实现 |
| `api-contract/websocket.md` | WebSocket 消息协议 | ✅ 已实现 |
| `api-contract/replay.md` | 对话回放 API | ✅ 已实现 |

### 📦 归档文档 (历史参考)

| 文档 | 说明 |
|------|------|
| `archive/agent-platform-design.md` | Agent 平台原始设计，核心已融入 steering |
| `archive/conversation-engine-design.md` | 对话引擎设计，已部分实现 |

---

## AI 工作流程指引

### 开发新功能前

1. 先阅读 `roadmap/` 下对应的规划文档
2. 查看 `api-contract/` 确认 API 设计
3. 确认功能是否在规划中，避免重复设计
4. 遵循规划文档中的数据模型和 API 设计

### 前后端同步开发时

1. 前端参考 `api-contract/` 定义类型
2. Mock 数据使用 snake_case (与后端一致)
3. 类型定义在 `frontend/src/types/api-future.ts`
4. 后端实现后迁移到 `api.ts`

### 修改现有功能时

1. 先阅读 `architecture.md` 了解模块关系
2. 查阅 `api.md` 确认接口规范
3. 遵循 `.kiro/steering/` 中的编码规范

### 不确定时

1. 先问用户确认需求
2. 参考 `roadmap/` 中的规划是否有相关设计
3. 如果是全新需求，建议创建 `.kiro/specs/` 进行规格化开发

---

## 快速链接

### 开发规范
- `.kiro/steering/QUICK-REFERENCE.md` - 快速参考卡 (始终生效)
- `.kiro/steering/backend-principles.md` - 后端开发原则
- `.kiro/steering/frontend-principles.md` - 前端开发原则
- `.kiro/steering/testing-principles.md` - 测试规范

### 代码模板
- `.kiro/templates/backend/api_route.py` - API 路由模板
- `.kiro/templates/backend/capability.py` - 能力模块模板
- `.kiro/templates/frontend/component.tsx` - React 组件模板

### 类型定义
- `frontend/src/types/api.ts` - 现有 API 类型
- `frontend/src/types/api-future.ts` - 未来 API 类型
- `frontend/src/types/models.ts` - 前端模型类型
