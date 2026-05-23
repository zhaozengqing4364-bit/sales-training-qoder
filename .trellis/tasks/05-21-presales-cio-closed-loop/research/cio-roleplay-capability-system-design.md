# CIO 虚拟客户角色扮演能力系统设计

## 1. 目标

当前目标不是给制造业 CIO 多写几句提示词，而是让系统稳定生成一个可训练、可追问、可复盘、可管理的虚拟客户。

这个虚拟客户需要同时具备：

- 清晰身份：知道自己是谁、职位是什么、权责边界是什么。
- 虚拟公司：有公司规模、业务背景、组织结构、现有系统和历史项目。
- 真实需求：有显性痛点、隐藏压力、预算条件、决策链和成功指标。
- 角色行为：能克制回答、能追问、能质疑空泛承诺、能按条件披露信息。
- 训练反馈：能在对话中表现为真实客户，在报告中转化为可解释复盘。
- 管理治理：能通过后台配置、发布门禁、快照、审计和回退长期维护。

本设计分为两个维度：

1. 不新增模块：如何用好现有资产，实现全面深入的角色背景和扮演能力。
2. 新增模块代码：如果要长期治理和稳定运行，应该新增什么最小模块。

## 2. 当前系统已经具备的能力

### 2.1 Persona：实时人格合同

`Persona` 是平台级 AI 对话人格，是实时 WebSocket 对练中角色提示词、知识库绑定和行为策略的事实源。

当前可承载：

- `persona_policy.system_prompt`
- `persona_policy.knowledge_base_ids`
- `persona_policy.tool_policy`
- `persona_policy.customer_pressure`
- `traits`
- `behavior_config`
- `scoring_weights`
- `tts_config`
- `status`

它适合承载“实时运行时必须强约束的压缩角色合同”，不适合承载全部公司剧本。

### 2.2 CaseItem：公司与需求剧本

`CaseItem` 是课程闭环中的业务剧本，适合承载：

- 行业。
- 公司档案。
- 客户角色。
- 显性痛点。
- 异议。
- 隐藏信息。
- 成功标准。
- 信息披露策略。

当前模型已经有这些字段：

- `industry`
- `company_profile`
- `customer_role`
- `pain_points`
- `objections`
- `hidden_information`
- `success_criteria`
- `allowed_disclosure_policy`
- `status`
- `version`
- `content_hash`

这说明系统已经具备虚拟公司和真实需求的配置基础。

### 2.3 RoleProfile：客户行为画像

`RoleProfile` 是客户行为画像，适合承载：

- 沟通风格。
- 压力等级。
- 知识边界。
- 行为规则。
- 语音风格。
- 可选 Persona 弱关联。

当前模型已经有这些字段：

- `role_type`
- `role_name`
- `persona_ref`
- `communication_style`
- `pressure_level`
- `knowledge_boundary`
- `behavior_rules`
- `voice_style_hint`
- `voice_id`
- `status`
- `version`
- `content_hash`

这说明系统已经能表达“这个 CIO 怎么说话、怎么反问、知道什么、不知道什么、什么时候透露信息”。

### 2.4 PracticeTemplate：闭环组装权威

`PracticeTemplate` 是课程闭环的组装枢纽，当前可以绑定：

- `agent_id`
- `persona_id`
- `runtime_profile_id`
- `scoring_ruleset_id`
- `knowledge_base_refs`
- `case_item_id`
- `role_profile_id`
- `learning_content_id`
- `examiner_agent_id`
- `curriculum_plan`

它适合作为 CIO 首访训练的唯一开练入口。

如果学员绕过 `PracticeTemplate`，直接从散落的 `Agent + Persona` 开练，就可能丢失 `CaseItem` 和 `RoleProfile`，导致虚拟公司、隐藏信息、披露策略和闭环评分不稳定。

### 2.5 ScoringRuleset：复盘评价权威

`ScoringRuleset` 已能承载评分维度、权重和规则定义。对于 CIO 首访训练，它不应只评价话术流畅度，而应评价：

