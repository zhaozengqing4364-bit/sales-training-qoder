# 全系统修复总计划（Full System Remediation Roadmap）

## TL;DR
> **Summary**: 基于当前审计结果，按“上线可信度恢复 → 架构风险收敛 → 清理与治理”三阶段推进全栈修复。优先修复认证、数据库一致性、关键用户流验证与实时链路风险，再收敛契约、状态管理和历史兼容面。
> **Deliverables**:
> - 真实认证闭环（WeCom SSO + 现有登录链路兼容）
> - 数据库模型/迁移一致性恢复，移除运行时 schema repair 依赖
> - 关键用户流最小 E2E 与全栈本地编排
> - 实时练习链路、错误契约、评估层、前端数据获取的风险收敛
> - CI/可观测性/契约同步基线
> **Effort**: XL
> **Parallel**: YES - 4 waves
> **Critical Path**: T1 后端误报分流 → T4 模型基线 → T6 迁移修复 → T5 认证闭环 → T9 E2E/CI 门禁 → T10 实时链路硬化

## Context
### Original Request
用户要求先完成全项目系统审计，再“整理成详细全面的计划”，后续按计划进行全面修复。

### Interview Summary
- 不执行代码修复；产出单一、详细、可执行的总修复计划。
- 范围覆盖前端、后端、数据库、测试、契约、可观测性。
- 计划需基于当前代码现实，而不是历史愿景。

### Metis Review (gaps addressed)
- 增加 **T1 后端 LSP/环境误报分流**，避免把依赖解析噪音当成真实缺陷批量修错。
- 把 **API 契约验证**、**最小 E2E**、**本地全栈编排**、**可观测性基线** 明确纳入，不允许只做代码修补。
- 对 React Query 收敛加范围护栏：Phase 1 不做全站改造，只覆盖关键用户流与高重复页面。
- 数据库整改按“模型基线先对齐 → 迁移生成与验证 → 移除 runtime repair 依赖”顺序执行。

## Work Objectives
### Core Objective
把当前系统从“可演示/可联调但生产闭环不稳”的状态，推进到“认证、数据库、关键用户流、实时链路、契约和验证体系均具备生产可信度”的状态。

### Deliverables
- 可工作的 WeCom SSO 方案（保留 dev-login 作为显式开发 fallback）
- 数据库 canonical schema、迁移、模型三者一致
- Playwright 最小关键流覆盖与全栈本地运行脚本
- StepFun realtime 关键链路的复杂度收敛与回归测试补齐
- 统一错误契约、前后端类型/契约同步
- 评估/report 层参数化与场景泛化
- 前端关键高重复数据加载模式收敛
- CI 质量门禁与基础可观测性闭环

### Definition of Done (verifiable conditions with commands)
- `cd backend && pytest` 通过核心业务与 DB/迁移相关测试集
- `cd backend && alembic upgrade head` 无错误，且 drift 检查通过
- `cd web && npm run typecheck && npm run test` 通过
- `cd web && npx playwright test` 至少覆盖登录、训练入口、practice smoke、admin analytics smoke
- `docs/api-contract/*.md` 与实际路由/schema 无已知未记录偏差
- 不再依赖 `legacy_schema_repair.py` 或 `Base.metadata.create_all` 进行生产 schema 纠偏

### Must Have
- 明确区分：已确认缺陷、环境噪音、历史兼容残留
- 所有关键改动配套自动化验证
- 先修 ship blockers，再做结构性收敛
- 保留现有已诚实降级的 admin inventory shell，不把 UI 壳修饰当成主任务

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不做全站 React Query 大迁移
- 不做“顺手”视觉重设计
- 不做无边界的后端全面重写
- 不把环境依赖解析噪音直接判定为业务缺陷
- 不在没有测试门禁前大规模改 realtime / DB / auth 主干

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after + targeted hardening；优先补关键流集成/E2E，再扩展单测
- QA policy: Every task has agent-executed scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 3-4 tasks per wave. Foundation tasks先锁基线，再并行进入跨层整改。

Wave 1: 基线澄清与执行底座
- T1 后端 LSP/环境误报分流
- T2 API 契约与共享类型基线
- T3 全栈本地编排与最小 E2E 基线
- T4 数据库 canonical schema 基线

Wave 2: Ship blockers
- T5 认证闭环（WeCom SSO + dev fallback + auth tests）
- T6 数据库漂移修复与迁移落地
- T7 遥测/健康检查/可观测性基线修复
- T8 错误契约统一

Wave 3: 核心风险收敛
- T9 Playwright 关键流扩容 + CI 质量门禁
- T10 StepFun realtime 关键链路硬化
- T11 Presentation 权限一致性修复
- T12 评估与 report 层参数化/泛化

Wave 4: 架构治理与清理
- T13 前端关键数据加载模式收敛
- T14 历史兼容面/重复路由/陈旧文件清理与文档同步

