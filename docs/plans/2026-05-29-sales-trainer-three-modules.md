# 销售训练首页：三模块自选（替代 17 关纵向闯关）

**日期**: 2026-05-29  
**状态**: 实施中  
**path_key**: `new_seller_modules_v1`

## 目标

- 首页由 **17 关纵向时间线** 改为 **3 张模块卡片**（自选，无强制解锁链）
- COO 十五讲保留在 **模块二「拜访前商务」** 内作为章节子导航，不再占首页 15 个 path level
- **不破坏 REST API**：沿用 `quiz` / `audio_scoring` 单元类型与 `config.path`；旧路径 `new_seller_goal_path` 通过 `path.enabled=false` 从前端默认隐藏

## 模块映射

| 模块 | 展示名 | 后端单元 | order_index | 学员入口 |
|------|--------|----------|-------------|----------|
| 1 | PPT演练 | `模块一：PPT演练`（`audio_scoring`，`purpose: ppt_pitch`） | 1 | `/sales-trainer/audio/{pptUnitId}`（上传讲解录音 + AI 评分） |
| 2 | 拜访前商务 | `模块二：拜访前商务`（quiz hub，`completion_rule: submitted`） | 2 | `/sales-trainer/learn/hub`（15 章软导航） |
| 3 | 金字塔演讲 | 三个 `audio_scoring`（5/10/15 分钟） | 3–5 | `/sales-trainer/audio/{unitId}` |

**解锁**: 所有单元 `unlock_after_unit_ids: []`；前端模块网格不展示「待解锁」。

**建议顺序**（仅文案）: PPT演练 → 拜访前商务 → 金字塔演讲（任选时长）。

## 入口 URL

| 场景 | URL |
|------|-----|
| 销售训练首页 | `/sales-trainer` |
| PPT 讲解录音上传 | `/sales-trainer/audio/{pptUnitId}` |
| 拜访前商务 hub | `/sales-trainer/learn/hub` |
| COO 单章阅读 | `/sales-trainer/learn/{cooQuizUnitId}?hub=1` |
| 金字塔 5 分钟 | `/sales-trainer/audio/{audio5UnitId}` |
| 金字塔 10 分钟 | `/sales-trainer/audio/{audio10UnitId}` |
| 金字塔 15 分钟 | `/sales-trainer/audio/{audio15UnitId}` |

## Seed 步骤

前置（若本地尚无 COO 数据）:

```bash
cd backend
PYTHONPATH=src python scripts/import_coo_learning_content.py
PYTHONPATH=src python scripts/seed_coo_questions.py
```

三模块路径:

```bash
cd backend
PYTHONPATH=src python scripts/seed_sales_trainer_three_modules.py
PYTHONPATH=src python scripts/seed_sales_trainer_three_modules.py --verify-only
```

脚本行为:

1. 将 `path_key=new_seller_goal_path` 且 `path.enabled=true` 的已发布单元设为 `enabled=false`（保留数据，不删 COO seed 脚本）
2. Upsert 5 个已发布单元并挂载 `new_seller_modules_v1`
3. 模块二绑定 `config-assets/coo-learning-content.id` 的 `learner.learning_content_id`

演示学员（与 COO demo 一致）: `sales-trainer.goal.demo.learner@example.com`

## 前端行为

- `path_key === new_seller_modules_v1` → `SalesTrainerModuleGrid`（替代 `PathLevelTimeline`）
- `PathMissionPanel` 简化为「选择下方模块开始训练」
- `NEXT_PUBLIC_SALES_TRAINER_LEGACY_PATH=1` 时仍展示 `new_seller_goal_path`（17 关），便于对照
- 默认仅展示 `new_seller_modules_v1`（若存在）

## 环境变量

| 变量 | 说明 |
|------|------|
| `NEXT_PUBLIC_COO_LEARNING_CONTENT_ID` | hub 与章节阅读的讲义 ID（与 import COO 一致） |
| `NEXT_PUBLIC_SALES_TRAINER_LEGACY_PATH=1` | 首页同时显示旧 17 关路径 |

## 验证

```bash
cd web
npx vitest run src/components/sales-trainer/sales-trainer-module-grid.test.tsx src/app/\(dashboard\)/sales-trainer/page.test.tsx
npx tsc --noEmit
```
