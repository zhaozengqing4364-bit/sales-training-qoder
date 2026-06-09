# 销售训练材料库与后台节点重构计划

**日期**: 2026-06-01  
**状态**: 方案草案，待评审  
**核心决策**: 销售训练材料单独管理，不复用 `/admin/presentations` 的 PPT 演练管理节点。  
**目标**: 让销售训练从“可上传录音并评分”升级为“材料版本、任务简报、评分方案、训练记录可管理、可追溯、可演进”的长期训练系统。

---

## 一、背景与问题

当前销售训练后台已经具备基础闭环：

1. 训练单元管理。
2. 训练路径管理。
3. 销售题库管理。
4. 录音评分标准管理。
5. 学员录音查询。
6. 评分结果查询。
7. 配置健康页。
8. 操作记录。

这套能力已经能完成：

```text
学员上传录音
  -> 后端保存音频
  -> 转写
  -> AI 评分
  -> 后台查看结果
```

但它仍缺少完整的“训练内容闭环”：

```text
训练材料版本
  -> 任务简报
  -> 训练任务
  -> 评分方案
  -> 学员提交
  -> 结果追溯
  -> 管理复盘
```

因此 PPT 演练页会显得过于直接：用户进入页面后马上看到上传录音，而不是先理解这关训练的作用、下载最新版 PPT、确认材料版本、阅读评分标准，再提交录音。

这个问题不是单个页面文案不足，而是后台缺少一个明确的一等对象：**销售训练材料**。

---

## 二、核心判断

### 2.1 销售训练材料必须单独管理

销售训练里的 PPT、逐字稿、讲解示例、任务附件，不应直接复用现有 `/admin/presentations`。

原因：

| 维度 | `/admin/presentations` | 销售训练材料库 |
|---|---|---|
| 核心语义 | PPT 演练文稿 | 培训材料 |
| 主要用途 | 实时 PPT 演示、PPT 演练运行时 | 学员下载、版本确认、任务绑定、评分追溯 |
| 管理重点 | PPT 解析状态、页数、演练配置 | 版本号、当前生效版本、发布说明、训练任务绑定 |
| 学员行为 | 进入演练 | 下载材料、按材料录音、确认版本 |
| 追溯要求 | 会话和文稿关系 | 提交时冻结材料版本、评分方案版本和任务版本 |

结论：底层文件存储能力可以复用，业务节点和数据模型应在 `sales_trainer` 域内独立。

### 2.2 后台节点应围绕“练什么、怎么练、练得怎么样”重组

当前后台偏“技术流水”：

- 训练单元。
- 学员录音。
- 评分结果。
- 操作记录。

未来后台应该偏“培训管理”：

- 管材料。
- 管任务。
- 管评分。
- 看学员训练记录。
- 看训练分析。

### 2.3 PPT 演练是第一个标准模板

PPT 演练不是一个特殊页面，而应该成为后续所有录音表达训练的样板：

```text
材料版本
  -> 任务简报
  -> 学员可见评分标准
  -> 上传录音
  -> AI 评分
  -> 结果复盘
```

当 PPT 演练跑顺后，金字塔演讲、行业方案讲解、渠道合作话术、老板汇报训练都可以复用这套结构。

---

## 三、目标与非目标

### 3.1 目标

1. 新增销售训练材料库，单独管理 PPT、逐字稿、示例录音和附件。
2. 支持材料版本化，明确当前生效版本、发布说明、文件 hash 和下载地址。
3. 训练任务可绑定一个或多个材料，并配置是否要求学员确认最新版。
4. PPT 演练页展示训练目标、最新版 PPT 下载、材料版本、评分标准和上传入口。
5. 录音提交时冻结材料版本、任务版本和评分方案版本，保证历史结果可解释。
6. 后台合并“学员录音”和“评分结果”为“学员训练记录”。
7. 将“录音评分标准”升级为“评分方案”，同时承载学员可见 rubric 与 AI 评分 prompt。
8. 保留现有基础闭环，不破坏已有 `audio_scoring` 和 `quiz` 单元。

### 3.2 非目标