### Dependency Matrix (full, all tasks)
| Task | Blocks | Blocked By |
|------|--------|------------|
| T1 | T5, T6, T8, T10, T12 | - |
| T2 | T8, T11, T13, T14 | - |
| T3 | T9 | - |
| T4 | T6 | - |
| T5 | T9 | T1 |
| T6 | T9, T10, T12 | T1, T4 |
| T7 | T9 | T1 |
| T8 | T9, T14 | T1, T2 |
| T9 | Final Verification | T3, T5, T6, T7, T8 |
| T10 | Final Verification | T1, T6, T9 |
| T11 | Final Verification | T2, T8 |
| T12 | Final Verification | T1, T6 |
| T13 | Final Verification | T2, T9 |
| T14 | Final Verification | T2, T8, T11, T13 |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 4 tasks → deep / unspecified-high
- Wave 2 → 4 tasks → deep / unspecified-high
- Wave 3 → 4 tasks → deep / unspecified-high
- Wave 4 → 2 tasks → visual-engineering / writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. 后端 LSP/环境误报分流

  **What to do**: 统一后端 Python 解释器、依赖、类型检查配置；把 `backend/src` 现有 LSP/pyright 诊断分为三类：真实代码错误 / 环境与 import 解析噪音 / 已废弃路径。产出一份可执行 triage 清单，并只保留真实缺陷进入后续任务。
  **Must NOT do**: 不要在此任务中修复业务逻辑；不要直接批量修改 websocket/auth/DB 代码。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 需要跨配置、依赖、类型与模块结构做严谨分流
  - Skills: [`fastapi-python`] - 识别 FastAPI/Pydantic/typing 误报与真实错误
  - Omitted: [`systematic-debugging`] - 本任务不是运行时 bug 复现，而是静态诊断分流

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: T5,T6,T8,T10,T12 | Blocked By: none

  **References**:
  - Pattern: `backend/pyproject.toml` - 后端依赖与工具配置源
  - Pattern: `backend/src/main.py` - 后端主装配面与导入入口
  - Pattern: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` - 当前 LSP 噪音/真实错误最密集热点之一
  - Pattern: `backend/src/admin/api/` - admin 路由群，错误契约与依赖模式样本

  **Acceptance Criteria**:
  - [ ] 生成一份 triage 结果，逐条标明真实错误/环境噪音/废弃路径
  - [ ] 为后续任务提供“只修真实缺陷”的输入清单
  - [ ] 记录并验证后端类型检查/诊断使用的统一环境配置命令

  **QA Scenarios**:
  ```
  Scenario: Backend diagnostics are classified deterministically
    Tool: Bash + lsp_diagnostics
    Steps: 运行统一诊断命令；抽样检查 websocket、auth、db 三个热点目录；对比 triage 分类结果
    Expected: 同一诊断不会同时出现在“真实错误”和“环境噪音”两类中
    Evidence: .sisyphus/evidence/task-1-backend-lsp-triage.txt

  Scenario: Environment noise filter does not suppress real syntax/type failures
    Tool: Bash + lsp_diagnostics
    Steps: 人为选取一个已知真实错误样本与一个已知 import 噪音样本，验证分类器输出
    Expected: 真实错误仍保留，环境噪音被单独归档
    Evidence: .sisyphus/evidence/task-1-backend-lsp-triage-samples.txt
  ```

  **Commit**: YES | Message: `chore(backend): normalize diagnostics baseline` | Files: `backend/pyproject.toml`, typecheck config files, `.sisyphus/evidence/*`

- [x] 2. 契约与共享类型基线收敛

  **What to do**: 对照 `docs/api-contract/README.md` 与实际 FastAPI 路由/Pydantic schema，收敛契约偏差；把已知前端本地重复类型（优先 `admin/settings`）迁回 `web/src/lib/api/types.ts` 或等价共享层；补充明确的 snake_case → camelCase 变换边界。
  **Must NOT do**: 不要顺手重写全部 API client；不要修改与本轮审计无关的页面展示。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 需要跨文档、后端 schema、前端类型三方比对
  - Skills: [`pydantic`, `react-best-practices`] - 分别用于后端 schema 边界和前端类型收敛
  - Omitted: [`frontend-design`] - 不是视觉改造任务

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T8,T11,T13,T14 | Blocked By: none

  **References**:
  - Pattern: `docs/api-contract/README.md:55-80` - 统一响应包裹与认证语义
  - Pattern: `docs/api-contract/*.md` - 各域契约源
  - Pattern: `web/src/lib/api/types.ts` - 前端共享 API 类型中心
  - Pattern: `web/src/app/admin/settings/page.tsx` - 已知本地类型重复热点
  - Pattern: `backend/src/agent/schemas.py` - 后端 schema 对照样本

  **Acceptance Criteria**:
  - [ ] 产出契约差异清单，并修复高优先级偏差
  - [ ] `admin/settings` 等热点不再维护独立漂移类型
  - [ ] 文档、后端 schema、前端共享类型三者对齐

  **QA Scenarios**:
  ```
  Scenario: Contract docs match live schema and client types
    Tool: Bash + Grep + Read
    Steps: 对 agents / analytics / model-configs / sessions 四类契约做字段抽样比对
    Expected: 响应包裹、核心字段名、认证语义与代码一致
    Evidence: .sisyphus/evidence/task-2-contract-diff.md

  Scenario: Frontend type consumers compile after shared-type consolidation
    Tool: Bash
    Steps: 运行 web typecheck；抽样打开 admin/settings、analytics、practice 相关页面
    Expected: 不再因本地类型移除引发编译错误
    Evidence: .sisyphus/evidence/task-2-web-typecheck.txt
  ```

  **Commit**: YES | Message: `refactor(contract): align api docs and shared types` | Files: `docs/api-contract/*`, `web/src/lib/api/types.ts`, affected consumers

- [x] 3. 全栈本地编排与最小 E2E 基线

  **What to do**: 为前端 + 后端 + 数据库 + websocket 关键流**从零建立**可重复的本地运行与 Playwright smoke baseline。基于现有 `scripts/dev-up.sh` / `scripts/README.md` / `web package scripts` / backend `uvicorn` 入口，新增或补齐 Playwright 配置、最小 fixture、启动脚本与文档；至少覆盖登录、训练入口、practice session smoke、admin analytics smoke。
  **Must NOT do**: 不要一开始写大规模 E2E 套件；不要覆盖所有页面。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: 涉及前后端协调、测试基建、脚本编排
  - Skills: [`frontend-audit`, `docker-compose-orchestration`] - 分别用于关键流验证与本地运行编排
  - Omitted: [`qa`] - 此任务先建基线，不在此轮做全站缺陷修复

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T9 | Blocked By: none

  **References**:
  - Pattern: `web/src/app/(auth)/login/page.tsx:55-68` - 登录入口现状
  - Pattern: `web/src/app/(user)/practice/[sessionId]/page.tsx:62-165` - practice smoke 入口
  - Pattern: `web/src/app/admin/analytics/page.tsx:93-109` - admin analytics 真实 API 聚合面
  - Pattern: `scripts/dev-up.sh` - 现有开发环境启动脚本基线
  - Pattern: `scripts/README.md` - 当前本地启动说明
  - Pattern: `web/package.json:5-12` - 前端 dev/test script 基线
  - Pattern: `backend/src/main.py:778-780` - backend `uvicorn` 本地入口

  **Acceptance Criteria**:
  - [ ] 仓库存在可执行的 Playwright smoke 配置
  - [ ] 本地一条命令可拉起跑 smoke 所需的服务
  - [ ] 至少 4 条关键流 smoke 测试可稳定运行

  **QA Scenarios**:
  ```
  Scenario: Full-stack smoke harness boots successfully
    Tool: Bash
    Steps: 运行本地编排命令；等待 web/backend/db 就绪；执行 health 检查
    Expected: 所有服务进入 ready 状态，websocket 与 API 可连接
    Evidence: .sisyphus/evidence/task-3-stack-boot.txt

  Scenario: Critical smoke flows pass under Playwright
    Tool: Playwright
    Steps: 执行 login、training entry、practice session smoke、admin analytics smoke
    Expected: 四条路径均通过，无 console error blocker
    Evidence: .sisyphus/evidence/task-3-playwright-report.html
  ```

  **Commit**: YES | Message: `test(e2e): add full-stack smoke baseline` | Files: `web/playwright.config.*`, `web/tests/e2e/*`, scripts/compose docs

- [x] 4. 数据库 canonical schema 基线整理

  **What to do**: 以 ORM + 迁移 + 当前 DB 语义为三方输入，确定 `ComprehensiveReport`、`StagedEvaluationResult` 等高风险表的 canonical schema；列出 drift 清单、保留字段、废弃字段、主键/外键/索引最终形态；为迁移修复任务提供唯一基线。
  **Must NOT do**: 不要直接生成迁移；不要在未确定 canonical schema 前修改业务代码。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 需要跨 ORM、Alembic、运行时 repair 逻辑做严谨归一
  - Skills: [`sqlalchemy-orm`, `postgresql-table-design`] - 分别用于 ORM 与关系设计审查
  - Omitted: [`database-backup-restore`] - 该任务是 schema 基线，不是备份演练

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T6 | Blocked By: none

  **References**:
  - Pattern: `backend/src/common/db/models.py` - 当前 ORM 真相
  - Pattern: `backend/alembic/versions/20260204_0900_006_staged_evaluation.py` - staged evaluation 迁移真相
  - Pattern: `backend/alembic/versions/20260205_0100_009_add_report_columns.py` - comprehensive report 迁移真相
  - Pattern: `backend/src/common/db/session.py` - runtime schema repair / create_all 痕迹
  - Pattern: `backend/src/common/db/legacy_schema_repair.py` - 历史补丁逻辑

  **Acceptance Criteria**:
  - [ ] 高风险表 canonical schema 文档化
  - [ ] drift 清单覆盖主键、外键、字段类型、索引、默认值
  - [ ] 后续迁移任务不再需要猜测最终 schema 形态

  **QA Scenarios**:
  ```
  Scenario: Canonical schema inventory is exhaustive for high-risk tables
    Tool: Read + Bash
    Steps: 比对 ORM 定义与 Alembic 迁移文件；列出差异
    Expected: `ComprehensiveReport`、`StagedEvaluationResult`、相关索引/FK 差异全部有记录
    Evidence: .sisyphus/evidence/task-4-schema-baseline.md

  Scenario: No migration task proceeds without canonical decision
    Tool: Bash
    Steps: 检查后续迁移文件变更是否引用 baseline 文档
    Expected: 所有 drift 修复 PR/commit 均引用同一 canonical schema baseline
    Evidence: .sisyphus/evidence/task-4-schema-baseline-check.txt
  ```

  **Commit**: YES | Message: `docs(db): define canonical schema baseline` | Files: schema notes, maybe `docs/` or repo-local DB docs, evidence files

- [x] 5. 认证闭环：完成 WeCom SSO + 保留 dev fallback

  **What to do**: 实现真实 WeCom SSO provider 集成边界，保留 dev-login 作为显式开发 fallback；统一前后端登录入口、回调、cookie/session 行为与失败处理；同步完善相关测试、mock provider、环境变量校验。
  **Must NOT do**: 不要删除现有本地登录能力；不要把未配置的生产凭据当成默认开发路径。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 认证跨前后端、cookie/session、环境配置、测试
  - Skills: [`fastapi-python`, `react-best-practices`] - 后端 OAuth 回调与前端登录边界配套
  - Omitted: [`accessibility`] - 本轮重点不是登录页可访问性精修

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: T9 | Blocked By: T1

  **References**:
  - Pattern: `backend/src/common/auth/service.py` - WeCom mock/TODO 源头
  - Pattern: `backend/src/common/auth/api.py` - 认证 API 面
  - Pattern: `backend/src/main.py` - dev-login / auth 注册入口
  - Pattern: `web/src/app/(auth)/login/page.tsx:55-68` - 当前前端禁用 WeCom 入口
  - External: `https://fastapi.tiangolo.com/tutorial/dependencies/` - 认证依赖组织参考

  **Acceptance Criteria**:
  - [ ] WeCom SSO provider 边界完成，支持真实环境变量配置
  - [ ] 未配置 SSO 凭据时，dev-login 明确可用且不会伪装成正式登录
  - [ ] 登录、回调、cookie/session、失败回跳测试通过

  **QA Scenarios**:
  ```
  Scenario: Real SSO path handles callback and session establishment
    Tool: Bash + curl / Playwright
    Steps: 使用测试 provider/mock callback 驱动认证完成；请求 `/users/me`
    Expected: 返回已认证用户；session cookie 建立成功
    Evidence: .sisyphus/evidence/task-5-wecom-sso.txt

  Scenario: Missing SSO config falls back to explicit dev-login only
    Tool: Playwright
    Steps: 在无 SSO 配置环境打开登录页；检查 WeCom CTA 和 dev-login 行为
    Expected: WeCom 不伪装可用；dev 路径明确且登录成功
    Evidence: .sisyphus/evidence/task-5-dev-fallback.png
  ```

  **Commit**: YES | Message: `feat(auth): implement wecom sso with dev fallback` | Files: auth backend/frontend + tests

- [x] 6. 数据库漂移修复与迁移落地

  **What to do**: 基于 T4 的 canonical schema，对齐 ORM、生成/修正 Alembic 迁移、执行升级验证，并移除对 `legacy_schema_repair.py` / `create_all` 的生产纠偏依赖。重点覆盖 `ComprehensiveReport`、`StagedEvaluationResult` 及相关索引/FK。
  **Must NOT do**: 不要绕过 Alembic 直接在运行时代码里打补丁；不要在未跑迁移验证前改动下游 API。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 数据层改动不可逆，需严谨验证
  - Skills: [`sqlalchemy-orm`, `postgresql-table-design`] - ORM 与关系迁移双重约束
  - Omitted: [`database-backup-restore`] - 不是灾备演练；若有数据迁移风险单独开项

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: T9,T10,T12 | Blocked By: T1,T4

  **References**:
  - Pattern: `backend/src/common/db/models.py` - 当前模型
  - Pattern: `backend/src/common/db/session.py` - runtime repair 痕迹
  - Pattern: `backend/src/common/db/legacy_schema_repair.py` - 待移除修复依赖
  - Pattern: `backend/alembic/versions/*` - 迁移历史

  **Acceptance Criteria**:
  - [ ] ORM 与迁移对齐到 canonical schema
  - [ ] `alembic upgrade head` 与新库初始化都无需 runtime schema repair
  - [ ] 相关模型导入、CRUD、报告读写测试通过

  **QA Scenarios**:
  ```
  Scenario: Fresh database reaches canonical schema via Alembic only
    Tool: Bash
    Steps: 创建空库；执行 `alembic upgrade head`；运行 schema smoke test
    Expected: 表结构正确生成，无 runtime repair 执行依赖
    Evidence: .sisyphus/evidence/task-6-alembic-upgrade.txt

  Scenario: Existing drifted database upgrades safely
    Tool: Bash + pytest
    Steps: 准备旧 schema fixture；执行升级；运行 report/evaluation 读写测试
    Expected: 升级完成且历史数据可读写
    Evidence: .sisyphus/evidence/task-6-drift-upgrade.txt
  ```

  **Commit**: YES | Message: `fix(db): reconcile models and migrations` | Files: models, alembic versions, DB tests

- [x] 7. 遥测、健康检查与最小可观测性基线修复

  **What to do**: 修复前端 telemetry 仍假定同源 `/api/v1/...` 的问题；把性能/错误上报明确改到可工作的 backend API base 或显式禁用；同时统一健康检查入口与本地 smoke 所需的 readiness 信号。
  **Must NOT do**: 不要引入大型监控平台；不要为尚未接通的指标做伪实时仪表板。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: 涉及前后端、配置、观测语义的跨层修复
  - Skills: [`react-best-practices`, `fastapi-python`] - 前端 telemetry 与后端 health surface 协同
  - Omitted: [`benchmark`] - 不是性能压测任务

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T9 | Blocked By: T1

  **References**:
  - Pattern: `web/src/lib/performance.ts:188-223` - 现有同源 telemetry 假设
  - Pattern: `web/next.config.ts:1-6` - 无 rewrite/proxy
  - Pattern: `web/src/components/ErrorBoundary.tsx` - 错误观测路径样本
  - Pattern: `backend/src/support/api/runtime_status.py` - runtime health 已有读面

  **Acceptance Criteria**:
  - [ ] performance/custom telemetry 发送路径明确可用或明确停用
  - [ ] smoke/E2E 可检查统一 readiness endpoint
  - [ ] 错误/性能上报不会静默打到不存在的 same-origin API

  **QA Scenarios**:
  ```
  Scenario: Telemetry dispatch reaches valid target
    Tool: Playwright + network inspection
    Steps: 触发 page load / custom metric / error boundary 样本
    Expected: 请求指向可达地址，返回非 404/网络错误
    Evidence: .sisyphus/evidence/task-7-telemetry.har

  Scenario: Health/readiness signal is consumable by local orchestration
    Tool: Bash
    Steps: 启动全栈；轮询 readiness endpoint
    Expected: 返回稳定 200 + machine-readable health payload
    Evidence: .sisyphus/evidence/task-7-health.txt
  ```

  **Commit**: YES | Message: `feat(obs): repair telemetry and readiness baseline` | Files: telemetry frontend, backend health/readiness, tests

- [x] 8. 统一错误契约与 API 失败语义

  **What to do**: 扫描并修复关键后端路由中 `HTTPException` / 直接异常 / envelope 混用问题；统一到文档约定的成功/失败包裹结构，并同步前端 API client 的错误解码逻辑。优先覆盖 agent/admin/presentation/prompt/evaluation 高流量面。
  **Must NOT do**: 不要一次性改所有长尾接口；不要在未更新契约文档前擅自改变返回体。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 需要跨路由层、schema、前端 client 一致收敛
  - Skills: [`fastapi-python`, `pydantic`] - 路由错误边界与 schema 兼容
  - Omitted: [`javascript-typescript-jest`] - 前端 client 只需消费验证，不是测试框架重点

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T9,T14 | Blocked By: T1,T2

  **References**:
  - Pattern: `docs/api-contract/README.md:55-74` - 统一响应格式
  - Pattern: `backend/src/prompt_templates/api/routes.py:78-83` - 已承认 envelope drift 的样本
  - Pattern: `backend/src/agent/api/agents.py` - 关键 admin/user API 面
  - Pattern: `backend/src/presentation_coach/api/presentations.py` - 大量用户可见错误语义面
  - Pattern: `web/src/lib/api/client.ts` - 前端错误解码主入口

  **Acceptance Criteria**:
  - [ ] 关键 API 失败路径统一返回 documented error envelope
  - [ ] 前端 client 不再需要处理多套失败结构
  - [ ] 文档与实现一致

  **QA Scenarios**:
  ```
  Scenario: Key API failures return uniform envelope
    Tool: Bash + curl
    Steps: 对 agents / presentations / prompt-templates / admin voice-runtime 发送 malformed request
    Expected: 均返回统一 `success=false/error/message/trace_id` 结构
    Evidence: .sisyphus/evidence/task-8-error-envelope.json

  Scenario: Frontend client decodes unified failures consistently
    Tool: Vitest / Bash
    Steps: 运行 API client failure decoding tests
    Expected: 不同接口的错误均落到统一前端错误分支
    Evidence: .sisyphus/evidence/task-8-client-errors.txt
  ```

  **Commit**: YES | Message: `refactor(api): unify error envelope semantics` | Files: key route files, client, contract docs, tests

- [x] 9. 关键流 Playwright 扩容与 CI 质量门禁

  **What to do**: 在 T3 的 smoke baseline 基础上，扩容到最小“上线可信度”测试矩阵：登录、dashboard、training entry、practice session、report/replay smoke、admin analytics、support/runtime。把 frontend typecheck、backend tests、Playwright、Alembic drift check 编进 CI。
  **Must NOT do**: 不要追求全站 E2E 覆盖；不要把 flaky 测试直接并入门禁而不先稳定。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: 覆盖跨前后端测试与 CI 编排
  - Skills: [`frontend-audit`, `github-workflows`] - UI 关键流与 CI 门禁落地
  - Omitted: [`qa-only`] - 本任务不仅报告，还要建立门禁

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification | Blocked By: T3,T5,T6,T7,T8

  **References**:
  - Pattern: `web/vitest.config.ts` - 现有前端测试基线
  - Pattern: `backend/tests/` - 后端测试基线
  - Pattern: `.github/workflows/` - 现有 CI 面

  **Acceptance Criteria**:
  - [ ] Playwright 覆盖关键用户流 smoke + 关键 admin smoke
  - [ ] CI 明确串联 backend tests / alembic check / web typecheck / web tests / Playwright
  - [ ] 门禁稳定，无已知高频 flaky

  **QA Scenarios**:
  ```
  Scenario: CI-quality matrix passes locally before CI merge
    Tool: Bash
    Steps: 顺序执行 backend tests、alembic check、web typecheck、vitest、playwright
    Expected: 全部退出码为 0
    Evidence: .sisyphus/evidence/task-9-quality-gate.txt

  Scenario: Playwright covers critical user journeys end-to-end
    Tool: Playwright
    Steps: 跑扩容后的 smoke matrix
    Expected: 登录、训练、practice、report、analytics、runtime 均通过
    Evidence: .sisyphus/evidence/task-9-playwright-report.html
  ```

  **Commit**: YES | Message: `ci(quality): enforce critical full-stack gates` | Files: workflow files, tests, scripts

- [ ] 10. StepFun realtime 关键链路硬化

  **What to do**: 以最小破坏原则收敛 `stepfun_realtime_handler.py` 的职责边界；把连接生命周期、重连、interrupt、backpressure、session cleanup、task spawning 的关键状态机与 side effects 拆出受测 helper/service；补齐 reconnect、disconnect、task cleanup、TTS/interrupt 的高价值回归测试。
  **Must NOT do**: 不要重写整个 realtime 协议；不要改变前端 `usePracticeWebSocket` outward contract。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 高复杂度实时链路与并发行为
  - Skills: [`fastapi-python`, `websocket-engineer`] - realtime 服务与 WebSocket 行为收敛
  - Omitted: [`artistry`] - 优先常规硬化而非激进重构

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification | Blocked By: T1,T6,T9

  **References**:
  - Pattern: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` - 主热点
  - Pattern: `backend/src/sales_bot/websocket/router.py` - socket 注册与 auth 入口
  - Pattern: `web/src/hooks/use-practice-websocket.ts:93` - hook 定义入口
  - Pattern: `web/src/hooks/use-practice-websocket.ts:840-876` - 前端保持不变的 outward contract 边界（public return）
  - Test: `backend/tests/integration/test_sales_realtime_reconnect_flow.py` - reconnect 样本
  - Test: `backend/tests/performance/test_interruption_latency.py` - interruption 性能样本

  **Acceptance Criteria**:
  - [ ] 主 handler 关键责任拆出，单文件复杂度下降
  - [ ] reconnect/disconnect/interrupt/backpressure cleanup 有明确回归测试
  - [ ] 前端 runtime outward contract 无破坏性变化

  **QA Scenarios**:
  ```
  Scenario: Realtime reconnect and cleanup remain correct
    Tool: pytest
    Steps: 运行 reconnect / disconnect / interruption 相关集成测试
    Expected: 无资源泄漏、无 stale task、状态恢复符合预期
    Evidence: .sisyphus/evidence/task-10-realtime-tests.txt

  Scenario: Practice smoke remains functional after handler refactor
    Tool: Playwright
    Steps: 跑 practice session smoke；触发 speak / interrupt / reconnect 情况
    Expected: UI 仍能连接、录音、收到响应；不中断核心流程
    Evidence: .sisyphus/evidence/task-10-practice-smoke.mp4
  ```

  **Commit**: YES | Message: `refactor(realtime): harden stepfun session lifecycle` | Files: sales_bot websocket modules + tests

- [ ] 11. Presentation 权限一致性修复

  **What to do**: 审核并修复 `presentation_coach/api/presentations.py` 与相关 admin presentation surfaces 中“绑定 current_user 但未真正授权”的路径；统一删除、替换、读写、缩略图、讲点、回放等 endpoint 的访问策略，确保 uploader/admin/learner 各自权限边界明确。
  **Must NOT do**: 不要改变 PPT 演练业务功能；不要重做 presentation 数据模型。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 权限边界跨 API/角色/前端消费面
  - Skills: [`fastapi-python`, `best-practices`] - API 授权治理
  - Omitted: [`accessibility`] - 本轮不是前端无障碍审计

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: Final Verification | Blocked By: T2,T8

  **References**:
  - Pattern: `backend/src/presentation_coach/api/presentations.py` - 用户/上传者权限热点
  - Pattern: `backend/src/admin/api/admin.py` - presentation 兼容/重复面
  - Test: `backend/tests/integration/test_presentation_delete_permissions.py` - 已有删除权限验证样本

  **Acceptance Criteria**:
  - [ ] 所有 presentation 关键 endpoint 权限语义一致
  - [ ] uploader/admin/learner 权限测试齐全
  - [ ] 无“参数绑定但未使用”的假授权路径残留

  **QA Scenarios**:
  ```
  Scenario: Unauthorized presentation mutations are rejected
    Tool: pytest + curl
    Steps: 以 learner / non-owner / admin 角色分别请求 delete/replace/update
    Expected: 仅合法角色通过，其余返回统一权限错误
    Evidence: .sisyphus/evidence/task-11-presentation-auth.txt

  Scenario: Legitimate presentation flows still work
    Tool: Playwright / pytest
    Steps: 上传者或 admin 执行上传、替换、查看详情、开启练习
    Expected: 正常读写，前端不出现 403 误拦截
    Evidence: .sisyphus/evidence/task-11-presentation-happy.txt
  ```

  **Commit**: YES | Message: `fix(presentation): align authorization boundaries` | Files: presentation APIs + tests + any impacted client guards

- [ ] 12. 评估与 report 层参数化/泛化

  **What to do**: 去掉 `staged_evaluation.py` 的 `scenario_type="sales"` 硬编码；明确 sales / presentation / future scenario 的输入、提示词、rubric 映射与 report read-side 兼容边界；补齐对 report generation trigger 的场景化测试。
  **Must NOT do**: 不要在此任务中重做评分体系；只做“参数化、泛化、兼容”。

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: 评估逻辑跨场景、跨报告读面、跨契约
  - Skills: [`fastapi-python`, `pydantic`] - schema 与业务层泛化
  - Omitted: [`ultrabrain`] - 先做结构收敛而不是算法重设计

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: Final Verification | Blocked By: T1,T6

  **References**:
  - Pattern: `backend/src/evaluation/services/staged_evaluation.py` - 当前硬编码 TODO 点
  - Pattern: `backend/src/evaluation/api.py` - 评估 API 面
  - Pattern: `docs/api-contract/effectiveness.md` - 当前方法论/rubric contract
  - Pattern: `backend/src/common/conversation/api.py` - report/replay 读面

  **Acceptance Criteria**:
  - [ ] scenario_type 不再硬编码 sales
  - [ ] sales / presentation 都有明确评估路径与测试
  - [ ] report/read-side 不因泛化改造而破坏兼容性

  **QA Scenarios**:
  ```
  Scenario: Sales and presentation evaluations both resolve correct rubric path
    Tool: pytest
    Steps: 分别构造 sales / presentation session fixtures，运行 staged evaluation
    Expected: 两类场景均能生成合法结果，无 hardcoded sales fallback
    Evidence: .sisyphus/evidence/task-12-evaluation-tests.txt

  Scenario: Existing report/replay consumers remain compatible
    Tool: pytest + curl
    Steps: 对 report/replay API 跑回归测试
    Expected: 响应结构不破坏前端已存在消费者
    Evidence: .sisyphus/evidence/task-12-report-compat.txt
  ```

  **Commit**: YES | Message: `fix(evaluation): parameterize scenario-specific scoring` | Files: evaluation services/api/tests/contracts

- [ ] 13. 前端关键数据加载模式收敛

  **What to do**: 仅在高价值页面收敛重复的数据加载模式：current-user/auth、dashboard root、admin analytics、support/runtime、practice/report/replay 读面。把通用 query key、loading/error orchestration、缓存失效策略提炼到共享层；避免在 Phase 1 之外扩散到全站。
  **Must NOT do**: 不要迁移所有页面；不要重写 practice 实时状态管理。

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: 既涉及数据层，也影响用户可感知 loading/error/empty 状态
  - Skills: [`tanstack-query-best-practices`, `react-best-practices`] - 关键页状态收敛
  - Omitted: [`frontend-design`] - 不涉及视觉风格升级

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: Final Verification | Blocked By: T2,T9

  **References**:
  - Pattern: `web/src/components/providers/app-providers.tsx` - QueryClient 基线
  - Pattern: `web/src/hooks/use-current-user.ts` - 现有 Query 使用样本
  - Pattern: `web/src/app/admin/analytics/page.tsx:93-109` - Promise.allSettled 聚合样本
  - Pattern: `web/src/app/(dashboard)/support/runtime/page.tsx:179-196` - runtime 读面样本
  - Pattern: `web/src/app/(dashboard)/page.tsx` - learner dashboard 读面样本

  **Acceptance Criteria**:
  - [ ] 至少 4 个关键页面改为共享 query/data hook 模式
  - [ ] loading/error/retry 模式收敛，不再每页重复手写
  - [ ] 不触碰 practice 实时 websocket 状态主干

  **QA Scenarios**:
  ```
  Scenario: Refactored pages preserve current user-facing behavior
    Tool: Playwright
    Steps: 打开 dashboard、analytics、support/runtime、report/replay 关键页面
    Expected: 数据仍正确显示；loading/error 行为与旧逻辑等价或更好
    Evidence: .sisyphus/evidence/task-13-critical-pages.png

  Scenario: Query cache and invalidation behave predictably
    Tool: Vitest / Playwright
    Steps: 执行登录、切换页面、刷新 analytics/support
    Expected: current-user 缓存、页面刷新与 retry 行为符合预期
    Evidence: .sisyphus/evidence/task-13-query-cache.txt
  ```

  **Commit**: YES | Message: `refactor(web): consolidate critical page data loading` | Files: critical pages, shared query hooks, tests

- [ ] 14. 兼容面清理与文档同步

  **What to do**: 清理已确认的历史兼容面和陈旧文件：presentation 重复 CRUD、deprecated/backup 文件、已无价值的中间层；同步更新 AGENTS、契约文档、运行说明和 inventory/live authority 注释，防止后续误判系统完成度。
  **Must NOT do**: 不要删除仍在运行时使用的兼容路径；删除前必须通过全量门禁。

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: 以清理 + 文档同步 + 小范围代码收尾为主
  - Skills: [`document-release`, `find-skills`] - 文档与兼容说明收敛
  - Omitted: [`code-refactoring`] - 不是算法/架构重构任务

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: Final Verification | Blocked By: T2,T8,T11,T13

  **References**:
  - Pattern: `backend/src/admin/api/admin.py` - presentation 兼容面
  - Pattern: `backend/src/presentation_coach/api/presentations.py` - 真实 presentation 主 API 面
  - Pattern: `backend/src/sales_bot/services/sales_handler.py.deprecated` - 陈旧文件样本
  - Pattern: `backend/src/presentation_coach/api/presentations.py.backup` - backup 文件样本
  - Pattern: `docs/api-contract/README.md` - 契约总索引
  - Pattern: `web/src/app/admin/page.tsx:125-132` - inventory/live authority 说明

  **Acceptance Criteria**:
  - [ ] 已确认不用的重复/陈旧面被删除或文档化保留
  - [ ] 契约、AGENTS、运行文档同步更新
  - [ ] 不再保留容易误导开发者的 backup/deprecated 噪音文件

  **QA Scenarios**:
  ```
  Scenario: Cleanup does not remove live paths
    Tool: Bash + pytest + Playwright
    Steps: 跑全量质量门禁；抽样访问 presentation、sales runtime、admin analytics
    Expected: live 路径行为不变，无 404/导入错误
    Evidence: .sisyphus/evidence/task-14-cleanup-gate.txt

  Scenario: Documentation reflects actual shipped authority surfaces
    Tool: Read + Grep
    Steps: 检查 AGENTS、api-contract、运行说明与 admin inventory 说明
    Expected: 文档不再暗示未接通能力已 fully live
    Evidence: .sisyphus/evidence/task-14-doc-sync.md
  ```

  **Commit**: YES | Message: `chore(repo): remove stale compatibility layers and sync docs` | Files: deprecated/backup files, docs, contract notes, route cleanup

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle

  **What to do**: 让 Oracle 逐任务审查实际变更与本计划是否一致，检查是否遗漏了 T1-T14 的关键交付、是否提前做了被 guardrails 禁止的扩散改造。
  **Must NOT do**: 不要仅凭 commit message 判定合规；必须按任务与验收标准逐条比对。

  **QA Scenarios**:
  ```
  Scenario: Oracle validates delivered work against T1-T14 scope
    Tool: oracle
    Steps: 读取最终 diff、质量门禁结果、关键证据文件；逐条对照 T1-T14 的 Acceptance Criteria
    Expected: Oracle 给出“全部交付 / 缺失项 / scope creep”明确结论
    Evidence: .sisyphus/evidence/f1-plan-compliance.md

  Scenario: Guardrail violations are explicitly checked
    Tool: Bash + Read
    Steps: 审查最终变更是否出现全站 React Query 迁移、视觉重设计、无边界后端重写等禁行项
    Expected: 没有 guardrail violation；若有则列出并阻断完成
    Evidence: .sisyphus/evidence/f1-guardrail-check.txt
  ```

- [ ] F2. Code Quality Review — unspecified-high

  **What to do**: 用独立 reviewer 对最终代码进行结构、可维护性、重复逻辑、错误处理与测试可信度审查，重点盯 auth/db/realtime/contract 改动面。
  **Must NOT do**: 不要只看格式化与 lint 结果；必须看关键代码路径与测试质量。

  **QA Scenarios**:
  ```
  Scenario: Reviewer inspects critical changed files for maintainability regressions
    Tool: Bash
    Steps: 读取 auth、db、realtime、presentation、evaluation、frontend query 相关最终改动
    Expected: 无明显重复逻辑、临时 TODO、未解释的兼容分支、低质量测试样本
    Evidence: .sisyphus/evidence/f2-code-review.md

  Scenario: Automated checks remain green after review comments are applied
    Tool: Bash
    Steps: 重新运行 backend tests、alembic check、web typecheck、vitest、playwright
    Expected: 全部退出码为 0，且 reviewer 指出的风险已关闭
    Evidence: .sisyphus/evidence/f2-post-review-gate.txt
  ```

- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)

  **What to do**: 对最终用户可见流做真实操作验证，重点覆盖登录、训练入口、practice 实时交互、report/replay、admin analytics、support/runtime。
  **Must NOT do**: 不要只复用单条 smoke；要验证关键 happy path + 一个失败/降级 path。

  **QA Scenarios**:
  ```
  Scenario: Critical user journeys work in browser after all fixes
    Tool: Playwright
    Steps: 登录 → dashboard → training entry → practice session → report/replay → admin analytics → support/runtime
    Expected: 页面加载正常、交互成功、无 blocker 级 console/network error
    Evidence: .sisyphus/evidence/f3-critical-user-journeys.html

  Scenario: Failure/degradation paths remain honest and functional
    Tool: Playwright
    Steps: 在缺失 SSO 配置、部分 analytics/runtime API 失败、practice reconnect 情况下执行降级验证
    Expected: UI 不崩溃；错误/降级文案与设计一致；不会假装 fully live
    Evidence: .sisyphus/evidence/f3-degradation-paths.html
  ```

- [ ] F4. Scope Fidelity Check — deep

  **What to do**: 用独立深度审查确认最终改动既没有漏掉 ship blockers，也没有引入未计划的大范围扩散；特别检查 T14 清理是否误删 live surface。
  **Must NOT do**: 不要把“顺便修了点别的”视为可接受；范围必须受本计划控制。

  **QA Scenarios**:
  ```
  Scenario: Final diff matches remediation roadmap and nothing more
    Tool: Bash
    Steps: 对照 roadmap 读取最终 diff、变更文件列表、证据目录
    Expected: 改动面落在 T1-T14 规划范围内，没有未计划的大规模旁支工作
    Evidence: .sisyphus/evidence/f4-scope-fidelity.md

  Scenario: Cleanup did not delete live authority surfaces
    Tool: Bash
    Steps: 顺序执行 live surface 抽样验证脚本：presentation API/页面、sales runtime tests、admin analytics smoke、support/runtime smoke、auth smoke
    Expected: 所有 live surface 仍可访问且测试通过
    Evidence: .sisyphus/evidence/f4-live-surface-check.txt
  ```

## Commit Strategy
- One commit per task unless task spans schema + tests that must remain atomic.
- DB drift work (T6) must be committed atomically with migration + ORM + tests.
- Realtime hardening (T10) may split into 2 commits max: structural extraction, then tests/cleanup.
- Cleanup/doc sync (T14) must be last normal task before Final Verification Wave.

## Success Criteria
- Ship blockers removed: WeCom SSO no longer mock-only; canonical DB schema stabilized; critical E2E exists.
- Scaling blockers reduced: realtime hotspot decomposed, errors/contracts unified, critical data-fetch patterns consolidated.
- Cleanup debt reduced: duplicate/stale compatibility surfaces removed, docs/AGENTS/contracts synchronized.
- Quality gate is enforceable by agents, not dependent on ad hoc human memory.
