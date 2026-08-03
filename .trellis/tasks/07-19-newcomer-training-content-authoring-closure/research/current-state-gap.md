# 当前实现与内容配置目标的差距

## 结论

当前系统已经有 Foundation 路径、运行时、发布、录音流水线和结构化 Coach，但“运营人员自行生产真实训练内容”的管理闭环没有完成。旧配置并未丢失，只是留在 Legacy `sales_trainer` 数据中；新 `/newcomer-training` 不读取该权威，因此形成了数据断层。

## 代码事实

- `web/src/components/layout/admin-sidebar.tsx` 把 Foundation 管理侧边栏收口成单个“新人训练工作台”入口。
- `web/src/components/admin/newcomer-training/workspace-nav.tsx` 虽有多个本地页签，但会按 `foundation_admin_permissions.py` 返回的 capability 过滤。
- `v2-path-editor.tsx` 支持 `lesson`、`quiz`、`audio_assessment`、`ai_coach`、`assignment` 五类活动，并绑定精确修订。
- `activity-resource-drawer.tsx` 的前端快速创建仅完整覆盖 `learning_unit` 与 `quiz`；录音材料、评分方案、教练 Profile、客户场景主要只能选择已有 Seed 资源。
- `content-workspace.tsx` 当前上传 allowlist 不含 PPT/PPTX、视频和音频；学员 Lesson Runner 主要呈现结构化文字内容。
- `question-review-workspace.tsx` 主要覆盖 AI 生成候选审核，没有完整暴露后端已有的手工题目修订与 Quiz 编排能力，也没有 Foundation 批量导入闭环。
- `foundation_standard_pack.py` 是录音资源和 Coach Profile 的主要创建来源，说明生产管理员缺少正式 Authoring Surface。
- `docs/adr/2026-07-17-foundation-admin-release-governance.md` 要求统一入口与分域写权威，并未要求删除各类配置入口。

## 当前数据库只读清点（2026-07-19）

Legacy：

- `sales_trainer_materials`：4；
- `sales_trainer_material_versions`：2；
- `sales_trainer_asset_revisions`：10；
- `sales_trainer_asset_active_revisions`：4；
- `sales_trainer_audio_score_prompts`：2；
- active `newcomer_training_path_orchestration` 修订中包含 `石犀ppt讲解` 和 `demo讲解`；
- 四条旧材料均名为 `石犀科技-企业介绍标准版（202606版）.pptx`，其中一条已发布、三条草稿。

Foundation：

- `learning_source_documents`：2；
- `learning_units_v2`：14；
- `learning_questions`：14；
- `learning_quizzes`：14；
- `audio_activity_resource_revisions`：4；
- `coach_profile_revisions`：1；
- `newcomer_paths`：2；
- `newcomer_path_revisions`：2。

这些 Foundation 数据主要来自标准 Seed，不能代替用户旧配置的迁移。

## 目标对象映射

| Legacy 对象 | Foundation 目标 | 迁移规则 |
|---|---|---|
| `SalesTrainerMaterial` + published version | `SourceDocument`/Revision 或领域音频材料引用 | 用 legacy id + 文件 hash 建稳定映射，保留文件名、purpose、版本和来源 |
| v1 `石犀ppt讲解` Activity | v2 `audio_assessment` ActivityDefinition | 创建/绑定 PPT 内容资产、录音材料、评分方案和能力映射 |
| v1 `demo讲解` Activity | v2 `audio_assessment` ActivityDefinition | 创建/绑定 Demo 内容资产或脚本、录音材料、评分方案和能力映射 |
| 旧音频评分 Prompt | governed Prompt/ScoringScheme exact revisions | 只迁移可验证合同；Prompt 正文不在普通 UI 暴露 |
| v1 orchestration revision | Foundation Path working revision + ReleasePlan | 先 dry-run 映射，再创建新修订；不覆盖已发布历史，不自动迁移 Enrollment |

## 必须避免

- 重新开放旧页面并让新旧两套同时写；
- 为迁移建立长期双写或请求时自动兼容读取；
- 把 Seed 当成管理员可配置能力；
- 用“路由存在”或“能绑定已有对象”宣称 CRUD 已闭环；
- 把旧训练结果、Prompt 或缺 lineage 数据伪装成 Foundation 已验证事实。

