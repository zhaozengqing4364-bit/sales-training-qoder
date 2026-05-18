# 学习内容 API 契约

> 状态: ✅ 已实现（2026-05-16 更新）
>
> 后端实现: `backend/src/curriculum_practice/api.py`（`learning_content_router`）
>
> 服务层: `backend/src/curriculum_practice/services/learning_contents.py`
>
> Schema: `backend/src/curriculum_practice/schemas.py`

## 概览

- 基础路径: `/api/v1/curriculum/learning-contents`
- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
- 权限要求: 管理员（`can_manage_practice_templates`）
- 响应包裹: 统一为 `{ "success": true, "data": ... }`

---

## 关键模型

### `LearningContent`

```typescript
interface LearningContent {
  content_id: string;
  title: string;
  description?: string;
  owner_id: string;
  source: string;
  import_batch_id: string;
  status: "draft" | "published" | "archived";
  version: number;
  chapters: LearningChapter[];
  published_at?: string;
  created_at: string;
  updated_at: string;
}
```

### `LearningChapter`

```typescript
interface LearningChapter {
  chapter_id: string;
  content_id: string;
  chapter_key: string;
  title: string;
  body_markdown: string;
  order_index: number;
  estimated_minutes?: number;
}
```

---

## 已实现接口清单

### 管理端

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/curriculum/learning-contents` | 分页查询学习内容列表 |
| `POST` | `/api/v1/curriculum/learning-contents` | 创建学习内容（默认 `draft`） |
| `GET` | `/api/v1/curriculum/learning-contents/{content_id}` | 查询学习内容详情 |
| `PUT` | `/api/v1/curriculum/learning-contents/{content_id}` | 更新学习内容 |
| `POST` | `/api/v1/curriculum/learning-contents/{content_id}/chapters` | 创建章节 |
| `PUT` | `/api/v1/curriculum/learning-contents/{content_id}/chapters/reorder` | 批量重排章节顺序 |
| `PUT` | `/api/v1/curriculum/learning-contents/{content_id}/chapters/{chapter_id}` | 更新章节 |
| `DELETE` | `/api/v1/curriculum/learning-contents/{content_id}/chapters/{chapter_id}` | 删除章节 |
| `POST` | `/api/v1/curriculum/learning-contents/{content_id}/publish` | 发布学习内容 |
| `POST` | `/api/v1/curriculum/learning-contents/{content_id}/archive` | 归档学习内容 |

### 学员端（学习页面）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/curriculum-practice/study/learning-contents/{content_id}` | 学员读取讲座内容（含进度） |
| `POST` | `/api/v1/curriculum-practice/study/learning-contents/{content_id}/progress` | 标记章节完成进度 |

---

## 发布门禁

`POST /publish` 会校验以下条件，任一不满足返回 400：

- 至少包含 1 个章节
- 所有章节 `title` 不为空
- 章节 `order_index` 连续（无跳号）
- 无安全标记内容（script 标签、prompt injection 特征）

---

## 种子数据规格

根据 `backend/tests/fixtures/examiner_final_gate.py` 定义：

| 字段 | 值 |
|------|-----|
| `owner_id` | `sales-enablement` |
| `source` | `admin_import` |
| `import_batch_id` | `issue-77-final-gate` |
| 章节数量 | ≥ 7 |
| 章节主题 | 客户画像识别、痛点挖掘、价值主张、ROI 证据、异议处理、推进承诺、复盘改进 |

---

## 错误码（当前实现）

| 错误码 | HTTP 状态 | 场景 |
|--------|-----------|------|
| `[LEARNING_CONTENT_NOT_FOUND]` | 404 | 学习内容不存在 |
| `[LEARNING_CONTENT_SERVICE_FAILED]` | 500 | 服务层异常 |
| `[LEARNING_PROGRESS_SERVICE_FAILED]` | 500 | 学习进度服务异常 |
| `[ROLE_REQUIRED]` | 403 | 非管理员操作 |

---

## 更新记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-05-16 | 契约初始创建 | 对齐 #67/#68 实现，记录种子数据规格与发布门禁 |