1. 不把销售训练材料库做成全公司通用 DAM 系统。
2. 不复用 `/admin/presentations` 作为销售训练 PPT 的管理入口。
3. 不在第一期做复杂内容包市场、跨租户分发或多人审批流。
4. 不在第一期做实时语音对练。
5. 不把 PPT 版本、下载链接、评分标准、任务文案硬编码到学员页面。
6. 不要求一次性替换所有后台菜单，可按阶段兼容旧入口。

---

## 四、后台节点设计

### 4.1 建议最终节点

| 节点 | 类型 | 说明 |
|---|---|---|
| 工作台 | 保留 | 销售训练总览、待处理事项、异常、快捷入口 |
| 训练模块 | 新增/替代训练路径 | 管 PPT 演练、拜访前商务、金字塔演讲等模块级入口 |
| 训练任务 | 训练单元升级命名 | 管具体可练任务，包含做题、录音、组合任务 |
| 训练材料库 | 新增 | 单独管理销售训练材料及其版本 |
| 销售题库 | 保留 | 管销售训练专属题目和分类 |
| 评分方案 | 升级录音评分标准 | 管学员可见评分标准、AI prompt、输出 schema、通过线 |
| 学员训练记录 | 合并 | 合并学员录音、转写、评分结果、重试操作 |
| 训练分析 | 后续新增 | 看通过率、薄弱维度、材料版本影响、团队表现 |
| 配置与审计 | 合并 | 合并配置健康、操作记录、系统异常和权限审计 |

### 4.2 当前节点迁移建议

| 当前节点 | 建议处理 | 目标节点 |
|---|---|---|
| 工作台 | 保留 | 工作台 |
| 训练单元 | 改名并增强 | 训练任务 |
| 训练路径 | 升级 | 训练模块 |
| 销售题库 | 保留 | 销售题库 |
| 录音评分标准 | 升级 | 评分方案 |
| 学员录音 | 合并 | 学员训练记录 |
| 评分结果 | 合并 | 学员训练记录 |
| 配置 | 降级归组 | 配置与审计 |
| 操作记录 | 降级归组 | 配置与审计 |

### 4.3 不建议继续扩张一级菜单

如果每新增一个能力就新增一个同级菜单，后台会越来越像技术模块堆叠。建议销售训练后台一级入口保持在 8-9 个以内，更多能力进入详情页或分组 tab。

### 4.4 兼容迁移原则

本计划不要求一次性删除旧入口。迁移期建议采用“新读侧先行、旧入口保留跳转或聚合”的方式：

1. `学员录音` 和 `评分结果` 在第一阶段继续保留，新增 `学员训练记录` read model 后再逐步把旧入口 redirect 或嵌入为筛选 tab。
2. `录音评分标准` 改名为 `评分方案` 时，底层先兼容现有 `AudioScorePrompt`，新增 learner rubric 字段后再调整 UI 文案。
3. `训练路径` 先保留当前聚合逻辑，新增 `训练模块` 后再把三模块展示配置迁入模块管理。
4. `训练单元` 短期不改 API 名称，UI 上逐步改成“训练任务”，避免大范围破坏已有接口和测试。
5. 销售训练材料库第一版只承载新 PPT 演练材料，不回填历史提交；历史提交材料快照为空时，详情页显示“该记录产生于材料版本追溯上线前”。

---

## 五、训练材料库设计

### 5.1 材料主档

材料主档表示一个长期存在的训练材料，例如“公司主胶片”。

建议字段：

| 字段 | 说明 |
|---|---|
| `material_id` | 主键 |
| `material_key` | 稳定业务标识，例如 `company_master_deck` |
| `name` | 材料名称 |
| `material_type` | 材料类型，如 `ppt_deck`、`script`、`example_audio`、`attachment` |
| `description` | 材料说明 |
| `purpose` | 用途，如 `ppt_pitch` |
| `status` | `draft`、`published`、`archived` |
| `current_version_id` | 当前生效版本 |
| `created_by` / `updated_by` | 创建和更新人 |
| `created_at` / `updated_at` | 时间 |

