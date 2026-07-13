# 新人训练录音活动「讲解前准备包」设计

## 目标

学员进入录音讲解活动后，不离开当前任务即可明确知道：本次使用哪一版讲解材料、评分会关注什么、优秀讲解可以怎样表达，以及准备完成后如何开始录音。管理员可在训练路径中配置优秀讲解文字稿，无需修改代码。

## 现状问题

- “打开材料”是直接指向材料文件的链接，学员会离开当前任务上下文。
- 页面只显示材料名称，没有材料版本、文件信息和本次实际评分关注点。
- 路径配置没有优秀讲解文字示例，学员看完 PPT 仍不知道合格表达长什么样。
- 材料版本已在提交时确认并冻结，但评分标准在页面上不可见，也没有把页面展示的 rubric revision 带回提交链路。

## 方案选择

采用当前页内的轻量准备包，不建设 PPT 转图片/PDF 的转换链路，也不新增“示范包”数据库表：

- PPT 原文件仍由现有受权限保护的材料版本文件端点提供，但降级为“在新标签页查看原文件”的次级动作。
- 当前页直接展示材料版本元数据、学员可理解的评分关注点和优秀讲解文字稿。
- 优秀讲解文字稿是 `AudioAssessmentConfig.example_transcript` 的可选纯文本字段，随不可变训练路径 revision 冻结。
- 材料和评分标准仍由成熟资源模块治理；活动详情只投影学员需要的公开信息。

## 学员交互

录音 Runner 顶部新增“讲解前准备”区域，默认展开，不需要点击跳转：

1. **本次材料**：材料名称、当前发布版本、文件名；提供“在新标签页查看 PPT 原文件”。
2. **评分会关注**：展示 rubric 标题、版本号和规范化后的维度名称/说明，不展示内部 key、数据库 ID 或 Prompt。
3. **优秀讲解示例**：展示管理员配置的文字稿；旧 revision 缺少文字稿时展示明确标注为“系统默认参考结构”的可信兜底，不冒充审核通过的标准答案。
4. **准备确认**：学员勾选“我已查看本次材料、评分要点和讲解示例”后，开始录音按钮才可用。

材料缺失或版本不可用时显示内联错误，不弹窗、不静默放行。没有绑定材料的录音活动保持可录音，但仍展示评分关注点和示例。

## 合同与数据流

### 路径配置

`AudioAssessmentConfig` 向后兼容增加：

```text
example_transcript: string | null，最长 8000 字
```

只允许纯文本。历史 revision 缺失时解析为 `null`。

### 活动详情

`AudioRunnerDescriptor` 保留现有字段并增加：

- `material_version_label`、`material_file_name`、`material_content_type`
- `scoring_rubric_revision_id`（只用于提交确认，不展示）
- `scoring_rubric_revision_no`、`scoring_rubric_title`
- `scoring_focuses: [{ label, description, weight }]`
- `example_transcript`

`NewcomerJourneyService._runner_descriptor()` 从学员固定的路径 revision 读取 `example_transcript`，从材料当前发布版本读取元数据，从当前发布 rubric revision 生成学员安全的评分投影。兼容旧 seed 的字符串维度和当前结构化维度。

### 提交冻结

前端提交录音时新增可选 `confirmed_scoring_rubric_revision_id`。后端若收到该值，必须验证它属于活动绑定的 rubric、状态为 published，并按该 revision 冻结 `score_scheme_snapshot`；旧客户端未传时保留现有“提交时取当前发布 revision”的兼容语义。材料继续使用既有 `confirmed_material_version_id` 精确冻结。

数据流：

```text
Path revision(example transcript + resource logical IDs)
  → Activity detail(material version + rubric revision learner projection)
  → Inline preparation pack
  → Learner confirms both visible revisions
  → Audio submission
  → Freeze exact material/rubric revisions + activity snapshot
```

## 管理后台

录音活动编辑器保留“评分标准、讲解材料、通过分、最多尝试次数”，新增“优秀讲解文字示例”多行文本框：

- helper text 说明文字稿应对应当前 PPT，建议包含开场、核心价值、客户场景和收尾。
- 保存前去除首尾空白；空字符串归一化为 `null`。
- 新建录音活动默认 `example_transcript = null`。
- 新环境 seed 为 PPT、产品 A/B、Demo 提供不同的具体文字示例。

## 错误与兼容

- 路径未知字段继续由 strict schema 拒绝；文字稿超过 8000 字阻止保存/发布。
- rubric revision 不匹配返回稳定的 409 业务错误，不回退到另一版评分标准。
- 旧路径、旧客户端和没有材料的活动继续可解析执行。
- 不新增表、不做数据库迁移、不引入 PPT 转换依赖。

## 测试与验收

- 后端合同：新字段 round-trip、旧 payload 默认、长度边界。
- Journey：材料版本元数据、rubric 新旧维度规范化、文字稿投影。
- 冻结：确认 rubric revision 成功；错误 logical ID/revision/status fail closed；旧客户端兼容。
- 管理端：文字稿编辑和保存 round-trip，新活动默认值。
- 学员端：准备包默认可见、原文件新标签打开、无直接页面跳转、确认前录音禁用、确认后启用、旧 revision 兜底。
- Playwright：公网活动页完成“进入活动 → 查看准备包 → 查看原文件入口不改变当前页 → 确认 → 开始录音按钮可用”，检查桌面/移动布局和控制台错误。

## 非目标

- 本轮不实现 PPT 逐页图片预览、Office 在线预览或 PDF 自动转换。
- 本轮不上传/播放优秀示范音频。
- 本轮不重做通用材料管理、评分引擎或新人训练路径首页。
