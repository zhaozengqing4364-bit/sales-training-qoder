# 当前工作区深度审计与理想架构演进方案

> 审计日期：2026-07-15
> 审计对象：sales-training-qoder 当前工作区，而不是仅审计 HEAD
> 分支：codex/newcomer-path-live-preview-layout
> 基准提交：db12a898
> 文档性质：现状审计、目标架构与整改路线图；不是功能已验收或生产可发布声明

---

## 0. 执行摘要

### 0.1 一句话结论

这个项目不是“架构很差”，而是“治理骨架已经相当完整，但关键运行时闭环还没有全部接实”。领域术语、不可变快照、发布修订、ADR、架构依赖门禁、测试资产和发布门禁都比普通同规模项目成熟；真正阻碍它达到理想状态的，是认证边界、数据迁移、并发一致性、持久任务、AI 调用治理、跨域依赖和证据可信性仍存在断点。

### 0.2 当前判断

- **审计初始快照健康分：72/100。** 这是整改前、按当时 17 项 finding 得出的分数；由于工作区仍混有大量未提交变更，整改后不伪造一个不可比较的新分数，改用下文逐项门禁证据判断。
- **当前工作区仍不应直接作为生产发布候选。** 原因不是主流程完全不可用，也不再是 Ruff/Mypy 失败——两项全量门禁已修复——而是生产密码重置交付、分布式限流、批量开户并发、持久任务和大工作区拆包仍未闭环。
- **不建议推倒重写，也不建议现在拆微服务。** 最合适的目标仍是“边界清晰、模块足够深、可持久恢复的模块化单体”。
- **“完美实现”不等于页面和接口更多。** 对本项目而言，它意味着从配置发布、训练执行、AI 评分、人工复核到达标结论，每一步都有不可变依据、权限范围、失败状态、恢复路径、审计记录和可验证的运行证据。
- **最先修的不是大文件，而是信任链。** 首发 schema、受管密码和 Team 权威已经收口；接下来的优先顺序应为：生产密码重置与分布式限流 → 组长只读可达性与批量开户并发 → 持久任务 → AI 与档案证据治理 → 依赖收敛与前端模块深化。

### 0.3 最重要的五个结论

1. 登录限流当前是进程内实现，并无条件信任转发头；多实例下限流不一致，错误代理配置下可绕过，恶意构造还可能造成内存增长。
2. 部门迁移碰撞风险已通过首发策略消除：不迁移旧开发数据，移除 `User.department`，所有数据库从新 baseline 重建，Team 成为唯一组织范围。
3. 环境共享密码登录 fallback 已退役，已有配置值保留但不再读取；console 密码重置投递和原始链接日志风险仍是当前认证 P0。
4. 音频处理、知识库处理和报告生成等用户可感知任务仍由 BackgroundTasks 或 asyncio.create_task 承担；ADR 已经准确描述目标，但当前只完成了 Phase 0 契约。
5. 现有 7 包强连通分量是“已治理、未消除”的架构债；依赖门禁通过只证明它没有继续扩大，不代表目标无环架构已经实现。

### 0.4 2026-07-15 首发基线整改状态

- 已建立新的单 root/head Alembic baseline，并将 pre-launch revisions 移出活动路径；应用启动只读校验 head。
- 已实现受保护的完整数据面 reset 编排、白名单配置快照、受管 temporary 管理员、幂等 system seed 和独立 verifier；目前只在隔离 PostgreSQL/Redis/文件目录验证，尚未对当前共享环境执行 `apply`。
- 当前 `backend/.env` 没有显式 `DATABASE_URL`，真实目标的只读 `inspect` 会以 `[RESET_DATABASE_URL_MISSING]` fail closed；在环境负责人提供并本地导出准确连接与范围前，工具不会猜测应用默认库，更不会执行删除。
- 已在同一隔离 PostgreSQL/Redis/文件数据面连续完成两次全量 reset，两次均得到同一 schema head、同一配置 fingerprint、一个临时管理员且业务表为空；另有中途失败后按原 manifest 续跑的证据。
- 已退役无保护的 `reset_db.py`、legacy schema repair 和 department-to-Team 迁移旁路。
- 本次整改不会自动删除或改写 endpoint、Secret、模型名、API key；数据库配置以原 ciphertext 和逻辑键恢复。
- 全量 Ruff、Mypy、TypeScript、前端测试和 Next.js production build 已恢复为绿色；后端完整 unit+contract 及首发关键集成链路的最新自然退出结果见 5.1。
- 因此下文 F-02 中的 shared-password 登录部分、F-03 的迁移脚本风险和 F-13 的旧 downgrade 风险属于“审计时成立、当前已按首发策略收口”；console reset transport、分布式限流、并发一致性、持久任务等结论仍有效。

---

## 1. 审计边界、方法与可信度

### 1.1 快照口径

审计开始时，当前工作区包含大规模未提交改动。复核时可见：

- 167 个已跟踪状态项；
- 47 个未跟踪状态项，其中包含本次审计的临时记录；
- 已跟踪差异约 7,689 行新增、1,427 行删除；
- 改动横跨账号、凭证、团队、批量开户、新人训练编排、管理后台和测试。

因此，本文把当前工作区视为正在形成的真实系统，而不是忽略未提交改动只看 db12a898。这个口径能更早发现正在引入的风险，但也意味着后续若工作区继续变化，结论需要按提交重新复核。

### 1.2 审计范围

本次覆盖：

- 领域模型与产品目标：CONTEXT.md；
- 系统架构与模块边界：docs/architecture.md、依赖政策；
- docs/adr 下全部 ADR；
- 后端业务、权限、认证、数据、迁移、后台任务、AI、指标；
- 前端路由、权限、API 契约、页面状态和高耦合区域；
- 单元、契约、集成、性能与浏览器测试资产；
- CI、质量门禁、发布与回滚文档；
- 当前未提交变更，而不仅是历史主分支。

### 1.3 分析方法

- 先同步并使用 CodeGraph 建立调用链与模块关系，索引状态为 1,957 个文件、35,833 个节点、95,759 条边；
- 对共享符号、权限链路、训练路径、持久任务、AI 调用和前端 API façade 做调用者与影响面复核；
- 对高风险结论回到当前磁盘源码核对行级证据；
- 运行架构门禁、静态检查、后端测试、前端测试和生产构建；
- 使用 Brooks-Lint Health Dashboard 的四维方法审视代码质量、架构、技术债和测试质量；
- 使用 Module、Interface、Implementation、Depth、Seam、Adapter、Leverage、Locality 和删除测试评估目标抽象是否值得存在。

### 1.4 未覆盖与残余不确定性

本次没有：

- 连接真实生产数据库执行部门迁移；
- 在两个或更多真实应用进程上验证登录限流；
- 对 PostgreSQL 执行批量开户并发确认压力测试；
- 执行 Playwright 全套浏览器测试；
- 调用真实 LLM、ASR、TTS、StepFun、COS 或企业微信；
- 执行生产备份恢复演练、故障注入、滚动发布或容量测试；
- 使用真实生产流量验证 SLO 和告警。

因此，本文对上述项目采用“已证实代码风险”“条件性生产风险”或“待验证能力缺口”的措辞，不把静态迹象伪装成线上事故。

---

## 2. 领域目标与当前系统画像

### 2.1 领域北极星

CONTEXT.md 已经明确：

- 新人训练路径不是实时销售对练的别名；
- 北极星结果是“每个新人形成一份可信的训练达标档案”；
- 训练达标档案必须回答练过什么、提交什么、AI 按什么标准评分、哪些能力达标、是否人工复核、未达标后是否重练；
- 历史 attempt、submission、session 和 result 必须读取创建时冻结的 snapshot 或 revision ref，不得用最新资产重建历史；
- Roleplay Contract 是运行时冻结合同，实时 Provider 不得回读最新配置重组语义。

这是非常好的领域边界。后续架构判断均以“训练达标结论是否可信”作为最高优先级，而不是以代码分层是否看起来整齐作为目标。

### 2.2 当前规模

| 区域 | 当前规模 |
| --- | ---: |
| 后端生产 Python | 652 个文件，约 202,945 行 |
| 前端 TypeScript / TSX | 638 个文件，约 148,602 行 |
| 后端测试文件 | 404 个 |
| 前端 Vitest 测试文件 | 191 个源测试文件；实跑收集 192 个测试文件 |
| 前端 Playwright spec | 7 个 |
| 后端 E2E 文件 | 2 个 |
| 架构包 | 15 个 |
| 当前跨包边 | 52 条 |
| 历史强连通分量 | 7 个包 |

### 2.3 当前架构的高层形态

~~~mermaid
flowchart TB
    User["学员 / 培训负责人 / 管理员 / 运维"]
    Web["Next.js 页面与组件"]
    SDK["全局 api façade + 逐步抽出的 domain builders"]
    Registry["FastAPI app_factory / router_registry 组合根"]

    User --> Web --> SDK --> Registry

    subgraph SCC["受控但仍存在的 7 包 SCC"]
        Common["common"]
        Agent["agent"]
        Curriculum["curriculum_practice"]
        Evaluation["evaluation"]
        Prompt["prompt_templates"]
        Trainer["sales_trainer"]
        Support["support"]

        Common <--> Agent
        Common <--> Curriculum
        Common <--> Evaluation
        Common <--> Prompt
        Trainer --> Common
        Support --> Common
        Curriculum <--> Trainer
        Agent <--> Support
        Curriculum --> Support
        Trainer --> Agent
    end

    Registry --> SCC
    Registry --> Admin["admin：管理交付层，但仍直接聚合多个领域"]
    Registry --> Runtime["training_runtime / sales_bot / presentation_coach"]
    Runtime --> Providers["StepFun / ASR / TTS / LLM / RAG Provider"]
    SCC --> Data["PostgreSQL / Redis / Chroma / 本地或对象存储"]
    Admin --> SCC
~~~

这个图只展示高风险依赖关系，不展开全部 52 条跨包边。router_registry 的高 fan-out 本身不是问题，因为组合根天然需要装配很多实现；真正的问题是 common 和若干业务包仍相互依赖、admin 仍直接了解多个领域内部实现。

---

## 3. 已经做得好的部分

### 3.1 领域语言和历史真实性