### 5.2 材料版本

材料版本表示某份材料的具体文件版本，例如“公司主胶片 v2026.06”。

建议字段：

| 字段 | 说明 |
|---|---|
| `version_id` | 主键 |
| `material_id` | 关联材料主档 |
| `version_label` | 版本号，如 `v2026.06.01` |
| `title` | 版本标题 |
| `file_name` | 原始文件名 |
| `content_type` | 文件类型 |
| `file_size_bytes` | 文件大小 |
| `storage_key` | 文件存储 key |
| `file_hash` | 文件 hash，用于追溯和防重复 |
| `release_notes` | 更新说明 |
| `status` | `draft`、`published`、`archived` |
| `published_at` / `published_by` | 发布时间和发布人 |
| `created_at` / `updated_at` | 时间 |

### 5.3 任务材料绑定

训练任务可以绑定一个或多个材料。

建议字段：

| 字段 | 说明 |
|---|---|
| `binding_id` | 主键 |
| `unit_id` | 训练任务 ID |
| `material_id` | 材料 ID |
| `required` | 是否必读或必下载 |
| `confirmation_required` | 是否要求学员确认使用最新版 |
| `version_policy` | `current_published` 或 `locked_version` |
| `locked_version_id` | 锁定版本时使用 |
| `display_order` | 展示顺序 |
| `learner_note` | 学员侧说明 |

第一期建议采用：

```text
学员端展示当前 published 最新版；
提交时冻结实际材料版本。
```

这比任务发布时永久锁死版本更适合 PPT 演练，因为用户确实应该拿最新版 PPT 训练。但历史提交必须冻结当时版本，保证追溯。

### 5.4 提交快照

学员提交录音时，需要记录当时的材料版本和评分方案版本。

建议在音频提交或训练记录中保存：

| 字段 | 说明 |
|---|---|
| `submission_id` | 提交 ID |
| `unit_id` | 训练任务 ID |
| `material_snapshot` | 材料版本快照 |
| `score_scheme_snapshot` | 评分方案快照 |
| `task_brief_snapshot` | 任务简报快照 |
| `confirmed_material_version_id` | 学员确认的材料版本 |
| `confirmed_at` | 学员确认时间 |

快照应至少包含：

```json
{
  "material_id": "xxx",
  "material_name": "公司主胶片",
  "version_id": "yyy",
  "version_label": "v2026.06.01",
  "file_hash": "sha256:...",
  "release_notes": "更新数据分类分级案例页",
  "published_at": "2026-06-01T00:00:00Z"
}
```

---

## 六、任务简报设计

### 6.1 简报定位

任务简报解决的是学员开始训练前的三个问题：

1. 这关为什么重要。
2. 我要拿什么材料练。
3. 什么算练得好。

PPT 演练页不应该是上传页，而应该是任务简报页和上传页的组合。

### 6.2 简报字段

建议训练任务增加 `brief` 配置，或新增独立 `SalesTrainerTaskBrief`。

字段建议：

| 字段 | 说明 |
|---|---|
| `brief_title` | 简报标题 |
| `brief_summary` | 一句话说明 |
| `training_goal` | 训练目标 |
| `why_it_matters` | 作用和意义 |
| `preparation_steps` | 准备步骤 |
| `success_criteria` | 成功标准 |
| `common_mistakes` | 常见扣分点 |
| `example_links` | 示例材料或示例录音 |
| `upload_instructions` | 上传说明 |
| `confirmation_items` | 上传前确认项 |

### 6.3 PPT 演练页推荐顺序

```text
返回销售训练
  -> 第 1 关：PPT 演练
  -> 本关训练目标
  -> 最新 PPT 下载
  -> 当前材料版本与更新说明
  -> 什么是好的 PPT 讲解
  -> 常见扣分点
  -> 录音建议
  -> 确认使用最新版 PPT
  -> 上传录音并评分
```

上传按钮应位于页面后段，而不是第一屏核心动作。

---

## 七、评分方案设计

### 7.1 从“录音评分标准”升级为“评分方案”

