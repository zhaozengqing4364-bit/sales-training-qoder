# Implementation Notes

## Baseline

- 任务开始时工作区已有 82 项未提交修改，包含新人训练编排、管理页面、测试与共享 `client-id` 工具。
- 采用增量修复；不回退、不覆盖、不纳入本任务之外的既有改动。
- CodeGraph 同步后索引包含 77 个当前变更文件。

## Confirmed Root Causes

- QA-001：活动 runners 仍直接调用 `crypto.randomUUID()`；共享 `web/src/lib/client-id.ts` 已存在但未覆盖考试、录音、作业、课程、AI 教练和实时对练。
- QA-002/006：活动路由页只有一次 Promise 链和布尔错误态，没有取消、超时、显式 retry 或刷新状态机；失败后会保持不收敛状态。
- QA-003：Journey 只执行显式 `prerequisites`；当前 seed 路径没有配置阶段/模块/活动依赖，且 `context_for_activity` 不校验 projected lock，导致详情/写入口可绕过。
- QA-004：后端 `ReadinessDossierService.list_workbench()` 返回 `{items,total}` 的 `activity_readiness_v1`，前端页面/类型期待 `{groups,summary}` 的 `readiness_dossier_v1`，属于跨层契约漂移。
- QA-005：目标环境的 CORS preflight 与直接 dev-login 当前均为 200；浏览器超时根因需以客户端生命周期测试继续缩小，不能归因于接口性能。
- QA-010：`RealtimeRunnerDescriptor` 当前只有 `type`，没有发布模板的角色、场景、目标或评分投影。
- 写入重试：原 runner 每次点击都生成新 token；在服务端已成功但响应丢失时，刷新/重试会绕过后端幂等约束，形成重复提交风险。
- 实时对练版本一致性：详情与开始服务读取“当前”模板/运行配置，已发布路径没有冻结绑定快照；后台后续编辑会静默改变在训学员运行时。

## Deviations

- 正式域名、TLS、HTTP 强制跳转和不安全上下文麦克风能力按用户要求延后；本任务只修复 UUID 兼容与可理解的媒体降级。
- 黑盒目标上的 dev-login HTTP/CORS 复测已恢复，仍保留客户端竞态回归测试，避免把偶发恢复当作根因修复。

## Verification Evidence

- 2026-07-14：目标后端 dev-login OPTIONS 与 POST 均在 1 秒内返回 200，并包含正确 `Access-Control-Allow-Origin` 与 credentials；响应内容未保存。
- Headless Playwright 初次启动因缺少系统 `libnspr4.so` 失败；后续浏览器调用必须经过项目 `run_playwright` 包装并使用 `.sisyphus/playwright-libs`。

## Completed Changes

### P1 core flow

- UUID 兼容：`web/src/lib/client-id.ts` 提供安全上下文/非安全上下文统一客户端 ID，六类活动 runner 不再直接依赖 `crypto.randomUUID()`；回退值补齐 UUID v4 version/variant bits。
- 活动加载与刷新恢复：`web/src/app/(dashboard)/newcomer-training/activities/[activityId]/page.tsx` 增加 request-key 状态、慢加载说明、10 秒超时、错误/重试和过期响应保护。
- 登录：`web/src/app/(auth)/login/page.tsx` 增加 in-flight ref，快速重复点击只发起一次登录；开发登录超时放宽到 15 秒。
- 顺序解锁：`backend/src/sales_trainer/orchestration/journey_service.py` 同时执行显式前置和旧发布路径的必修顺序门禁；详情仍可展示锁定原因，所有写入口经 `context_for_activity` 返回 409，不能深链绕过。
- Seed 路径：`backend/scripts/seed_newcomer_training_path.py` 补齐活动、模块和阶段前置条件。
- 达标审核：`backend/src/sales_trainer/services/readiness_dossier_service.py` 输出前端约定的六状态分组与 summary，对缺失状态桶、未知/单学员配置异常做兜底；前端再做运行时空值保护。
- 达标审核详情：统一为活动原生 `readiness_dossier_v1`，补齐模块、能力、证据、历史审核、补训任务、实时门禁、诊断和下一步动作；决策统一为 `approve/require_retraining/mark_manual_follow_up`，同时兼容旧 `reject/retrain` 输入。
- 幂等重试：新增按“活动 + 逻辑输入”持久化到 sessionStorage 的 client token store；不确定失败与刷新后复用 token，确认成功才清除，输入变化才创建新 token。考试、录音、课程、作业、AI 教练和实时对练均接入。
- 实时对练发布快照：路径保存草稿时冻结模板版本/内容 hash、runtime hash、治理资产 hash 和学员可见 runner 快照；发布前校验漂移，开始会话时再次校验。后台后续修改不会静默改变已发布路径，漂移时明确阻止启动并要求重新保存/发布。
- 活动轮询：从固定 interval 改为上一次请求完成后再安排下一次，并在卸载/切换时 abort，避免慢网下同一活动产生并发轮询和陈旧响应覆盖。

