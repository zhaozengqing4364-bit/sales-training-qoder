# 新人销售基础训练目标架构合同

> 状态：Accepted contract。Foundation 运行时与首发发布门禁已完成；2026-07-20 复核确认“管理员内容生产与 Legacy 真实内容迁移”尚未闭环，不能再以 Seed、路由存在或可绑定已有修订作为 Authoring 完成证据。更正见 [`2026-07-20-foundation-authoring-and-legacy-migration-authority.md`](../adr/2026-07-20-foundation-authoring-and-legacy-migration-authority.md)。

## 1. 模块地图与唯一写权威

| 模块 | 唯一写权威 | 不拥有 |
|---|---|---|
| `newcomer_training` | `Path`、`PathRevision`、`Stage`、`ActivityDefinition`、`Cohort`、`Enrollment`、`ActivityAttempt` 通用信封、Gate、Journey | 活动详情、AI 输出、最终复核决定 |
| `learning` | `SourceDocument`/Revision、`LearningUnit`/Revision、`QuestionCandidate`、`QuestionRevision`、`QuizRevision` 与 Quiz 详情 | Path、通用 Attempt、能力结论 |
| `audio_assessment` | `AudioSubmission`、音频 Artifact 引用、`TranscriptRevision`、质量报告、`ScoreOutcomeVersion` 与音频 Outcome | Provider 路由、通用 Attempt、最终达标 |
| `ai_coach` | `AiCoachSession`、Turn、`TrainingCard`、Response、Coach Outcome、`RemediationCycle` | 通用聊天、模型配置、最终达标 |
| `competency_evidence` | Canonical Competency、Mapping、不可变 `CompetencyEvidence`、有效性/替代关系 | Path 进度、人工决定 |
| `readiness` | `ReadinessDossier`、Snapshot、Review Queue、`ReviewDecision`、Appeal、`RetrainingAssignment` | 活动明细、Provider、证据事实改写 |
| `task_runtime` | `DurableTask`、租约、进度、重试与死信 | 业务最终结果 |
| `ai_platform` | Invocation、Provider/模型路由、预算、血缘、Schema 校验 | 业务 Rubric、通过规则、正式状态 |
| `identity_access` | Organization、Team、Actor、Capability、对象范围策略 | 业务对象状态 |
| `storage` | 上传会话、对象引用、签名和保留策略 | 训练结果 |
| `configuration_governance` | 配置工作修订、发布、回滚、影响记录 | 业务对象本身 |
| `observability` | Trace、日志、指标和审计基础设施 | 业务事实 |
| `shared_kernel` | ID、时间、Actor/Organization 引用、Result/Error、事务与 Outbox 基础类型 | ORM 注册表、业务 Service、Provider、配置 Facade |

一个业务对象只有表中所列模块可以写；其他模块只保存稳定 ID、已发布 revision ID、内容哈希或本模块拥有的不可变快照。跨域关系不得藏在无约束 JSONB 中。

## 2. 依赖与内部层次

```text
delivery -> application -> domain/contracts + ports
adapters -> ports/domain
application_root -> adapters + application
```

- Controller/route 只做协议解析、认证上下文和响应映射。
- Application 层拥有用例、权限调用、事务边界、状态命令、幂等和 Outbox。
- Domain 层拥有状态机、不变量、确定性评分与 Gate。
- Adapter 实现 Port；业务模块不得跨域导入 ORM、Repository 或内部 Service。
- 组合根是唯一可同时依赖多个具体 Adapter 的位置。
- `shared_kernel` 和 `ai_platform` 不得反向依赖业务模块。

机器规则、临时例外、Owner 和接入时点见 [`newcomer-foundation-guard-policy.yaml`](newcomer-foundation-guard-policy.yaml)。这些规则已接入 `architecture_dependency_guard.py` 与最终质量门禁；新增违规和过期例外均 fail closed。

## 3. 核心聚合不变量

