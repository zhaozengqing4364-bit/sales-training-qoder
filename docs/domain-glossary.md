# 新人销售基础训练领域词典

> 状态：2026-07-16 起为目标产品权威。它定义业务语言，不声明目标代码已经上线。

## 路径与执行

**训练路径（`Path`）**：可持续演进的训练计划身份。_避免：课程树、Workflow。_

**训练路径修订（`PathRevision`）**：某一时点不可变的路径内容；工作修订发布后冻结。_避免：最新配置。_

**训练阶段（`Stage`）**：路径中的业务顺序与阶段结果，直接包含活动定义。_禁用：Phase、Module（仅可描述 Legacy 代码）。_

**训练活动定义（`ActivityDefinition`）**：可执行训练活动的冻结定义；首发仅 `lesson`、`quiz`、`audio_assessment`、`ai_coach`、`assignment`。其中 `assignment` 专指三段异步客户场景录音，不是任意文本/文件作业。_禁用：Realtime Activity（首发）、通用 Assignment。_

**学员路径（`Enrollment`）**：学员在 Cohort 中对一个已发布 `PathRevision` 的冻结绑定。_禁用：自动升级 Enrollment。_

**训练尝试（`ActivityAttempt`）**：一次学习尝试的通用生命周期信封；技术重试不新建 Attempt，学习重试新建 Attempt。

**活动结果（`ActivityOutcome`）**：活动模块产生的标准化结果与证据引用；重评追加版本，不覆盖历史。

## 内容与题目

**来源资料（`SourceDocument`）**：可追溯授权来源及其不可变修订。

**内容类型（`content_kind`）**：来源资料的封闭呈现类型，包括文档、幻灯片、Demo 视频/受控链接、讲解稿、示范音频和附件；它不是任意 HTML/脚本或万能 JSON 资源。

**学习单元（`LearningUnit`）**：面向训练目的精编的内容修订，不等同于原始资料。

**候选题（`QuestionCandidate`）**：AI 或导入产生、尚未成为正式题目的审核对象。

**题目修订（`QuestionRevision`）**：经审核的题目工作/发布版本；审核通过不等于发布。

**试卷修订（`QuizRevision`）**：冻结题目、顺序/抽题策略、答案与评分合同的测验版本。

**内容审核（`approved`）**：确认内容可进入发布准备的人工状态。它不改变 published pointer，且不等于正式发布。

## 音频、教练与达标

**录音提交（`AudioSubmission`）**：原始音频及处理链路的业务主语。

**录音讲解材料（`AudioMaterial`）**：PPT/Demo 等异步讲解任务的目标、来源、必讲要点、参考结构与学员说明的稳定逻辑资源；只引用受治理内容的 exact revision。

**评分方案（`ScoringScheme`）**：维度、权重、阈值、红线、证据要求、人工复核和已发布 AI 合同引用的稳定逻辑资源；普通界面不等同于 Prompt 编辑器。

**异步客户场景（`Scenario`）**：由 `discovery`、`objection`、`commitment` 三段任务组成的非实时录音训练资源。_禁用：把它称为实时对练。_

**转写修订（`TranscriptRevision`）**：追加式 ASR 或获批更正结果，含分段、置信度与来源。

**评分结果版本（`ScoreOutcomeVersion`）**：一次评分或重评的不可变结果版本。

**AI 教练会话（`AiCoachSession`）**：围绕明确训练目标和白名单训练卡的结构化会话。_避免：通用聊天。_

**训练卡（`TrainingCard`）**：AI Coach 中有类型、可校验、可持久化的练习单元。

**补练周期（`RemediationCycle`）**：针对薄弱能力的有限轮次训练；达到上限转人工。

**能力证据（`CompetencyEvidence`）**：带来源、血缘、置信度和有效性的不可变事实。

**达标档案（`ReadinessDossier`）**：汇总证据、完整性、趋势、风险与人工决定的单一读取权威。

**复核决定（`ReviewDecision`）**：培训负责人基于证据作出的正式结论。_禁用：AI 自动认定达标。_

**补练任务（`RetrainingAssignment`）**：绑定薄弱能力、来源证据和目标的行动对象。

**发布计划（`ReleasePlan`）**：对路径及依赖修订执行预览、校验、影响分析和原子发布的对象。

**工作修订（`working revision`）**：逻辑资源当前可编辑版本；可参与同一发布计划的依赖准备，但在审核、校验和 ReleasePlan 完成前不对未来学员正式生效。

**内容生产（`Authoring`）**：管理员对逻辑资源执行创建、保存工作修订、校验、审核、比较、查看引用、归档和提交 ReleasePlan 的完整流程。Seed 已有、路由存在或能绑定已有修订都不等于 Authoring 完成。

**能力（`Competency`）**：跨活动保持稳定、可由证据支持和人工复核的训练能力定义；它不是某次 Activity、题目、总分或 AI 自由生成的弱项标签。

首发标准能力固定为七项：产品知识、客户理解、需求发现、价值表达、异议处理、流程与合规、沟通结构。内部 stable key 只用于合同和持久化，普通用户界面始终使用这些中文名称和可行动说明。

**发布（`Publication`）**：通过 ReleasePlan 将 exact working revisions 及依赖闭包原子提升为面向未来使用的已发布版本。发布不自动迁移既有 Enrollment、不重评历史结果，也不覆盖旧修订。

**基础训练达标（`foundation_ready`）**：培训负责人基于有效 ReadinessDossier 记录的正式 ReviewDecision，仅表示首发范围内的基础训练达标；不表示真实客户场景、岗位胜任或业绩预测，AI/规则不能单独授予。

## 用户语言规则

普通用户界面使用上述中文词，不显示 `Prompt`、Provider、`traceId`、workflow、raw JSON、数据库 ID、原始枚举、Mock、Seed 或内部错误码。工程文档提到 Legacy 的 Phase、Module、Realtime 或自动迁移时，必须同时标明其非目标状态。
