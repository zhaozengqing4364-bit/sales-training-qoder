# 知识库管理 API 契约

> 状态: 📋 计划中
> 
> 参考: `docs/roadmap/backend-gap-analysis.md` - 2.3 知识库管理 API

## 数据模型

### KnowledgeBase 实体

```typescript
interface KnowledgeBase {
  id: string;                              // UUID
  name: string;                            // 名称，最大 100 字符
  description: string;                     // 描述，最大 500 字符
  category: 'product' | 'competitor' | 'faq' | 'policy';
  
  vector_collection: string;               // ChromaDB collection 名称
  embedding_model: string;                 // 嵌入模型
  
  document_count: number;                  // 文档数量
  total_chunks: number;                    // 总分块数
  
  status: 'active' | 'archived';
  created_at: string;
  updated_at: string;
}
```

### KnowledgeDocument 实体

```typescript
interface KnowledgeDocument {
  id: string;                              // UUID
  knowledge_base_id: string;
  
  title: string;                           // 文档标题
  file_type: 'pdf' | 'docx' | 'txt' | 'md';
  file_url: string;                        // 文件存储 URL
  file_size: number;                       // 文件大小 (bytes)
  
  status: 'pending' | 'processing' | 'ready' | 'failed';
  chunk_count: number;                     // 分块数量
  error_message?: string;                  // 处理失败时的错误信息
  
  created_at: string;
}
```

---

## API 端点

### 知识库 CRUD

#### 创建知识库

```http
POST /api/v1/admin/knowledge
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体:**
```json
{
  "name": "产品手册-企业版",
  "description": "包含产品功能、定价、技术规格等信息",
  "category": "product"
}
```

**响应 (201 Created):**
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
    "created_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 获取知识库列表

```http
GET /api/v1/admin/knowledge?page=1&page_size=20&category=product
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "knowledge_bases": [
      {
        "id": "kb-uuid-001",
        "name": "产品手册-企业版",
        "description": "包含产品功能、定价、技术规格",
        "category": "product",
        "document_count": 5,
        "total_chunks": 128,
        "status": "active",
        "updated_at": "2025-01-11T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  },
  "trace_id": "abc123"
}
```

#### 获取知识库详情

```http
GET /api/v1/admin/knowledge/{knowledge_base_id}
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "kb-uuid-001",
    "name": "产品手册-企业版",
    "description": "包含产品功能、定价、技术规格",
    "category": "product",
    "vector_collection": "kb_uuid_001",
    "embedding_model": "text-embedding-ada-002",
    "document_count": 5,
    "total_chunks": 128,
    "status": "active",
    "created_at": "2025-01-11T10:00:00Z",
    "updated_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 更新知识库

```http
PUT /api/v1/admin/knowledge/{knowledge_base_id}
Authorization: Bearer <token>
Content-Type: application/json
```

**请求体:**
```json
{
  "name": "产品手册-企业版 v2",
  "description": "更新后的产品文档"
}
```

#### 删除知识库

```http
DELETE /api/v1/admin/knowledge/{knowledge_base_id}
Authorization: Bearer <token>
```

**注意:** 删除知识库会同时删除所有关联文档和向量数据

---

### 文档管理

#### 上传文档

```http
POST /api/v1/admin/knowledge/{knowledge_base_id}/documents
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**请求:**
- `file`: 文件 (PDF, DOCX, TXT, MD)
- `title`: 文档标题 (可选，默认使用文件名)

**响应 (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "id": "doc-uuid-001",
    "title": "产品功能说明.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "status": "pending",
    "created_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

**注意:** 文档上传后会异步处理，状态变化: `pending` → `processing` → `ready`/`failed`

#### 获取文档列表

```http
GET /api/v1/admin/knowledge/{knowledge_base_id}/documents?page=1&page_size=20
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "documents": [
      {
        "id": "doc-uuid-001",
        "title": "产品功能说明.pdf",
        "file_type": "pdf",
        "file_size": 1024000,
        "status": "ready",
        "chunk_count": 45,
        "created_at": "2025-01-11T10:00:00Z"
      },
      {
        "id": "doc-uuid-002",
        "title": "定价方案.docx",
        "file_type": "docx",
        "file_size": 512000,
        "status": "processing",
        "chunk_count": 0,
        "created_at": "2025-01-11T10:05:00Z"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  },
  "trace_id": "abc123"
}
```

#### 获取文档详情

```http
GET /api/v1/admin/knowledge/{knowledge_base_id}/documents/{document_id}
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "doc-uuid-001",
    "knowledge_base_id": "kb-uuid-001",
    "title": "产品功能说明.pdf",
    "file_type": "pdf",
    "file_url": "https://storage.example.com/docs/xxx.pdf",
    "file_size": 1024000,
    "status": "ready",
    "chunk_count": 45,
    "created_at": "2025-01-11T10:00:00Z"
  },
  "trace_id": "abc123"
}
```

#### 删除文档

```http
DELETE /api/v1/admin/knowledge/{knowledge_base_id}/documents/{document_id}
Authorization: Bearer <token>
```

#### 预览文档内容

```http
GET /api/v1/admin/knowledge/{knowledge_base_id}/documents/{document_id}/preview
Authorization: Bearer <token>
```

**响应:**
```json
{
  "success": true,
  "data": {
    "chunks": [
      {
        "index": 0,
        "content": "产品概述\n\n我们的企业版产品提供...",
        "metadata": {
          "page": 1,
          "section": "概述"
        }
      },
      {
        "index": 1,
        "content": "核心功能\n\n1. 实时语音识别...",
        "metadata": {
          "page": 2,
          "section": "功能"
        }
      }
    ],
    "total_chunks": 45
  },
  "trace_id": "abc123"
}
```

---

### 知识库检索 (内部 API)

#### 检索相关内容

```http
POST /api/v1/internal/knowledge/{knowledge_base_id}/search
Authorization: Bearer <internal-token>
Content-Type: application/json
```

**请求体:**
```json
{
  "query": "产品价格是多少",
  "top_k": 3,
  "similarity_threshold": 0.7
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "content": "标准版: ¥9,999/年\n企业版: ¥29,999/年",
        "score": 0.92,
        "metadata": {
          "document_id": "doc-uuid-001",
          "document_title": "定价方案.docx",
          "chunk_index": 5
        }
      }
    ]
  },
  "trace_id": "abc123"
}
```

---

## 错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `[KNOWLEDGE_BASE_NOT_FOUND]` | 404 | 知识库不存在 |
| `[DOCUMENT_NOT_FOUND]` | 404 | 文档不存在 |
| `[KNOWLEDGE_BASE_IN_USE]` | 400 | 知识库被 Agent/Persona 引用，无法删除 |
| `[UNSUPPORTED_FILE_TYPE]` | 400 | 不支持的文件类型 |
| `[FILE_TOO_LARGE]` | 400 | 文件过大 (最大 50MB) |
| `[DOCUMENT_PROCESSING_FAILED]` | 500 | 文档处理失败 |

---

## 前端类型定义

参考: `frontend/src/types/api-future.ts`

```typescript
// 已定义类型
export interface APIKnowledgeBase { ... }
export interface APIKnowledgeDocument { ... }
export interface APICreateKnowledgeBaseRequest { ... }
export interface APIKnowledgeBaseListResponse { ... }
```