当前“录音评分标准”主要面向 AI prompt。未来需要拆成两个视角：

| 视角 | 内容 |
|---|---|
| 学员可见 rubric | 评分维度、权重、优秀标准、扣分点、通过线 |
| AI 评分 prompt | system prompt、scoring template、output schema、模型参数 |

两者应属于同一评分方案，避免学员看到的标准和 AI 实际执行的标准分叉。

### 7.2 评分方案字段

建议字段：

| 字段 | 说明 |
|---|---|
| `scheme_id` | 评分方案 ID |
| `name` | 名称 |
| `purpose` | 用途，如 `ppt_pitch` |
| `learner_rubric` | 学员可见评分标准 |
| `ai_system_prompt` | AI system prompt |
| `ai_scoring_template` | AI scoring template |
| `output_schema` | 输出 schema |
| `pass_threshold` | 默认通过线 |
| `version` | 版本 |
| `status` | `draft`、`published`、`archived` |

### 7.3 PPT 讲解建议 rubric

PPT 演练第一版可以使用如下维度：

| 维度 | 建议权重 | 判断重点 |
|---|---:|---|
| 主线结构 | 25% | 是否按公司主胶片逻辑展开，开场、背景、方案、价值、行动完整 |
| 关键内容覆盖 | 25% | 是否覆盖关键页、关键概念和必须讲清的产品能力 |
| 客户价值表达 | 20% | 是否把功能转成客户收益，而不是照念参数 |
| 证据与案例 | 15% | 是否使用案例、数据或边界说明增强可信度 |
| 表达清晰度 | 15% | 语言是否自然，节奏是否适合客户理解 |

这些权重、维度、文案都必须在评分方案中配置，不应写死在页面组件里。

---

## 八、学员训练记录设计

### 8.1 合并原因

当前“学员录音”和“评分结果”分开，更符合技术过程，但不符合管理员查询习惯。

管理员真正要看的是：

1. 谁练了哪一关。
2. 用了哪份材料。
3. 上传了什么录音。
4. 转写是否成功。
5. AI 按哪个评分方案打分。
6. 是否通过。
7. 失败后是否需要重试。

因此建议合并成“学员训练记录”。

### 8.2 列表字段

| 字段 | 说明 |
|---|---|
| 学员 | 姓名、邮箱、部门 |
| 训练任务 | 任务名称、模块 |
| 材料版本 | 材料名、版本号 |
| 提交状态 | uploaded、transcribing、scoring、scored、failed |
| 总分 | AI 总分 |
| 是否通过 | passed |
| 提交时间 | created_at |
| 操作 | 查看详情、重试转写、重试评分 |

### 8.3 详情页分区

1. 基本信息。
2. 训练任务。
3. 使用材料版本。
4. 上传录音。
5. 转写文本。
6. AI 评分结果。
7. 评分方案版本。
8. 操作记录。
9. 重试操作。

---

## 九、配置化判断

### 9.1 稳定代码逻辑

以下属于稳定代码逻辑，可以写入代码：

1. 材料、材料版本、任务绑定、提交快照的数据一致性。
2. 文件上传、存储、下载签名、hash 计算。
3. 材料状态流转：draft、published、archived。
4. 一个材料只能有一个当前生效版本的约束。
5. 学员只能读取 published 材料。
6. 提交时冻结材料版本和评分方案版本。
7. 管理员和培训负责人权限边界。
8. 操作记录写入。

### 9.2 可配置业务规则

以下不能硬编码：

1. PPT 下载地址。
2. 最新 PPT 版本号。
3. 材料更新说明。
4. 任务目标、作用意义、准备步骤。
5. 上传前确认项。
6. 学员可见评分维度、权重、优秀标准、扣分点。
7. 是否必须确认最新版才能上传。
8. 训练模块展示顺序。
9. 训练任务展示文案。
10. 通过线。
11. 推荐学习顺序。

### 9.3 新增配置项清单

