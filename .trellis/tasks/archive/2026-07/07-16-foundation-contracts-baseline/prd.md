# 切片 0：契约冻结与干净架构基线

## Goal

在任何大规模实现开始前，把新人销售基础训练首发版的产品边界、领域语言、模块所有权、状态机、API 契约、数据迁移策略、权限边界和质量门禁冻结为仓库权威。

本切片不追求“先写出页面”，而是解决当前代码、旧 Trellis 任务和现有 Spec 对产品方向存在冲突的问题，确保后续 8 个垂直切片不会分别发明路径结构、达标口径、AI 调用方式或兼容策略。

## Parent Outcome

父任务：[`07-16-newcomer-sales-foundation-platform`](../07-16-newcomer-sales-foundation-platform/prd.md)

本切片完成后，后续实现必须以本任务更新后的 ADR、Spec、API Contract 和父任务决策记录为准。

## What Is Already Decided

- 产品中心是新人销售基础训练，不是通用 Agent 平台。
- 首发结果是 `foundation_ready`；实时客户语音对练延期。
- 学员路径使用 `PathRevision -> Stage -> ActivityDefinition`。
- Cohort 绑定已发布 PathRevision；Enrollment 默认冻结，不自动迁移。
- 五类首发活动：Lesson、Quiz、Audio、AI Coach、异步客户场景录音。
- AI 是受治理的训练能力，不是所有模块直接调用模型。
- 正式达标必须基于不可变证据和人工复核，不允许模型直接授予。
- 当前开发期采用干净切换；不保留永久兼容层、永久双写或两个写权威。

## Problem Statement

当前仓库中存在至少四类会阻断后续实现的契约冲突：

1. 现有新人路径 Spec 仍使用 `Phase -> Module -> Activity`，而目标模型只保留 `Stage -> ActivityDefinition`。
2. 现有发布语义会把活跃 Enrollment 同步到最新修订，而目标语义要求默认冻结。
3. 现有活动类型包含 realtime，目标首发明确延期。
4. 旧任务、现有代码和文档对题目生成、录音处理、AI Coach、评分结论和任务运行时各自存在不同权威。

如果不先冻结契约，后续切片即使“能跑”，也会形成新的结构债和数据歧义。

## Requirements

### R1. Product Boundary ADR

- 新增或更新 ADR，记录首发产品承诺、用户角色、正式结论和延期范围。
- 明确 `foundation_ready` 只表示基础训练达标，不代表真实销售岗位胜任。
- 明确 Realtime 不进入首发导航、活动定义、默认种子、权限配置和验收用例。
- 明确后续 Realtime 必须通过新 PathRevision 和更高等级结论接入。

### R2. Domain Model ADR

- 冻结以下核心聚合和所有权：
  - Path / PathRevision / Stage / ActivityDefinition；
  - Cohort / Enrollment；
  - ActivityAttempt / ActivityOutcome；
  - SourceDocument / LearningUnit / QuestionCandidate / QuestionRevision / QuizRevision；
  - AudioSubmission / TranscriptRevision / ScoreOutcomeVersion；
  - AiCoachSession / TrainingCard / RemediationCycle；
  - CompetencyEvidence / ReadinessDossier / ReviewDecision。
- 每个对象必须定义唯一写权威、生命周期状态、不变量和允许的跨域引用方式。
- JSONB 只用于聚合内部的有类型配置；不得把跨域关系或正式状态隐藏在无约束 JSON 中。

### R3. Ubiquitous Language

- 更新领域词典，统一“路径、修订、阶段、活动、尝试、结果、证据、能力、档案、复核、补练、发布”等中文用户语言和英文代码名。
- 标记禁用或仅保留在历史代码中的术语：Phase、Module、Realtime Activity、自动升级 Enrollment、AI 自动认定达标。
- 普通用户界面不得出现内部状态、原始枚举、Prompt、traceId、workflow、raw JSON 等工程字段。

### R4. Module Ownership And Dependency Rules

- 冻结父任务 `architecture.md` 中的目标模块地图。
- 明确模块内部层次：delivery -> application -> domain/ports；adapter 实现 port；composition root 负责装配。
- 禁止业务模块跨域导入 ORM、Repository 或内部 Service。
- 禁止 `common/shared_kernel` 反向依赖具体业务模块。
- 定义 ActivityRuntime、TaskRuntimePort、AIInvocationPort、CompetencyEvidenceWriter 等稳定接口。
- 为允许的依赖边和临时例外建立机器可检查的白名单；白名单必须有删除期限。

### R5. State Machines

- 为 PathRevision、Enrollment、ActivityAttempt、DurableTask、AudioSubmission、QuestionCandidate、QuestionRevision、AiCoachSession、ReadinessDossier、ReviewDecision、ReleasePlan 定义状态图。
- 每个状态图包含：
  - 初始状态；
  - 允许命令；
  - 转移前置条件；
  - 幂等语义；
  - 终态；
  - 取消、失败、重试、过期和人工介入路径；
  - 审计事件。
- 状态转移必须集中管理，不允许后续散落在 Controller、React 页面或 Provider Adapter。

### R6. API Contract Baseline

- 定义首发 API 命名空间：
  - 学员：`/api/v1/newcomer-training/**`；
  - 管理：`/api/v1/admin/newcomer-training/**`。
