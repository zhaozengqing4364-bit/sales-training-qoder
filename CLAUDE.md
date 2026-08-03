最多使用1个agent
所有的回复到要使用中文！！！！
优先级：
1. codegraph_explore：理解功能链路、业务流程、架构区域
2. codegraph_node：查看某个 symbol 或文件的源码和调用关系
3. codegraph_search：定位 symbol
4. codegraph_callers：查调用点
5. codegraph impact / affected：改动前后做影响分析和测试选择
禁止只以“当前能跑”为完成标准。
### 上下文内完成原则（In-Flow Completion）

业务系统不应为了数据模型完整而打断用户当前任务。

当用户在完成主流程时遇到缺失数据、缺失关联对象、缺失角色、缺失配置或缺失上下文，系统应优先在当前页面、弹窗、抽屉或内联区域提供就地处理能力，而不是要求用户跳转到另一个模块。

默认交互模式：

- 从已有数据中选择；
- 快速新建最小必要对象；
- 自动关联到当前上下文；
- 后台同步到标准数据模型；
- 支持稍后补充或指派他人补充；
- 保留权限校验、去重检查、审计记录和失败反馈。

前台体验要轻，后台治理要稳。

禁止为了维护数据表，让用户离开当前任务流程去另一个页面补资料后再回来。

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tools** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them. `codegraph_node` returns one symbol's source + callers, or reads a whole file with line numbers. If the tools are listed but deferred, load them by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` and `codegraph node <symbol-or-file>` print the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->
# Finding Your Unknowns — Working Guidelines

