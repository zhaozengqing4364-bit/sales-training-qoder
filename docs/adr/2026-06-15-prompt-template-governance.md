# ADR 2026-06-15：提示词模板治理台与系统模板保护

## 背景

`/admin/prompts` 原先更像技术模板表：英文名称和枚举直接暴露给运营，系统模板可直接编辑，默认模板允许历史多条并存，场景绑定为空或重复时页面缺少有效提示。实际运行中，legacy 评估/报告和 presentation helper 会通过 `PromptTemplateService` 选择默认模板或场景绑定模板；一旦同一 `prompt_type` 有多个默认、变量结构非法，运行时可能解析失败或使用非预期模板。

同时，系统模板属于平台兜底能力，直接编辑会影响后续所有调用，又缺少“复制后编辑、预览、替换默认/绑定”的安全路径。

## 决策

采用“系统模板只读 + 自定义副本编辑 + 默认/绑定唯一约束 + 治理修复 dry-run”的模型：

1. 系统模板不可直接编辑或停用，只能复制为自定义模板后调整。
2. 同一 `prompt_type` 只能有一个默认模板，由数据库唯一索引和服务端 `set_default` 共同保证。
3. 同一 `scenario_type + scenario_id + prompt_type` 只能有一个活跃场景绑定。
4. 所有模板响应返回中文展示字段、绑定数量、运行时生效状态、可编辑/可停用原因。
5. 治理修复入口必须支持 `dry_run=true`，正式执行写审计。
6. 模板正文、变量、JSON/Jinja 合同保持运行时兼容；中文化只改变运营展示和已知系统模板说明文本，不改变内部枚举。
7. 平台模板 CRUD、默认模板、场景绑定和治理修复只允许平台 `admin` / `super_admin`，权限判断集中在 `prompt_templates.permissions.can_manage_prompt_templates`。销售训练 `content_admin` / `newcomer_content_admin` 只能管理销售训练内容，不能直接改平台 PromptTemplate。
8. 销售训练对 PromptTemplate 的使用只通过业务绑定和运行时编译进入：`modules[].ai_coach.prompt_template_id`、`scoring_prompt_template_id`、模型、阈值、重试和失败策略等高风险字段由 `sales_trainer.manage_prompts` 控制，字段集合集中在 `sales_trainer.ai_coach_policy.AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS`。

## 备选方案

1. **只改前端中文文案**：成本低，但多默认、非法变量、系统模板误改仍会造成运行时事故。
2. **允许系统模板直接编辑但加二次确认**：减少 clone 流程，但风险仍集中在兜底模板，且不利于审计区分平台基线和客户自定义策略。
3. **完全迁移到 ConfigBundle**：长期治理更统一，但本轮会牵涉运行时 authority 迁移、历史数据兼容和更多页面重构，超出当前修复闭环。

## 取舍

选择当前方案，因为它先修复已确认的运行时一致性问题，又不改变已有 prompt contract 和调用方。系统模板只读牺牲了一点编辑速度，但换来明确回滚路径：默认模板和场景绑定都可以切回原模板，自定义副本也可以停用或替换。

## 影响

- 后端新增 prompt/default 和 scenario binding 唯一索引，历史冲突在迁移和治理接口中先修复。
- API 新增 `impact`、`clone`、`repair-defaults`，并扩展 `PromptTemplate` 响应字段。
- 前端 `/admin/prompts` 改为提示词治理台：健康状态、生效矩阵、模板列表、影响预览和治理操作。
- 场景绑定改为独立 `/admin/prompts/bindings` 向导，避免在列表页混入绑定编辑。
- 运行时仍使用 `PromptTemplateService.compile_runtime_prompt_contract(...)`；不改变 live StepFun voice instruction authority。
- 销售训练后台只持有 PromptTemplate 绑定权，不持有平台模板正文编辑权；如果绑定、发布或回滚涉及 AI Coach 高风险字段，必须同时满足 `sales_trainer.manage_prompts`。

## 回滚

1. 回滚前端页面可恢复旧列表，但后端服务保护不应回退，否则会重新开放多默认和系统模板误改风险。
2. 如唯一索引导致历史数据无法迁移，先执行 `repair-defaults?dry_run=true` 查明冲突，再正式修复或人工清理。
3. 若必须回退数据库约束，Alembic downgrade 仅删除新增唯一索引，不恢复已中文化或已修复的数据；这类数据修复可通过 SystemLog 审计快照人工回放。