### Path / PathRevision / Stage / ActivityDefinition

- `PathRevision` 工作态可编辑，发布后内容、顺序、资源引用与策略快照不可变。
- 结构只有 `PathRevision -> Stage -> ActivityDefinition`；`Phase`、`Module` 不进入新 Schema。
- 首发活动封闭联合只有 `lesson`、`quiz`、`audio_assessment`、`ai_coach`、`assignment`。
- `ActivityDefinition.config` 是有类型 JSONB；未知字段、可执行代码、组件名、URL、脚本和 Provider 密钥拒绝。
- 发布必须经 `ReleasePlan` 校验依赖闭包；Realtime 不能出现在首发修订。

### Cohort / Enrollment

- Cohort 必须绑定一个已发布 PathRevision。
- 一个组织内，同一学员对同一 Path 只有一个非终态 Enrollment。
- Enrollment 默认冻结 revision；发布和 Journey 读取都不得自动移动。
- 迁移只能通过 `MigrateEnrollmentRevision` 预览 + 确认命令，保留 Attempt 并发版本与审计。

### ActivityAttempt / ActivityOutcome

- Attempt 冻结 ActivityDefinition、PathRevision 和活动需要的资源修订。
- `(organization_id, idempotency_key, command_type)` 唯一；技术重试返回同一逻辑写入。
- 活动模块写详细记录并返回标准 `ActivityOutcome`；Journey 只引用 Outcome，不跨表推断。
- 重评追加 Outcome/Score 版本；不得覆盖已发生的提交、AI 原始结果或人工决定。

### 内容、音频、Coach、Evidence 与 Readiness

- SourceDocument 与 LearningUnit 分离；AI 不修改来源资料。
- Candidate 与 Question 分离；候选审核通过不等于发布。
- TranscriptRevision 与 ScoreOutcomeVersion 追加式保存；低置信度转写不能直接正式评分。
- Coach 只执行白名单训练卡，学员输入先持久化再调用 AI，补练轮次有上限。
- CompetencyEvidence 是不可变事实；ReadinessDossier 是派生档案；ReviewDecision 是人工正式命令。
- `foundation_ready` 只能由确定性 Gate 满足后的人工作出；AI 不能直接授予。

## 4. 稳定接口

```python
class ActivityRuntime(Protocol):
    type_key: ActivityType
    async def project(self, context: ActivityExecutionContext) -> ActivityProjection: ...
    async def execute(self, command: ActivityCommand, context: ActivityExecutionContext) -> ActivityExecutionAccepted: ...
    async def reconcile(self, attempt: ActivityAttemptSnapshot, evidence: ActivityEvidenceSnapshot) -> ActivityOutcome: ...

class ActivityDefinitionCompiler(Protocol):
    async def validate(self, definition: ActivityDefinition) -> tuple[ValidationIssue, ...]: ...
    async def preview(self, definition: ActivityDefinition, actor: ActorContext) -> ActivityPreview: ...
    async def compile(self, definition: ActivityDefinition) -> CompiledActivityDefinition: ...

class TaskRuntimePort(Protocol):
    async def enqueue(self, command: TaskCommand) -> TaskReference: ...
    async def request_cancel(self, task_id: str, actor: ActorContext) -> TaskProjection: ...
    async def get(self, task_id: str, viewer: ActorContext) -> TaskProjection: ...

class AIInvocationPort(Protocol):
    async def invoke(self, request: GovernedAIRequest) -> AIInvocationResult: ...

class CompetencyEvidenceWriter(Protocol):
    async def append(self, evidence: NewCompetencyEvidence) -> CompetencyEvidenceRef: ...
```

这些是调用者和契约测试的外部 Seam。具体 Repository、Provider、队列与 ORM 是内部 Adapter，不得出现在上述 Interface。

## 5. 五类活动合同

