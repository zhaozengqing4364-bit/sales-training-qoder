# Phase 0 子代理 D：测试与 CI 门禁审计报告

> 日期：2026-06-27  
> 范围：只读核对后端、前端、Playwright、CI 测试覆盖；未修改业务代码；未启动外部服务；未运行全量耗时测试。  
> 依据：`AGENTS.md`、`CLAUDE.md`、`audit-synthesis.md`、`.trellis/spec/backend/index.md`、`.trellis/spec/frontend/index.md`、`backend/pyproject.toml`、`web/package.json`、`web/vitest.config.ts`、`web/playwright.config.ts`、`.github/workflows/*`、`scripts/critical-quality-gate.sh`、测试文件清单与 CodeGraph 探索。

## 1. 现有测试事实

### 后端测试配置与命令

- 配置 authority：`backend/pyproject.toml`
  - `testpaths = ["tests"]`
  - `pythonpath = ["src"]`
  - `addopts = "-v --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=48 --import-mode=importlib"`
  - markers：`contract`、`integration`、`performance`
- 测试树事实：`backend/tests` 共有约 388 个 Python 测试/辅助文件，其中 `unit` 约 255、`integration` 约 91、`contract` 约 28、`e2e` 约 3、`performance` 约 6。
- 常用命令：
  - `cd backend && pytest tests/unit/`
  - `cd backend && pytest tests/integration/`
  - `cd backend && pytest tests/contract/`
  - `cd backend && pytest tests/e2e/`
  - `cd backend && pytest`，带 48% coverage floor。

### 后端新人训练覆盖点

已有较多局部覆盖，集中在 `backend/tests/unit` 与 `backend/tests/integration`：

- learner 首页/路径 projection：
  - `backend/tests/unit/test_sales_trainer_phase2_projection.py`
  - `backend/tests/unit/test_sales_trainer_path_projection_ai_coach.py`
  - `backend/tests/unit/test_sales_trainer_dashboard_recommendation.py`
  - `backend/tests/integration/test_newcomer_training_path_config_api.py`
- 文章/考试：
  - `backend/tests/unit/test_newcomer_training_path_articles.py`
  - `backend/tests/unit/test_newcomer_training_path_papers.py`
  - `backend/tests/unit/test_newcomer_training_path_attempt_lineage.py`
  - `backend/tests/integration/test_newcomer_training_path_article_api.py`
  - `backend/tests/integration/test_newcomer_training_path_paper_api.py`
  - `backend/tests/integration/test_business_etiquette_quiz_api.py`
  - `backend/tests/integration/test_business_etiquette_learning_units_api.py`