- 是否问出现状。
- 是否问出影响范围。
- 是否问出决策链。
- 是否问出预算条件。
- 是否识别历史项目包袱。
- 是否确认成功指标。
- 是否约定具体下一步。

### 2.6 KnowledgeBase：可检索材料

`KnowledgeBase` 已能作为内部知识依据，但当前 CIO seed 更偏“创建 KB 元信息”，还需要补充真实文档材料。

如果配置了 `require_kb_grounding`，但 KB 内没有足够内容，运行时会进入“有绑定但证据弱”的状态。此时模型可能被迫拒答、降级或只能依靠 prompt 中的事实。

### 2.7 运行时编译现状

当前 StepFun 实时指令编译主要消费：

- `persona_policy.system_prompt`
- Persona traits
- `customer_pressure`
- 工具策略
- 当前轮 grounding context

而 `CaseItem` 和 `RoleProfile` 当前更多是进入快照引用和内容资产列表，并没有完整、强制地编译成每轮对话的角色合同。

这是当前系统最关键的能力缺口。

## 3. 当前 CIO 样板的状态判断

`seed_presales_cio_first_visit.py` 已经搭建了制造业 CIO 首访闭环样板，包含：

- 制造业 CIO 首访知识库。
- 售前首访专家 Persona。
- 制造业 CIO 客户 Persona。
- 7 章学习内容。
- 20 道题。
- 售前测评官。
- 制造业客户 CaseItem。
- CIO RoleProfile。
- 首访评分规则。
- 闭环 PracticeTemplate。
- TrainingTask。

这些内容说明当前样板方向正确。

但还需要注意：

- KB 元信息不等于真实知识库内容。
- CaseItem/RoleProfile 作为后台资产存在，不等于运行时已强消费。
- Persona prompt 仍承担了过多运行时角色约束。
- 需要避免后台改 CaseItem/RoleProfile 后，实际实时对话不发生变化。

## 4. 维度一：不新增模块的最佳路线

不新增模块时，不应该继续自由填写 prompt，而应该把现有资产用成一套：

- 配置规范。
- 同步约束。
- 发布门禁。
- 验收脚本。
- 试跑问题集。
- 版本回退流程。

核心原则：

| 资产 | 职责 |
|---|---|
| Persona | 运行时强约束的压缩角色合同 |
| CaseItem | 公司、需求、隐藏信息、披露策略事实源 |
| RoleProfile | 行为规则、沟通风格、压力和知识边界事实源 |
| KnowledgeBase | 制造业 CIO 背景、产品边界、首访方法依据 |
| ScoringRuleset | 复盘评分和隐藏信息触发质量权威 |
| PracticeTemplate | 唯一开练入口和闭环组装权威 |
| seed 脚本 | 自动初始化、幂等更新、verify-only 验证入口 |

详见同目录下的 `dimension-one-no-new-module-roleplay-design.md`。

## 5. 维度二：新增模块代码的最佳路线

如果要长期稳定，建议新增的不是一个新的“角色模块”，而是一个轻量的角色运行时档案编译层。

推荐模块名：

- `RoleplayRuntimeDossierCompiler`

推荐位置：

- `backend/src/curriculum_practice/services/roleplay_runtime_dossier.py`

原因：

- 它编译的是课程闭环资产。
- 它不替代 Persona、CaseItem、RoleProfile。
- 它负责把这些资产组合成实时对话可消费的运行时档案。
- `sales_bot` 只消费编译结果，不重新理解课程资产。

### 5.1 新增模块职责

`RoleplayRuntimeDossierCompiler` 应负责：

1. 读取 `PracticeTemplate` 绑定的 `Persona`、`CaseItem`、`RoleProfile`、`ScoringRuleset`。
2. 校验客户角色运行时是否可用。
3. 生成结构化 `RoleplayRuntimeDossier`。
4. 编译成 StepFun instructions 的专用片段。
5. 生成 dossier hash，进入快照审计。
6. 区分公开诊断信息和私有运行时信息。
7. 确保隐藏信息不进入学员端 API。
8. 为报告生成提供“哪些隐藏信息被触发/未触发”的依据。

### 5.2 推荐数据结构