- 明确资源、命令、查询、分页、筛选、错误结构、幂等键、ETag/version、权限和审计语义。
- 定义 Journey Projection、Activity Workspace、Task Status、Evidence Dossier 和 Admin Queue 的 ViewModel 契约。
- 禁止前端继续直接消费跨域 ORM 形态或自行拼装达标结论。
- 明确旧 API 的删除清单和替代点；不设计永久转发 Facade。

### R7. Event Contract Baseline

- 冻结至少以下公开领域事件：
  - `ActivityOutcomeRecorded`；
  - `CompetencyEvidenceUpdated`；
  - `JourneyProgressChanged`；
  - `ReadinessReviewRequested`；
  - `ReviewDecisionRecorded`；
  - `RetrainingAssigned`；
  - `EnrollmentRevisionMigrated`。
- 每个事件定义 schema version、producer、consumer、事务边界、幂等键、重放语义和敏感字段规则。
- 明确事件通过同库 Outbox 可靠发布；Redis 或进程内队列不得成为事实权威。

### R8. Permission Matrix

- 冻结学员、培训负责人、内容编辑、训练管理员、系统管理员的能力矩阵。
- 明确组织隔离、对象级权限、跨组织拒绝、人工复核权限、发布权限、Prompt 高风险权限和重评权限。
- 权限以后端策略为权威；前端只消费 capability projection。
- 高风险命令必须定义 preview / confirm / audit / rollback 或 compensation。

### R9. AI Governance Contract

- Prompt 集中管理、修订化、可发布、可回滚。
- 模型、temperature、token、timeout、retry、rate limit 和预算配置化。
- AI 输出区分事实、计算、推断和建议。
- 所有正式结果必须由确定性规则或人工命令落库；模型原始输出不能直接改正式状态。
- 定义 fake provider、contract test、gold set 和降级响应的最低要求。

### R10. Migration And Clean-Cut Plan

- 盘点旧表、旧路由、旧 Facade、旧 seed、旧 Activity Handler、直接 Provider 调用和重复前端入口。
- 对每一项记录：
  - 新权威；
  - 数据是否保留；
  - 转换脚本；
  - 验证查询；
  - 删除时点；
  - 回滚或重建方式。
- 允许开发环境清库重建，但 migration 必须可在空库和具有旧开发数据的库中给出明确结果。
- 禁止长期双写；每个切片建立新权威后删除对应旧写入。

### R11. Quality And Verification Baseline

- 更新后端、前端、API、AI、安全和测试 Spec。
- 定义架构 Guard、OpenAPI diff、状态机测试、权限矩阵测试、Migration 测试和 E2E 门禁。
- 定义父任务性能 SLO 的测量口径与测试环境。
- 定义每个切片必须运行的最小命令和最终全量验证命令。

## Deliverables

- 产品边界 ADR。
- 领域模型与模块边界 ADR。
- 路径修订与 Enrollment 冻结 ADR。
- AI 治理与持久化任务 ADR。
- 更新后的领域词典、架构、API、安全、测试、AI Governance 文档。
- 状态机与权限矩阵。
- 数据与旧权威迁移清单。
- 架构依赖白名单和自动化 Guard 设计。
- 后续切片可直接引用的命令、事件、错误和 ViewModel 契约。

## Acceptance Criteria

- [x] 所有现有 Spec 中关于 Phase/Module、Realtime 首发、Enrollment 自动迁移的冲突已消除。
- [x] 父任务、ADR、Spec、API 文档和领域词典对核心对象使用同一命名与层级。
- [x] 每个核心对象只有一个明确写权威。
- [x] 五类首发活动的 ActivityDefinition、Attempt、Outcome 契约完整。
- [x] 所有正式状态转移都有命令、前置条件、幂等和审计语义。
- [x] 学员与管理 API 的资源边界、错误结构、权限和版本策略可直接生成测试。
- [x] 旧 API、旧表、旧写入和旧任务的保留/迁移/删除矩阵完整，无“以后再看”的模糊项。
- [x] 已冻结机器可读的 Guard detector、失败码、允许边、临时例外、Owner、到期日和 failure probe；Slice 8 按父任务执行计划实现并证明其能识别跨模块 ORM、shared kernel 反向依赖、动态 Activity 导入和业务模块直连 AI Provider。本切片不得把设计合同伪报为已启用 Guard。
- [x] 文档明确本切片不实现业务功能，后续切片不得绕过契约自行发明结构。
- [x] 所有变更均有 CodeGraph 事实或现有代码引用，没有虚构路由、数据或状态。

## Definition Of Done

- 文档互相链接且无相互矛盾。
- 关键 ADR 已被后续各子任务引用。
- `task.py validate` 通过。
- 相关文档 lint、链接检查或仓库既有文档校验通过。
- 执行计划、迁移矩阵、权限矩阵和状态机由至少一次交叉复核确认。
- 未解决事项只允许是不会改变产品边界、数据权威或安全模型的实现细节。

## Out Of Scope

- 不实现新的业务页面、API 或数据库表。
- 不迁移生产数据。
- 不接入真实 AI、ASR 或对象存储 Provider。
- 不实现 Realtime 客户语音对练。
- 不为了文档统一而重构无关模块。

## Risk And Rollback

- 风险等级：P1。
- 最大风险是文档与真实代码脱节；所有结论必须基于 CodeGraph 和源码证据。
- 本切片只改契约与文档，可通过版本控制回滚。
- 若发现已有用户可见行为必须保留，先记录为迁移约束，不静默恢复永久兼容层。