- 录音评分：
  - `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
  - `backend/tests/unit/test_sales_trainer_services.py`
  - `backend/tests/unit/test_sales_trainer_paraformer_file_asr.py`
  - `backend/tests/integration/test_sales_trainer_api.py`
  - `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py`
  - `backend/tests/integration/test_newcomer_training_path_regrade_api.py`
- AI Coach：
  - `backend/tests/unit/test_sales_trainer_ai_coach.py`
  - `backend/tests/unit/test_sales_trainer_ai_coach_chat.py`
  - `backend/tests/unit/test_business_etiquette_ai_coach_progress_service.py`
  - `backend/tests/integration/test_business_etiquette_ai_coach_progress_api.py`
- 管理端看板/记录：
  - `backend/tests/contract/test_sales_trainer_phase2_contract.py`
  - 覆盖 manager dashboard contract、training records pagination、record detail record types、material version filter、department scope。
- 权限不足：
  - `backend/tests/unit/test_newcomer_training_path_permissions.py`
  - `backend/tests/integration/test_newcomer_training_path_rbac_api.py`
  - `backend/tests/integration/test_sales_trainer_api.py` 中包含普通用户禁止 admin API、同部门 scope、owner/admin 音频访问。
- 配置异常：
  - `backend/tests/unit/test_newcomer_training_path_config_bindings.py`
  - `backend/tests/unit/test_newcomer_training_path_config_revision.py`
  - `backend/tests/unit/test_newcomer_training_path_score_prompts.py`
  - `backend/tests/integration/test_newcomer_training_path_config_api.py` 中包含 AI Coach 高风险字段 save/publish/rollback 拒绝。
- 历史回放/历史证据：
  - `backend/tests/unit/test_newcomer_training_path_record_lineage.py`
  - `backend/tests/unit/test_history_service_evidence_projection.py`
  - `backend/tests/integration/test_history_evidence_flow.py`
  - `backend/tests/integration/test_replay_api.py`

CodeGraph 额外提示：

- `ArticleBindingService` 有 `test_newcomer_training_path_articles.py` 和 boundary 测试覆盖。
- `TrainingRecordService` 有 record lineage 与 phase2 projection 覆盖。
- `EffectiveAudioTrainingConfig` / `EffectiveAudioTrainingConfigResolver` 被 `audio_submission_service.py` 与 `api.py` 使用，但 CodeGraph 未找到直接覆盖测试；虽然音频 lineage 间接覆盖 active path audio bindings，仍建议补直接 unit 或 contract。
- `ArticleExamBinding` / `article_exam_prerequisite_service.py` 相关绑定服务未见明确覆盖，文章完成后解锁考试的跨模块前置条件应补门禁。

### 前端测试配置与命令

- 配置 authority：`web/vitest.config.ts`
  - runner：Vitest 4 + jsdom
  - include：`**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}`
  - exclude：`tests/e2e/**`
  - coverage thresholds：lines/functions/statements 30%，branches 25%。
- `web/package.json`
  - `npm run test` = `vitest run`
  - `npm run test:coverage` = `vitest --run --coverage`
  - `npm run e2e` = `playwright test`
  - `npm run lint` = `eslint`
- 测试文件事实：`web/src` + `web/tests/e2e` 约 190 个 `.test/.spec` 文件。

### 前端新人训练覆盖点

- learner 首页：
  - `web/src/app/(dashboard)/sales-trainer/page.test.tsx`
    - 已覆盖 catalog fallback、path-first layout、学习链接、三模块 grid、额外单元展开、realtime placeholder disabled。
  - `web/src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx`
    - 覆盖配置路径存在时不暴露 legacy/verification units。
  - `web/src/app/(dashboard)/sales-trainer/next-step-panel.test.tsx`
    - 覆盖 AI Coach fallback 与 unavailable fallback。
- 文章/考试：
  - `web/src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx`
    - 覆盖章节阅读、考试解锁、过期 progress 不可信、AI Coach 入口、quiz result、AI 短答 feedback、历史 attempt 标记、pending 不渲染失败、错误保留答案、缺配置 remediation。
  - `web/src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx`
    - 覆盖专用考试页提交、未读章节前置、缺 paper 配置错误。
  - `web/src/app/(dashboard)/sales-trainer/quiz/[unitId]/page.test.tsx`
  - `web/src/app/(dashboard)/sales-trainer/quiz/result/[attemptId]/page.test.tsx`
- 录音评分：
  - `web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx`
    - 覆盖 level context、pass threshold、上传文件、材料 markdown preview。
  - `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx`
    - 覆盖授权播放/下载、poll terminal scored state、timeout retry guidance、失败建议、frozen scoring snapshot、对象型建议不崩溃。
- AI Coach：
  - `web/src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx`
    - 覆盖 resume、streamed card delta、缺 unit snapshot、submit stream failure、训练卡渲染、free text、reasoning stream、选项提交评分、disabled config、followup prompt、固定命令 event id。
  - `web/src/components/ai-coach/interactions/AiCoachInteractionRenderer.test.tsx`
- 管理端看板：
  - `web/src/app/admin/sales-trainer/page.test.tsx`
    - 覆盖 manager dashboard summary、弱项、风险学员、AI Coach 配置入口、训练记录入口。
  - `web/src/app/admin/sales-trainer/training-records/page.test.tsx`
  - `web/src/app/admin/sales-trainer/training-records/[recordType]/[recordId]/page.test.tsx`
  - `web/src/app/admin/sales-trainer/audio-submissions/page.test.tsx`
  - `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx`
  - `web/src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx`
- 配置异常/发布回滚：
  - `web/src/app/admin/sales-trainer/paths/page.test.tsx`
    - 覆盖 diagnostics、remediation focus、article binding check failed 时保留配置中心、保存 working revision、要求 reason、publish、rollback。
  - `web/src/app/admin/sales-trainer/articles/page.test.tsx`
  - `web/src/app/admin/sales-trainer/materials/page.test.tsx`
  - `web/src/app/admin/sales-trainer/settings/page.test.tsx`
  - `web/src/app/admin/sales-trainer/ai-coach/page.test.tsx`
- API facade：
  - `web/src/lib/api/sales-trainer.test.ts`
    - 覆盖 learner units/paths、quiz submit、audio upload/presign/object storage fallback、admin quiz attempts、historical regrade。
  - `web/src/lib/api/newcomer-training.test.ts`
    - 覆盖 module article、paper submit、paper revision、article bind、release preview、paper publish/rollback、path config revisions。

### Playwright E2E 覆盖事实

- 配置 authority：`web/playwright.config.ts`
  - `testDir = web/tests/e2e`
  - `workers = 1`
  - `trace = retain-on-failure`
  - `screenshot = only-on-failure`
  - `video = retain-on-failure`
  - HTML 报告与结果输出到 `.sisyphus/evidence/${SMOKE_EVIDENCE_PREFIX}-*`
- 现有 E2E 文件：
  - `web/tests/e2e/smoke.spec.ts`
    - 覆盖 unauthenticated redirect、login、dashboard、training entry、practice session、report、replay、admin analytics、support runtime。
  - `web/tests/e2e/sales-phase4.spec.ts`
    - 覆盖真实浏览器通过 `/ws/sales` 完成 Sales Training Flow 并暴露 report evidence chain。
  - `web/tests/e2e/presentation-phase4.spec.ts`
    - 覆盖 `/ws/presentation` 与 corrupted PPT 降级。
  - `web/tests/e2e/audit/audit.spec.ts`
- 明确缺口：没有 `newcomer-training-closed-loop.spec.ts` 或等价 Playwright 用例覆盖 “learner 首页 -> 文章/考试 -> AI Coach -> 录音评分 -> 管理端看板/记录 -> 历史回放”。

### CI 门禁事实

- `.github/workflows/release-truth-gate.yml`
  - 安装 Node/Python、Playwright Chromium。
  - 执行 `python scripts/check_secret_hygiene.py`。
  - 执行 `bash scripts/critical-quality-gate.sh`。
- `scripts/critical-quality-gate.sh`
  - 前端 typecheck：`cd web && npx tsc --noEmit`
  - Vitest 仅跑固定 `VITEST_GATE_TARGETS`，当前没有新人训练 learner/admin 页面测试。
  - Playwright 跑：
    - `tests/e2e/smoke.spec.ts`
    - `tests/e2e/presentation-phase4.spec.ts`
    - `tests/e2e/sales-phase4.spec.ts`
  - 后端 `BACKEND_GATE_TARGETS` 仅包含 auth、history/report/replay、admin analytics、support runtime、business rules、model config、release verification，不包含 `sales_trainer/newcomer/business_etiquette` 核心测试。
  - `BACKEND_SMOKE_REGRESSION_TARGETS` 也未包含新人训练闭环测试。
- `.github/workflows/roleplay-contract-eval.yml`
  - 专注 roleplay contract eval，不覆盖新人训练异步闭环。
- `.github/workflows/nfr-performance-check.yml`
  - 专注性能与 load test，不覆盖新人训练业务正确性。

## 2. 缺失测试矩阵

| 能力/风险 | unit | integration | contract | e2e | CI |
| --- | --- | --- | --- | --- | --- |
| learner 首页 active path 唯一真源，禁用 catalog fallback 生产生成新数据 | 有 projection/页面局部覆盖，但仍有 fallback 测试 | 缺“无 active revision fail-closed”集成门禁 | 缺 TrainingJourney/ModuleProgress contract | 缺真实浏览器首页诊断态 | 未进 gate |
| 文章学习 -> 完成章节 -> 考试前置 | 有文章/页面局部覆盖 | 有 article/paper API，但缺完整跨接口前置集成 | 缺 article-exam prerequisite contract | 缺闭环 E2E | 未进 gate |
| 考试提交、AI 短答、历史 attempt snapshot | 有较多 | 有 paper/quiz/API | 有 phase2 records 但缺 TrainingJourney contract | 缺闭环 E2E | 未进 gate |
| 录音上传 -> 转写 -> 评分 -> 结果页 -> 管理端记录 | 有 lineage、service、页面覆盖 | 有 upload/regrade/admin file 权限 | 缺音频 submission 到 journey 的 contract | 缺闭环 E2E；真实 provider 可 nightly | 未进 gate |
| AI Coach 必过能力，disabled/坏配置 fail-closed | 有 schema/chat/page 覆盖 | 有 progress API，缺完整 session -> journey 集成 | 缺 AI Coach session contract 与失败语义 | 缺闭环 E2E | 未进 gate |
| 实时对练纳入新人训练闭环 | sales realtime 有独立 E2E | 缺 sales_trainer module binding -> runtime preflight 集成 | 缺 realtime module binding contract | 现有 `sales-phase4` 不经过新人训练入口 | CI 只保销售 realtime，不保新人训练接入 |
| 管理端看板下钻：总览 -> 学员 -> 记录 -> 证据 -> 补救 | 有页面局部 | contract 有 manager dashboard/training records | 缺 dashboard drilldown contract | 缺闭环 E2E | 未进 gate |
| 权限不足：learner/admin/support/training_manager/content_admin 分层 | 有 RBAC 局部 | 有 granular RBAC 与 admin forbidden | 缺 capability 五层一致 contract | 缺 Playwright 直链/按钮 fail-closed | 未进 gate |
| 配置异常：缺失、非法、disabled、fallback、发布失败 | 有页面和 service 局部 | 有 path config 高风险字段拒绝 | 缺 config health/dependency graph contract | 缺 Playwright 配置异常态 | 未进 gate |
| 历史回放：归档材料、历史 score/prompt snapshot、replay evidence | 有 lineage/record 局部 | 有 history/replay 通用，不是新人训练闭环专属 | 缺 snapshot-first 历史展示 contract | 缺新人训练历史回放 E2E | 通用 replay 在 gate，新人训练不在 |

## 3. 每个阶段最小验证命令

以下命令是建议门禁，不代表本次已执行。

### Phase 0：契约冻结与测试门禁补齐

```bash
cd backend && pytest -c pyproject.toml \
  tests/contract/test_sales_trainer_phase2_contract.py \
  tests/integration/test_newcomer_training_path_config_api.py \
  tests/integration/test_newcomer_training_path_rbac_api.py \
  --no-cov -q

cd web && npx vitest run \
  'src/lib/api/sales-trainer.test.ts' \
  'src/lib/api/newcomer-training.test.ts' \
  'src/app/(dashboard)/sales-trainer/page.test.tsx' \
  'src/app/admin/sales-trainer/paths/page.test.tsx'
```

### Phase 1：安全权限与对象级授权

```bash
cd backend && pytest -c pyproject.toml \
  tests/unit/test_newcomer_training_path_permissions.py \
  tests/integration/test_newcomer_training_path_rbac_api.py \
  tests/integration/test_sales_trainer_api.py \
  --no-cov -q

cd web && npx vitest run \
  'src/app/admin/sales-trainer/training-records/page.test.tsx' \
  'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' \
  'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx'
```

### Phase 2：路径单一真源与配置治理

```bash
cd backend && pytest -c pyproject.toml \
  tests/unit/test_newcomer_training_path_config_bindings.py \
  tests/unit/test_newcomer_training_path_config_revision.py \
  tests/unit/test_sales_trainer_phase2_projection.py \
  tests/integration/test_newcomer_training_path_config_api.py \
  --no-cov -q

cd web && npx vitest run \
  'src/app/(dashboard)/sales-trainer/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/page-newcomer-scope.test.tsx' \
  'src/app/admin/sales-trainer/paths/page.test.tsx'
```

### Phase 3：内容资产、快照和死数据治理

```bash
cd backend && pytest -c pyproject.toml \
  tests/unit/test_newcomer_training_path_material_governance.py \
  tests/unit/test_newcomer_training_path_audio_lineage.py \
  tests/unit/test_newcomer_training_path_attempt_lineage.py \
  tests/unit/test_newcomer_training_path_record_lineage.py \
  --no-cov -q

cd web && npx vitest run \
  'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx' \
  'src/app/admin/sales-trainer/materials/page.test.tsx'
```

### Phase 4：TrainingJourney 聚合

```bash
cd backend && pytest -c pyproject.toml \
  tests/contract/test_sales_trainer_phase2_contract.py \
  tests/integration/test_sales_trainer_api.py \
  tests/integration/test_business_etiquette_ai_coach_progress_api.py \
  tests/integration/test_newcomer_training_path_paper_api.py \
  --no-cov -q

cd web && npx vitest run \
  'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx' \
  'src/app/admin/sales-trainer/page.test.tsx' \
  'src/app/admin/sales-trainer/training-records/page.test.tsx'
```

### Phase 5：AI Coach 必过闭环

```bash
cd backend && pytest -c pyproject.toml \
  tests/unit/test_sales_trainer_ai_coach.py \
  tests/unit/test_sales_trainer_ai_coach_chat.py \
  tests/unit/test_business_etiquette_ai_coach_progress_service.py \
  tests/integration/test_business_etiquette_ai_coach_progress_api.py \
  --no-cov -q

cd web && npx vitest run \
  'src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx' \
  'src/app/admin/sales-trainer/ai-coach/page.test.tsx'
```

### Phase 6：实时对练纳入新人训练闭环

```bash
cd backend && pytest -c pyproject.toml \
  tests/contract/test_sales_websocket_contract.py \
  tests/integration/test_sales_realtime_reconnect_flow.py \
  tests/integration/test_runtime_preflight_api.py \
  --no-cov -q

cd web && npx playwright test tests/e2e/sales-phase4.spec.ts --workers=1
```

新增新人训练入口绑定后，必须再加：

```bash
cd web && npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
```

### Phase 7：前后端契约和 UI/UX 收口

```bash
cd web && npx tsc --noEmit
cd web && npx vitest run \
  'src/lib/api/sales-trainer.test.ts' \
  'src/lib/api/newcomer-training.test.ts' \
  'src/app/(dashboard)/sales-trainer/**/*.test.tsx' \
  'src/app/admin/sales-trainer/**/*.test.tsx'