- CONTEXT.md 对训练路径、达标档案、能力项、发布修订、快照、配置双轨和 Roleplay Contract 的定义清楚。
- “历史记录不得从 latest asset 重建”是一条正确且高价值的系统不变量。
- 新人训练路径和实时对练被明确分开，避免了因为复用技术模块而扭曲产品语言。

### 3.2 架构治理不是口号

- module-dependency-policy.yaml 把稳定边、临时边、owner、退役条件和到期日变成了可执行政策。
- architecture_dependency_guard.py 能扫描静态 import、函数内 import、TYPE_CHECKING 和字面量动态 import。
- 当前门禁实跑通过，说明新改动没有违反已声明的依赖基线。
- 文档明确承认 7 包 SCC 仍存在，没有把“门禁通过”写成“系统已无环”。

### 3.3 测试和发布门禁基础很强

- 后端全量 unit + contract、integration 都能在当前工作区通过；
- 前端 Vitest、TypeScript、ESLint 和 Next.js 生产构建通过；
- critical-quality-gate 已包含 Ruff、架构门禁、全量 Mypy、后端覆盖率、前端覆盖率、按变更选择的 integration / E2E 和 changed coverage；
- release-truth-gate 配置了 PostgreSQL、Redis 和浏览器依赖，不再只是少量白名单测试。

### 3.4 当前新功能里有正确的安全与产品设计

- 管理员创建账号时只持久化临时密码哈希，明文只在响应中返回；
- credential_version 可使旧会话失效；
- 临时凭证只能取得 password_change scope；
- 显式团队关系保留 effective_from / effective_to，部门字符串不再作为授权权威；
- 团队页面支持在当前流程中快速新建缺失的学员或组长，符合上下文内完成原则；
- 批量开户按团队做 savepoint，单个团队失败不会回滚已完成的其他团队；
- 新人路径编辑器已经具备资源选择、快速创建、检查、发布、预览和冲突 revision id。

### 3.5 已经存在值得保留的深模块

- RealtimeProviderPort 已形成真实 Provider seam，运行时引擎与 StepFun transport 的分离方向正确；
- Roleplay Contract 把多处运行时语义冻结成一个深接口；
- 训练路径 revision / snapshot 把复杂的历史一致性隐藏在相对稳定的契约后；
- 前端 domain builder 正在从全局 client 中抽离传输细节，这个方向值得继续，但迁移尚未完成。

---

## 4. Brooks-Lint Health Dashboard（整改前快照）

**Mode:** Health Dashboard
**Scope:** 整个项目的当前脏工作区快照
**Composite Score:** 72/100（整改前，不作为当前发布分数）
**Trend:** First run — no trend data

| Dimension | Score | Top Finding |
| --- | ---: | --- |
| Code Quality | 65/100 | 当时变更包含认证与迁移安全风险，且 Ruff / Mypy 门禁为红；两项静态门禁现已修复 |
| Architecture | 65/100 | 7 包 SCC 与进程内用户可感知任务仍未退役 |
| Tech Debt | 75/100 | 共享密码、AI 治理和文档权威仍是显式过渡债 |
| Test Quality | 85/100 | 测试数量和通过率强，但并发、崩溃恢复和生产适配器证据不足 |

计分采用 balanced 预设：Critical 每项减 15，Warning 每项减 5，Suggestion 每项减 1；每个维度最多计入 3 个 finding。综合权重为代码质量 25%、架构 30%、技术债 25%、测试 20%，加权结果 71.5，四舍五入为 72。

历史中的多个 100 分记录都是 Gate 3–6 的增量 Architecture Audit，只审计特定变更集合，并明确排除了无关脏工作区。它们不能与本次全工作区 Health Dashboard 直接比较，也不能作为当前发布证明。

### Top Findings

#### Critical — R4 Accidental Complexity：认证限流把部署拓扑和代理信任隐含在内存字典里

**Symptom:** APIRateLimiter 使用单进程字典计数，无条件读取 X-Forwarded-For / X-Real-IP，blocked key 又不会被周期清理。
**Source:** Code Complete — Defensive Programming。
**Consequence:** 多 worker 下请求可以分摊绕过限额；不可信转发头可伪造来源；攻击者可制造大量永久 blocked key 造成内存增长。
**Remedy:** 使用带 TTL 的共享原子存储，明确 trusted proxy allowlist，限制键空间，并把生产配置纳入 release readiness。

#### 已收口的原 Critical — R6 Domain Model Distortion：中文部门会被迁移成同一个团队编码

**Symptom:** migrate_departments_to_teams.py 只保留 a-z0-9，纯中文部门都会得到 team；脚本随后按该编码复用已有 Team。
**Source:** Domain-Driven Design — Ubiquitous Language 与 Identity。
**Consequence:** 原本不同的部门可能被合并到同一授权边界，造成成员和组长越权可见，且迁移表面上仍能成功。
**Remedy:** 迁移前生成显式映射与碰撞报告，编码使用稳定映射或“可读前缀 + 稳定短哈希”，发现碰撞时 fail closed。

#### Critical — R5 Dependency Disorder：7 包强连通分量仍然存在

**Symptom:** agent、common、curriculum_practice、evaluation、prompt_templates、sales_trainer、support 仍处于一个 SCC。
**Source:** Clean Architecture — Dependency Rule。
**Consequence:** 领域改动可能沿循环边传播，common 无法成为真正稳定的内核，测试选择和独立理解成本持续升高。
**Remedy:** 先删除 common 指向领域包的上行边，再拆 agent/support 和 curriculum/sales_trainer 的双向依赖；每删除一条边同步收缩 policy。

#### Critical — R4 Accidental Complexity：用户可感知任务仍依赖进程生命周期

**Symptom:** 音频处理、知识库文档处理和报告生成仍通过 BackgroundTasks 或 asyncio.create_task 触发；持久任务 ADR 只完成契约冻结。
**Source:** Software Engineering at Google — Sustainability 与规模下的可靠性。
**Consequence:** 崩溃、滚动发布或实例回收后，任务可能丢失或永久停在 processing，用户只能看到不完整结果。
**Remedy:** 实现数据库任务表、原子 claim、lease、retry_wait、dead letter、事件审计和幂等 handler，再按任务类型灰度接管。

#### 部分收口的原 Critical — R3 Knowledge Duplication：凭证权威曾分裂为哈希、共享密码和 console 重置链接

**Symptom:** 登录会对无 hashed_password 的账号回退到 AUTH_USER_PASSWORDS_JSON / AUTH_SHARED_PASSWORD；密码重置只有 console adapter，默认把含原始 token 的 reset_link 写入日志；生产配置检查没有禁止这些模式。
**Source:** The Mythical Man-Month — Conceptual Integrity。
**Consequence:** 一个共享秘密可能影响大量账号；拥有日志读取权的人可能获取重置 token；系统无法证明生产凭证只有一个权威。
**Remedy:** 提供真实交付实现，禁止生产 console transport，迁移所有活跃账号到受管凭证，并由 release readiness 阻止共享密码兼容模式上线。

---

## 5. 实测验证结果

### 5.1 已运行

| 检查 | 命令摘要 | 结果 |
| --- | --- | --- |
| CodeGraph | sync / status / explore / node | 索引已同步，1,957 文件，35,833 节点，95,759 边 |
| 架构依赖门禁 | architecture_dependency_guard.py --check | 通过 |
| Git 空白检查 | git diff --check | 通过 |
| 后端 Ruff | `.venv/bin/ruff check src tests scripts` | 通过 |
| 后端 Mypy | `.venv/bin/mypy src` | 670 个 source files 全部通过 |
| 新账号/团队/新人路径定向测试 | 相关 unit + integration | 111 passed，1 warning，63.68s |
| 后端 unit + contract（整改后全量） | `.venv/bin/pytest -q tests/unit tests/contract` | 3,126 passed，1 skipped，76 warnings；coverage 68.71%，自然退出 0，755.83s |
| Reset 最新增量 | stage resume + snapshot encryption/tamper | 7 passed；另有 secret hygiene 1 passed |
| 首发关键 integration（整改后） | auth/admin users/teams/provisioning/Team scope/newcomer/sales trainer/password reset/startup | 89 passed，1 warning，61.35s |
| 后端 integration（审计初始全量） | `pytest tests/integration --no-cov` | 544 passed，21 skipped，67 warnings，278.34s；首发整改后未重跑所有非相关 integration |
| 前端 TypeScript | tsc --noEmit | 通过 |
| 前端 ESLint | eslint . | 退出 0；0 error，80 个当前工作区 warning |
| 前端 Vitest | vitest run | 192 files passed；1,157 passed，6 skipped，约 307s |
| 前端生产构建 | next build | 通过；完成 89 个静态页面数据生成单元 |
| Alembic 当前一致性 | heads / current / check | 唯一 head/current 均为 `20260715_0000_001`；No new upgrade operations detected |
| 隔离完整 reset | PostgreSQL 55432、Redis DB 14、临时文件/Chroma | 连续两次完成；同一配置 fingerprint、一个临时管理员、业务表为空；未连接 COS |

### 5.2 如何解释这些结果

- 大量测试通过，说明项目具备真实的回归资产，不是“只能演示”的空壳；本轮还把 Ruff/Mypy 从红恢复为绿，SQLAlchemy 类型问题通过 typed mapping 修复，没有用全局 ignore 掩盖。
- unit + contract 仍有 76 个 warnings，其中包括 replay 测试里的 AsyncMock coroutine 未等待，以及第三方弃用/收集 warning。测试通过不等于 warning 可以永久忽略；这也是全量门禁尚未等价于生产发布证明的原因之一。
- 当前全量 unit + contract 覆盖率为 68.71%，超过仓库 48% 阈值；该数字只代表这一组测试，不代表真实 Provider、并发、故障恢复或浏览器闭环覆盖。
- 首发整改后重跑了 89 个认证、账号、Team、开户、新人、销售训练和 startup 关键 integration；其余 integration 只有审计初始全量证据，发布前仍应在拆分后的目标 commit 上自然退出一次。

### 5.3 未运行