| 类型 | 定义冻结 | 详细写权威 | 完成条件 | 失败语义 |
|---|---|---|---|---|
| `lesson` | LearningUnit revision、完成策略 | `learning` | 确定性阅读/确认条件满足 | 内容缺失阻断，不伪造完成 |
| `quiz` | QuizRevision、题目/答案/评分合同 | `learning` | 客观题规则 + 异步简答结果 + 红线 Gate | AI 失败保留答案并进入 `needs_review` |
| `audio_assessment` | 任务、材料、评分方案、限制 | `audio_assessment` | Validate/Transcribe/Score/Finalize 产生 Outcome | 技术质量失败不等于能力不通过 |
| `ai_coach` | Profile、Prompt、模型路由、Rubric、卡片/轮次上限 | `ai_coach` | 必做检查点与掌握 Gate 满足 | 输入保留；缺合同 fail closed；超限转人工 |
| `assignment` | 三段异步客户场景录音脚本、每段目标、材料与评分/审核合同 | `audio_assessment` 的异步场景 Adapter（Journey 仍以 assignment 类型编排） | 三段均形成有效 Outcome，并按配置完成规则/人工审核 | 缺段、低置信度或未审核不得完成；不允许泛化为任意文本/文件作业 |

## 6. 当前事实与迁移边界

新人首发消费者已使用 `PathRevision -> Stage -> ActivityDefinition`、冻结 Enrollment、统一 Activity Workspace/Command、持久任务、受治理 AI、持久录音流水线和结构化 Coach。旧 `sales_trainer` Phase/Module、自由聊天 Coach、同步/进程内音频 writer 和新人 Realtime 入口不再是首发写权威；仓库内其他产品域的 Legacy 能力不能被新人路径重新引用。

Competency Evidence/Readiness 单写、ReleasePlan/统一管理工作台、性能/可访问性门禁及 Foundation Legacy 消费者清理均已完成。删除结果、明确保留项和回滚边界见 [`newcomer-foundation-clean-cut.md`](newcomer-foundation-clean-cut.md)。

上述“统一管理工作台已完成”只证明首发运行和已预置资源的管理投影；不表示 PPT/Demo、多媒体内容、手工/导入题库、录音材料/评分、Coach Profile、异步场景的管理员 CRUD 已完成。Legacy 新人写消费者虽已退出 v2 运行链路，但当前真实 Legacy 内容仍须按只读清单和显式迁移计划处理。

## 7. 内容生产资源联合与生命周期补充（2026-07-20）

管理员 Authoring 的封闭业务资源联合为：

```text
source_document | learning_unit | question | quiz |
audio_material | scoring_scheme | coach_profile | scenario
```

- `prompt`、模型路由、Provider 与密钥不是普通内容资源；它们由 AI 治理单独授权，只能以已发布 exact refs 进入评分或 Coach 修订。
- Source 可用 `content_kind` 表达 document、slide deck、Demo 视频/受控链接、script、example audio 和 attachment；不新增万能媒体 JSON 表。
- `audio_material`、`scoring_scheme`、`scenario` 与 `coach_profile` 必须有稳定逻辑身份及明确 working/published pointers。当前只有 revision row 的派生指针属于 Authoring 缺口，不得宣称为完整生命周期。
- 每个逻辑资源依次执行 create/save working、validate、review/approve（适用时）、ReleasePlan publish、supersede/archive。审核通过不等于发布。
- Path 可在同一准备期绑定合法 working ref，但只有 ReleasePlan exact dependency closure 全部通过后才能正式生效。
- 已发布修订不可变；被 Path、Attempt、Outcome 或 Evidence 引用的历史版本永久保留。

资源 API、错误语义和 capability 矩阵见 [`../api-contract/newcomer-training-v2.md`](../api-contract/newcomer-training-v2.md) 与上述 2026-07-20 ADR；Legacy 字段映射见 [`newcomer-foundation-legacy-authoring-mapping.md`](newcomer-foundation-legacy-authoring-mapping.md)。
