# Phase 9 新人训练完整 E2E / CI Gate 设计与落点研究

> 任务：`06-27-newcomer-training-closed-loop-optimization-plan`
>
> 日期：2026-06-27
>
> 范围：只做现状研究、测试/CI 设计与最小落地建议；不改业务代码。

## 2026-06-29 闭环复核附录

本文件保留 Phase 9 当时的落地计划。当前工作树已把“先以 fail-closed/disabled 诊断态纳入 gate”的 realtime 路径升级为 deterministic local provider 真实 `/ws/sales` E2E，并把真实 provider 作为分类专项 gate：

- 默认 full gate：deterministic newcomer E2E 11 passed / 1 skipped，realtime roleplay local provider 已走 active path start API、sales websocket、Journey outcome 和 admin record。
- AI Coach real provider gate：DeepSeek/OpenAI-compatible provider 于 2026-06-29 06:06 passed，`fallback_used=false`。
- StepFun real provider gate：于 2026-06-29 06:05 到达上游后 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`，保留为外部授权阻塞，不伪装通过。
- 最新证据：`.sisyphus/evidence/task-9-quality-gate.txt`、`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json`、`.sisyphus/evidence/newcomer-real-provider-gate.json`。

## 研究结论摘要

- 当前仓库已经有可运行的 Playwright 基础设施，但 **E2E 重点仍在通用 smoke、PPT Phase4、Sales Phase4、前端路由审计**，还没有“新人训练完整闭环”E2E。
- 当前仓库已经有大量新人训练后端 `unit/integration/contract` 测试，以及前端 `Vitest` 页面级测试；**缺口在跨前后端的真实旅程编排** 与 **CI 中显式的新人训练 gate 分层**。
- 现有 E2E provider 替身体系已经满足“不打真实 provider”的基本要求：`PHASE4_E2E_PROVIDER=local` + versioned fixture script + transcript/manifest evidence。新人训练闭环应复用这条 seam，而不是新造一套 mock 技术栈。
- Phase 9 的最小先落地应先做 **deterministic closed-loop E2E smoke slice**，覆盖 learner 首页、文章/考试、录音评分、AI Coach、管理端看板、权限不足、配置异常、历史回放；**实时对练先以 fail-closed / disabled 诊断态纳入 gate**，待 runtime binding 契约与 seed 能力稳定后再升级为真实运行时 E2E。

## 1. 当前 E2E / CI 事实

### 1.1 Playwright 现状

- 配置文件：`web/playwright.config.ts`
- `testDir`：`web/tests/e2e`
- 执行模型：`workers=1`、`fullyParallel=false`、单 `chromium` project
- 默认 `baseURL`：`http://localhost:3445`
- `globalSetup`：`web/tests/e2e/global-setup.ts`
- `globalTeardown`：`web/tests/e2e/global-teardown.ts`
- 失败证据：trace / screenshot / video 保留；HTML report 输出到 `.sisyphus/evidence/*-playwright-report`

### 1.2 当前 Playwright 覆盖内容

- `web/tests/e2e/smoke.spec.ts`
  - 覆盖登录、dashboard、training entry、practice session、report、replay、admin analytics、support runtime。
  - 重点是全栈 smoke baseline，不是新人训练闭环。
- `web/tests/e2e/presentation-phase4.spec.ts`
  - 覆盖 `/ws/presentation` 真 WebSocket 路径。
  - 通过本地 provider fixture script 驱动，不依赖真实 StepFun。
- `web/tests/e2e/sales-phase4.spec.ts`
  - 覆盖 `/ws/sales` 真 WebSocket 路径。
  - 同样走本地 provider fixture script。
- `web/tests/e2e/audit/audit.spec.ts`
  - 偏路由/页面审计，检查关键路径是否出现 404、`[object Object]`、禁用文案等。
  - 当前 audit route 不含新人训练 learner/admin 闭环页。

### 1.3 当前 smoke / seed 基础设施