> Derived from [A Field Guide to Fable: Finding Your Unknowns](https://x.com/trq212/article/2073100352921215386) by Thariq (Anthropic).
> Core insight: **the map is not the territory.** The map is the user's prompt, rules, and acceptance criteria; the territory is the real codebase and its actual constraints. The gap between them is made of *unknowns*. Every unknown forces you to guess, and accumulated wrong guesses are how long tasks go badly off course.

**Tradeoff:** These guidelines bias toward discovery over speed. For trivial tasks (typo-level fixes), use judgment and skip the ceremony.

## The Four Kinds of Unknowns

Every task the user gives you contains four kinds of information:

1. **Known knowns** — what the prompt explicitly states.
2. **Known unknowns** — what the user knows they haven't figured out yet.
3. **Unknown knowns** — standards the user holds but never wrote down because they felt obvious. They will only recognize them when they see your output ("no, not like that").
4. **Unknown unknowns** — options, risks, and possibilities the user hasn't considered at all.

Your job is not to take the prompt and grind. Your job is to surface types 2, 3, and 4 — before, during, and after implementation. **Every blindspot pass, brainstorm, interview, and prototype is a cheap way to find a problem before it becomes expensive to fix.**

## Pre-implementation

### 1. Blindspot Pass

When the user enters unfamiliar territory (a new module, an unfamiliar technology, a type of work they haven't done):

- Quickly survey the codebase/domain and list what the user likely doesn't know they don't know.
- Tell them what "good" looks like in this domain, what the historical potholes are, and what questions they should be asking.
- The goal is to teach the user to prompt you better — not to make decisions for them.

### 2. Brainstorm & Prototype

When the task involves "I'll know it when I see it" criteria (visual design, interaction, direction):

- Produce several clearly different options or mock prototypes first (single HTML file, fake data). **Do not touch real code.**
- Let the user react to something concrete instead of imagining from a description.
- Why: reversing a wrong direction later costs far more than reviewing a mock now. Small spec changes can cause drastically different implementations.

### 3. Interview

When ambiguity remains after brainstorming, interview the user:

- One question at a time.
- Prioritize questions whose answers would change the architecture. Don't spend the question budget on trivia.

### 4. References

When the user struggles to describe what they want, proactively ask: "Is there an existing implementation/component/library that looks like what you want? Point me at it." Source code is the best reference, even in a different language.

### 5. Implementation Plan

Before executing a complex task, present an implementation plan for review:

- Lead with the parts the user is most likely to change: data models, type interfaces, user-facing behavior.
- Bury the mechanical refactoring at the bottom — they trust you on that part.

## During implementation

### 6. Implementation Notes

While executing a long task, maintain a temporary `implementation-notes.md`:

- When an edge case forces you off the plan: pick the conservative option, log it under "Deviations", and keep going.
- Never silently change direction — every deviation must leave a trace so the user can fix the map next time.

## Post-implementation

### 7. Explainer & Quiz

After a large change, when the user asks (or the change is far bigger than they expected), produce a change report:

- Include the context, the intuition, what was done, and why.
- End with a quiz about the change. The user truly understands it only when they pass.
- Why: a diff gives only shallow understanding — much of the behavior depends on existing code paths. Merging without understanding is how future unknowns accumulate.

## Reminders

- Too-specific instructions make you follow orders when a pivot is warranted; too-vague instructions make you guess with "industry best practices" that may not fit this project. When you feel this tension, stop and ask instead of pushing through.
- When a long-horizon task comes back wrong, the likely cause is not model capability — it's undefined unknowns. Instead of retrying, bring the user back through the unknown-discovery process.
- # AGENTS.md — AI 开发协作规范

## 0. 适用范围

本文件是仓库级长期规则，只保留高频、稳定、必须遵守的工程底线。项目细节放入专题文档：

- `docs/architecture.md`：架构边界、模块职责
- `docs/domain-glossary.md`：领域词、用户语言、禁用术语
- `docs/uiux.md`：页面契约、信息架构、状态规范
- `docs/api.md`：API 契约、错误码、分页、兼容性
- `docs/security.md`：权限、安全、敏感数据、审计
- `docs/testing.md`：测试策略与运行命令
- `docs/ai-governance.md`：AI、Prompt、模型、工具调用治理
- `docs/adr/`：架构决策记录

更深目录的 `AGENTS.md` 优先于本文件。若规则冲突，先说明冲突，再按“更具体规则优先、用户目标优先、安全与数据底线不可突破”执行。

## 1. 输出与协作

- 所有回复、计划、错误解释、交付说明默认使用中文。
- 不输出无价值过程流水账；只给计划、关键发现、阻塞、结果和验证。
- 不把内部思考、工具调用记录、模型局限当成交付内容。
- 非阻塞不确定性：基于合理假设继续，并在交付说明标明假设。
- 阻塞不确定性：提出最少必要问题。
- 默认最小必要改动；禁止顺手重构无关代码。
- 失败必须显眼；禁止吞异常、静默跳过、伪造成功。

## 2. 工作模式

- **Simple**：单文件、小改动、明确 bug、不涉及权限/状态/API/数据库/核心 UI。直接改，最小实现，说明验证。
- **Standard**：普通功能或跨文件改动。先简短计划，读相关链路，明确成功标准，实现后验证。
- **Team**：架构、大重构、复杂 bug、多模块/权限/数据/AI/测试联动，或用户要求多 agent。主 agent 负责决策和交付，子 agent 只做探索与复核，结论必须有代码证据。

复杂任务不得跳过计划、影响分析和验证。高风险任务不得直接执行破坏性操作。

## 3. CodeGraph First

仓库根目录存在 `.codegraph/` 时，理解代码必须优先使用 CodeGraph：

1. `codegraph_explore`：理解功能链路、业务流程、架构区域
2. `codegraph_node`：查看 symbol 或文件源码与调用关系
3. `codegraph_search`：定位 symbol
4. `codegraph_callers`：查看调用点
5. `codegraph impact / affected`：改动前后做影响分析和测试选择

没有 `.codegraph/` 时跳过，不自行创建索引。禁止未读调用者就修改共享函数，禁止在已有同类实现旁新增重复实现。

## 4. 开发前检查

写代码前快速确认：

- 用户是谁，要完成什么任务，成功标准是什么。
- 涉及哪些页面、API、状态、权限、数据结构。
- 哪些是稳定代码逻辑，哪些是可配置业务规则。
- 是否会泄露测试数据、工程字段、内部术语。
- 如何验证、如何回滚或降级。

若现有代码无法确认完整体系，优先复用现有结构；没有现有体系时，以最小侵入方式预留扩展点，避免规则散落。

## 5. 产品与前端

前端按任务组织，不按数据库对象组织。页面必须让用户 3 秒内知道当前任务、主操作和下一步。

新增或重构业务页面必须具备页面契约：目标用户、使用场景、用户任务、主操作、核心信息、数据来源、加载/空/错误/无权限/成功状态、禁止展示信息、埋点或审计事件。

界面必须使用用户语言。普通用户界面不得默认展示：`E2E`、`test`、`mock`、`seed`、`Phase*`、`ToolExecutor`、`Prompt`、`traceId`、`workflow`、`raw JSON`、数据库主键、原始枚举、内部错误码。技术细节只能放在管理员调试、审计详情、开发者模式或日志系统。

API 数据进入页面前必须映射：`API DTO -> Domain Model -> ViewModel -> UI Component`。列表、风险、待办必须先去重、聚合、分组、排序、解释，再展示下一步动作。

业务系统必须遵守上下文内完成原则：用户在主流程中缺少数据、关联对象、角色、配置或上下文时，应优先在当前页面、弹窗、抽屉或内联区域完成选择、快速新建、自动关联、稍后补充、权限校验、去重、审计和失败反馈；不得要求用户离开当前任务去其他模块补资料后再回来。

UI 必须覆盖：loading、empty、error、success、disabled、readonly、permission denied、partial/stale data、submitting、retrying。表单必须覆盖 label、helper text、校验错误、dirty、重复提交防护、服务端错误映射、未保存离开提醒。

优先使用现有设计系统、组件库、token 和布局模式。禁止随机渐变、模板 dashboard、无业务意义大卡片、空泛营销文案、多个主操作抢焦点。新增 UI 至少满足基础可访问性：键盘可用、焦点可见、表单有 label、图标按钮有 accessible name、颜色不是唯一信息来源。

## 6. 后端与数据

后端守住数据一致性、权限边界、状态流转、事务、审计、API 契约、配置治理和错误可定位。

推荐分层：`controller/route` 只处理协议；`application service` 编排用例、事务、权限和状态；`domain service` 放核心规则；`repository/dao` 负责数据访问；`policy/permission` 做对象级权限；`state machine` 集中状态；`rules/config/dictionary` 管理规则、配置和枚举；`audit/log/events` 记录关键行为。

禁止 controller 混合权限、状态、配置、文案和数据库操作。禁止只靠前端隐藏按钮做权限。禁止状态流转散落在多个函数。禁止业务阈值、评分、排序、开关、模板硬编码在深层业务代码。

API 必须稳定、兼容、错误结构统一。新增字段保持向后兼容；删除或改变语义必须有废弃期。分页、排序、筛选规则统一。前端展示字段与内部工程字段隔离。

涉及 schema、migration、批量修复时，必须考虑旧数据、影响条数、可重复执行、dry-run、锁表风险、回滚或补偿方案。不得默认手动改生产数据。

关键写入必须考虑事务、幂等、重复提交、并发、外部超时、重试安全、部分失败补偿和用户可见结果。

## 7. 安全、权限、可观测性

涉及登录、权限、文件上传、导出、Webhook、第三方接口、AI 工具调用、管理后台、隐私数据、批量操作时，必须做轻量安全分析。

底线：后端权限校验、对象级权限、输入校验、输出转义、敏感数据脱敏、密钥不入库/日志/前端、管理员操作留痕、高风险操作可预览/确认/回滚。

关键功能必须记录 requestId/traceId、结构化日志、业务事件、接口耗时、外部调用结果、失败原因、异常堆栈、审计记录和必要指标。日志不得输出密码、token、密钥、身份证、手机号等敏感信息。

## 8. AI 功能治理

凡涉及 AI 助手、评分、推荐、总结、工具调用，必须可控、可追踪、可降级。

- Prompt 集中管理并版本化。
- 模型、temperature、max tokens、timeout、retry、rate limit 配置化。
- AI 输出必须有依据、不确定性、人工确认、可编辑和失败兜底。
- 高风险建议不得自动执行。
- AI 工具调用必须有 input schema、权限校验、对象范围校验、幂等键、dry-run、preview、confirm、audit log、timeout、rate limit、回滚或补偿。
- 禁止把 AI 生成内容标记为已验证事实。

## 9. 风险分级

- **P0**：生产数据破坏、认证授权、支付资金、合同订单、大迁移、破坏性 API、大重构、AI 自动高风险动作。必须说明影响、回滚、验证、dry-run 或灰度。
- **P1**：数据库结构、核心状态机、核心接口/页面、管理规则、多模块联动。必须说明兼容性、配置、权限、状态影响和回归路径。
- **P2**：普通功能、页面、接口、非核心业务规则。标准实现和验证。
- **P3**：文案、样式、小 bug。最小改动，不引入新抽象。

## 10. 测试与验证

不得只说“已测试”。必须说明覆盖场景、命令和结果。

优先级：自动化测试、类型检查、lint、构建、单测、集成测试、E2E、手工关键路径、权限边界、状态流转、配置异常、回归风险。

Bug 修复优先新增复现测试。核心流程至少覆盖一条关键路径。无法测试时必须说明原因和残余风险。

## 11. ADR、依赖、发布

以下情况必须新增或更新 ADR：新技术栈、核心数据模型、权限模型、状态机、配置中心、后台管理机制、部署方式、重大重构、影响长期维护成本的设计决策。

不得为小问题引入新依赖。新增依赖必须说明解决的问题、替代方案、维护状态、安全/license 风险、包体积/构建/部署影响和移除路径。

高风险功能必须支持 feature flag、灰度、快速关闭、回滚或补偿、失败降级和可观测指标。长期 feature flag 必须清理。

## 12. 交付说明

简单任务可精简，但不得只回复“已完成”。交付说明至少包含：

- 本次完成
- 主要改动
- 验证结果
- 未验证项及原因
- 风险等级
- 发布与回滚方式

涉及 UI、权限、状态、API、数据、AI、配置、migration 时，必须补充对应影响、兼容性、审计和回归路径。

## 13. Definition of Done

完成必须同时满足：

- 用户路径清晰，主操作明确，状态完整。
- 普通用户界面不泄露测试数据、工程字段和内部术语。
- API 契约稳定，权限以后端校验为准，对象级权限明确。
- 状态流转集中管理，可调整规则不散落。
- 配置有默认值、校验和兜底。
- 关键写入有事务、幂等、并发处理和审计。
- 日志和错误可定位且不泄露敏感信息。
- 改动范围可解释，与现有风格一致。
- 验证证据充分，风险和回滚路径明确。
- 无必要新依赖，无无关重构，未完成事项已记录。

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `zhaozengqing4364-bit/sales-training-qoder`. See `docs/agents/issue-tracker.md`.

### Triage labels

The repository uses the five default canonical triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

The repository uses a single-context domain documentation layout. See `docs/agents/domain.md`.