- Playwright 全套 E2E；
- critical-quality-gate 作为一个完整脚本的自然退出；其 Ruff、Mypy、unit/contract、关键 integration 和前端主要组件已分别通过，但 selected E2E、changed coverage 等后段仍未形成同一次证据；
- 首发整改后的后端全量 integration（当前只有整改前全量证据和整改后 89 个关键链路证据）；
- performance / NFR 全套；
- 真实 Provider 与真实对象存储集成；
- PostgreSQL 并发、进程崩溃、滚动发布和恢复演练。

这些是发布前仍需补齐的证据，不应在交付说明中写成“隐含通过”。

---

## 6. 风险总表

| ID | 优先级 | 结论 | 类型 | 影响面 |
| --- | --- | --- | --- | --- |
| F-01 | 条件性 P0 | 限流不跨进程且代理头无信任边界 | 已证实代码风险 | 登录、忘记密码、可用性 |
| F-02 | 条件性 P0 | 共享密码 fallback 已退役；console 重置链接仍未被生产门禁阻止 | 部分完成，剩余代码风险 | 全部账号、日志安全 |
| F-03 | 已完成 | 不再执行部门历史迁移；`User.department` 已移除，Team 为唯一权威 | 首发 baseline 已消除 | 团队权限、历史迁移 |
| F-04 | P1 | training_manager 的任务只读能力被路由外层提前拒绝 | 已证实权限缺陷 | 组长工作台 |
| F-05 | P1 | 批量开户只保证顺序幂等，不保证并发幂等 | 高置信一致性风险 | 账号、团队、批次状态 |
| F-06 | P1 | 持久任务只有契约，没有表、worker 和运行时接管 | 已承认过渡债 | 音频、知识库、报告 |
| F-07 | P1 | AI 调用绕过统一治理，max_tokens 配置未生效 | 已证实治理缺口 | 成本、可追溯、输出一致性 |
| F-08 | P1 | 7 包 SCC 与 9 组临时依赖仍待退役 | 受控架构债 | 全后端变更传播 |
| F-09 | P1 | 前后端各自维护角色和 capability 语义 | 已证实知识重复 | 导航、路由、权限解释 |
| F-10 | P1 | 档案和 replay 的部分证据失败会静默变成 None | 已证实可信性风险 | 训练达标档案 |
| F-11 | P1 | 配置中心仍以 not_started / read_only 为主 | 显式过渡债 | 配置权威、发布回滚 |
| F-12 | P1 | HTTP 指标使用原始 URL path 标签 | 已证实运维风险 | Prometheus 稳定性 |
| F-13 | 已完成 | 旧破坏性 revision 已归档且不再可执行；首发后采用 forward-only 增量 | 首发 baseline 已消除旧链风险 | 团队、开户数据 |
| F-14 | P1 | Ruff/Mypy 已修复，但变更包仍过大且工作区不干净 | 部分完成，剩余交付风险 | 审查、回滚、发布 |
| F-15 | P2 | 前端全局 API/type façade 和巨型页面传播改动 | 受控技术债 | 前端维护与测试选择 |
| F-16 | P1 | 高风险并发、重启、生产适配器测试缺口 | 已证实测试缺口 | 数据和可靠性证明 |
| F-17 | P1 | 文档 source of truth 路径失效或未纳入版本控制 | 已证实治理缺口 | Agent、开发、审计 |

---

## 7. 详细问题分析

### F-01：认证限流的共享状态和代理信任边界不成立

**证据**

- backend/src/common/rate_limit/api_limiter.py:34-58 明确是 In-memory API rate limiter；
- 其状态保存在单例字典 _storage；
- 226-242 行直接信任 X-Forwarded-For 和 X-Real-IP，不判断直接对端是否为可信代理；
- 70-77 行清理过期项时排除 blocked 条目；
- 登录 key 是 IP + email，攻击者可以通过伪造来源和邮箱扩大键空间。

**Symptom:** 安全控制的正确性取决于“恰好只有一个应用进程”和“上游恰好清洗了转发头”，但这两个前提没有被代码或发布门禁表达。
**Source:** Code Complete — Defensive Programming。
**Consequence:** 多实例时每个进程独立计数；未清洗代理头时可绕过限流；大量 blocked key 可长期占用内存；日志中还会记录 IP:email 组合。
**Remedy:** 将登录和找回密码限流迁移到 Redis 原子脚本或等价共享存储；只在 request.client.host 属于 trusted proxy allowlist 时读取转发头；所有 key 设置 TTL；对键做规范化和散列；明确 Redis 故障时登录和找回密码的 fail-open / fail-closed 策略。

**验收**

- 两个应用进程共同消耗同一个限流额度；
- 不可信客户端自己发送 X-Forwarded-For 时被忽略；
- 10 万个不同标识过期后键数量回落；
- release readiness 在 production 下校验 trusted proxy 和共享限流配置；
- 测试覆盖 IPv4、IPv6、代理链、空 client、Redis 不可用和时钟窗口边界。

### F-02：生产凭证权威仍没有闭环

**当前状态（2026-07-15）**：受管密码已成为登录唯一权威；`AUTH_SHARED_PASSWORD` / `AUTH_USER_PASSWORDS_JSON` 的现有环境值不会被 reset 删除，但生产认证代码不再读取。下面关于 shared-password fallback 的源码行号是审计时证据，现已失效。console password reset、原始 reset link 日志和 production readiness 缺口仍未修复，因此本 finding 只关闭了一半。

**证据**

- backend/src/common/auth/api.py:292-353 先查用户哈希，再回退 AUTH_USER_PASSWORDS_JSON 和 AUTH_SHARED_PASSWORD；
- backend/src/common/services/password_reset.py:36-69 的 EmailService 只有 ConsoleEmailService 一个运行时实现，没有真实生产投递实现；
- 默认 PASSWORD_RESET_EMAIL_TRANSPORT=console；
- ConsoleEmailService 会把包含原始 token 的 reset_link 写入应用日志；
- backend/src/common/monitoring/logger.py:21-31、157-180、247-298 只按字段名标记脱敏；reset_link 不命中敏感标记，底层 structlog processor 也没有接入 URL/token 内容扫描，因此完整链接不会被当前共享日志链路清除；
- backend/src/common/analytics/release_readiness.py:74-128 检查 dev login、secret、JWT、debug、CORS，但没有检查共享密码、未迁移账号或 console reset transport。

**Symptom:** “受管用户哈希”“环境共享密码”“控制台重置链接”同时具有认证意义，生产模式没有强制收敛到一个凭证权威。
**Source:** The Mythical Man-Month — Conceptual Integrity。
**Consequence:** 共享密码泄露的爆炸半径覆盖全部兼容账号；日志读者可能拿到未消费的重置 token；用户收到“重置链接已发送”但实际只有服务日志；无法证明所有活跃账号都可独立撤销。
**Remedy:** 先实现真实的企业微信、IAM 或邮件投递 Implementation，再保留 EmailService Interface；迁移所有活跃用户到 hashed_password；增加 production release checks，拒绝 console transport、拒绝 AUTH_SHARED_PASSWORD、拒绝仍无哈希的活跃账号；token 只能以 hash 入库，日志中不得出现原始 token 或完整 URL。

**验收**

- production 启动在 console transport 或共享密码启用时失败；
- 数据库检查显示全部活跃账号拥有受管凭证或明确的外部 IdP 绑定；
- 找回密码可真实投递、可审计但不可从日志恢复 token；
- token 只能使用一次，重发会撤销旧 token；
- 凭证迁移具备 dry-run、总量、冲突清单、灰度和回滚窗口。

### F-03：部门到团队迁移存在确定性的编码碰撞

**当前状态（2026-07-15）**：已通过首发 baseline 策略整体消除，而不是修补历史转换算法。旧 migration/script 只归档留证，不进入新库；`users.department`、`User.department` 和部门字符串授权 fallback 已从首发 schema/生产链路移除，Team 关系成为唯一组织和权限权威。下面内容保留为“不应重新激活旧迁移”的历史依据。

**证据**

- backend/scripts/migrate_departments_to_teams.py:22-24 使用正则仅保留 a-z0-9；
- “华东销售”“华南销售”“销售一部”等纯中文名称都会变成 team；
- 69-75 行按编码查找已有 Team，命中后会复用；
- 76-82 行随后把组长和学员写入这个团队；
- 脚本检查了“每部门恰好一个组长”，却没有检查不同部门的 code collision。

**Symptom:** 业务身份 department 被映射到一个不具单射性的技术 slug。
**Source:** Domain-Driven Design — Identity。
**Consequence:** 不同部门可被合并到同一 Team，直接改变对象级授权；脚本还能继续返回成功，使错误难以及时发现。
**Remedy:** 将迁移拆成“发现 → 显式映射审批 → 应用”三步；生成 department、proposed_code、leader、member_count、collision_group 的 CSV/JSON 清单；编码使用人工映射优先，自动值采用规范化前缀加稳定短哈希；任何碰撞、已有团队同码异名、重复成员或多个主组长都必须阻止 apply。

**验收**

- 中文、空白、符号、大小写、同音和超长名称都有测试；
- dry-run 输出每个预计写入和跳过原因；
- apply 必须绑定 dry-run 产物 hash，防止审批后数据漂移；
- 迁移后校验每位学员最多一个主团队、每团队最多一个主组长；
- 在真实 PostgreSQL 快照副本上执行并提供恢复证明。

### F-04：团队组长的任务只读能力在路由层不可达

**证据**

- backend/src/common/training_tasks/service.py:38-89 已实现 TeamScopePolicy 驱动的组长读取；
- backend/src/common/api/training_tasks.py 的 GET list / detail 会调用该对象级策略；
- create、batch assign、update、cancel、expire 等写操作仍在 endpoint 内用 can_manage_training_tasks 限制为平台管理员；
- 但 backend/src/router_registry.py:128-132 在整个 router 外层只允许 admin、support、user；
- role_matches_allowed 不会把 training_manager 映射成其中任意角色。

**Symptom:** 应用服务表达了“组长可读、不可写”，组合根却在进入应用服务前拒绝了组长。
**Source:** Clean Architecture — Policy 不应散落在外层机制。
**Consequence:** 组长工作台无法复用已经实现的团队范围读取；开发者可能为了修页面另开旁路接口，进一步复制权限逻辑。
**Remedy:** 让 router 外层只承担认证，能力和对象范围由 endpoint / application policy 决定；如果暂时保留角色 gate，至少加入 training_manager，但必须保留每个写 endpoint 的管理员检查。

