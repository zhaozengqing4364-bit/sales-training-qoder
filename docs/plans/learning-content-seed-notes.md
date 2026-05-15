# Learning content seed notes

## Planned initial content: 售前试点 7 章讲义

Issue #67 定义的初始讲义大纲，共 7 章，章节顺序不可变更：

| Order | Chapter Title |
|-------|---------------|
| 1 | 产品与场景定位 |
| 2 | 目标客户画像 |
| 3 | 核心价值主张 |
| 4 | 常见异议处理 |
| 5 | 竞品对比话术 |
| 6 | 成交推进步骤 |
| 7 | 复盘与改进清单 |

## Ownership & source

| Field | Value |
|-------|-------|
| Owner | `curriculum-team` |
| Source | `presales-pilot-manual` |
| Import / create method | Admin LearningContent UI 或 `/api/v1/curriculum/learning-contents` API create + chapter 接口 |
| Verification entry | Backend integration test + Admin LearningContent detail page + publish gate 校验 |

## Current entry point: manual creation via Admin UI or API

当前 #67 的后端 `LearningContent` API 已实现（create / list / detail / publish），Admin UI 也已提供列表和详情编辑界面。

**章节内容目前通过以下方式录入：**

- **Admin UI**：在 LearningContent 详情页逐个添加章节，填写标题和内容。
- **API**：`POST /api/v1/curriculum/learning-contents` 创建讲义主体，再通过 chapter 子资源接口逐章上传。

## No automatic seed in place

**当前代码中没有自动 seed 脚本。** 7 章初始内容不会在任意环境中自动落库。

如果有自动初始化需求，应另行创建 seed 脚本或 fixture（例如 `backend/scripts/seed_learning_content.py`），通过 `POST /api/v1/curriculum/learning-contents` API 逐个创建讲义和章节。该脚本不属于 #67 范围。

## Content body intentionally not committed

章节正文（每章的讲解文本、示例话术等）**未包含在本仓库中**。这些内容属于产品/内容团队的交付物，需由 `curriculum-team` 提供最终文案后再通过上述入口录入。

## Verification path

Publish gate 会对讲义执行以下校验，确保内容完整：

- 讲义至少包含 1 个章节
- 所有章节 content 非空
- 章节 order 连续无间隙
- 无 safety-flagged 内容

通过 Admin LearningContent detail 页可逐章查看内容；backend integration test 覆盖 publish gate 的校验逻辑。

## Rollout notes

1. 由 `curriculum-team` 提供 7 章最终文案。
2. 通过 Admin UI 或 API 逐章创建讲义内容。
3. 通过 publish gate 校验后发布。
4. 如需自动化 seed，后续另建脚本，不在 #67 范围内。
