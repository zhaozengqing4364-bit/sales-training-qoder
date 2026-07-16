# 统一路径评分标准与录音评分标准

## Goal

路径编排里的「评分标准」与侧栏「录音评分标准」使用同一套数据与同一套编辑能力，使路径活动绑定后 AI 评分能读到完整提示词并正常打分。

## What I already know

* 路径就地新建走 `POST .../scoring-rubrics`，落库为 `audio_scoring_rubric` 资产（仅 title / pass_score / dimensions）。
* 「录音评分标准」页走 `SalesTrainerAudioScorePrompt`（`/audio-score-prompts`），含 system_prompt、scoring_template、learner_rubric、output_schema。
* 评分引擎 `DeucateScoringService` 只消费 `SalesTrainerAudioScorePrompt`：需要 `system_prompt` + 含 `{transcript}` 的 `scoring_template`；解析模型 JSON 字段固定为 `total_score` / `summary|feedback` / `strengths` / `improvements` / `dimension_scores`。
* 路径活动冻结的 `score_scheme_snapshot` 目前只有 rubric payload，不含 `prompt_id` / `prompt_snapshot`，提交后会 `[SCORING_PROMPT_REQUIRED]`。
* 内容库「管理评分标准」已链到 `/admin/sales-trainer/score-standards`，但创建链路未打通。

## Decisions (locked)

* **就地新建交互 = B**：最小字段创建并绑定（名称 + 维度 + 默认提示词含 `{transcript}` 与固定 JSON 输出要求），弹窗提供「去完善提示词」链到 `/admin/sales-trainer/score-standards/{id}/edit`；不在路径页塞完整表单，也不强制跳走才能创建。
* **旧数据 = 1**：不自动迁移旧 `audio_scoring_rubric`；路径发布/资源校验对旧绑定给出可操作错误，要求管理员重新选择或新建评分标准。

## Requirements

* 路径活动「选择已有」列出已发布的录音评分标准（与列表页同源，`SalesTrainerAudioScorePrompt`）。
* 路径就地新建写入同一套 score prompt（创建后即 published，可立即绑定），并可在录音评分标准页看到、编辑、再发布修订。
* 最小创建成功后展示「去完善提示词」入口；不阻断绑定。
* 活动配置字段可继续叫 `scoring_rubric_id`，语义为 `prompt_id`。
* `ActivityAudioSnapshotService.freeze` 必须按 prompt 冻结可评分快照（含 `prompt_id` + `prompt_snapshot`，对齐 unit 路径 `resolve_score_scheme`）。
* 旧 `audio_scoring_rubric` 绑定：列表不再推荐；校验 fail-closed，文案引导重绑。
* 评分说明缺少 `{transcript}` 时创建/更新被拒绝（与现网一致）。

## Acceptance Criteria

* [x] 在路径新建评分标准后，录音评分标准列表立即可见同一条。
* [x] 在录音评分标准页编辑并发布后，路径活动「选择已有」可选到同一条。
* [x] 绑定该标准的路径活动提交录音后，评分不再因缺少 prompt 失败（在 Deucate 可用前提下）。
* [x] 仍绑定旧 `audio_scoring_rubric` 的活动在路径校验/发布时得到明确「请重新选择评分标准」类错误。
* [x] 就地新建成功 UI 提供「去完善提示词」链到完整编辑页。
* [x] 就地创建并绑定评分标准后，路径草稿必须自动持久化（`scoring_rubric_id` 写入服务端 working revision）；「去完善提示词」前若仍有未保存修改，须先保存成功再打开编辑页。保存失败时不得假装已保存，并阻止跳转或给出可恢复错误。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 改 Deucate 提供商或更换评分模型协议。
* 重做完整评分标准可视化设计系统。
* 自动迁移旧 `audio_scoring_rubric` → score prompt。
* 自动迁移历史训练单元配置。

## MVP Scope

1. 后端：路径 scoring-rubrics list/create 改为基于 AudioScorePrompt；freeze 带 prompt_snapshot；校验拒绝旧 rubric。
2. 前端：就地新建走统一 API + 默认提示词 +「去完善」链接；选择已有同源列表。
3. 测试：创建同源、freeze 含 prompt、旧绑定校验失败。

## Technical Notes

### 提示词格式（代码事实）

| 字段 | 要求 |
|---|---|
| `system_prompt` | 必填，自然语言即可 |
| `scoring_template` | 必填，**必须包含 `{transcript}`**；可选 `{purpose}` `{unit_name}` `{scoring_standard}` |
| `learner_rubric.criteria` | 每行 `维度名 \| 权重 \| 说明`（学员可见） |
| `output_schema` | JSON Schema 对象，可空；**当前 HTTP Deucate 客户端不会把 schema 传给模型** |
| 模型返回 JSON | 后端固定读取：`total_score`、`summary`/`feedback`、`strengths`、`improvements`、`dimension_scores` |

### 拟议实现方向

1. `listScoringRubrics` / `createScoringRubric` 读写 score-prompt（或薄封装保持路径 API 形状）。
2. `ActivityAudioSnapshotService.freeze` 加载 published prompt，写入 `prompt_id` + `prompt_snapshot` + learner_rubric/pass_threshold。
3. 前端 `resource-picker-drawer` 创建并绑定后自动 `persistDraft`（同「保存草稿」）；成功文案「评分标准已创建；路径草稿已保存」；「去完善提示词」前若仍 dirty 须先保存成功再 `window.open` 新标签，失败不跳转。
4. `resource_validator`：`scoring_rubric_id` 必须对应 published AudioScorePrompt，不再认 `audio_scoring_rubric` 资产为有效绑定。