**验收**

- 通过完整 app mount，以 training_manager token 调用 GET list / detail，能看到本团队且看不到外部团队；
- 同一 token 调用 create、batch assign、update、cancel、expire、complete 他人任务和 start 他人任务均为 403 或 404；
- user 只能读自己的任务；
- admin 行为不回归。

### F-05：批量开户的幂等只在顺序调用下成立

**证据**

- backend/src/admin/services/provisioning.py:223-420 的 confirm 先读取 batch 和 executions，再把状态改成 processing；
- 没有 SELECT FOR UPDATE、条件 UPDATE、版本号或 lease；
- 两个请求可同时看到同一个 pending execution；
- 唯一约束可能阻止重复用户，但不能保证 batch 和 execution 最终状态由唯一执行者写入；
- backend/tests/integration/test_bulk_provisioning_service.py:27-60 的“idempotent”测试是先 confirm 完成后再顺序调用第二次；
- test_admin_users_api.py 的 “multiple_updates” 测试同样是两个顺序 await，不是并发测试。

**Symptom:** API 有 idempotency_key 和状态字段，但没有原子状态领取，因此命名提供了超过实现的安全感。
**Source:** Software Engineering at Google — Tests 应验证真实的并发语义。
**Consequence:** 并发确认可能让两个事务重复创建、互相触发唯一约束、覆盖 batch 状态，或让成功数据对应失败批次；客户端无法可靠判断是否需要重试。
**Remedy:** 对 batch 使用 compare-and-set 或 FOR UPDATE SKIP LOCKED；对每个 team execution 做原子 claim；失败请求返回稳定的 409 in_progress / already_completed；结果表持久化非敏感摘要，明文凭证仍只在成功执行者的单次响应中出现；所有 handler 保持幂等。

**验收**

- 两个独立 PostgreSQL session 同时 confirm 同一 batch，只有一个取得 claim；
- 最终用户、团队、成员和组长关系无重复；
- batch / execution 状态与真实数据一致；
- 请求在 commit 前断开、commit 后响应中断、worker 崩溃都有明确重试结果；
- 只把真实并发测试命名为 concurrency。

### F-06：持久任务 ADR 正确，但实现停留在 Phase 0

**证据**

- docs/adr/2026-07-06-persistent-background-task-contract.md 明确写明当前只冻结状态机，不接管运行时；
- CodeGraph 只发现 backend/src/common/jobs/persistent_task_contract.py 中的状态、重试和失败分类；
- 没有 persistent_tasks migration、repository、worker、claim 或 lease sweeper；
- 音频仍由 sales_trainer/api.py:257-267 的 BackgroundTasks 调度；
- 知识库文档处理仍由 common/knowledge/api.py 的 BackgroundTasks 调度；
- 报告生成仍在 common/db/session_lifecycle.py:504-549 使用 asyncio.create_task。

**Symptom:** 业务对象有 processing / failed / retry 等状态，但任务执行事实不持久。
**Source:** A Philosophy of Software Design — 模块接口没有隐藏完整复杂性。
**Consequence:** HTTP 进程退出时任务事实消失；滚动发布可能留下永久 processing；多实例重复执行没有 lease；人工只能从业务状态反推任务发生了什么。
**Remedy:** 按既有 ADR 实现数据库任务记录和事件表，由 application transaction 同时写业务状态与 task/outbox；worker 原子 claim、续租、分类重试、死信；业务 handler 留在所属领域，common/jobs 只拥有调度语义。

**验收**

- enqueue 幂等、claim、lease 过期恢复、retry、dead letter、cancel 和事件审计在 PostgreSQL 上通过；
- worker 在“副作用完成但状态未提交”后重跑不会重复评分、重复向量写入或重复报告；
- 进程重启后 queued / running 任务可恢复；
- UI 能显示业务结果位置、处理中、失败原因和重试动作，而不是只显示 toast。

### F-07：AI 调用没有统一穿过治理边界

**证据**

- presentation_coach/services/point_extraction.py:49-90 在服务内部硬编码 Prompt，并直接调用 get_llm_service().llm.apredict；
- sales_bot/services/summary_service.py:54-123 同样硬编码 Prompt 并直调底层 LLM；
- common/ai/config_manager.py:273-284 会读取 LLM_MAX_TOKENS；
- common/ai/llm_service.py:215-243 只消费 temperature、timeout 和 max_retries；
- OpenAI、Azure 和 Anthropic 初始化均没有传入 max_tokens。

**Symptom:** 配置看起来支持 max tokens，实际调用不生效；部分 Prompt 和调用绕过版本、lineage、cost、audit 和统一 schema。
**Source:** The Pragmatic Programmer — DRY 是知识单一表达，而不只是代码去重。
**Consequence:** 成本上限不可依赖；同一模型配置在不同路径表现不同；无法回答某次结论使用了哪个 Prompt revision、模型配置和降级策略；直接 apredict 路径难以统一熔断、配额和可观测性。
**Remedy:** 建立 AiInvocation Module，Interface 接收 task_type、prompt_ref/revision、structured input、output schema、model policy、max tokens、timeout、trace context 和 actor；OpenAI-compatible、Azure、Anthropic 作为真实 Adapter；所有调用返回带 lineage、usage、cost、latency、degradation 和 validation 的结果。

**验收**

- 静态扫描禁止业务代码访问 .llm.apredict / ainvoke；
- max_tokens 在所有 Provider contract test 中可观察生效；
- 每个 AI 结果都能关联 prompt revision、model config version、输入摘要、token usage 和 trace；
- schema 解析失败明确标为 degraded/failed，不得用默认分冒充已验证事实；
- 高风险输出进入人工复核，不直接改变达标结论。

### F-08：7 包 SCC 是受控债，不是已完成目标

**证据**

- docs/architecture.md:1052-1056 明确列出 7 包 SCC；
- module-dependency-policy.yaml 有 9 组 temporary_edges，全部到期日为 2026-10-31；
- common 仍指向 agent、curriculum_practice、evaluation、prompt_templates、roleplay；
- curriculum_practice 与 sales_trainer、agent 与 support 仍有双向关系；
- 当前架构 guard 通过。

**Symptom:** 项目有很强的依赖治理，但稳定内核仍向业务实现上行，多个 Bounded Context 不能独立理解。
**Source:** Clean Architecture — Dependency Rule。
**Consequence:** common 的任何改动都可能触发广泛回归；跨域查询容易直接读取实现模型；临时边如果只延期不删除，会把迁移政策变成永久白名单。
**Remedy:** 按“删边”而不是“拆文件”推进：第一优先 common → domain；第二优先 agent ↔ support；第三优先 curriculum_practice ↔ sales_trainer；admin 最终只调用各领域 governance port。每条边必须有 consumer 清单、替代接口和零调用删除证明。

**验收**

- baseline_sccs 从 7 逐步缩小，最终为空；
- common 不 import 任何业务包；
- admin 只依赖 application interface / read model；
- 每次删边同步删除 temporary edge，而不是等到统一到期；
- 到期日前 CI 对任何未退役临时边 fail closed。

### F-09：角色与 capability 知识在前后端重复表达

**证据**

- backend/src/common/auth/roles.py 集中维护后端角色词表、别名和角色集合；
- web/src/lib/auth/current-user.ts 又维护一套 PLATFORM_ADMIN、CONTENT_ADMIN、MANAGER、OPERATIONS 和 AUDITOR 集合；
- web/src/components/layout/sidebar.tsx:116-123 仍直接比较 admin、support、training_manager；
- report、replay、login redirect 和若干管理页面也存在直接 role equality；
- 后端 router mount、endpoint policy、sales_trainer permissions、前端导航和页面 gate 的角色粒度不完全一致。

**Symptom:** 同一个“谁能做什么”的业务知识同时出现在路由、服务、前端 helper、sidebar 和页面。
**Source:** Refactoring — Shotgun Surgery 与 Divergent Change。
**Consequence:** 新增或调整角色需要多处同步；合法角色可能看不到入口或被错误跳转；前端 capability 与后端对象级权限可能给出不同解释。
**Remedy:** 后端成为唯一授权权威，在 current-user / session response 返回稳定 CapabilitySet 和 scope summary；前端只用 capability 控制展示和交互，不重新推导角色；对象级授权仍在后端 application policy 执行。

**验收**

- 前端生产代码不再根据 raw role 推导业务能力，展示文案映射除外；
- capability contract 有版本、默认 fail closed、测试矩阵和审计解释；
- 每个高风险页面同时验证“入口是否展示”和“API 是否允许”；
- training_manager、support、content_admin、operations、readonly_auditor 和别名角色都有端到端契约测试。

### F-10：证据加载失败与“确实没有证据”没有被区分

**证据**

- backend/src/common/conversation/replay.py:357-367 在构建 audio_audit 时捕获所有 Exception；
- 捕获后只把 replay_data.audio_audit 设为 None；
- 该路径没有结构化日志、指标、degradation code 或用户可恢复动作；
- 同一系统把“可信训练达标档案”定义为北极星结果。

**Symptom:** 技术失败、数据缺失和业务上不存在音频被折叠为同一个 None。
**Source:** Domain-Driven Design — 模型必须表达业务上不同的状态。
**Consequence:** 培训负责人可能把“证据加载失败”误解为“学员没有音频证据”；审计无法证明结论是否基于完整材料；静默降级违反仓库的失败显眼原则。
**Remedy:** 对证据采用 available / absent / unavailable 三态或等价结构；unavailable 必须带 reason_code、trace_id、last_success_at、retryable 和恢复动作；记录结构化日志与指标，但不让次要证据故障击穿整个 replay。

**验收**

- 无音频、存储暂不可用、权限拒绝、数据损坏和未知异常在 API 上可区分；
- 达标档案在证据不完整时不能显示“完整可信”；
- 管理员可从 trace 下钻，学员只看到可理解的降级和重试提示；
- 测试证明降级不会泄露内部异常或原始存储路径。

### F-11：配置中心仍是过渡信息架构，不是统一运行时权威

**证据**