### P2/P3 follow-up

- QA-007：当前基线已包含稳定 `/admin/learning-contents/new` 路由、列表跳转和新建页测试；本轮未重复实现，回归测试通过。黑盒环境表现与当前代码不一致，需确认部署版本。
- QA-008：操作日志隐藏 actor UUID；未知动作/对象和数字原因使用业务化兜底；目标优先显示业务名称；原始技术详情仅 `admin_full_access` 可展开。
- QA-010：实时对练 descriptor 只投影已发布模板/客户案例/角色档案/评分规则集的学员可见信息，包括角色、场景、目标、评分依据、通过分和发布版本；不返回 agent/persona/runtime/template/ruleset ID。核心绑定缺失时 `configuration_ready=false` 并禁止开始。
- QA-010 运行前门禁：查询 `VoiceRuntimeProfile`，要求存在且启用，并要求路径配置的 runtime profile 与已发布模板一致；缺失或不一致均在详情页提前阻止，不等到 start API 才失败。
- QA-011：管理首页移除 API 名、projection/runtime、manager-lite 等工程术语；模板列表状态/模式/场景中文化并隐藏内部 ID；新人训练设置把 `file`、`fun-asr`、`active_missing` 和策略来源映射为管理员语言；操作日志内部数据受控展示。
- QA-012：移动端“保存草稿”按钮增加 `whitespace-nowrap`，不再逐字换行。

## Files Changed By This Remediation

### Backend

- `backend/scripts/seed_newcomer_training_path.py`
- `backend/src/sales_trainer/orchestration/contracts.py`
- `backend/src/sales_trainer/orchestration/activities/base.py`
- `backend/src/sales_trainer/orchestration/activities/ai_coach.py`
- `backend/src/sales_trainer/orchestration/activities/assignment.py`
- `backend/src/sales_trainer/orchestration/activities/audio_assessment.py`
- `backend/src/sales_trainer/orchestration/activities/quiz.py`
- `backend/src/sales_trainer/orchestration/activities/realtime_roleplay.py`
- `backend/src/sales_trainer/orchestration/journey_service.py`
- `backend/src/sales_trainer/orchestration/repository.py`
- `backend/src/sales_trainer/services/readiness_dossier_service.py`
- `backend/src/sales_trainer/services/realtime_binding_snapshot_service.py`
- `backend/src/sales_trainer/services/realtime_roleplay_start_service.py`
- `backend/src/sales_trainer/orchestration/revision_service.py`
- `backend/tests/unit/test_newcomer_orchestration_journey_service.py`
- `backend/tests/unit/test_newcomer_orchestration_repository.py`
- `backend/tests/unit/test_sales_trainer_readiness_dossier_service.py`
- `backend/tests/integration/test_newcomer_orchestration_learner_api.py`
- `backend/tests/integration/test_newcomer_orchestration_admin_api.py`

### Frontend

- `web/src/lib/client-id.ts`
- `web/src/lib/client-id.test.ts`
- `web/src/lib/idempotency-token-store.ts`
- `web/src/lib/idempotency-token-store.test.ts`
- `web/src/lib/api/client-domains.ts`
- `web/src/lib/api/client.auth.test.ts`
- `web/src/lib/api/types/newcomer-training.ts`
- `web/src/app/(auth)/login/page.tsx`
- `web/src/app/(auth)/login/page.test.tsx`
- `web/src/app/(dashboard)/newcomer-training/activities/[activityId]/page.tsx`
- `web/src/app/(dashboard)/newcomer-training/activities/[activityId]/page.test.tsx`
- `web/src/app/admin/sales-trainer/readiness/page.tsx`
- `web/src/app/admin/sales-trainer/readiness/page.test.tsx`
- `web/src/components/newcomer-training/activity-runners/ai-coach-runner.tsx`
- `web/src/components/newcomer-training/activity-runners/assignment-runner.tsx`
- `web/src/components/newcomer-training/activity-runners/audio-assessment-runner.tsx`
- `web/src/components/newcomer-training/activity-runners/lesson-runner.tsx`
- `web/src/components/newcomer-training/activity-runners/quiz-runner.tsx`
- `web/src/components/newcomer-training/activity-runners/realtime-roleplay-runner.tsx`
- `web/src/components/newcomer-training/activity-runners/realtime-roleplay-runner.test.tsx`
- `web/src/components/newcomer-training/activity-shell.test.tsx`
- `web/src/lib/sales-trainer/operation-log-display.ts`
- `web/src/lib/sales-trainer/operation-log-display.test.ts`
- `web/src/app/admin/sales-trainer/operation-logs/page.tsx`
- `web/src/app/admin/sales-trainer/operation-logs/page.test.tsx`
- `web/src/components/admin/newcomer-training/path-editor.tsx`
- `web/src/components/admin/newcomer-training/path-editor.test.tsx`
- `web/src/components/admin/curriculum-practice/template-list.tsx`
- `web/src/app/admin/curriculum-practice/templates/page.tsx`
- `web/src/app/admin/curriculum-practice/templates/page.test.tsx`
- `web/src/lib/sales-trainer/settings-presentation.ts`
- `web/src/lib/sales-trainer/settings-presentation.test.ts`
- `web/src/app/admin/sales-trainer/settings/page.tsx`
- `web/src/app/admin/page.tsx`
- `web/src/app/admin/page.test.tsx`