cd web && npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
```

## 4. 完整 Playwright E2E 设计

建议新增：`web/tests/e2e/newcomer-training-closed-loop.spec.ts`

### 目标

验证真实浏览器中新人训练闭环：

```text
登录
  -> learner 新人训练首页读取 active path revision
  -> 文章章节学习
  -> 章节完成后考试可用
  -> 考试提交并看到结果/AI 短答反馈
  -> AI Coach 可进入、可生成训练卡、可提交答案
  -> 录音作业上传并进入 scored/failed/processing 可解释状态
  -> 管理端看板看到记录、风险/弱项、训练记录详情
  -> 历史回放/结果页使用 snapshot-first 证据
  -> 权限不足与配置异常 fail-closed，有 trace/evidence
```

### 前置数据

优先通过后端 seed/API 准备，避免 UI 创建流程过长：

- 用户：
  - learner：`newcomer.e2e@qoder.ai`
  - content_admin：只管理内容，不看训练记录。
  - training_manager：可看同部门训练记录。
  - unauthorized learner 或跨部门 manager：用于权限不足断言。
- active path revision：
  - `path_key = new_seller`
  - 至少 4 个模块：
    - `business_skills_article_exam`：绑定 published learning content + paper。
    - `ai_coach`：enabled，绑定已发布 prompt/scoring prompt 或本地 fake provider。
    - `audio_scoring`：绑定 material + score prompt + pass threshold。
    - `realtime_roleplay`：Phase 6 前可断言 disabled/coming-soon；Phase 6 后绑定 runtime config。
- 学习内容：
  - published article，至少 2 个 chapter。
  - paper 至少包含 single choice + short answer。
- 录音：
  - 使用小型 fixture wav，或 mock/local provider 让评分可确定。
- 管理端：
  - 训练记录、manager dashboard、audio submission、quiz attempt 详情可查询。

### 主路径步骤与断言

1. 登录 learner。
   - 断言进入 dashboard，无 console error，无 4xx/5xx 阻塞请求。
2. 进入 `/sales-trainer`。
   - 断言标题“新人训练路径”。
   - 断言使用 path-first layout，不出现 legacy catalog-only 内容。
   - 断言显示当前阶段、下一步、可见内容、未开放/disabled 原因。
3. 进入商务技巧文章。
   - 断言章节列表来自 configured learning units。
   - 完成 required chapters。
   - 断言考试入口从 disabled 变为 enabled。
4. 进入商务技巧考试。
   - 提交选择题与短答。
   - 断言跳转 result。
   - 断言 pending 短答不被渲染成失败；评分完成后显示 AI scoring provenance/feedback。
5. 进入 AI Coach。
   - 断言配置 enabled。
   - 断言 session resume/create 成功。
   - 断言 stream 状态、训练卡、reasoning/assistant text 不串位。
   - 提交训练卡答案，断言 scored feedback 与下一步。
6. 进入录音作业。
   - 上传 fixture 音频。
   - 断言 result 页轮询到 terminal 状态。
   - 断言结果使用 frozen scoring snapshot，不暴露 storage key。
   - 对 timeout/processing 只断言可恢复状态，不伪装为成功。
7. 登录 training_manager/admin。
   - 进入 `/admin/sales-trainer`。
   - 断言 summary 记录数、pass rate、weak dimensions、risk learners 包含该 learner。
   - 进入 training records，断言 quiz/audio/ai_coach 记录可下钻。
   - 进入 record detail，断言 evidence、snapshot、regrade/remediation 信息完整。
8. 历史回放。
   - learner 进入历史或结果页。
   - 断言历史 attempt/submission 仍可查看 snapshot；若材料已归档，显示只读历史证据或明确不可用原因。

### 权限不足场景

- learner 直达 `/admin/sales-trainer`：
  - 断言 403/无权限页面，不出现管理数据。
- content_admin 直达训练记录/operation logs/settings：
  - 断言无权限或 capability fail-closed。
- 跨部门 training_manager 访问他人 submission/attempt：
  - API 返回 403；UI 显示权限不足，不吞成“无记录”。

### 配置异常场景

建议单独 describe，使用 API 临时发布坏配置或指向 fixture：

- 无 active path revision：
  - learner 首页显示配置诊断/不可用，不生成 legacy 新训练数据。
- article binding 缺失：
  - 文章/考试入口显示 remediation，不出现 fake success。
- AI Coach disabled 或坏 prompt：
  - AI Coach 页面显示 unavailable/typed error，不创建 session。
- audio scoring prompt/material 缺失：
  - 上传入口 disabled 或 preflight fail-closed，不允许提交后才失败。
- realtime module Phase 6 前 disabled：
  - 显示未开放原因；Phase 6 后若 runtime config 缺失，显示 terminal config error，不重连掩盖。

### 失败证据

沿用 `web/playwright.config.ts`：

- `trace.zip`：`retain-on-failure`
- screenshot：`only-on-failure`
- video：`retain-on-failure`
- HTML report：`.sisyphus/evidence/${SMOKE_EVIDENCE_PREFIX}-playwright-report`
- 额外建议：
  - 在 E2E 内写入 `.sisyphus/evidence/newcomer-training-run-manifest.jsonl`
  - 记录 `path_revision_id`、`learner_user_id`、`attempt_id`、`submission_id`、`ai_coach_session_id`、`trace_id`、失败 endpoint。

## 5. CI 门禁改造建议和风险

### 必改建议

1. 在 `scripts/critical-quality-gate.sh` 增加新人训练后端 gate target：

```bash
SALES_TRAINER_BACKEND_GATE_TARGETS=(
  "tests/contract/test_sales_trainer_phase2_contract.py"
  "tests/integration/test_newcomer_training_path_config_api.py"
  "tests/integration/test_newcomer_training_path_rbac_api.py"
  "tests/integration/test_newcomer_training_path_article_api.py"
  "tests/integration/test_newcomer_training_path_paper_api.py"
  "tests/integration/test_business_etiquette_ai_coach_progress_api.py"
  "tests/integration/test_sales_trainer_api.py"
  "tests/unit/test_newcomer_training_path_audio_lineage.py"
  "tests/unit/test_sales_trainer_ai_coach.py"
)
```

2. 在 `VITEST_GATE_TARGETS` 增加最小新人训练前端 gate target：

```bash
"src/lib/api/sales-trainer.test.ts"
"src/lib/api/newcomer-training.test.ts"
"src/app/(dashboard)/sales-trainer/page.test.tsx"
"src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx"
"src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx"
"src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx"
"src/app/(dashboard)/sales-trainer/audio/[unitId]/page.test.tsx"
"src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx"
"src/app/admin/sales-trainer/page.test.tsx"
"src/app/admin/sales-trainer/paths/page.test.tsx"
"src/app/admin/sales-trainer/training-records/page.test.tsx"
```

3. 新增 Playwright `newcomer-training-closed-loop.spec.ts` 后加入 release truth gate：

```bash
cd web
SMOKE_REUSE_EXISTING_STACK=1 \
SMOKE_EVIDENCE_PREFIX=task-newcomer-training \
npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
```

4. 保留真实 provider 测试为 nightly/release：

- PR gate 使用 local/fake provider，保证确定性。
- `backend/tests/integration/test_sales_trainer_real_providers.py`、真实 realtime provider 可放 nightly 或手动 release gate。
- CI 必须区分 provider unavailable skip、infra missing warning、业务失败 hard fail。

### 风险

- 运行时间风险：把所有 `sales_trainer` 测试直接塞进 critical gate 会拉长 PR 时间；建议先纳入上面的最小目标集，其余用 nightly。
- 数据准备风险：闭环 E2E 若依赖 UI 从零创建内容，容易慢且脆；应使用 seed/API 建立 deterministic fixture。
- 外部服务风险：AI Coach、ASR、realtime provider 不应在 PR gate 依赖真实外部服务；PR gate 走 fake/local provider，release/nightly 才跑真实 provider。
- 脆弱选择器风险：新人训练页面中文文案仍在演进，Playwright 应优先用 role/name + 稳定业务断言；必要时加 `data-testid`，但不要用 CSS 深层选择器。
- 权限误判风险：前端页面测试多为 mock API，不能证明后端对象级权限；权限边界必须以后端 integration/contract 为主，Playwright 只验证用户可见 fail-closed。
- CI 假绿风险：当前 release gate 不跑新人训练核心后端/前端目标，即使局部测试存在也不会阻止合并；这是 Phase 0 最大门禁缺口。

## 6. 本次未执行与限制

- 未运行全量后端/前端/Playwright 测试，符合“不要跑全量耗时测试、不要启动外部服务”的限制。
- 尝试后端 `pytest --collect-only` 时，本机 `python` 不存在，`python3` 指向无 pytest 的 Python 3.14；未安装依赖，改用源文件测试名扫描与配置读取作为覆盖事实。
- 未验证现有测试当前是否全部通过；本报告只描述覆盖事实、缺口和门禁计划。

## 7. 结论

新人训练局部单元、集成、前端页面测试基础较厚，但缺三类硬门禁：

1. 缺新人训练完整 Playwright E2E：没有真实浏览器覆盖 learner 首页、文章/考试、AI Coach、录音评分、管理看板、权限不足、配置异常、历史回放的同一闭环。
2. CI release truth gate 未纳入销售训练核心测试：`critical-quality-gate.sh` 当前后端/前端目标列表基本不包含 `sales_trainer/newcomer/business_etiquette`。
3. 新契约缺口未被 contract tests 固化：TrainingJourney、ModuleProgress、AI Coach session、realtime module binding、config health/dependency graph、snapshot-first 历史展示仍缺契约门禁。