- backend/src/admin/config_bundles/domains.py:30-154 列出 10 个配置域；
- 其中 8 个 migration_status 为 not_started，2 个为 read_only；
- 没有 fully_migrated；
- training_content、customer_simulation、ai_analysis、model_and_voice、knowledge_rag、report_rules、release_governance、audit 仍指向 legacy pages；
- 领域本身已经同时存在 ConfigBundle、Prompt、RAG Profile、ModelConfig、业务规则、训练路径 revision 等不同治理机制。

**Symptom:** 管理界面已经有“配置中心”的概念，但各域的实际写入权威、active revision、回滚和运行时读取来源仍不一致。
**Source:** The Mythical Man-Month — Conceptual Integrity。
**Consequence:** 管理员难以判断改哪个页面才会影响运行时；同一配置可能有双写、只读投影或 legacy authority；发布与回滚证据无法统一解释。
**Remedy:** 复用统一的 revision lifecycle kernel，但保留各领域自己的校验和业务语义；一次只迁移一个配置域，明确 source of truth、dual-read mismatch 指标、legacy write freeze、consumer 切换和退役条件。

**验收**

- 每个配置域文档明确唯一 writer、唯一 active revision 读取路径和历史快照规则；
- 管理页面显示 migration status、实际生效版本和 stale/dual-read 状态；
- dual-read mismatch 为零后才能禁用 legacy writer；
- 运行时快照记录最终解析出的 revision ref，不能只记录配置名称。

### F-12：Prometheus 使用原始 URL path，标签基数不可控

**证据**

- backend/src/common/monitoring/metrics.py:164-197 直接读取 scope.path；
- http_requests_total 和 http_request_duration_seconds 都把原始 path 放进 endpoint label；
- 系统存在大量带 learnerId、sessionId、submissionId、contentId 的动态路由。

**Symptom:** 每个对象 ID 都可能生成新的 Prometheus time series。
**Source:** Code Complete — 数据结构和资源使用必须有明确边界。
**Consequence:** 随业务量增长，metrics 内存、抓取时间和存储成本会随对象数增长；监控系统自身可能成为故障源，聚合查询也失去意义。
**Remedy:** 在路由解析后使用 route template 或稳定 route name 作为 label；未匹配路由统一标记 unknown；禁止 user_id、session_id、trace_id、error message 等进入 label。

**验收**

- 对同一路由发送 10,000 个不同 ID，请求序列数量保持常数；
- 404、500、未匹配路由有稳定低基数标签；
- 指标 label allowlist 有单元测试；
- 增加 series count、scrape duration 和 exporter 内存告警。

### F-13：数据库 downgrade 不是安全的业务回滚

**当前状态（2026-07-15）**：列出的 `094`、`095` 已移出活动 Alembic 路径，首发空库不会执行它们，也不能 downgrade 回这些归档 revision。当前 active history 只有 `20260715_0000_001`；首发后的 schema 变化必须新建线性 revision，并以 forward fix、feature flag 或整套备份恢复作为业务回滚。下面保留旧风险作为未来 migration 审查的反例。

**证据**

- 20260714_1500_094_explicit_teams.py:115-118 直接删除 team_leader_assignments、team_memberships 和 teams；
- 20260714_1600_095_provisioning_batches.py:109-112 直接删除开户批次、执行和行记录；
- ADR 文本要求只有确认无新数据后才能 downgrade；
- migration 本身没有数据量检查、备份证明或 fail closed guard。

**Symptom:** 文档知道 downgrade 有破坏性，但可执行脚本仍允许无条件删除业务和审计数据。
**Source:** Code Complete — Defensive Programming。
**Consequence:** 运维把 schema downgrade 当成功能回滚时会永久丢失团队授权关系和开户审计；即使应用代码回退成功，数据事实也无法恢复。
**Remedy:** 默认采用 forward-only rollback：先关闭 feature、保留新表、回退读写路径；如保留 downgrade，必须在表非空时拒绝，要求显式 break-glass 参数、备份 ID 和恢复检查；发布 runbook 明确禁止自动 schema downgrade。

**验收**

- 非空表 downgrade 自动失败；
- 备份、导出、恢复和行数校验在临时 PostgreSQL 上演练；
- rollback 流程不删除新关系，旧版本应用可安全忽略新表；
- 审计记录保留到合规期限。

### F-14：当前工作区不是可审查的原子变更包

**当前状态（2026-07-15）**：原 Ruff 和 45 个 Mypy 问题已用正式 SQLAlchemy typed mapping 与精确类型修复，全量静态门禁通过，没有用大面积 ignore 压制；但大工作区、多业务切片混合和未提交文件问题仍在，因此本 finding 仍为 P1。

**证据**

- 审计开始时有 167 个已跟踪状态项、47 个未跟踪状态项；
- 账号凭证、团队、批量开户、新人训练、前端设计与 Trellis 文档混在一个工作区；
- 审计开始时 Ruff 有 1 个错误；现已修复；
- 审计开始时 Mypy 有 45 个错误，集中在 7 个相关文件；现已修复并通过 670 个 source files；
- 之前的 Brooks 100 是独立 Gate 增量审计，不覆盖当前差异。

**Symptom:** 多个不同风险等级和回滚边界的工作混合在一起，质量门禁已经无法给出“哪一项导致失败”的清晰信号。
**Source:** Software Engineering at Google — 小而可审查的变更。
**Consequence:** 审查者难以验证安全假设；回滚一个功能可能带走另一个；历史基准和当前工作区不可比较；合并冲突和遗漏测试概率升高。
**Remedy:** 按垂直业务切片拆成独立 change package：凭证生命周期、显式团队、批量开户、组长只读、新人训练 UI；每个包包含 migration、API、UI、测试、ADR 和回滚证据，并在进入下一包前恢复全绿。

**验收**

- 每个变更包能独立解释用户路径、数据变化、权限、审计、发布和回滚；
- Ruff、Mypy、unit、contract、selected integration、selected E2E、changed coverage 全绿；
- SQLAlchemy 类型问题通过映射模型或声明修正解决，而不是大面积 type ignore；
- 工作区不混入生成目录、历史 smoke 构建和无关文档。

### F-15：前端兼容 façade 有价值，但内部仍过浅、过宽

**证据**

- web/src/lib/api/types.ts 为 6,873 行、709 个导出定义；
- web/src/lib/api/client.ts 为 4,962 行；
- 252 个前端文件直接引用全局 API types；
- client-domains 和 domains 目录已开始抽取，但全局 api 对象仍包含大量内联领域；
- report page 为 2,962 行，admin users page 为 1,477 行；
- users page 同时管理查询、筛选、创建、编辑、账号状态、导出、批量分配、凭证展示和多套 dialog state。

**Symptom:** façade 对消费者保持兼容，这是优势；但它背后仍聚合大量 DTO、错误、传输、映射和页面编排，改变一个领域容易触及全局文件。
**Source:** A Philosophy of Software Design — Deep Modules 与 Information Leakage。
**Consequence:** 类型文件成为冲突热点；页面测试必须理解很多无关状态；API DTO 直接进入 UI，领域语义和展示语义混合；迁移一半后又容易出现新旧两套入口。
**Remedy:** 保留 outward api façade 作为稳定 Interface，同时把 Implementation 逐域迁到 auth、identity、teams、training-journey、assets、practice、evaluation 等 domain SDK；每域执行 DTO → Domain Model → ViewModel；巨型页面按用户任务拆 controller hook / reducer、presenter 和视图组件。

**删除测试**

- 现在直接删除全局 façade 会迫使 252 个消费者同时变化，因此 façade 仍有高兼容价值；
- 如果删除某个拟议的 generic repository 不会产生两套真实重复实现，就不要创建它；
- domain SDK 完成后，只有 consumer 数量归零、兼容测试通过，才能删除旧 export。

**验收**

- 新功能不再向 types.ts 和 client.ts 增加领域实现；
- 单个领域变更只触及该域 SDK、presenter 和页面；
- 页面不直接显示 raw enum、error_code、trace_id 或数据库主键；
- reducer / state machine 覆盖 loading、empty、error、partial、stale、submitting、retrying 和 conflict。

### F-16：测试资产很强，但没有覆盖最昂贵的失败模式

**证据**

- 最新后端全量 unit + contract 为 3,126 passed、1 skipped；审计初始全量 integration 为 544 passed、21 skipped，首发整改后关键 integration 为 89 passed；
- 最新前端 Vitest 为 1,157 passed、6 skipped；
- 新批量开户测试覆盖 50 行、顺序重入、单团队回滚和失败团队重试；
- 没有真实 PostgreSQL 双 session 并发 confirm；
- 没有双应用进程共享限流测试；
- 没有持久任务 crash / lease / restart 测试，因为实现尚不存在；
- 没有中文部门 collision 测试；
- admin-users-account-status Playwright 用 page.route mock API，验证的是前端交互，不是账号后端闭环；
- unit + contract 存在未等待 coroutine warning，integration 有 SAWarning 和测试收集 warning。

**Symptom:** 测试数量和主路径覆盖很好，但与生产事故成本最高的并发、重启、代理、迁移和真实适配器风险没有对齐。
**Source:** How Google Tests Software — 风险驱动测试组合。
**Consequence:** 测试可以全部通过，同时生产仍出现重复开户、限流绕过、任务丢失、授权合并或凭证无法交付；误导性测试名会制造额外信心。
**Remedy:** 建立风险—测试矩阵，把 P0/P1 风险绑定到最小真实环境：PostgreSQL 并发、Redis 多进程、worker 崩溃恢复、migration snapshot、真实浏览器+后端账号生命周期；逐步把非预期 warning 升级为失败。

**验收**

- 测试名只描述实际并发或实际端到端；
- create account → first login → forced change → business access → suspend → old session invalid 的真实 E2E 通过；
- bulk confirm、credential reset、team reassignment 有并发和重复提交测试；
- 持久任务故障注入可证明 at-least-once + 幂等；
- warning allowlist 仅保留已登记、带到期日的第三方弃用。

### F-17：文档权威路径已经漂移

**证据**

- 根 AGENTS.md 声明 design.md、docs/api.md、docs/security.md、docs/uiux.md、docs/domain-glossary.md 为权威文档；
- 这些路径当前不存在；
- 工作区存在一个未跟踪且拼写为 DESING.md 的 3,000 多行设计规范；
- docs/testing.md 只有 30 行，docs/ai-governance.md 只有 11 行；
- API 实际权威主要在 docs/api-contract；
- architecture.md 中的测试数字和历史 Gate 结果是时间点证据，当前实跑数字已经变化。