| 配置项 | 用途 | 默认值 | 读取位置 | 管理入口 | 校验规则 | 权限 | 兜底策略 |
|---|---|---|---|---|---|---|---|
| `material.material_type` | 区分 PPT、逐字稿、示例录音等 | `ppt_deck` | 材料库服务 | 训练材料库 | 必须在允许枚举内 | admin/培训负责人 | 非法拒绝保存 |
| `material.current_version_id` | 当前生效材料版本 | 无 | 学员任务页 | 训练材料库 | 必须指向 published 版本 | admin/培训负责人 | 缺失则学员页提示材料未发布 |
| `unit.material_bindings` | 训练任务绑定材料 | 空数组 | 学员任务页/提交服务 | 训练任务 | material 必须 published | admin/培训负责人 | 缺失则不展示材料区 |
| `unit.material_confirmation_required` | 是否必须确认最新版 | `true` for PPT 演练 | 学员任务页/提交服务 | 训练任务 | 布尔值 | admin/培训负责人 | 缺失按 false，PPT 模板默认 true |
| `unit.task_brief` | 任务简报 | 空对象 | 学员任务页 | 训练任务 | 字段长度、数组项长度限制 | admin/培训负责人 | 缺失展示基础标题说明 |
| `score_scheme.learner_rubric` | 学员可见评分标准 | 空数组 | 学员任务页/结果页 | 评分方案 | 维度非空，权重总和建议 100 | admin/培训负责人 | 缺失只展示通过线和提示 |
| `score_scheme.pass_threshold` | 通过线 | 70 | 评分服务/学员页 | 评分方案或任务覆盖 | 0-100 | admin/培训负责人 | 缺失使用安全默认值 |
| `module.display_order` | 模块展示顺序 | 1 | 学员首页 | 训练模块 | 正整数 | admin/培训负责人 | 缺失按创建时间排序 |
| `module.enabled` | 模块是否展示 | true | 学员首页 | 训练模块 | 布尔值 | admin/培训负责人 | 缺失按 false 处理 |

### 9.4 配置缺失处理

| 场景 | 处理方式 |
|---|---|
| 训练任务未绑定材料 | 学员页不展示材料区，但允许非材料型任务继续 |
| PPT 演练未绑定 published 材料 | 学员页阻断上传，提示管理员配置最新版 PPT |
| 材料无当前版本 | 学员页展示“材料未发布”，后台工作台提示待处理 |
| 评分方案无学员 rubric | 仍可评分，但学员页只展示通过线，并在后台提示配置不完整 |
| 提交时材料版本变化 | 提交时读取当前版本并冻结，用户确认版本与冻结版本不一致则提示重新确认 |

### 9.5 配置非法处理

| 场景 | 处理方式 |
|---|---|
| 材料版本文件 hash 缺失 | 不允许发布 |
| `current_version_id` 指向非 published 版本 | 不允许保存或发布 |
| rubric 权重非法 | 后台保存失败或发布失败 |
| 任务绑定 archived 材料 | 不允许发布训练任务 |
| 必须确认但提交缺少确认版本 | 拒绝提交并返回明确错误 |

---

## 十、权限与审计

### 10.1 权限建议

| 操作 | admin | 培训负责人 | 学员 |
|---|---:|---:|---:|
| 创建材料 | 是 | 是 | 否 |
| 上传材料版本 | 是 | 是 | 否 |
| 发布材料版本 | 是 | 可配置 | 否 |
| 归档材料 | 是 | 可配置 | 否 |
| 绑定材料到任务 | 是 | 是 | 否 |
| 查看材料下载链接 | 是 | 是 | 仅 published |
| 查看训练记录 | 全部 | 本部门 | 本人 |
| 重试转写/评分 | 是 | 本部门 | 否 |

短期可以沿用 `can_manage_sales_trainer` 和 `team_scope_department`。长期建议接入细粒度权限：

- `sales_trainer.material.read`
- `sales_trainer.material.write`
- `sales_trainer.material.publish`
- `sales_trainer.record.read`
- `sales_trainer.record.retry`

### 10.2 操作记录

需要新增或规范以下操作：

