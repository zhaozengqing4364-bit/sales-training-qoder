# 题库管理 API 契约

> 状态: ✅ 已实现（2026-05-16 更新）
>
> 后端实现: `backend/src/curriculum_practice/api.py`（`test_bank_router`）
>
> 服务层: `backend/src/curriculum_practice/services/test_bank.py`
>
> 导入服务: `backend/src/curriculum_practice/services/test_bank_importer.py`
>
> Schema: `backend/src/curriculum_practice/schemas.py`

## 概览

- 基础路径: `/api/v1/curriculum/test-bank`
- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
- 权限要求: 管理员（`can_manage_practice_templates`）
- 响应包裹: 统一为 `{ "success": true, "data": ... }`

---

## 关键模型

### `QuestionItem`

```typescript
interface QuestionItem {
  question_id: string;
  category_id: string;
  chapter_key?: string;
  dimension: string;
  prompt: string;
  reference_answer?: string;
  expected_keywords: string[];
  difficulty: "easy" | "medium" | "hard";
  scoring_dimensions: string[];
  status: "draft" | "published" | "archived";
  owner_id: string;
  source: string;
  import_batch_id: string;
  version: number;
  created_at: string;
  updated_at: string;
}
```

### `QuestionCategory`

```typescript
interface QuestionCategory {
  category_id: string;
  name: string;
  parent_category_id?: string;
  description?: string;
  status: "active" | "archived";
}
```

### `AssetRef`（共享引用模型）

```typescript
interface AssetRef {
  asset_type: "learning_content" | "test_bank" | "examiner_agent";
  asset_id: string;
  version: number;
  hash: string;
  snapshot_label: string;
}
```

---

## 已实现接口清单

### 题目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/curriculum/test-bank/questions` | 分页查询题目（支持 category/dimension/status 过滤） |
| `POST` | `/api/v1/curriculum/test-bank/questions` | 创建题目（默认 `draft`） |
| `GET` | `/api/v1/curriculum/test-bank/questions/{question_id}` | 查询题目详情 |
| `PUT` | `/api/v1/curriculum/test-bank/questions/{question_id}` | 更新题目 |
| `POST` | `/api/v1/curriculum/test-bank/questions/{question_id}/publish` | 发布题目 |
| `POST` | `/api/v1/curriculum/test-bank/questions/{question_id}/archive` | 归档题目 |

### 题目分类树

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/curriculum/test-bank/categories` | 查询分类树 |
| `POST` | `/api/v1/curriculum/test-bank/categories` | 创建分类 |
| `PUT` | `/api/v1/curriculum/test-bank/categories/{category_id}` | 更新分类 |
| `DELETE` | `/api/v1/curriculum/test-bank/categories/{category_id}` | 删除分类 |

### 批量导入

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/curriculum/test-bank/imports` | 上传 CSV/JSONL 文件导入（≤10MB，后台任务） |
| `GET` | `/api/v1/curriculum/test-bank/imports/{task_id}` | 查询导入任务状态与行级错误 |

### AI 题目生成

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/curriculum/test-bank/generation/preview` | 从讲座章节生成题目预览 |
| `POST` | `/api/v1/curriculum/test-bank/generation/confirm` | 确认保存生成的题目草稿 |

---

## 导入格式

### CSV（RFC 4180）

```
chapter_key,dimension,prompt,reference_answer,expected_keywords,difficulty
chapter-01,product_knowledge,请描述客户画像识别要点...,识别客户关键特征...,客户|画像|特征,medium
```

### JSONL（支持多行 Markdown）

```jsonl
{"chapter_key": "chapter-02", "dimension": "value_logic", "prompt": "请用价值主张框架回答...", "reference_answer": "价值主张三要素: ...", "expected_keywords": ["价值", "差异", "证据"], "difficulty": "hard"}
```

- 导入上限: 10MB
- 编码要求: UTF-8
- 后台异步处理，返回 `task_id` 供轮询

---

## 发布门禁

`POST /questions/{question_id}/publish` 会校验：

- `reference_answer` 不为空
- `scoring_dimensions` 至少包含 1 个维度
- 无安全标记内容（script 标签、prompt injection 特征）

---

## 种子数据规格

根据 `backend/tests/fixtures/examiner_final_gate.py` 定义：

| 字段 | 值 |
|------|-----|
| `owner_id` | `sales-enablement` |
| `source` | `admin_import` |
| `import_batch_id` | `issue-77-final-gate` |
| 题目数量 | ≥ 20 |
| 考察维度 | `product_knowledge`、`objection_handling`、`value_logic`（≥ 3 个维度） |
| 每题绑定 | 每道题绑定一个 `chapter_key`（从关联学习内容中引用） |

---

## 错误码（当前实现）

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `[QUESTION_NOT_FOUND]` | 404 | 题目不存在 |
| `[CATEGORY_NOT_FOUND]` | 404 | 分类不存在 |
| `[CATEGORY_HAS_QUESTIONS]` | 400 | 分类下有题目，无法删除 |
| `[TEST_BANK_SERVICE_FAILED]` | 500 | 服务层异常 |
| `[IMPORT_TOO_LARGE]` | 413 | 导入文件超过 10MB |
| `[IMPORT_INVALID_FORMAT]` | 400 | 格式不符合 CSV/JSONL 规范 |
| `[ROLE_REQUIRED]` | 403 | 非管理员操作 |

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-05-16 | 契约初始创建 | 对齐 #69/#70/#71 实现，记录 AssetRef 共享模型、导入约束与种子数据规格 |