**Symptom:** 规则要求所有 Agent 先读某些 source of truth，但这些文件不存在、命名错误或未纳入版本控制。
**Source:** The Pragmatic Programmer — DRY 与可执行知识。
**Consequence:** 不同开发者会选择不同文档；设计规则可能完全不被读取；历史测试数字被误当成当前证据；安全和 AI 决策继续只存在于代码或 ADR 碎片里。
**Remedy:** 将 DESING.md 评审后正式落地为根 design.md；要么创建缺失的 canonical docs，要么修改 AGENTS.md 指向真实权威；把历史审计明确标记 snapshot；增加文档链接检查和 ADR 状态检查。

**验收**

- AGENTS.md 中所有强制路径都存在并受版本控制；
- 一个主题只有一个 canonical doc，其他文档只链接；
- docs/security.md 明确认证、能力、对象范围、凭证、日志和生产门禁；
- docs/ai-governance.md 明确 Prompt revision、模型配置、tool、证据和人工复核；
- CI 校验内部链接、ADR status 和架构数字的自动生成区块。

---

## 8. 与 2026-07-03 审计相比发生了什么

### 8.1 已明显改善

- 模块依赖已经从“文档边界”升级为可执行 policy 和 CI guard；
- common.db.models 与前端类型 façade 已开始做兼容迁移，而不是一次性破坏性删除；
- critical-quality-gate 现在覆盖全量 unit + contract、全量 Mypy、前端 coverage、selected integration / E2E 和 changed coverage；
- 账号状态、受管凭证、显式团队和组长对象范围已经形成 ADR、模型、服务、API 和 UI；
- 新人训练活动编排、不可变 enrollment / revision 和 in-flow 资源创建比 7 月初完整；
- 当前前端全量 TypeScript、ESLint、Vitest 和生产构建可通过。

### 8.2 仍未闭环

- 进程内后台任务在 7 月初已被识别，7 月 6 日 ADR 也已接受，但仍停在 Phase 0；
- 角色口径虽然新增了后端集中词表，路由、服务和前端 capability 仍会漂移；
- 监控基础存在，但原始 path 标签等问题使可观测性仍未达到生产成熟度；
- 文档与工作区纪律仍削弱快照可审计性；
- 账号与 Team 的首发 schema/认证风险已收口；开户并发一致性、生产重置交付和组长任务路由仍未闭环。

### 8.3 应如何理解“过去的优化”

过去的 Gate 0A–6 不是无效工作。它们成功建立了依赖政策、兼容 façade、运行时 provider 边界和测试门禁。问题在于项目现在进入了下一阶段：不能再只证明“边界没有继续变坏”，而要证明“临时边真的在减少、运行任务能恢复、生产凭证只有一个权威、达标档案能解释证据缺口”。

---

## 9. 要达到理想状态还缺什么

| 能力 | 当前状态 | 还缺什么 | 完成定义 |
| --- | --- | --- | --- |
| 可信训练达标档案 | 已有领域定义、readiness service、快照和 revision | 证据三态、AI lineage、人工复核、任务失败可恢复、统一审计 | 每个结论可追溯到不可变输入、规则、模型、人工动作和降级状态 |
| 新人训练闭环 | 管理编辑、学员活动、发布修订、live enrollment 已存在 | 真实 manager review → remediation → learner complete → before/after E2E | 主用户能在一个任务流中发现问题、指派补练、复核并形成结论 |
| 身份与凭证 | 受管哈希、临时密码、credential_version 已存在；共享密码 fallback 已退役 | 真实重置交付 adapter、production 门禁、SSO 绑定策略 | 每个账号独立撤销；原始秘密不入日志；生产无 console/shared password 兼容路径 |
| 团队授权 | 显式 team / membership / leader 和历史有效期已存在；department 已退出 schema/授权 | 组长任务路由、统一 capability、并发调岗规则 | department 永不参与授权；对象范围在 API、审计和 UI 一致 |
| 批量开户 | 预览、团队 savepoint、失败重试、一次性凭证已存在 | 原子 claim、并发幂等、断线恢复、结果审计、生产交付 | 重复/并发请求不重复创建，结果与数据状态严格一致 |
| 持久任务 | ADR 和状态机 helper 已存在 | 表、repository、worker、lease、dead letter、管理查询 | 发布、崩溃、多实例下任务不丢，重复执行不重复副作用 |
| AI 治理 | LLM service、模型配置、部分 Prompt 管理已存在 | 统一 invocation、max tokens、生效证明、lineage、成本、schema、人工复核 | 任一 AI 输出都可解释、可降级、可追责、可重放 |
| 配置治理 | ConfigBundle、revision 和治理页面并存 | 逐域唯一 writer、active revision、dual-read 退役 | 管理员能准确知道改动何时、对谁、以哪个版本生效 |
| 可观测性 | trace、日志、metrics、release verification 已存在 | 低基数指标、任务指标、SLO、告警、统一审计下钻 | 事故能从业务对象 → task → provider → trace → 配置版本闭环定位 |
| 前端产品架构 | 设计系统、domain builders、presenter 局部存在 | DTO/Domain/ViewModel 分层、capability 驱动、巨型页面拆分、真实状态覆盖 | 一个领域变更局部化，用户不看到工程字段，失败可恢复 |
| 发布与恢复 | 静态门禁、unit/contract、关键 integration、前端测试和 build 已绿；首发 reset 有隔离恢复证据 | 工作区拆包、PG 并发、Playwright、真实 COS/Provider、备份恢复、灰度和故障注入 | 发布有证据包，回滚不丢业务数据，故障可在目标时间内恢复 |
| 租户策略 | 代码没有明确 tenant / organization 边界 | 明确单客户单部署还是多租户 SaaS | 若多租户，tenant 成为数据、缓存、任务、对象存储和审计的一等边界 |

---

## 10. 理想架构：边界清晰、模块够深的模块化单体

### 10.1 目标结构

~~~mermaid
flowchart TB
    User["用户与运营角色"]

    subgraph Delivery["Delivery / Composition"]
        Web["Next.js 任务工作区"]
        DomainSDK["前端 Domain SDK + Presenter / ViewModel"]
        HTTP["FastAPI HTTP / WebSocket Adapter"]
        AdminDelivery["Admin 交付层：只组合用例，不拥有领域状态"]
    end

    subgraph Domains["Application + Domain Modules"]
        IAM["Identity & Access\n用户、凭证、团队、Capability、对象范围"]
        Journey["Training Journey\n路径、Enrollment、Activity、Attempt、Remediation"]
        Assets["Learning & Assessment Assets\n内容、题库、Prompt、Rubric、Revision"]
        Practice["Practice Session\nSession、Snapshot、Roleplay Contract"]
        Eval["Evaluation & Readiness\n评分事实、证据、档案投影、人工复核"]
        Config["Configuration Governance\n统一生命周期内核 + 各域校验"]
    end

    subgraph Platform["Platform Modules / Ports"]
        Tasks["Persistent Task\noutbox、claim、lease、retry、dead letter"]
        AI["AI Invocation\nprompt/model lineage、usage、schema、policy"]
        Realtime["Realtime Provider Port\nprovider-neutral engine"]
        Storage["Object Storage Port\nlocal dev / COS production"]
        Obs["Audit & Observability\n事件、日志、指标、trace、SLO"]
    end

    subgraph Adapters["Infrastructure Adapters"]
        PG["PostgreSQL"]
        Redis["Redis"]
        Providers["OpenAI-compatible / Azure / Anthropic / StepFun"]
        COS["COS / 企业交付渠道"]
    end

    User --> Web --> DomainSDK --> HTTP
    AdminDelivery --> HTTP
    HTTP --> IAM
    HTTP --> Journey
    HTTP --> Assets
    HTTP --> Practice
    HTTP --> Eval
    HTTP --> Config

    Journey --> IAM
    Journey --> Assets
    Practice --> Assets
    Eval --> Journey
    Eval --> Practice

    IAM --> Tasks
    Journey --> Tasks
    Assets --> Tasks
    Eval --> Tasks
    Assets --> AI
    Eval --> AI
    Practice --> Realtime
    Journey --> Storage
    Assets --> Storage

    Tasks --> PG
    AI --> Providers
    Realtime --> Providers
    Storage --> COS
    Obs --> PG
    Tasks --> Redis
~~~

### 10.2 依赖规则

1. Delivery 可以依赖 application interface，但不能成为业务规则权威。
2. Domain 不能 import admin、FastAPI、Next.js、具体 Provider 或其他领域的 ORM model。
3. common 只保留真正稳定的 kernel type、错误协议、trace context 和 platform port，不得反向依赖业务包。
4. 跨域同步调用只通过小而深的 Interface；跨域组合查询使用专门 read model，不直接跨包拼 ORM。
5. transaction 由 application service 拥有；领域服务不自行 commit。
6. 业务写入与异步任务投递用同事务 outbox / task row 保证。
7. 历史展示只读 snapshot / revision ref；active/latest 只决定新运行。
8. 前端只能以服务端 CapabilitySet 决定可见操作，以 ViewModel 决定展示，不直接渲染 raw DTO。
9. 指标、日志和审计是业务写入的一部分，但失败策略要明确，不能静默吞掉影响结论的证据。

### 10.3 领域边界

| Module | 拥有 | 暴露的 Interface | 禁止 |
| --- | --- | --- | --- |
| Identity & Access | User、Credential、Team、Membership、LeaderAssignment、CapabilitySet | authenticate、current_actor、team_scope、credential lifecycle | 业务域直接判断 role 字符串；department 授权 |
| Training Journey | Path、Enrollment、Activity、Attempt、NextAction、Remediation | learner journey、manager progress、activity commands | 直接创建实时连接；从 latest 重建历史 |
| Asset Governance | LearningContent、Question、Prompt、Rubric、Revision | resolve published revision、validate、publish、rollback | 运行时读取未发布草稿 |
| Practice Session | PracticeSession、runtime snapshot、Roleplay Contract | start、transition、reconnect descriptor | 读取 admin 页面配置拼运行时 |
| Evaluation & Readiness | score fact、evidence、review、dossier projection | evaluate、review、readiness dossier | AI 默认分伪装成业务评分 |
| Persistent Task | task row、lease、retry、event | enqueue、claim、complete、fail、requeue | 拥有音频/知识/报告业务逻辑 |
| AI Invocation | model policy、invocation、usage、lineage | invoke structured task | 业务代码直接访问 provider client |
| Audit & Observability | audit event、trace、metric projection | record、query、correlate | 把对象 ID 和错误文本放进 metric label |
| Admin Delivery | 页面和 API 组合 | 调用各域治理 use case | 直接读写所有领域内部表 |

