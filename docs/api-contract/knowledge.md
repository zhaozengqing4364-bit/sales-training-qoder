# 知识库管理 API 契约

> 状态: ✅ 已实现（2026-02-10 更新）
>
> 后端实现: `backend/src/common/knowledge/api.py`
>
> 相关 Schema: `backend/src/common/knowledge/schemas.py`

## 概览

- 基础路径: `/api/v1`
- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
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
  file_type: "pdf" | "docx" | "txt" | "md" | "xlsx" | "xls";
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

### `KnowledgeDictionaryEntryResponse`

```typescript
interface KnowledgeDictionaryEntryResponse {
  id: string;
  knowledge_base_id: string;
  canonical_term: string;
  aliases: string[];
  term_type: string;
  status: "draft" | "active" | "archived";
  confidence: number; // 0-100
  source: "manual" | "auto_extract" | string;
  evidence_count: number;
  extraction_metadata?: {
    method?: "llm" | "fallback_rule" | string;
    llm_provider?: string;
    llm_model?: string;
    generation_rationale?: string;
    alias_reasons?: Record<string, string>;
    alias_confidence?: Record<string, number>;
    risk_markers?: string[];
    evidence_snippet?: string;
    chunk_id?: string;
    document_id?: string;
    chunk_index?: string | number;
    is_potential_duplicate?: boolean;
    duplicate_of_canonical_term?: string;
    fallback_reason?: string;
  } | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

interface KnowledgeDictionaryEntryListResponse {
  items: KnowledgeDictionaryEntryResponse[];
  total: number;
}

interface KnowledgeDictionaryGenerateResponse {
  created: number;
  skipped: number;
  items: KnowledgeDictionaryEntryResponse[];
}
```

> 运行时语义：仅 `status = "active"` 且包含 `aliases` 的词条会随绑定知识库注入检索运行时 `transcript_normalization_lexicon`，用于查询归一化和别名扩展；最终回答仍必须由知识库证据命中支撑，词典不会绕过 evidence gate。
>
> LLM 辅助抽取语义：`POST .../dictionary-entries/generate` 优先使用全局 LLM 配置生成草稿；LLM 不可用或输出无法校验时回退规则抽取。所有生成结果仍为 `draft`，人工发布为 `active` 后才参与运行时归一化。`extraction_metadata` 仅用于人工审核来源、证据、别名原因、风险和回退原因。

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

### 知识库词典

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/admin/knowledge/{kb_id}/dictionary-entries` | 查询知识库词典条目，可用 `status` 过滤 |
| `POST` | `/api/v1/admin/knowledge/{kb_id}/dictionary-entries` | 创建词典条目（默认草稿） |
| `PUT` | `/api/v1/admin/knowledge/{kb_id}/dictionary-entries/{entry_id}` | 更新词典条目或发布/归档 |
| `DELETE` | `/api/v1/admin/knowledge/{kb_id}/dictionary-entries/{entry_id}` | 删除词典条目 |
| `POST` | `/api/v1/admin/knowledge/{kb_id}/dictionary-entries/generate` | 从已就绪文档抽取候选词，生成草稿 |

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
- 允许类型: `pdf` / `docx` / `txt` / `md` / `xlsx` / `xls`
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

### 创建并发布知识库词典条目

```http
POST /api/v1/admin/knowledge/{kb_id}/dictionary-entries
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "canonical_term": "石犀科技",
  "aliases": ["实习科技", "石溪科技"],
  "term_type": "organization",
  "status": "draft",
  "confidence": 96,
  "notes": "ASR 易误识别词"
}
```

```json
{
  "success": true,
  "data": {
    "id": "dict-uuid-001",
    "knowledge_base_id": "kb-uuid-001",
    "canonical_term": "石犀科技",
    "aliases": ["实习科技", "石溪科技"],
    "term_type": "organization",
    "status": "draft",
    "confidence": 96,
    "source": "manual",
    "evidence_count": 0,
    "notes": "ASR 易误识别词",
    "created_at": "2026-05-09T13:00:00Z",
    "updated_at": "2026-05-09T13:00:00Z"
  }
}
```

发布词条：

```http
PUT /api/v1/admin/knowledge/{kb_id}/dictionary-entries/{entry_id}
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{ "status": "active" }
```

### 从知识库文档生成词典草稿

```http
POST /api/v1/admin/knowledge/{kb_id}/dictionary-entries/generate?limit=30
Authorization: Bearer <token>
```

```json
{
  "success": true,
  "data": {
    "created": 2,
    "skipped": 4,
    "items": [
      {
        "id": "dict-uuid-002",
        "knowledge_base_id": "kb-uuid-001",
        "canonical_term": "石犀科技",
        "aliases": [],
        "term_type": "auto",
        "status": "draft",
        "confidence": 80,
        "source": "auto_extract",
        "evidence_count": 4,
        "notes": "从知识库已就绪文档中自动抽取，需人工补充误识别别名后发布。",
        "created_at": "2026-05-09T13:01:00Z",
        "updated_at": "2026-05-09T13:01:00Z"
      }
    ]
  }
}
```

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
| `[KNOWLEDGE_DICTIONARY_ENTRY_NOT_FOUND]` | `404` | 词典条目不存在或不属于当前知识库 |
| `[KNOWLEDGE_DICTIONARY_ENTRY_DUPLICATE]` | `409` | 同一知识库下标准词重复 |
| `[KNOWLEDGE_DICTIONARY_ENTRY_INVALID]` | `400` | 词典条目违反数据库约束（非重复类） |
| `[REQUEST_VALIDATION_ERROR]` | `422` | 词典状态、置信度或字段长度不合法 |

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-02-10 | 契约状态改为已实现 | 对齐 `knowledge/api.py` 真实路由 |
| 2026-02-10 | 明确 admin/internal 双检索契约 | 统一 `results + total` 响应结构 |
| 2026-02-10 | 补齐文档重处理接口 | 增加 `reprocess` 约束与响应示例 |
| 2026-02-10 | 清理历史规划引用 | 移除已废弃 roadmap 引用与旧示例 |
| 2026-05-09 | 新增知识库级词典契约 | 支持创建/生成/发布 KB-scoped alias dictionary，并说明 evidence gate 约束 |