- 启动脚本：`scripts/dev-smoke-up.sh`
  - 拉起本地全栈。
  - 运行 `alembic upgrade head`。
  - 引导 smoke admin：`backend/scripts/bootstrap_auth_admin.py`
  - 引导 smoke 回放证据：`backend/scripts/bootstrap_smoke_practice_evidence.py`
  - 写入 `.dev/smoke/state.env`
- 停止脚本：`scripts/dev-smoke-stop.sh`
- 当前 smoke seed 已提供：
  - smoke admin 账号
  - report/replay 所需 Sales Phase4 会话证据
- 当前 smoke seed **未提供**：
  - 新人训练 active path revision 闭环数据
  - 商务技巧文章/考试/AI Coach/录音/训练记录一整套可重复 seed
  - 新人训练 manager/team scoped 权限矩阵数据

### 1.4 当前 provider/mock seam 事实

- 后端本地 provider seam：`backend/src/sales_bot/websocket/phase4_local_provider.py`
- 开关：
  - `PHASE4_E2E_PROVIDER=local`
  - `PHASE4_E2E_PROVIDER_SCRIPT=<fixture>.json`
  - `PHASE4_E2E_PROVIDER_TRANSCRIPT=<jsonl>`
- 当前 fixture：
  - `backend/tests/e2e/fixtures/sales-provider-script.v1.json`
  - `backend/tests/e2e/fixtures/presentation-provider-script.v1.json`
- 当前已有后端自测：
  - `backend/tests/e2e/test_websocket_flow.py`
  - 证明 local provider transcript / response 脚本是受测试保护的。

### 1.5 当前 CI gate 脚本事实

- 质量门禁脚本：`scripts/critical-quality-gate.sh`
- 当前包含：
  - secret scan
  - `web` typecheck
  - 指定 Vitest gate targets
  - `playwright test tests/e2e/smoke.spec.ts`
  - `playwright test tests/e2e/presentation-phase4.spec.ts`
  - `playwright test tests/e2e/sales-phase4.spec.ts`
  - 指定后端 gate targets / smoke regression targets
- 当前 **没有**：
  - 新人训练 learner/admin 闭环 Playwright 测试命令
  - 新人训练闭环 seed/bootstrap 步骤
  - 新人训练配置异常/权限矩阵/historical replay 的专用 E2E gate

### 1.6 当前新人训练自动化现状

- 前端已有大量页面级 `Vitest`：
  - learner 首页：`web/src/app/(dashboard)/sales-trainer/page.test.tsx`
  - 文章学习：`.../business-skills/page.test.tsx`
  - 考试：`.../business-skills/exam/page.test.tsx`
  - AI Coach：`.../business-skills/coach/page.test.tsx`
  - 录音上传：`.../audio/[unitId]/page.test.tsx`
  - 录音结果：`.../audio/result/[submissionId]/page.test.tsx`
  - 做题结果：`.../quiz/result/[attemptId]/page.test.tsx`
  - 管理端工作台与训练记录等页面测试
- 后端已有大量新人训练测试：
  - integration：journey / rbac / material / paper / article / ai coach progress / regrade / path config 等
  - unit：path config revision / audio lineage / papers / permissions / audit logs / training journey service 等
- 结论：
  - **局部业务规则覆盖不差**
  - **跨层真实旅程仍缺**

## 2. 新人训练闭环 E2E 场景矩阵

### 2.1 设计原则

- 场景必须以 `active path revision` 为唯一真源，禁止依赖 legacy learner fallback 伪成功。
- 场景必须区分：
  - happy path
  - typed terminal failure
  -权限 fail-closed
  -历史回放 snapshot-first
- 实时对练在 Phase 9 分两级：
  - L1：disabled / config-invalid / permission-denied 诊断 E2E，必须先上
  - L2：runtime binding + outcome projection ready 后，再上真实运行时 E2E

### 2.2 场景矩阵