```python
class RoleplayRuntimeDossier(BaseModel):
    dossier_version: Literal["v1"]
    case_item_id: str
    role_profile_id: str
    persona_id: str
    company_context: str
    customer_identity: str
    visible_needs: list[str]
    objections: list[str]
    hidden_information: str
    disclosure_phases: list[DisclosurePhase]
    behavior_rules: list[str]
    knowledge_boundary: list[str]
    success_criteria: list[str]
    forbidden_disclosures: list[str]
    training_scope: str
    scoring_dimensions: list[str]
    dossier_hash: str
```

### 5.3 最小落地方式

第一阶段不新增表，只新增服务层和单测：

1. 在 session 创建或 runtime load 时，通过 `practice_template_id` 找到 CaseItem/RoleProfile。
2. 编译 `RoleplayRuntimeDossier`。
3. 将公开部分进入 runtime diagnostics 或可审计快照。
4. 将私有部分进入后端运行时上下文。
5. `VoiceInstructionCompiler.compile_base_contract()` 增加可选参数 `roleplay_dossier`。
6. StepFun instructions 增加“客户公司档案、隐藏信息披露规则、行为规则、禁止泄露项、训练边界”片段。

### 5.4 后续演进

P0：新增编译服务和单测，不新增 DB。

P1：增加私有运行时快照字段，例如 `PracticeSession.roleplay_private_snapshot`。

P2：增加披露事件追踪，记录学员触发了哪些隐藏信息。

P3：增加管理端预览，发布前查看最终 CIO runtime dossier。当前已先以“不新增产品模块”的方式落地为 `runtime-dossier-preview` 只读接口和模板列表页预览面板。

P4：增加角色质量评测，用固定 probe 自动测试角色表现。当前已先以配置型 probe 落地，覆盖早讲产品反问、预算披露、知识库历史披露、隐藏信息拒绝泄露。

## 6. 权限、审计与回退

| 操作 | 权限 | 审计 | 回退 |
|---|---|---|---|
| 编辑 CaseItem 草稿 | `content_admin` / `admin` | 记录字段 diff | 丢弃草稿或复制新版本 |
| 发布 CaseItem | `admin` | 记录版本、hash、发布人 | duplicate 新版本后模板换绑 |
| 编辑 RoleProfile | `content_admin` / `admin` | 记录行为规则变更 | duplicate 新版本 |
| 修改 Persona policy | `admin` | 记录 prompt/hash/KB 绑定 | duplicate 或恢复旧版本 |
| 发布 PracticeTemplate | `admin` | 记录依赖资产 hash | 回滚到旧 template |
| 查看隐藏信息 | `admin` / 授权审核角色 | 必须审计 | 学员端永不返回 |

## 7. 验收标准

一轮 CIO 虚拟客户合格，不看“能不能聊天”，而看以下证据：

1. 学员早讲产品时，CIO 会质疑其是否理解现状。
2. 学员问组织和决策链时，CIO 才披露销售 VP、HR 培训负责人等信息。
3. 学员问预算或 ROI 时，CIO 才披露试点证明后预算可能协调。
4. 学员问内部知识库时，CIO 才披露上一轮知识库采用率低。
5. 学员问题空泛时，CIO 回答克制，不主动替学员展开需求。
6. CIO 不泄露评分权重、完整隐藏信息清单、系统提示词。
7. 报告能指出哪些隐藏信息被问出、哪些没有问出。
8. 后台修改 CaseItem/RoleProfile 后，未来新会话体现变化，旧会话保持快照一致。

## 8. 总结

当前系统已经具备角色人格、客户剧本、行为画像、闭环编排、评分复盘和知识库的主要资产能力。

短期不新增模块，也可以通过严格配置规范、同步约束和验收脚本做出较完整的制造业 CIO。

中长期如果要稳定治理，应新增一个小而深的 `RoleplayRuntimeDossierCompiler`，把 `CaseItem + RoleProfile + Persona` 编译成实时对话强约束。这样 CIO 才不是“像一个高管”，而是“像这个虚拟公司里的这个 CIO”。