部分文件在任务开始前已有未提交 WIP；上述改动均为局部增量，没有回退其他人的工作。

## Verification Commands And Results

- Frontend P1 回归：
  - `cd web && npx vitest run 'src/lib/client-id.test.ts' 'src/lib/api/client.auth.test.ts' 'src/app/(auth)/login/page.test.tsx' 'src/app/(dashboard)/newcomer-training/activities/[activityId]/page.test.tsx' 'src/app/admin/sales-trainer/readiness/page.test.tsx' 'src/components/newcomer-training/activity-shell.test.tsx' 'src/components/newcomer-training/activity-runners/realtime-roleplay-runner.test.tsx' 'src/lib/sales-trainer/operation-log-display.test.ts' 'src/app/admin/sales-trainer/operation-logs/page.test.tsx'`
  - 结果：9 files / 59 tests passed。
- Frontend P2 主闭环（含 QA-007 现有路由）：
  - `cd web && npx vitest run 'src/lib/sales-trainer/operation-log-display.test.ts' 'src/app/admin/sales-trainer/operation-logs/page.test.tsx' 'src/components/admin/newcomer-training/path-editor.test.tsx' 'src/app/admin/learning-contents/page.test.tsx' 'src/app/admin/learning-contents/new/page.test.tsx'`
  - 结果：5 files / 32 tests passed；随后 QA-010 纳入时 6 files / 34 tests passed。
- Frontend 用户语言映射：
  - `cd web && npx vitest run 'src/app/admin/curriculum-practice/templates/page.test.tsx' 'src/app/admin/page.test.tsx' 'src/lib/sales-trainer/settings-presentation.test.ts' 'src/components/newcomer-training/activity-runners/realtime-roleplay-runner.test.tsx' 'src/lib/sales-trainer/operation-log-display.test.ts' 'src/app/admin/sales-trainer/operation-logs/page.test.tsx'`
  - 结果：6 files / 23 tests passed。
- Frontend 静态检查：`cd web && npx tsc --noEmit` 通过；聚焦 ESLint `npx eslint --quiet ...` 通过。
- Backend P1 单元：`cd backend && .venv/bin/pytest --no-cov -q tests/unit/test_newcomer_orchestration_journey_service.py tests/unit/test_sales_trainer_readiness_dossier_service.py`，9 passed。
- Backend P1 集成：`cd backend && .venv/bin/pytest --no-cov -q tests/integration/test_newcomer_orchestration_learner_api.py tests/integration/test_newcomer_orchestration_admin_api.py`，11 passed。
- Backend 最终相关回归：
  - `cd backend && .venv/bin/pytest --no-cov -q tests/unit/test_newcomer_orchestration_journey_service.py tests/unit/test_newcomer_realtime_activity.py tests/unit/test_sales_trainer_realtime_roleplay_start.py tests/unit/test_newcomer_orchestration_contracts.py tests/unit/test_sales_trainer_readiness_dossier_service.py tests/integration/test_newcomer_orchestration_learner_api.py`
  - 结果：31 passed，只有 passlib `crypt` 弃用警告。
- Backend 静态检查：`cd backend && .venv/bin/ruff check src/sales_trainer/orchestration/contracts.py src/sales_trainer/orchestration/journey_service.py tests/unit/test_newcomer_orchestration_journey_service.py`，通过。
- Frontend 最终受影响回归：`npx tsc --noEmit`、聚焦 ESLint，以及 UUID/幂等 token/录音重试/活动轮询/登录/设置/操作日志 7 个测试文件，结果 28 tests passed。
- Backend 最终受影响回归：contracts、revision、journey、realtime activity/start、readiness、admin API、seed 共 8 个测试文件，结果 49 tests passed；聚焦 Ruff format/check 通过，仅有 passlib `crypt` 弃用警告。
- CodeGraph 同步后按 `affected` 补跑完整影响集：Frontend 7 files / 38 tests passed；加入 Journey 批量投影后 Backend 31 files / 150 tests passed，只有既有 passlib/agent 字段弃用警告。
- `git diff --check` 通过。
- CodeGraph impact：`_runner_descriptor` 的直接影响为 `activity_detail`；相关 journey unit、learner API integration、realtime start service 已覆盖。共享 descriptor/type 的 affected 集较大，已额外执行 contract、readiness 和 activity shell 测试。