| 编号 | 场景 | 入口 | 关键断言 | 推荐层级 |
|---|---|---|---|---|
| E2E-NC-001 | learner 首页 active journey 正常渲染 | `/sales-trainer` | 显示 path revision、模块阶段、next action、诊断字段不伪成功 | PR gate |
| E2E-NC-002 | learner 首页配置缺失 fail-closed | `/sales-trainer` | 返回空路径或 typed diagnostic；UI 不展示 fake module grid | PR gate |
| E2E-NC-003 | learner 首页权限不足 | `/sales-trainer` | learner 以外角色/无权用户进入时展示明确权限提示或 403 页面 | PR gate |
| E2E-NC-004 | 商务技巧文章学习完成章节 | `/sales-trainer/business-skills` | 章节完成状态、unit progress、下一步入口正确 | PR gate |
| E2E-NC-005 | 商务技巧考试 happy path | `/sales-trainer/business-skills/exam?unitId=...` | 仅在 article progress 完成后允许提交；提交后跳转结果页 | PR gate |
| E2E-NC-006 | 商务技巧考试缺 paper 绑定 | 同上 | 显示“暂未绑定商务技巧考卷”等 typed config error，不伪成功 | PR gate |
| E2E-NC-007 | AI Coach happy path | `/sales-trainer/business-skills/coach` | 能开启 session、收到 streamed card / assistant delta、写入 progress | PR gate |
| E2E-NC-008 | AI Coach 配置异常 | 同上 | prompt/scoring prompt 缺失时 fail-closed，显示 trace/typed diagnostic | PR gate |
| E2E-NC-009 | 录音上传与评分 happy path | `/sales-trainer/audio/[unitId]` | 必须确认材料版本；提交后进入 result；显示 snapshot score/result | PR gate |
| E2E-NC-010 | 录音评分 provider timeout/typed failure | `/sales-trainer/audio/result/[submissionId]` | 显示“待重试”等业务文案，不泄露 provider error code 原文 | PR gate |
| E2E-NC-011 | 历史回放/结果页 snapshot-first | quiz/audio result + training record detail | 历史记录基于 frozen snapshot，不受后续 active revision 漂移影响 | PR gate |
| E2E-NC-012 | 管理端工作台/看板读取新人训练聚合 | `/admin/sales-trainer` | completion/pass/risk learner/weak dimensions 可见 | PR gate |
| E2E-NC-013 | 管理端训练记录详情 | `/admin/sales-trainer/training-records/...` | 展示 path lineage、effective score、regrade/remediation 信息 | PR gate |
| E2E-NC-014 | manager 部门范围权限 | admin records/journeys | manager 只能看到本部门；越权对象 fail-closed | PR gate |
| E2E-NC-015 | content_admin 能配内容但不能看学员记录 | admin pages | 内容页可进、training records/全局日志拒绝 | PR gate |
| E2E-NC-016 | ops/settings/logs 权限矩阵 | admin settings/logs | ops 可看健康/日志，不可改内容；content_admin 不可看 | PR gate |
| E2E-NC-017 | 实时对练模块 disabled 诊断 | learner 首页模块卡片 | runtime binding 未就绪时模块 disabled_reason 明确，不能偷偷创建 session | PR gate |
| E2E-NC-018 | 实时对练真实运行时 happy path | learner -> realtime module -> outcome -> dashboard | session/result/journey/outcome projection 全链路成立 | Nightly / Release |

### 2.3 最小必须覆盖的闭环组合

Phase 9 最小闭环不要求一次性把所有矩阵都做成 Playwright。建议先把以下 8 个做成最小强门禁：

- `E2E-NC-001` learner 首页 happy path
- `E2E-NC-002` learner 首页配置缺失
- `E2E-NC-005` 商务技巧考试 happy path
- `E2E-NC-007` AI Coach happy path
- `E2E-NC-009` 录音上传与评分 happy path
- `E2E-NC-012` 管理端工作台
- `E2E-NC-015` content_admin 权限不足
- `E2E-NC-017` 实时对练 disabled / config-invalid 诊断