---

## 11. 架构深化机会

### 11.1 Identity & Access Module

**当前问题**

认证、账号管理、团队、角色别名、页面导航和业务权限分散。现有 common/auth 和 common/teams 已经形成雏形，但 admin/users、router mount 和前端 current-user 仍表达策略。

**建议**

- Interface：Actor、CapabilitySet、TeamScope、CredentialAuthority；
- Implementation：受管密码、企业微信身份、临时 legacy environment credential；
- Adapter：FastAPI dependency、admin account commands、前端 session DTO；
- Depth：隐藏角色别名、会话版本、团队有效期、对象范围和凭证状态；
- Leverage：登录、组长工作台、管理员、训练任务、审计共同受益；
- Locality：新增角色或能力只改 IAM policy 和 capability contract。

**删除测试**

删除这个模块会迫使每个业务域重复角色别名、团队范围和凭证状态，因此它有真实高 Leverage。相反，不需要再额外创造一个只包装 User CRUD 的 generic repository。

### 11.2 Persistent Task Module

**当前问题**

有正确的状态机契约，但没有执行 Implementation。

**建议**

- 先实现 PostgreSQL task row、event、repository 和 worker；
- 只有数据库执行和 legacy inline 执行两个真实 Implementation 同时存在时，再把它们收敛为切换 Seam；
- handler registry 只映射 task_type 到各领域 handler；
- application transaction 负责 enqueue；
- worker 负责 lease 和调度，不理解业务内部状态。

**删除测试**

没有该模块，音频、知识库、报告和归档会分别复制 claim、retry、dead letter 和审计，因此抽象成立。当前不要先设计一个过度通用的外部 broker interface；数据库真值实现完成后再决定 Redis/RQ/Arq 是否只是加速 Adapter。

### 11.3 AI Invocation Module

**当前问题**

Provider 初始化集中，但 Prompt、调用、schema、max tokens、usage 和降级并未全部集中。

**建议**

- Interface：AiInvocationRequest / AiInvocationResult；
- 真实 Adapter：OpenAI-compatible、Azure、Anthropic；
- 输入包括 prompt revision、model policy、actor、object scope、trace 和幂等键；
- 输出包括 structured value、validation、evidence、usage、cost、latency 和 degradation；
- 高风险评估写入 candidate result，人工确认后才成为 verified fact。

**删除测试**

删除后每条 AI 路径都要重新实现超时、重试、token 限制、lineage、schema 和成本，因此这是高 Leverage 深模块。

### 11.4 Readiness Dossier Projection Module

**当前问题**

达标档案跨活动、attempt、录音、AI 评分、人工复核、重训和快照；如果每个页面自行拼数据，可信性规则会重复。

**建议**

- 把档案定义成只读 projection，不拥有上游业务事实；
- 输入只能是不可变 outcome、snapshot ref、AI lineage、review event 和 task status；
- 显式表达 evidence completeness；
- 学员、培训负责人和审计员使用不同 ViewModel，但共享同一事实投影；
- 禁止页面从 latest asset 重新解释历史。

**删除测试**

没有该模块，report、replay、manager dashboard、learner journey 会重复拼接“达标”语义，因此抽象成立；它不需要伪装成通用 repository。

### 11.5 Configuration Lifecycle Kernel

**当前问题**

多个配置域都有 draft、validate、publish、rollback、active revision 和 audit，但实现成熟度不一。

**建议**

- 共享生命周期状态机、revision metadata、expected_revision CAS、审计和 rollout；
- 每个领域保留自己的 schema、校验、编译和运行时 snapshot；
- Config Center 是治理入口，不是把所有配置压成一个无类型 JSON 表；
- 用 dual-read mismatch 证明迁移，而不是直接切断 legacy。

**删除测试**

删除生命周期 kernel 会在 Prompt、题库、训练路径、评分规则、RAG 和语音策略中复制发布语义，故有 Leverage；领域校验不应被抽进这个 kernel。

### 11.6 Frontend Domain SDK 与 Presenter

**当前问题**

全局 façade 稳定了兼容，但 DTO、领域模型、展示状态仍常在页面内混合。

**建议**

- 每个业务域有 types/dto、model、presenter、client、query keys 和 tests；
- outward api 保持兼容，内部委托到 domain SDK；
- 复杂页面用 reducer 或显式状态机管理 dirty、submitting、conflict、partial success；
- 用户可见字符串只来自 presenter，不渲染 raw enum 或内部错误；
- 优先拆 users、practice report、replay 和 path editor 这类高变更页面。

**删除测试**

如果移除某个 domain presenter 会让多个页面重复状态、格式和动作映射，则它成立；如果组件只有一个调用者且没有隐藏复杂性，保持本地实现。

### 11.7 已有 Seam 应继续深化，而不是重新发明

| 已有 Seam | 真实 Adapter | 建议 |
| --- | --- | --- |
| RealtimeProviderPort | StepFun 与测试/替代 Provider | 保持 provider-neutral engine，禁止业务包回读 transport 细节 |
| Assignment/Object Storage | local 与 COS | production 强制对象存储；local 仅开发；补病毒扫描和恢复 |
| Credential Authority | managed password、WeCom、legacy env | 明确 authoritative 顺序并退役 legacy |
| API domain builder | 多个前端业务域 builder | 继续迁移，保持外层 façade 兼容 |

---

## 12. 分阶段优化路线

### Phase 0：建立可比较的基线

**目标**

把当前大工作区拆成可审查、可发布、可回滚的变更包。

**动作**

1. 保存当前快照和审计文档；
2. 按凭证、团队、批量开户、组长只读、新人训练 UI 拆分变更；
3. 修复 Ruff 和 Mypy；
4. 每个切片生成 test selection manifest 和 changed coverage；
5. 明确哪些历史文档是 snapshot，哪些是 canonical。

**通过门槛**

- critical-quality-gate 自然退出 0；
- 工作区不包含无关改动；
- 每个切片有 ADR / API / migration / UI / test / rollback 对应关系。

### Phase 1：先封住安全和数据一致性

**目标**

消除 F-01 至 F-05 的生产风险。

**动作**

1. 分布式限流、trusted proxy、TTL 和生产配置检查；
2. 真实密码重置交付 adapter，console transport 在 production fail closed；
3. 修复 training_manager 任务读路由；
4. 批量开户 batch/execution 原子 claim 和 PostgreSQL 并发测试；
5. 指标 route template 化；
6. 保持首发后 migration 线性、forward-only，并对未来破坏性 downgrade 持续 fail closed。

**灰度与回滚**

- 使用现有 EXPLICIT_TEAM_SCOPE_ENABLED 安全关闭组长入口，但绝不回退到 department 授权；
- 不重新启用共享密码或 department 授权 compatibility flag；
- schema 不回退，优先关闭 writer、保留表和数据；
- 限流新实现支持 shadow compare，确认误伤率后切主。

### Phase 2：让用户可感知任务可恢复

**目标**

完成持久任务 ADR Phase 1–4。

**动作**

1. persistent_tasks / events migration；
2. repository、claim、lease、sweeper、retry、dead letter；
3. worker run_once 和长期进程；
4. 先接 audio submission，再接 knowledge document，再接 report generation，最后接 archive；
5. 运维查询、人工 requeue、业务对象反向链接；
6. 任务指标和 SLO。

**通过门槛**

- kill -9 worker、应用滚动发布和 lease 过期故障注入通过；
- 重复执行不重复外部副作用；
- 业务 UI 能解释处理中、失败、重试和结果位置；
- legacy BackgroundTasks 对应 task type 的调用点为零后再退役。

### Phase 3：补齐 AI 与档案信任链

**目标**

任何评分、总结和建议都能回答“基于什么、由什么模型、是否完整、是否人工确认”。

**动作**

1. AiInvocation request/result 契约；
2. 将 direct apredict 路径迁移；
3. max tokens、timeout、retry、rate limit、cost 全部生效；
4. Prompt revision、model config version 和 input snapshot 写入 lineage；
5. Readiness Dossier 增加 evidence completeness；
6. AI 失败不再默认成正常评分；
7. 高风险结论加入 review state。

**通过门槛**

- AI 调用静态守门；
- provider parity contract tests；
- 任一档案结论可下钻到输入证据和人工动作；
- 模型不可用时有明确降级，不把生成内容标为事实。

### Phase 4：缩小 SCC，深化前端模块

**目标**

把“受控依赖债”真正变成递减曲线。

**动作**

1. 删除 common → domain 边；
2. 建立 neutral observability contributor，拆 agent ↔ support；
3. 通过 asset / journey port 拆 curriculum_practice ↔ sales_trainer；
4. admin 改为各领域 governance use case 的交付层；
5. 前端新代码停止增长 global types/client；
6. 按 consumer 清单迁移 domain SDK 和 presenter；
7. 拆 users、report、replay 等高变更页面。

**通过门槛**

- SCC 每个里程碑都缩小；
- temporary edge 数量单调下降；
- 一个领域改动不触及全局 façade 实现；
- common.db.models 和全局 types façade 的 production consumer 有明确下降曲线。

### Phase 5：生产运营与产品闭环

**目标**

证明系统能长期运行，而不是只证明测试环境能通过。

**动作**

1. 真实浏览器+后端账号生命周期 E2E；
2. 培训负责人复核 → 补练 → 学员完成 → before/after E2E；
3. 备份恢复、对象存储恢复、Redis 故障和滚动发布演练；
4. 定义登录、训练启动、AI 评分、档案生成、任务积压 SLO；
5. 配置告警、容量基线和应急 runbook；
6. 明确单租户部署或多租户产品决策；
7. 生产数据脱敏、保留期、导出和删除策略。

**通过门槛**