| action | target_type | 说明 |
|---|---|---|
| `material_created` | `sales_trainer_material` | 创建材料 |
| `material_version_uploaded` | `sales_trainer_material_version` | 上传材料版本 |
| `material_version_published` | `sales_trainer_material_version` | 发布材料版本 |
| `material_version_archived` | `sales_trainer_material_version` | 归档版本 |
| `unit_material_bound` | `sales_trainer_unit` | 任务绑定材料 |
| `material_confirmed` | `sales_trainer_audio_submission` | 学员确认材料版本 |
| `submission_snapshot_frozen` | `sales_trainer_audio_submission` | 提交冻结材料和评分方案快照 |

---

## 十一、学员端体验

### 11.1 PPT 演练页改造

现状：

```text
标题
  -> 作业说明
  -> 通过标准
  -> 上传音频
```

目标：

```text
标题
  -> 本关训练目标
  -> 最新 PPT 下载
  -> 材料版本和更新说明
  -> 什么是好的 PPT 讲解
  -> 常见扣分点
  -> 录音建议
  -> 确认使用最新版
  -> 上传录音
```

### 11.2 上传前确认

PPT 演练应要求用户确认：

```text
我已下载并使用当前最新版 PPT：公司主胶片 v2026.06.01
```

只有确认后才允许上传。确认状态随版本变化失效。

### 11.3 结果页补充材料追溯

结果页应展示：

1. 使用材料：公司主胶片。
2. 材料版本：v2026.06.01。
3. 评分方案：PPT 标准讲解评分方案 v3。
4. 是否通过。
5. 维度分。
6. 优点和改进建议。

---

## 十二、数据流

### 12.1 管理端发布材料

```text
管理员进入训练材料库
  -> 创建材料主档
  -> 上传材料版本
  -> 填写版本号和发布说明
  -> 校验文件 hash、类型、大小
  -> 发布版本
  -> 设置为当前生效版本
  -> 写入操作记录
```

### 12.2 管理端配置 PPT 演练任务

```text
管理员进入训练任务
  -> 选择 PPT 演练任务
  -> 绑定“公司主胶片”
  -> 配置必须确认最新版
  -> 配置任务简报
  -> 绑定评分方案
  -> 发布任务
```

### 12.3 学员提交

```text
学员进入 PPT 演练
  -> 页面读取任务、材料当前版本、评分方案 rubric
  -> 下载最新版 PPT
  -> 确认使用最新版
  -> 上传录音
  -> 后端冻结材料版本、任务简报、评分方案
  -> 后端转写和评分
  -> 学员查看结果
```

### 12.4 后台复盘

```text
管理员进入学员训练记录
  -> 按学员、部门、任务、材料版本筛选
  -> 查看录音、转写、评分、材料快照
  -> 必要时重试转写或评分
  -> 分析某材料版本下的通过率和薄弱维度
```

---

## 十三、API 与后端模块建议

### 13.1 后端模块

建议新增或扩展：

```text
backend/src/sales_trainer/
  material_models.py 或 models.py 扩展
  material_schemas.py 或 schemas.py 扩展
  services/material_service.py
  services/material_binding_service.py
  services/task_brief_service.py
  services/training_record_service.py
```

如果保持当前模块规模，可以先在现有 `models.py`、`schemas.py`、`api.py` 中扩展，但 service 应单独拆开，避免 `unit_service` 继续膨胀。

### 13.2 管理端 API

建议新增：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/admin/sales-trainer/materials` | 材料列表 |
| POST | `/api/v1/admin/sales-trainer/materials` | 创建材料 |
| GET | `/api/v1/admin/sales-trainer/materials/{material_id}` | 材料详情 |
| PATCH | `/api/v1/admin/sales-trainer/materials/{material_id}` | 更新材料主档 |
| POST | `/api/v1/admin/sales-trainer/materials/{material_id}/versions` | 上传或注册版本 |
| POST | `/api/v1/admin/sales-trainer/material-versions/{version_id}/publish` | 发布版本 |
| POST | `/api/v1/admin/sales-trainer/material-versions/{version_id}/archive` | 归档版本 |
| POST | `/api/v1/admin/sales-trainer/units/{unit_id}/materials` | 绑定材料 |
| GET | `/api/v1/admin/sales-trainer/training-records` | 学员训练记录列表 |
| GET | `/api/v1/admin/sales-trainer/training-records/{record_id}` | 训练记录详情 |

### 13.3 学员端 API

建议新增：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/sales-trainer/units/{unit_id}/brief` | 获取任务简报、材料、rubric |
| GET | `/api/v1/sales-trainer/material-versions/{version_id}/download-url` | 获取材料下载链接 |
| POST | `/api/v1/sales-trainer/units/{unit_id}/material-confirmations` | 确认材料版本 |