## 3. fixture / seed / mock 策略

## 3.1 总体策略

- 不走真实 provider。
- 不依赖外部 SaaS、真实 StepFun、真实 Deucate、真实 DashScope。
- 优先复用现有本地 provider seam 与 deterministic fixture。
- 测试数据必须分成两层：
  - `stack bootstrap seed`
  - `scenario-specific fixture/override`

## 3.2 推荐 seed 分层

### A. smoke baseline seed

复用 `scripts/dev-smoke-up.sh` 的职责，但补新人训练种子：

- admin / content_admin / training_manager / support / ops / learner 账号
- learner 部门与 manager 部门映射
- active `newcomer_training_path_v1`
- 商务技巧 learning content + paper
- 音频模块 unit + material + score prompt
- AI Coach 可用 prompt / scoring prompt
- 至少 1 条历史 quiz/audio/training record

建议实现形式：

- 新增独立 bootstrap 脚本，而不是把所有逻辑继续堆进现有 `bootstrap_smoke_practice_evidence.py`
- 例如：
  - `backend/scripts/bootstrap_newcomer_training_e2e_seed.py`
- 由未来 E2E/CI 命令显式调用

### B. 场景局部覆盖 seed

使用单独环境变量或 per-test 预置：

- `NEWCOMER_E2E_SCENARIO=happy_path`
- `NEWCOMER_E2E_SCENARIO=config_missing`
- `NEWCOMER_E2E_SCENARIO=content_admin_forbidden`
- `NEWCOMER_E2E_SCENARIO=realtime_disabled`

原则：

- 不为每个场景建独立数据库快照文件
- 用统一 seed + 小范围 override，避免维护爆炸

## 3.3 mock / provider 策略

### 录音评分 / 实时对练

- 复用现有 `PHASE4_E2E_PROVIDER=local`
- 为新人训练新增 versioned provider script，例如：
  - `backend/tests/e2e/fixtures/newcomer-audio-provider-script.v1.json`
  - `backend/tests/e2e/fixtures/newcomer-realtime-provider-script.v1.json`
- transcript 仍输出到 `.sisyphus/evidence/*.jsonl`

### AI Coach

- 不建议在浏览器层 `route.fulfill` 伪造所有接口。
- 更建议走后端已有流式/事件语义，由后端消费 deterministic fixture。
- 理由：
  - 可以验证 typed event shape
  - 可以验证 progress/journey 落库
  - 可以避免前端 mock 与真实 API 结构漂移

### 文章 / 考试 / path config

- 优先真实后端 + SQLite/in-memory DB seed
- 不建议 Playwright 中大面积 `page.route()` mock，因为这会绕开：
  - active revision
  - RBAC
  - snapshot lineage
  - typed failure

## 3.4 历史回放策略

- 复用现有 `bootstrap_smoke_practice_evidence.py` 的“先制造可回放证据，再写 state/env”的思路
- 但新人训练需要额外冻结：
  - `path_revision_id / no`
  - paper snapshot
  - score prompt snapshot
  - material version snapshot
  - AI Coach session snapshot
- 最好让 seed 直接创建“历史记录 + 当前 active revision 已不同”的对照数据，用于验证 snapshot-first

## 4. CI gate 分层建议

## 4.1 分层目标

- PR 上跑 deterministic、快、稳定、无外部依赖的 gate
- Nightly / Release 上跑更重、更多场景、更多 evidence 校验
- 真实 provider 只放 Nightly / Release，且允许显式跳过并单独报表

## 4.2 建议分层

### Gate A：静态与快速单测

- `web`: `npx tsc --noEmit`、`npm run lint`、目标 Vitest
- `backend`: 新人训练相关 unit/contract 快速集
- 目标：< 5 分钟

### Gate B：新人训练 integration/contract gate