## QA-009 Performance Scope

- Journey 投影原先对每个非课程活动串行查询一次最新 attempt；现改为按 enrollment 一次批量取得每个活动的最新 attempt，再注入 handler 投影，14 活动路径不再产生该组 N+1 查询。
- 活动页增加 1 秒慢加载说明、10 秒超时、重试、请求取消和陈旧响应保护；轮询不会在慢网下并发叠加。
- 新增 repository 批量投影测试，并回归 quiz、audio、assignment、AI coach、realtime、lesson、journey 与 learner API，21 tests passed。
- 冷启动、首屏 chunk、课程内容外部投影和 400ms RTT 的最终数值仍必须在正式域名/目标部署上重新量测；当前没有可证明资源拆包或缓存收益的部署侧 trace，因此未做猜测性改造。

## Residual Risks / Release / Rollback

- 正式域名、TLS 证书、HTTP→HTTPS 强制跳转尚未实施。UUID 回退已避免关键写入在创建 client token 时崩溃，但 `http://IP` 仍不是安全上下文，真实麦克风/getUserMedia 仍不可用。
- 未执行真实 ASR、评分 Provider、实时 WebSocket、麦克风允许/拒绝/无设备和第三方超时回归；原因是正式域名、TLS、真实 Provider 凭据与目标环境不在本轮授权/条件内。不能把自动化测试视为 Provider 通过。
- QA-007 当前代码已存在稳定路由，但黑盒环境曾不稳定，发布后必须核对构建版本、CDN/浏览器缓存及连续进入/返回/刷新。
- Realtime descriptor 与路径快照字段是加法 API 变更；前后端需同批发布。旧的已发布路径没有快照，为兼容读取仍可使用旧投影，但必须重新保存并发布后才获得不可变绑定和漂移门禁。
- 顺序前置条件与实时绑定快照进入正式路径都需要管理员重新保存并发布路径；不要直接在生产执行 seed 脚本覆盖正式数据。
- 风险等级：P1（核心训练写入/门禁/达标审核跨层修复），无数据库 schema/migration，无生产数据修复。
- 发布：后端与前端同批灰度；部署后按报告清单回归登录、14 活动解锁、PPT/Demo 提交、对练启动、达标审核、操作日志和移动端。
- 回滚：回退本节文件清单对应版本并重新部署即可；无数据迁移需回滚。若对练投影异常，可优先回退 runner descriptor 与前端 realtime runner，保留 UUID、活动加载和门禁修复。

## 2026-07-14 用户与团队配置闭环补充

- 根因：`/admin/users` 用响应中不存在的 `user_id` 作为勾选键；所有行都落为 `undefined`，点击任意一行后所有行同时命中。改为 API 契约中的 canonical `id`，并限制批量训练只勾选学员角色。
- 角色语义：账号角色 `training_manager` 展示为“培训管理员”；只有存在显式 `TeamLeaderAssignment` 时才展示为“销售组长”。`user/support/admin` 分别改为“学员/技术支持/平台管理员”。
- 配置路径：新增 `/admin/teams`，位于“组织与权限 → 团队与成员”。页面支持团队创建、主/代理组长设置、学员分配、当前关系查看，并明确本期销售组长只读、任务仍由平台管理员分配。
- 上下文内完成：团队页可就地快速创建缺失的学员或培训管理员账号，创建后自动选中并继续保存关系；一次性临时密码仍只显示一次。
- API：`GET /admin/teams` 兼容保留 `leader_user_ids/member_count`，并加法返回具名 `leaders/members`，使用两次批量 join 查询替代按团队 N+1。
- 验证：前端 5 files / 31 tests passed，TypeScript 与聚焦 ESLint 通过，Next production build 通过；后端 2 integration tests passed，Ruff check/format 通过。
- 部署黑盒：开发者快速登录 489ms；点击“销售学员”后仅 1 个 checkbox 选中；团队页正确显示“角色验收销售组”、销售组长和销售学员；390px 无横向溢出。前后端已重启并通过公网 health/页面探测。
- 偏差：未在真实环境创建新账号或改动团队关系，只读取既有 `qa.*@qoder.ai` 账号与“角色验收销售组”；避免产生需要清理的测试数据。
