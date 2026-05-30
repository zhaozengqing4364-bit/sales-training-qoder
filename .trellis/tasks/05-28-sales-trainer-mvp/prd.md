# 石犀销售训练 MVP 基础闭环

## Goal

按 `docs/design/sales-trainer-system.md` 落地最小可用闭环：复用现有题库完成做题模块，提供不限录音时长的上传、转写和 Deucate 提示词评分原子能力，并让后台可查询操作记录、原音频与 AI 评分结果。

## Confirmed Scope

- 训练对象是石犀科技数据安全/数据流动治理产品销售新人。
- 支持 `single_choice`、`multiple_choice`、`true_false`、`short_answer`；优先适配现有 `QuestionItem`，不新造完整题库框架。
- 支持任意时长录音上传；`duration_seconds` 仅作可选留存元数据，不用于拒绝上传或通关判断。
- 音频上传后留存文件、来源信息、转写、评分结果和操作日志。
- AI 评分只采用可发布的评分提示词调用 Deucate，不引入复杂规则引擎或多模型仲裁。
- 提供最小学员页面和后台管理页面，支持查询、上传、查看结果、配置训练单元与评分提示词。

## Configuration Boundary

- 稳定代码逻辑：鉴权/访问边界、状态流转、持久化、题目提交与已支持题型自动判分、转写/评分流程编排、审计事件、错误码。
- 可配置规则：音频 MIME allowlist、文件大小、存储 backend、转写/模型超时、训练单元及提示词、评分通过线。
- 明确禁止：不得添加固定录音时长限制；不得把评分提示词或可调整通过线散落写入页面/服务逻辑。
- 兜底：格式/大小/超时配置缺失时使用安全默认值；提示词缺失或非法时拒绝评分并留存失败状态；非法题型绑定必须阻断并写操作记录。

## Implementation Slices

1. Backend contract completion: add audio source and transcript snapshot retention, authorized playback/download, OSS processing bridge, storage/timeout errors, unsupported-question audit, and tests.
2. Frontend entry points: typed API facade, learner quiz/audio/result pages, admin unit/audio/prompt/log pages and navigation.
3. Documentation and verification: mark completed items in the design document, record defects discovered during test, then execute relevant backend/frontend/browser validation.

## Acceptance Criteria

- [ ] Doing a supported quiz persists answers and grades objective question types; unsupported configured question structures cannot be published silently.
- [ ] A learner can upload audio of any duration without a duration-based validation failure, and the system persists metadata, original file, transcript and score snapshot.
- [ ] A permitted user can play/download retained audio; an unauthorized user cannot access it.
- [ ] Local and configured OSS upload paths have a processing path or a clearly typed operational failure covered by tests.
- [ ] Admin surfaces expose operation logs, audio records and score results; configuration mutations remain audit-visible.
- [ ] Learner and admin pages consume the backend through the central API facade and provide the MVP workflows.
- [ ] Design document completion marks and test/fix notes match the implemented evidence.
- [ ] Targeted lint/typecheck/tests and a real browser validation path pass before completion is reported.

## Out Of Scope

- Customer role-play, game progression, advanced manager analytics, live WebSocket conversations and new generalized question-bank infrastructure.
- Any fixed recording-duration policy.