音频上传接口需要扩展：

```json
{
  "unit_id": "xxx",
  "purpose": "ppt_pitch",
  "confirmed_material_version_id": "yyy",
  "source_page": "sales_trainer_audio_upload"
}
```

服务端不能只信前端传入的材料版本；应在提交时重新读取任务绑定和当前材料版本，校验确认版本仍有效。

---

## 十四、前端页面建议

### 14.1 管理端新增页面

```text
web/src/app/admin/sales-trainer/materials/page.tsx
web/src/app/admin/sales-trainer/materials/new/page.tsx
web/src/app/admin/sales-trainer/materials/[materialId]/page.tsx
web/src/app/admin/sales-trainer/materials/[materialId]/versions/[versionId]/page.tsx
```

### 14.2 管理端改造页面

| 页面 | 改造 |
|---|---|
| `admin/sales-trainer/units/*` | 增加材料绑定、任务简报配置 |
| `admin/sales-trainer/paths` | 升级为训练模块视角 |
| `admin/sales-trainer/score-standards` | 改名评分方案，增加 learner rubric |
| `admin/sales-trainer/audio-submissions` | 并入训练记录 |
| `admin/sales-trainer/score-results` | 并入训练记录 |

### 14.3 学员端改造页面

| 页面 | 改造 |
|---|---|
| `/sales-trainer/audio/[unitId]` | 改为任务简报 + 材料下载 + rubric + 上传 |
| `/sales-trainer/audio/result/[submissionId]` | 展示材料版本和评分方案版本 |
| `/sales-trainer` | 模块卡片展示材料/任务完整度提示 |

---

## 十五、分期实施计划

### P0：设计与契约固化

目标：先明确契约，不改大范围 UI。

交付：

1. 更新 `docs/api-contract/sales-trainer.md`。
2. 定义材料、材料版本、任务绑定、提交快照 DTO。
3. 定义训练记录 read model。
4. 明确权限和操作记录 action。

验收：

1. 契约能回答 PPT 演练材料从哪里来。
2. 契约能回答提交后如何追溯材料版本。
3. 契约能回答材料缺失时学员页怎么失败。

### P1：销售训练材料库

目标：后台可单独管理销售训练材料。

交付：

1. 后端材料主档和材料版本表。
2. 材料版本上传或注册。
3. 发布、归档、设置当前版本。
4. 后台材料库列表和详情页。
5. 操作记录。

验收：

1. 管理员可创建“公司主胶片”。
2. 管理员可上传 `v2026.06.01` 并发布。
3. 同一材料只有一个当前 published 版本。
4. 学员无法读取 draft 材料。

### P2：训练任务绑定材料与任务简报

目标：训练任务可以绑定材料并展示简报。

交付：

1. 训练任务增加材料绑定。
2. 训练任务增加任务简报配置。
3. PPT 演练任务绑定公司主胶片。
4. 学员端 brief API。

验收：

1. PPT 演练页能展示最新版 PPT。
2. 页面能展示训练目标、作用意义、准备步骤。
3. 材料缺失时阻断上传并给出明确提示。

### P3：评分方案升级

目标：评分标准从 prompt 管理升级为评分方案。

交付：

1. 评分方案增加 learner rubric。
2. 学员页展示 rubric。
3. 结果页展示维度解释。
4. 兼容旧 `AudioScorePrompt` 数据。

验收：

