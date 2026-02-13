# 知识库管理 API 契约

> 状态: ✅ 已实现（2026-02-10 更新）
>
> 后端实现: `backend/src/common/knowledge/api.py`
>
> 相关 Schema: `backend/src/common/knowledge/schemas.py`

## 概览

- 基础路径: `/api/v1`
- 认证方式: `Authorization: Bearer <token>`
- 响应包裹: 统一为 `{ "success": true, "data": ... }`
- 路由分组:
  - 管理前缀: `/api/v1/admin/knowledge`
  - 内部检索前缀: `/api/v1/internal/knowledge`

> 说明：当前知识库接口在实现层使用 `get_current_user` 做鉴权（需要登录态），并未额外区分管理员角色。

---

## 关键模型

### `KnowledgeBaseResponse`

```typescript
interface KnowledgeBaseResponse {
  id: string;
  name: string;
  description?: string;
  category: "product" | "competitor" | "faq" | "policy";
  vector_collection: string;
  embedding_model: string;
  document_count: number;
  total_chunks: number;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
}
```

### `KnowledgeDocumentResponse`

```typescript
interface KnowledgeDocumentResponse {
  id: string;
  knowledge_base_id: string;
  title: string;
  file_type: "pdf" | "docx" | "txt" | "md";
  file_url: string;
  file_size: number;
  status: "pending" | "processing" | "ready" | "failed";
  chunk_count: number;
  error_message?: string;
  created_at: string;
}
```

### `KnowledgeSearchResponse`

```typescript
interface KnowledgeSearchResponse {
  results: Array<{
    content: string;
    score: number;
    metadata: {
      document_id: string;
      document_title: string;
      chunk_index: number;
    };
  }>;
  total: number; // 2026-02-10 规范口径：明确返回总条数
}
```

---

## 已实现接口清单

### 知识库 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/admin/knowledge` | 创建知识库 |
| `GET` | `/api/v1/admin/knowledge` | 分页查询知识库 |
| `GET` | `/api/v1/admin/knowledge/{kb_id}` | 查询知识库详情 |
| `PUT` | `/api/v1/admin/knowledge/{kb_id}` | 更新知识库 |
| `DELETE` | `/api/v1/admin/knowledge/{kb_id}` | 删除知识库 |

### 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/admin/knowledge/{kb_id}/documents` | 上传文档（`202 Accepted`，异步处理） |
| `GET` | `/api/v1/admin/knowledge/{kb_id}/documents` | 分页查询文档 |
| `GET` | `/api/v1/admin/knowledge/{kb_id}/documents/{doc_id}` | 查询文档详情 |
| `DELETE` | `/api/v1/admin/knowledge/{kb_id}/documents/{doc_id}` | 删除文档 |
| `GET` | `/api/v1/admin/knowledge/{kb_id}/documents/{doc_id}/preview` | 分页预览分块 |
| `POST` | `/api/v1/admin/knowledge/{kb_id}/documents/{doc_id}/reprocess` | 重新处理文档（`202 Accepted`） |

### 知识检索

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/admin/knowledge/{kb_id}/search` | 管理端检索 |
| `POST` | `/api/v1/internal/knowledge/{kb_id}/search` | 内部检索（同响应契约） |

---

## 典型请求与响应

### 创建知识库

```http
POST /api/v1/admin/knowledge
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "name": "产品手册-企业版",
  "description": "包含产品功能、定价、技术规格",
  "category": "product"
}
```

```json
{
  "success": true,
  "data": {
    "id": "kb-uuid-001",
    "name": "产品手册-企业版",
    "category": "product",
    "vector_collection": "kb_uuid_001",
    "document_count": 0,
    "status": "active",
    "created_at": "2026-02-10T10:00:00Z"
  }
}
```

### 上传文档

```http
POST /api/v1/admin/knowledge/{kb_id}/documents
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

表单字段:
- `file`（必填）
- `title`（可选，默认文件名）

上传限制:
- 允许类型: `pdf` / `docx` / `txt` / `md`
- 单文件大小: 最大 `50MB`
- 非法文件内容会返回 `400`

```json
{
  "success": true,
  "data": {
    "id": "doc-uuid-001",
    "title": "产品功能说明.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "status": "pending",
    "created_at": "2026-02-10T10:05:00Z"
  }
}
```

### 预览文档分块

```http
GET /api/v1/admin/knowledge/{kb_id}/documents/{doc_id}/preview?page=1&page_size=10
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "chunks": [
      {
        "index": 0,
        "content": "产品概述...",
        "metadata": {
          "page": 1,
          "section": "概述"
        }
      }
    ],
    "total_chunks": 45
  }
}
```

### 管理端检索

```http
POST /api/v1/admin/knowledge/{kb_id}/search
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "query": "产品价格是多少",
  "top_k": 5,
  "similarity_threshold": 0.7
}
```

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "content": "标准版: ¥9,999/年；企业版: ¥29,999/年",
        "score": 0.92,
        "metadata": {
          "document_id": "doc-uuid-001",
          "document_title": "定价方案.docx",
          "chunk_index": 5
        }
      }
    ],
    "total": 1
  }
}
```

### 内部检索

```http
POST /api/v1/internal/knowledge/{kb_id}/search
Authorization: Bearer <token>
Content-Type: application/json
```

> 请求体与响应体与管理端检索一致，同样返回 `results + total`。

### 重新处理文档

```http
POST /api/v1/admin/knowledge/{kb_id}/documents/{doc_id}/reprocess
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "message": "Document reprocessing started",
    "document_id": "doc-uuid-001"
  }
}
```

---

## 错误码（当前实现）

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `[KNOWLEDGE_BASE_NOT_FOUND]` | `404` | 知识库不存在 |
| `[DOCUMENT_NOT_FOUND]` | `404` | 文档不存在 |
| `[KNOWLEDGE_BASE_IN_USE]` | `400` | 知识库被 Agent / Persona 引用，禁止删除 |
| `[UNSUPPORTED_FILE_TYPE]` | `400` | 不支持的文件类型 |
| `[FILE_TOO_LARGE]` | `400` | 文件超过 50MB |
| `[EMPTY_FILE]` | `400` | 空文件 |
| `[INVALID_FILE]` / `[INVALID_FILE_CONTENT]` | `400` | 文件名或文件内容不合法 |
| `[FILE_SAVE_FAILED]` | `500` | 文件落盘失败 |
| `[INVALID_STATUS]` | `400` | 文档状态不允许重处理 |

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-02-10 | 契约状态改为已实现 | 对齐 `knowledge/api.py` 真实路由 |
| 2026-02-10 | 明确 admin/internal 双检索契约 | 统一 `results + total` 响应结构 |
| 2026-02-10 | 补齐文档重处理接口 | 增加 `reprocess` 约束与响应示例 |
| 2026-02-10 | 清理历史规划引用 | 移除已废弃 roadmap 引用与旧示例 |
