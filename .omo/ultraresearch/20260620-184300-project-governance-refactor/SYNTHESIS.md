# 项目治理重构 UltraResearch 综合结论

日期：2026-06-20
范围：当前仓库整体治理重构规划；本轮不改业务代码。

## 结论摘要

当前项目不是“没有架构”，而是“已有多套局部正确的架构并行存在，但缺少统一边界、统一发布真相、统一治理读面”。最危险的不是某个单点文件过大，而是多个模块在配置、权限、审计、运行时快照、前端路由/API 门面上各自维护一套类似规则，长期会导致修一处牵三处、后台配置与运行时实际行为不一致、测试门禁无法给出可信结论。

推荐方案不是全量重写，而是分阶段收敛：

1. 先修门禁：迁移图测试、CI 分支触发、依赖治理、质量门禁权威。
2. 再固化契约：后端依赖边界、前端路由/API 门面、配置治理库存、公开投影规则。
3. 再拆模块：把启动装配、domain contributor、Sales Trainer/Newcomer API、AI Coach 工作流、审计读面逐步剥离。
4. 最后处理深层运行时：Roleplay Contract 共享归属、StepFun 继承关系、training task lookup port 等高风险边界。

## 调研输入

团队并行产物：

- Member A：后端 composition root 与 domain boundary 依赖。
- Member B：前端路由归属、API facade、UI state coupling。
- Member C：配置治理、domain contract、状态、权限、审计、AI prompt 边界。
- Member D：测试、CI、migration、scripts、release workflow、Ultra Loop 执行策略。

关键本地材料：

- `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-a-backend-boundary-memo.md`
- `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-B-frontend-governance-memo.md`
- `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-c-governance-memo.md`
- `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8/artifacts/member-d-tests-ci-migrations-release-ultraloop-memo.md`
- `.omo/ultraresearch/20260620-182415-architecture-audit/SYNTHESIS.md`
- `.trellis/tasks/06-20-06-20-project-governance-refactor-plan/prd.md`

## 当前主要问题

### 1. 后端边界：有扩展缝，但组合根职责混杂

已确认后端关键组合根：

- `backend/src/app_factory.py`
- `backend/src/router_registry.py`
- `backend/src/websocket_routes.py`
- `backend/src/app_lifespan.py`
- `backend/src/common/services/practice_session_ports.py`

核心问题：

- `router_registry.register_routers()` 同时承担 HTTP router 注册和 domain contributor bootstrap。
- `common` 仍存在对具体 domain 的反向依赖，例如 `common/services/session_runtime_repair_service.py -> sales_bot`。
- 现有测试 `backend/tests/unit/test_runtime_dependency_contract.py` 已经把这些违规列入 allowlist，这说明仓库已有边界意识，但债务尚未归零。

判断：

- 先收紧 allowlist 与组合根职责，再逐步移动 runtime descriptor、Roleplay Contract shared primitive、training task lookup port。
- 不建议第一步就做 realtime runtime 大拆分。

### 2. 前端边界：路由、API、页面状态三处重复维护业务知识

核心问题：

- 全局 admin sidebar、Sales Trainer module nav、capability projection 各自维护导航/权限表现。
- `web/src/lib/api/domains/sales-trainer.ts` 同时承载 learner/admin sales-trainer 与 admin newcomer-training 调用。
- `web/src/lib/api/types.ts` 过大，领域类型不利于局部推理。
- 学员页、商务技巧页、AI Coach 页存在页面组件直接编排业务流程和状态转换的情况。

判断：

- 先建立 Sales Trainer route registry，使全局侧栏和模块导航消费同一个 route/capability 描述。
- 再拆 API facade，把 Newcomer Training 与 Sales Trainer 的 learner/admin 域拆清。
- 页面重构应走 hook/workflow/reducer 分层，不做视觉大改版。

### 3. 配置治理：控制很强，但多轨并行

现有治理轨道：

- `ConfigBundle` / `BusinessRuleConfig`
- `SalesTrainerAssetRevision`
- `PromptTemplate` / `SystemLog`
- `SalesTrainerOperationLog`
- Roleplay Contract / Situation Pack / ScoringRuleset

核心问题：