- 后端精选：
  - `tests/integration/test_newcomer_training_journey_api.py`
  - `tests/integration/test_newcomer_training_path_rbac_api.py`
  - `tests/integration/test_newcomer_training_path_material_api.py`
  - `tests/integration/test_newcomer_training_path_paper_api.py`
  - `tests/integration/test_business_etiquette_ai_coach_progress_api.py`
  - `tests/contract/test_sales_trainer_phase2_contract.py`
- 目标：保护闭环契约与权限，不等待浏览器

### Gate C：新人训练 deterministic Playwright smoke

- 新增 `web/tests/e2e/newcomer-training-closed-loop.spec.ts`
- 只跑最小强门禁场景
- 使用本地 seed + local provider seam
- 目标：保护真实用户旅程

### Gate D：跨域现有核心 E2E

- 保留现有：
  - `smoke.spec.ts`
  - `presentation-phase4.spec.ts`
  - `sales-phase4.spec.ts`
- 说明：新人训练不是替代它们，而是新增一个并列 gate

### Gate E：Nightly / Release 扩展 gate

- 新人训练完整矩阵，包括：
  - manager scope
  - content_admin / ops 权限矩阵
  - realtime_roleplay disabled + runtime-ready 双态
  - snapshot drift / rollback preview / historical replay
- 可追加 release readiness evidence 校验

### Gate F：真实 provider smoke

- 仅 Nightly / Release
- 对应已有原则：真实 provider 测试纳入 nightly/release 策略
- 不应成为 PR block

## 4.3 对 `scripts/critical-quality-gate.sh` 的落点建议

未来落点建议，不在本次任务实施：

- 在现有 smoke / presentation / sales Phase4 之间新增新人训练 Playwright 段
- 在后端 gate targets 中显式加入新人训练 integration/contract 关键清单
- 输出独立 evidence：
  - `task-9-newcomer-playwright-report`
  - `newcomer-e2e-transcript.jsonl`
  - `newcomer-e2e-seed-manifest.jsonl`

## 5. 最小先落地测试清单和命令

## 5.1 最小先落地清单

### Playwright

新增一个 spec 文件优先，不要一开始拆太碎：

- `web/tests/e2e/newcomer-training-closed-loop.spec.ts`

第一批测试建议 8 条：

1. learner 首页 happy path
2. learner 首页 config missing fail-closed
3. 商务技巧考试 happy path
4. AI Coach happy path
5. 录音上传 + 评分结果 happy path
6. admin 工作台聚合可见
7. content_admin 无法进入训练记录
8. 实时对练模块 disabled/config-invalid 诊断

### 后端精选 gate

- `backend/tests/integration/test_newcomer_training_journey_api.py`
- `backend/tests/integration/test_newcomer_training_path_rbac_api.py`
- `backend/tests/integration/test_newcomer_training_path_material_api.py`
- `backend/tests/integration/test_newcomer_training_path_paper_api.py`
- `backend/tests/integration/test_business_etiquette_ai_coach_progress_api.py`
- `backend/tests/unit/test_sales_trainer_training_journey_service.py`
- `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
- `backend/tests/unit/test_newcomer_training_path_permissions.py`

## 5.2 建议命令

### 本地只跑新人训练 Playwright

```bash
cd web
SMOKE_REUSE_EXISTING_STACK=1 \
NEWCOMER_E2E_SEED=baseline \
PHASE4_E2E_PROVIDER=local \
npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
```

### 本地先拉栈再跑

```bash
bash scripts/dev-smoke-up.sh
cd web
PHASE4_E2E_PROVIDER=local \
npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
bash scripts/dev-smoke-stop.sh
```

### 后端新人训练精选 gate

```bash
cd backend
pytest \
  tests/integration/test_newcomer_training_journey_api.py \
  tests/integration/test_newcomer_training_path_rbac_api.py \
  tests/integration/test_newcomer_training_path_material_api.py \
  tests/integration/test_newcomer_training_path_paper_api.py \
  tests/integration/test_business_etiquette_ai_coach_progress_api.py \
  tests/unit/test_sales_trainer_training_journey_service.py \
  tests/unit/test_newcomer_training_path_audio_lineage.py \
  tests/unit/test_newcomer_training_path_permissions.py
