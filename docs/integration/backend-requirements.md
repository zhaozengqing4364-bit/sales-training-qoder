# 后端开发需求规范 (Backend API Requirements)

> **文档说明**: 本文档基于前端已完成的功能模块和 Mock 数据结构，定义了后端 API 必须实现的接口规范。前端代码已完全适配以下数据结构和交互逻辑。
> **最后更新**: 2026-01-11

---

## 1. 核心规范 (Core Standards)

*   **API 基础路径**: `/api/v1` (或其他，需与前端 `.env` 配置一致)
*   **响应格式 (Response Envelope)**:
    所有接口必须返回统一的 JSON 结构：
    ```json
    {
      "success": true,
      "data": { ... }, // 具体的业务数据
      "trace_id": "req_123456", // 可选，用于追踪
      "error": "ERROR_CODE", // 仅在 success: false 时出现
      "message": "错误描述" // 仅在 success: false 时出现
    }
    ```
*   **查询参数 (Query Params)**:
    列表接口支持以下通用参数：
    *   `page`: 页码 (默认 1)
    *   `page_size`: 每页数量 (默认 10)
    *   `search`: 模糊搜索关键词
    *   `status`: 状态过滤 (如 "active", "published")
    *   `role`: 角色过滤 (如 "admin", "manager")
    *   `category`: 分类过滤 (如 "sales", "customer")

---

## 2. 接口定义 (API Endpoints)

### 2.1 认证模块 (Authentication)

*   `POST /auth/login`
    *   **Request**: `{ email, password }`
    *   **Response**: `{ token: string, user: { id, name, email, role } }`
    *   **说明**: 返回 JWT Token，前端将存储在 localStorage 中用于后续请求的 `Authorization` 头。

### 2.2 用户端仪表盘 (User Dashboard)

*   `GET /dashboard/stats`
    *   **Response**: `DashboardStats`
    *   **说明**: 返回本周活动统计（总时长、场次、趋势）和上次训练评分。
*   `GET /dashboard/recommendation`
    *   **Response**: `Recommendation`
    *   **说明**: 返回系统推荐的训练内容。
*   `GET /sessions`
    *   **Query**: `limit`
    *   **Response**: `SessionItem[]`
    *   **说明**: 返回用户的训练历史列表。

### 2.3 训练模块 (Training)

*   `GET /agents`
    *   **Query**: `category` ("sales" | "customer")
    *   **Response**: `Agent[]`
    *   **说明**: 获取训练助手列表。**关键字段**: `ui_metadata` (包含 `icon_key`, `theme_color`, `tags`) 必须返回，用于前端渲染。

### 2.4 管理后台 - 用户管理 (Admin: Users)

*   `GET /admin/users`
    *   **Query**: `page`, `page_size`, `search`, `status`, `role`
    *   **Response**: `AdminUser[]`
*   `DELETE /admin/users/{id}`
    *   **Response**: `{ success: true }`

### 2.5 管理后台 - 智能体管理 (Admin: Agents)

*   `GET /admin/agents`
    *   **Query**: `page`, `page_size`, `search`, `status`
    *   **Response**: `AdminAgent[]`
*   `GET /admin/agents/{id}`
    *   **Response**: `AdminAgent` (详情)
*   `PUT /admin/agents/{id}`
    *   **Request**: `Partial<AdminAgent>`
    *   **Response**: `AdminAgent` (更新后的数据)
*   `DELETE /admin/agents/{id}`
    *   **Response**: `{ success: true }`

### 2.6 管理后台 - 角色管理 (Admin: Personas)

*   `GET /admin/personas`
    *   **Query**: `page`, `page_size`, `search`
    *   **Response**: `AdminPersona[]`
*   `GET /admin/personas/{id}`
    *   **Response**: `AdminPersona`
*   `PUT /admin/personas/{id}`
    *   **Request**: `Partial<AdminPersona>`
    *   **Response**: `AdminPersona`
*   `DELETE /admin/personas/{id}`
    *   **Response**: `{ success: true }`

### 2.7 管理后台 - 知识库 (Admin: Knowledge)

*   `GET /admin/knowledge-bases`
    *   **Query**: `page`, `page_size`, `search`
    *   **Response**: `AdminKnowledgeBase[]`
*   `DELETE /admin/knowledge-bases/{id}`
    *   **Response**: `{ success: true }`
*   **TODO**: 需要补充 `POST /admin/knowledge-bases/{id}/upload` 接口用于文件上传。

### 2.8 管理后台 - 训练记录与日志 (Admin: Records & Logs)

*   `GET /admin/training-records`
    *   **Query**: `page`, `page_size`, `search`
    *   **Response**: `SessionItem[]` (复用 SessionItem 结构)
*   `DELETE /admin/training-records/{id}`
    *   **Response**: `{ success: true }`
*   `GET /admin/system-logs`
    *   **Query**: `page`, `page_size`, `search`
    *   **Response**: `SystemLog[]`

---

## 3. 数据类型参考 (Types Reference)

请严格参考前端 `web/src/lib/api/types.ts` 中的 TypeScript 接口定义来设计数据库模型和 DTO。

**关键类型摘要**:

```typescript
// Agent UI Metadata (必须存储或在后端映射)
interface AgentUIMetadata {
    icon_key: string;       // e.g. "User", "Zap", "Headphones"
    theme_color: string;    // e.g. "bg-orange-50 text-orange-600"
    tags?: string[];
}

// Session Item (历史记录)
interface SessionItem {
    id: string;
    scenario_type: "sales_bot" | "presentation";
    title: string;
    start_time: string;     // ISO8601
    duration_seconds: number;
    overall_score: number;
    feedback_summary?: string; // 列表页显示的简短反馈
}
```

---

## 4. 开发建议 (Recommendations)

1.  **优先实现 Auth 和 User**: 这是系统运行的基础。
2.  **Mock 数据迁移**: 可以直接将前端 `web/src/lib/api/mock-data/` 中的 JSON 数据作为初始数据库种子数据 (Seed Data)。
3.  **CORS**: 确保后端配置了正确的 CORS 策略，允许前端域名访问。