- 多套 store 都有效，但缺少一个统一 governance inventory/read model。
- Sales Trainer Path Config 不在 ConfigBundle 库存中，配置中心无法完整呈现。
- Prompt governance 与 Sales Trainer `manage_prompts` 权限边界没有形成跨域契约。
- AI Coach `generation_model` / `scoring_model` 暴露为高风险配置，但当前 runtime 调用未明确消费这些字段。
- AI Coach short-answer scoring contract hash 没有清晰持久化链路。

判断：

- 不要第一步把所有 Sales Trainer 配置迁入 `BusinessRuleConfig`。
- 使用现有 `ConfigBundleAdapter` 模式建立统一读面。
- 审计先做 normalized read model，再考虑表结构迁移。

### 4. 测试与发布：有质量门禁，但权威不唯一

关键事实：

- 当前 Alembic head 是 `20260616_086`。
- `backend/tests/unit/common/test_alembic_migration_graph.py` 仍期待 `20260609_1300_080_ai_proactive`，已由 Member D 验证失败。
- `scripts/critical-quality-gate.sh` 是最接近发布真相的全栈门禁。
- `.github/workflows/release-truth-gate.yml` 只触发 `main` 和 `001-ai-practice-system`，当前团队基线为 `dev`。
- backend pytest 默认 coverage 门槛是 48，但 critical gate 的 backend targeted tests 使用 `--no-cov`。
- release verification service/runner 与 shell quality gate 是两套 release truth。

判断：

- Ultra Loop 第一波必须先修门禁，不然长时间重构后无法判断红灯归因。
- 发布真相应收敛到 `scripts/critical-quality-gate.sh`，release verification 可以作为记录层或桥接层。

## 目标架构原则

### 后端

- `app_factory` 只负责 app 创建与生命周期连接。
- router registry 只负责 HTTP/WS route mounting。
- domain contributor bootstrap 单独成为 composition 模块。
- `common` 只能依赖 port/protocol/type，不反向依赖具体 domain。
- Runtime snapshot/contract 采用 freeze/hash/read-only 语义。

### 前端

- page 只负责 route shell 和用户触发。
- hook/workflow 负责编排业务流程。
- component 负责展示和交互控件。
- API domain facade 与后端边界一致。
- route/capability registry 是导航和权限展示的唯一来源。
- learner public projection 默认拒绝敏感字段。

### 配置治理

每个可配置业务面都必须声明：

- surface key
- owner domain
- backing store
- lifecycle
- permission policy
- audit policy
- status policy
- snapshot policy
- public projection policy

第一阶段保留既有 backing store，用 adapter/read model 收敛治理面。

### 测试发布

- 修复已知红灯后再进入大循环。
- 每个任务“实现 + 测试 + 验证”绑定在同一个 todo。
- 小步 focused gate，切片后 full gate。
- release truth 只保留一个可执行权威。

## 首要风险

1. Alembic migration graph 测试已红，必须先修。
2. CI 分支触发与实际开发基线不一致。
3. backend quality gate 可能绕开 coverage 门槛。
4. `router_registry` 组合根职责混杂导致后端边界继续扩散。
5. `common -> domain` allowlist 如果不收紧，会固化反向依赖。
6. Sales Trainer/Newcomer API facade 继续混合，会加剧前后端契约漂移。
7. AI Coach 暴露但未生效的 model 配置会造成运营误判。
8. scoring contract hash 持久化不足会影响评分复盘。
9. 审计 carrier 分裂会让“谁改了影响学员的规则”难以回答。
10. 页面状态继续堆在 page 组件，会让后续 UI 或接口改动变成连锁修改。

## 推荐实施顺序

1. 门禁预检与已知红灯修复。
2. 后端 contributor bootstrap 与 dependency guard 收紧。
3. 前端 route registry 与 API facade 拆分。
4. 配置治理 inventory、ConfigBundleAdapter、审计 read model。
5. AI Coach prompt/model/hash 补齐。
6. 页面 workflow/hook/reducer 分层。
7. script/migration/release workflow 治理。
8. Roleplay Contract shared ownership 与 realtime 深层边界。

## 本轮不做

- 不直接修改业务代码。
- 不做数据库迁移。
- 不改前端视觉。
- 不重命名对外 URL。
- 不一次性迁移所有配置存储。
- 不拆 realtime runtime 主干。

## 下一产物

执行计划写入：

- `.omo/plans/project-governance-refactor.md`