```

### 未来汇入 critical gate 的新增段

```bash
cd web
SMOKE_REUSE_EXISTING_STACK=1 \
PHASE4_E2E_PROVIDER=local \
npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts
```

## 5.3 为什么先只落一个 spec

- 当前仓库 Playwright 还不是 page object / fixture-heavy 体系
- 先用一个闭环 spec 聚合最小旅程，成本最低
- 待场景稳定后再拆：
  - `newcomer-training-learner.spec.ts`
  - `newcomer-training-admin.spec.ts`
  - `newcomer-training-permissions.spec.ts`
  - `newcomer-training-realtime.spec.ts`

## 6. 暂停条件

出现以下任一情况，Phase 9 新人训练 E2E/CI gate 不应继续扩写，应先停下补契约或 seed 能力：

1. **active path revision 仍非 learner 唯一真源**
   - 现象：测试只能靠 legacy fallback 才能通过。
2. **新人训练 seed 无法稳定创建 deterministic 闭环数据**
   - 现象：同一条 E2E 在空库/重跑后结果不一致。
3. **AI Coach / 音频评分没有本地 deterministic provider seam**
   - 现象：必须依赖真实模型或外部网络才能过。
4. **实时对练 runtime binding / permission / outcome projection 契约未冻结**
   - 现象：E2E 只能验证“能连上”，不能验证闭环结果。
5. **权限矩阵未稳定**
   - 现象：content_admin、manager、ops 的后端 fail-closed 语义仍频繁变化。
6. **历史记录 snapshot-first 语义未稳定**
   - 现象：回放页/结果页依赖 latest asset，seed 无法制造稳定断言。
7. **关键 typed failure 仍未标准化**
   - 现象：同类配置错误在不同入口报错文案/状态码/错误码不一致。
8. **CI 时间或稳定性失控**
   - 现象：PR gate 明显超时，或 flaky rate 超过可接受阈值。

## 7. 推荐实施顺序

1. 先补新人训练 deterministic seed 脚本
2. 再补单文件 Playwright 闭环 spec
3. 再把后端精选新人训练测试加入 gate
4. 再把新人训练 Playwright 挂到 `critical-quality-gate.sh`
5. 最后再扩到 realtime_roleplay 真运行时 E2E 与 Nightly/Release 扩展矩阵

## 8. 风险与建议

- 当前最大风险不是“没有测试框架”，而是 **没有新人训练专用 deterministic 闭环 seed**。
- 当前第二风险是 **实时对练纳入闭环的契约尚未稳定**，不应直接承诺 PR gate 上真运行时 happy path。
- 当前最务实方案是：
  - PR gate 先卡住异步闭环主链路 + 权限 + 配置异常 + 历史回放
  - realtime happy path 放 Nightly/Release，直到 runtime binding、provider readiness、journey projection 固化

## 9. 本次研究使用的主要依据

- `AGENTS.md`
- `CLAUDE.md`
- `docs/api-contract/sales-trainer.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/frontend/index.md`
- `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/prd.md`
- `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/audit-synthesis.md`
- `scripts/critical-quality-gate.sh`
- `web/playwright.config.ts`
- `web/tests/e2e/smoke.spec.ts`
- `web/tests/e2e/presentation-phase4.spec.ts`
- `web/tests/e2e/sales-phase4.spec.ts`
- `web/tests/e2e/audit/audit.spec.ts`
- `scripts/dev-smoke-up.sh`
- `scripts/dev-smoke-stop.sh`
- `backend/scripts/bootstrap_smoke_practice_evidence.py`
- `backend/src/sales_bot/websocket/phase4_local_provider.py`
- 现有新人训练前端页面测试与后端新人训练 integration/unit/contract 测试