- 发布证据包包含代码门禁、迁移 dry-run、E2E、恢复演练、SLO 和回滚；
- 关键告警能关联业务对象、task、trace、Provider 和配置 revision；
- 主用户能在一个工作流内完成推进、复核和恢复。

---

## 13. 优先级 Backlog

| 顺序 | 项目 | 优先级 | 依赖 | 完成证据 |
| ---: | --- | --- | --- | --- |
| 1 | 禁止 production console password reset；shared password 登录已退役 | P0 | 真实交付 Adapter | release readiness + 真实投递集成测试 |
| 2 | 分布式登录限流与 trusted proxy | P0 | Redis 运行策略 | 双进程测试 + header spoof 测试 |
| 3 | 修复组长任务 GET 路由 | P1 | 现有 Team policy | 完整 app RBAC 测试 |
| 4 | 批量开户原子 claim | P1 | PostgreSQL | 双 session 并发测试 |
| 5 | 持久任务表与 repository | P1 | ADR 已有 | enqueue / claim / event PG 测试 |
| 6 | Worker、lease 和 dead letter | P1 | #5 | crash / restart 故障注入 |
| 7 | 接管音频任务 | P1 | #6 | 重复执行不重复评分 |
| 8 | 接管知识库和报告任务 | P1 | #6 | pending 不丢、可重试 |
| 9 | HTTP metric route template | P1 | 无 | cardinality 测试 |
| 10 | AI Invocation 契约与 max tokens | P1 | Prompt / model revision | provider parity tests |
| 11 | Readiness evidence completeness | P1 | #6、#10 | 档案 lineage E2E |
| 12 | 服务端 CapabilitySet | P1 | IAM policy | 前后端契约矩阵 |
| 13 | 配置域逐个迁移 | P1 | lifecycle kernel | dual-read mismatch 为零 |
| 14 | 删除 common 上行边 | P1 | Ports / read models | SCC 缩小 |
| 15 | 前端 domain SDK / presenter | P2 | consumer 清单 | global façade 增量为零 |
| 16 | 文档 source of truth 修复 | P1 | 文档负责人 | link / ADR status CI |
| 17 | 构建产物与 CodeGraph hygiene | P3 | 无 | 清理约 679MB 本地历史构建产物，索引排除生成目录 |
| 18 | 部门迁移碰撞由新 baseline 消除 | 已完成 | 首发 reset | 双次隔离 reset + Team scope + schema parity |
| 19 | 修复 Ruff / Mypy | 已完成 | typed ORM 与精确类型 | Ruff 全量通过；Mypy 670 files 通过 |
| 20 | 归档旧破坏性 downgrade | 已完成 | 首发 baseline | active history 单 root/head，旧 revision 不可执行 |

---

## 14. 不应该做的事

1. **不要现在拆微服务。** 当前主要问题是依赖方向、执行持久性和权威分裂；拆进程只会把本地循环变成网络循环。
2. **不要大爆炸重写。** 现有 snapshot、revision、测试和 ADR 是高价值资产，应通过兼容 façade 渐进迁移。
3. **不要以文件行数作为唯一拆分依据。** 组合根高 fan-out 和兼容 façade 可以合理；要看 Depth、Leverage 和 Locality。
4. **不要为每个类创建 Interface。** 只有两个真实 Implementation 或明确的测试/迁移 Seam 存在时，抽象才值得。
5. **不要先造 generic repository。** 领域查询、快照和对象范围语义不同，通用 CRUD 会泄露复杂性。
6. **不要把 schema downgrade 当成功能回滚。** 高风险数据结构应 forward fix、feature flag 和保留数据。
7. **不要用前端隐藏按钮代替授权。** 前端 capability 只负责体验，后端对象 policy 才是安全边界。
8. **不要用 latest 配置修补历史。** 任何旧 attempt、submission、session、score 和 dossier 都只读冻结依据。
9. **不要因为单元测试多就跳过故障注入。** 并发、崩溃和多实例只能由对应环境证明。
10. **不要继续引用增量 100 分证明全仓健康。** 每个分数必须带 scope、commit 和命令结果。

---

## 15. 发布 Definition of Done

### 15.1 代码与架构

- Ruff、Mypy、TypeScript、ESLint、Next build 全绿；
- architecture guard 通过且 temporary edges 未增加；
- critical-quality-gate 自然退出 0；
- 当前变更包没有无关文件；
- 新共享 Interface 通过删除测试，并至少有两个真实 Implementation 或明确迁移 Seam。

### 15.2 数据与权限

- migration 有 dry-run、碰撞清单、影响行数、锁评估、备份和恢复证据；
- production 无 shared password、无 console reset、无未迁移活跃凭证；
- team scope、task scope、dossier scope 有角色×对象矩阵；
- 并发写入有 CAS / lock、幂等键、冲突响应和审计；
- 任何回滚不删除新增业务事实。

### 15.3 可靠性与 AI

- 用户可感知后台任务持久化并可恢复；
- AI 调用有 prompt/model lineage、max tokens、timeout、usage、schema 和降级；
- 证据不完整时档案明确标记；
- Provider 失败不会被伪装成成功；
- 关键任务、队列、AI 和档案有 SLO 与告警。

### 15.4 前端与产品

- 主用户三秒内知道任务、主操作和下一步；
- 缺失团队、账号、资源和配置可在当前流程内处理；
- loading、empty、no result、error、partial、permission、stale、conflict、submitting、retrying 和 recovery 按场景覆盖；
- 不展示 raw enum、error code、trace、数据库 ID 或测试术语；
- 核心页面键盘、焦点、窄屏、长文本和真实大数据验证通过；
- 账号生命周期和新人达标闭环有真实浏览器+后端 E2E。

### 15.5 文档与运营

- design.md、security、API、testing、AI governance 和 ADR 权威路径真实存在；
- 发布证据记录 commit、scope、命令、结果、跳过项和残余风险；
- 有备份恢复、任务积压、Provider 故障、Redis 故障、凭证事故 runbook；
- SLO、告警阈值、值班责任和降级开关明确。

---

## 16. 需要产品或平台负责人明确的决策

这些不是本次可以靠读代码替代的决定，但不应继续隐含：

1. **租户模型**：单客户单部署，还是多租户 SaaS？若是后者，tenant 必须进入每张业务表、缓存键、任务、对象存储和审计范围。
2. **凭证交付权威**：企业微信、企业 IAM、SMTP 邮件还是管理员线下交付？密码重置不能永久依赖 console。
3. **持久 worker 部署**：与 API 同镜像独立进程，还是独立 deployment？并发数、lease、升级和停机策略是什么？
4. **对象存储生产策略**：COS 是否强制？本地文件只允许开发还是也支持单机私有部署？
5. **SLO**：登录、训练启动、实时首包、音频评分、档案生成和任务恢复的目标时间分别是多少？
6. **AI 合规**：哪些文本和音频可以发送到哪个 Provider？保留期、脱敏、人工复核和模型切换要求是什么？
7. **兼容债到期责任**：2026-10-31 的 9 组 temporary edge 由谁按什么里程碑逐条删除，而不是统一延期？

---

## 17. 最终建议

项目最值得保留的是它已经建立的领域合同、不可变快照、发布修订、架构门禁和测试资产。最需要改变的是“定义了治理，但运行路径仍允许绕过治理”的部分。

建议下一轮只做三个连续、可发布的 tracer bullet：

1. **生产认证安全包**：生产禁用 console password reset、接入真实交付，并把登录限流迁移到可信代理边界下的共享原子存储；shared-password fallback 与中文部门迁移已在首发 baseline 中收口，不再重复建设兼容层；
2. **可靠执行包**：实现持久任务最小闭环并只接管音频处理；
3. **可信档案包**：统一 AI Invocation，给 Readiness Dossier 增加 lineage 与 evidence completeness。

这三步完成后，再进入 SCC 删除和前端 façade 深化。顺序不能反过来：先把信任链和恢复能力做实，结构优化才会转化成真正的业务可靠性。

---

## 附录 A：关键证据索引

- 领域北极星与快照规则：CONTEXT.md
- 当前架构与 SCC：docs/architecture.md:1039-1057
- 依赖政策：docs/architecture/module-dependency-policy.yaml
- 持久任务 ADR：docs/adr/2026-07-06-persistent-background-task-contract.md
- 凭证 ADR：docs/adr/2026-07-14-managed-account-credential-lifecycle.md
- 团队范围 ADR：docs/adr/2026-07-14-explicit-team-scope.md
- 登录兼容路径：backend/src/common/auth/api.py:282-376
- 密码重置传输：backend/src/common/services/password_reset.py:36-87
- 生产配置检查：backend/src/common/analytics/release_readiness.py:74-128
- API 限流：backend/src/common/rate_limit/api_limiter.py:34-263
- 部门迁移：backend/scripts/migrate_departments_to_teams.py:22-90
- 任务路由：backend/src/router_registry.py:128-132
- 任务对象策略：backend/src/common/training_tasks/service.py:34-89
- 批量开户：backend/src/admin/services/provisioning.py:223-475
- 进程内任务：backend/src/sales_trainer/api.py、backend/src/common/knowledge/api.py、backend/src/common/db/session_lifecycle.py
- AI 直调：backend/src/presentation_coach/services/point_extraction.py、backend/src/sales_bot/services/summary_service.py
- LLM 参数：backend/src/common/ai/config_manager.py、backend/src/common/ai/llm_service.py
- 指标标签：backend/src/common/monitoring/metrics.py:156-197
- 前端角色：web/src/lib/auth/current-user.ts、web/src/components/layout/sidebar.tsx
- 前端 façade：web/src/lib/api/types.ts、web/src/lib/api/client.ts、web/src/lib/api/client-domains.ts
- 配置迁移状态：backend/src/admin/config_bundles/domains.py
- 测试与发布：scripts/critical-quality-gate.sh、.github/workflows/release-truth-gate.yml

## 附录 B：报告使用方式

- 本报告是当前工作区快照，不替代具体 ADR、API contract、security contract 和 runbook；
- 每完成一个 Phase，应更新相应 canonical 文档，并新增同范围的验证记录；
- 若代码与本文不一致，以当前代码和最新已接受 ADR 为准，同时把差异回写；
- 下一次健康评分必须注明 commit 和工作区是否干净，避免把增量分数与全仓分数混用。