1. 学员能看到“什么是好的 PPT 讲解”。
2. AI 评分仍使用 published prompt。
3. 学员可见 rubric 和 AI prompt 同属一个 published 版本。

### P4：提交快照与训练记录合并

目标：提交时冻结材料版本和评分方案版本，后台统一查看训练记录。

交付：

1. 音频提交保存材料快照。
2. 音频提交保存评分方案快照。
3. 新增训练记录列表。
4. 合并学员录音和评分结果详情。

验收：

1. PPT 更新后，旧提交仍显示旧版本。
2. 管理员能按材料版本筛选训练记录。
3. 详情页能看到录音、转写、评分、材料版本、操作记录。

### P5：训练模块升级与分析

目标：从训练路径升级到模块化训练包。

交付：

1. 训练模块管理。
2. 模块展示顺序、启停、关联任务。
3. 训练分析：通过率、薄弱维度、材料版本影响。

验收：

1. 首页三模块可后台配置。
2. 不再依赖 seed 脚本调整模块结构。
3. 管理员能看到 PPT 演练整体通过率。

---

## 十六、测试计划

### 16.1 后端测试

1. 材料创建、更新、发布、归档。
2. 材料版本 hash 缺失时禁止发布。
3. 同一材料当前版本唯一。
4. 任务绑定 archived 材料时禁止发布。
5. 学员只能读取 published 材料。
6. 提交时材料版本冻结。
7. 提交时确认版本过期则拒绝。
8. 培训负责人只能看本部门训练记录。
9. 操作记录 action 写入。

### 16.2 前端测试

1. 材料库列表展示材料和当前版本。
2. 材料详情页展示版本历史。
3. 训练任务表单可绑定材料。
4. PPT 演练页展示训练目标、下载按钮、rubric。
5. 未确认最新版时上传按钮不可用。
6. 材料缺失时显示可操作错误。
7. 训练记录详情展示材料版本和评分方案版本。

### 16.3 E2E 验证路径

最小真实旅程：

```text
管理员创建公司主胶片
  -> 上传并发布 v2026.06.01
  -> PPT 演练任务绑定材料和评分方案
  -> 学员进入 PPT 演练
  -> 下载并确认最新版
  -> 上传录音
  -> 系统完成转写与评分
  -> 后台训练记录查看材料快照和评分结果
```

---

## 十七、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 材料库做得过大 | 拖慢交付 | 第一版只支持销售训练材料，不做通用 DAM |
| 与 `/admin/presentations` 概念混淆 | 后台理解成本高 | 菜单和文案明确“销售训练材料”，不叫 PPT 演练管理 |
| 评分方案改名影响旧页面 | 路由和测试需要调整 | 保留旧路由 redirect，底层兼容旧 DTO |
| 提交快照增加数据复杂度 | 实现成本上升 | 第一版使用 JSON snapshot，后续再抽 read model |
| 权限粒度不够 | 培训负责人能力过大或过小 | 短期沿用角色，长期接入细粒度 permission |
| 版本确认增加学员操作 | 上传路径稍长 | 只对 PPT 演练等材料强依赖任务开启确认 |

---

## 十八、建议优先级

最高优先级：

1. 销售训练材料库。
2. PPT 演练任务绑定最新版 PPT。
3. 学员页展示材料下载和版本确认。
4. 提交时冻结材料版本。

第二优先级：

1. 评分方案 learner rubric。
2. 学员训练记录合并。
3. 训练任务简报结构化。

第三优先级：

1. 训练模块管理。
2. 训练分析。
3. 配置资产导入导出。

---

## 十九、最终建议

这次不要把问题理解成“PPT 演练页缺几个文案块”，而要把它理解成销售训练系统进入第二阶段的信号。

第一阶段已经证明：

```text
录音上传、转写、AI 评分、后台查询可以跑通。
```

第二阶段要补上：

```text
材料版本、任务简报、评分方案、训练记录追溯。
```

只要这四件事补齐，销售训练就不再是几个孤立功能，而会变成可长期运营的训练内容系统。PPT 演练是第一个样板，后续所有行业化、场景化、客户角色化训练，都应该复用这条管理链路。
