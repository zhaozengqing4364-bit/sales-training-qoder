# Phase 5 新人训练闭环测试矩阵与缺口清单

> 日期：2026-06-27
>
> 范围：只读代码、测试与 CI 设计；不改业务代码、不改测试代码。
>
> 输出目标：为下一阶段 `TrainingJourney + AI Coach + realtime + admin analytics + E2E` 提供可执行测试矩阵、当前缺口清单、CI 门禁建议和人工决策项。

## 2026-06-29 闭环复核附录

本文件保留 Phase 5 当时的测试矩阵建议。当前工作树已完成并验证以下当时未覆盖项：

- realtime 已通过 `POST /sales-trainer/realtime-roleplay/start`、`/ws/sales` deterministic local provider、TrainingJourney outcome、admin training record projection 纳入新人训练闭环；真实 StepFun provider gate 也已执行到上游，但因 StepFun HTTP 401 保持外部授权阻塞。
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts` 已进入 `scripts/critical-quality-gate.sh`，覆盖 learner 首页、商务技巧文章/考试、录音评分、AI Coach、realtime local provider、管理端 analytics/records、权限不足、配置异常、历史回放和移动端筛选。
- 最新证据：`.sisyphus/evidence/task-9-quality-gate.txt` 2026-06-29 06:12 `Critical quality gate passed`。

## 0. 结论先行

- 当前代码已经有不少局部测试锚点：`active path revision`、权限、AI Coach chat、训练记录投影、后台路径配置页、learner 首页、audio/quiz 结果页、admin training records。
- 当前代码还没有“新人训练闭环”级别的统一证明链。最缺的是：
  - `TrainingJourney` 聚合与状态机权威测试。
  - 从 learner 首页进入，到文章/考试/AI Coach/录音/实时对练/管理端记录的单条闭环 E2E。
  - realtime 纳入 `sales_trainer` 后的 binding / preflight / outcome projection 契约测试。
  - 三类等级进入 journey / dashboard / admin analytics 的统一 contract。
- 现有 release gate 明显偏通用 smoke、sales realtime、presentation realtime，不覆盖新人训练闭环主线。

## 1. 当前代码事实

### 1.1 已有测试锚点

- 后端：
  - 路径修订与真源：`backend/tests/unit/test_newcomer_training_path_config_revision.py`
  - 权限与 fail-closed：`backend/tests/unit/test_newcomer_training_path_permissions.py`、`backend/tests/integration/test_newcomer_training_path_rbac_api.py`
  - AI Coach：`backend/tests/unit/test_sales_trainer_ai_coach.py`、`backend/tests/unit/test_sales_trainer_ai_coach_chat.py`、`backend/tests/integration/test_business_etiquette_ai_coach_progress_api.py`
  - 训练记录投影：`backend/tests/unit/test_newcomer_training_path_record_lineage.py`、`backend/tests/unit/test_sales_trainer_phase2_projection.py`、`backend/tests/contract/test_sales_trainer_phase2_contract.py`
  - realtime 独立链路：`backend/tests/integration/test_sales_realtime_reconnect_flow.py`
- 前端：
  - learner 首页：`web/src/app/(dashboard)/sales-trainer/page.test.tsx`
  - AI Coach 页面：`web/src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx`
  - admin 路径配置：`web/src/app/admin/sales-trainer/paths/page.test.tsx`
  - admin training records：`web/src/app/admin/sales-trainer/training-records/page.test.tsx`
  - 通用 analytics：`web/src/app/admin/analytics/page.test.tsx`
- E2E：
  - 只有通用 smoke、sales realtime、presentation realtime。
  - 没有新人训练闭环专属 Playwright 规格。

### 1.2 代码层面的关键事实

- `SalesTrainerPathConfigService.active_projection()` 以 active revision 为 learner 路径权威；`get_config()` 仍保留 `legacy_migration_snapshot` 只读兼容。
- `sales_trainer.permissions` 已是本域权限权威，且测试已锁定 manager allowlist、ops/content_admin/admin 差异。
- `TrainingRecordService` 已能统一投影 audio / quiz / ai_coach 的 lineage 与 effective score，但还不是 `TrainingJourney` 聚合。
- `docs/api-contract/sales-trainer.md` 已把 realtime binding 写入契约方向，但代码与测试仍未形成“从 sales_trainer 入口进入 realtime 再回写 journey/dashboard”的证明链。
- `web/src/app/(dashboard)/sales-trainer/page.test.tsx` 已证明首页走 path-first、无 active path 时 fail-closed，但没有覆盖“阶段等级 + admin analytics + 历史回放 + realtime 接入”的完整旅程。

## 2. 要证明什么

### 2.1 P0 / P1 / P2 分级

| 级别 | 要证明的结论 | 审计问题映射 |
| --- | --- | --- |
| P0 | learner 入口只能消费 active path revision；无 active revision 不得制造伪成功 | `audit-synthesis.md` 中“单一真源”“废弃 catalog fallback” |
| P0 | realtime 进入闭环前必须经过 binding、provider readiness、权限、outcome projection、rollback 语义 | “realtime 纳入闭环前必须补契约/权限/配置/回滚” |
| P1 | 权限 fail-closed：content_admin 不能看训练记录；manager 仅部门范围；ops/admin 语义明确 | “权限与安全”所有条目 |
| P1 | 三类等级进入 DTO、状态机、筛选、admin analytics，而不是只存在文档 | “三类等级模型”“训练阶段等级” |
| P1 | AI Coach 是必过模块，缺 prompt/revision/config 时必须 typed failure | “AI Coach 首版必过”“高风险字段治理”“fail-open 风险” |
| P1 | 历史回放 snapshot-first：audio/material/paper/record 不受当前 active 资产漂移影响 | “内容资产与历史回放” |
| P1 | TrainingJourney 成为闭环聚合权威，前端不自行拼状态 | “TrainingJourney 聚合”“状态机集中管理” |
| P1 | 配置异常能诊断：missing / invalid / disabled / fallback / readiness not ready | “配置治理”“publish impact preview”“provider readiness” |
| P2 | learner 看板和 admin analytics 连续下钻可用，弱项、补救、趋势可解释 | “UI/UX 和可视化” |
| P2 | Playwright 覆盖关键旅程与失败恢复，不只覆盖 happy path | “完整 E2E 与 CI gate” |

### 2.2 闭环证明链

本阶段测试最终要形成下面这条证据链：

```text
active path revision
  -> learner 首页 path-first 投影
  -> 模块进入（文章/考试/AI Coach/录音/realtime）
  -> 结果冻结与状态机流转
  -> TrainingJourney 聚合
  -> training records / manager dashboard / admin analytics
  -> 历史回放 / 补救 / 重评 / 审计
```

任何一段没有测试权威，闭环都不成立。

## 3. 后端测试矩阵

### 3.1 Unit / Service 矩阵

| 模块 | 要证明什么 | 现有锚点 | 缺口 | 建议新增测试 |
| --- | --- | --- | --- | --- |
| active path revision 唯一真源 | `active_projection()` 是 learner 唯一真源；legacy 仅诊断只读 | `test_newcomer_training_path_config_revision.py` | 缺 `TrainingJourney` 侧对 active revision 缺失的 fail-closed | `test_sales_trainer_journey_source_of_truth.py`：无 active revision、active disabled、legacy snapshot only 三态 |
| 权限 fail-closed | 角色、部门、对象范围统一由权限层生效 | `test_newcomer_training_path_permissions.py` | 缺 journey/read-model 上的对象级权限单测 | `test_sales_trainer_journey_permissions.py`：learner/self、manager/department、content_admin/forbidden、ops/admin |
| 三类等级 | role / learner level / training stage 进入状态决策 | 无直接锚点 | 完全缺失 | `test_sales_trainer_journey_levels.py`：不同 learner level 可见模块、stage transition、admin filter payload |
| AI Coach 配置治理 | prompt/scoring prompt/revision 必须存在、发布、用途匹配 | `test_sales_trainer_ai_coach.py`、`test_sales_trainer_ai_coach_chat.py` | 缺 “必过模块 + journey outcome” 单测 | `test_sales_trainer_ai_coach_journey_outcome.py` |
| realtime binding 占位/真实接入 | placeholder 不能发布为真实模块；真实 binding 必须 preflight | 仅 path config 页面契约和 sales realtime 独立测试 | `sales_trainer` 侧完全缺失 | `test_sales_trainer_realtime_binding_validation.py` |
| 历史回放 | audio/material/paper 读取冻结快照 | `test_newcomer_training_path_record_lineage.py`、`test_newcomer_training_path_audio_lineage.py` | 缺 archived material 只读回放、prompt revision 冻结 | `test_sales_trainer_history_replay_snapshot.py` |
| 配置异常 | missing / invalid / disabled / fallback / readiness typed error | `test_newcomer_training_path_config_revision.py` | 缺 provider readiness 与 publish impact preview | `test_sales_trainer_config_health_readiness.py`、`test_sales_trainer_publish_preview.py` |
| journey 状态机 | 合法/非法/重复提交流转 | 无 | 完全缺失 | `test_sales_trainer_journey_state_machine.py` |

### 3.2 Integration / API 矩阵

| 链路 | 要证明什么 | 现有锚点 | 缺口 | 建议新增集成测试 |
| --- | --- | --- | --- | --- |
| learner `/paths` | 缺 active revision 时首页诊断明确，无 fallback 正式数据 | `test_newcomer_training_path_config_api.py`、首页前端测试间接覆盖 | 缺 “journey API + learner path API 一致性” | `test_newcomer_training_journey_api.py::test_should_fail_closed_without_active_revision` |
| 文章 -> 考试 | 章节完成、前置条件、考试提交、结果状态进入 journey | `test_newcomer_training_path_article_api.py`、`test_newcomer_training_path_paper_api.py`、`test_business_etiquette_quiz_api.py` | 缺跨 API 串联断言 | `test_newcomer_training_closed_loop_article_exam_api.py` |
| 录音评分 | 提交、转写、评分、结果、记录、journey 一致 | `test_sales_trainer_api.py`、`test_newcomer_training_path_audio_regrade_api.py` | 缺音频结果写回 journey / dashboard | `test_newcomer_training_closed_loop_audio_api.py` |
| AI Coach | start/send/submit/progress -> session status -> journey | `test_business_etiquette_ai_coach_progress_api.py` | 缺 progress 与 training records / analytics 的联动 | `test_newcomer_training_ai_coach_journey_api.py` |
| realtime placeholder | placeholder 模块不可进入 runtime | 无 | 完全缺失 | `test_newcomer_training_realtime_placeholder_api.py` |
| realtime 真实接入 | runtime binding 校验、创建前 preflight、outcome 写回 | sales realtime 独立测试存在 | `sales_trainer` 闭环接入缺失 | `test_newcomer_training_realtime_binding_api.py` |
| 历史回放 | archived material / old prompt revision / legacy_snapshot_only 返回稳定 | 通用 history/replay 测试，不是新人训练专属 | 缺闭环域专测 | `test_newcomer_training_history_replay_api.py` |
| admin analytics | dashboard / records / detail / remediation 用同一 journey/projection | `test_sales_trainer_phase2_contract.py` | 缺阶段等级、learner level、AI Coach/realtime 类型 | `test_newcomer_training_admin_analytics_api.py` |
| 配置异常 | path config / AI Coach / readiness 失败时返回 typed envelope | `test_newcomer_training_path_config_api.py` | 缺 dependency graph / readiness / publish preview | `test_newcomer_training_config_health_api.py` |

### 3.3 Contract 矩阵

| 契约 | 要锁定的字段/语义 | 现有锚点 | 缺口 |
| --- | --- | --- | --- |
| `TrainingJourney` | `journey_id`、`path_key`、`path_revision_id/no`、`learner_level`、`training_stage`、`module_progress[]`、`latest_recommendation`、`trace_id` | 无 | 必须新增 |
| `ModuleProgress` / `ModuleOutcome` | `module_key`、`module_type`、`status`、`effective_score`、`legacy_snapshot_only`、`history_replay_available` | 无 | 必须新增 |
| admin analytics | `role_level`、`learner_level`、`training_stage` 筛选与汇总字段 | 现有 phase2 contract 只覆盖 records/dashboard 基本字段 | 必须扩充 |
| AI Coach failure | terminal/transient/recoverable、`fallback_applied/reason`、prompt lineage | 局部 page/unit 测试 | 缺统一 contract |
| realtime binding | `runtime_binding`、`provider_readiness_snapshot`、`failure_policy`、`rollback_policy` | 文档有，测试无 | 必须新增 |
| 历史回放 | `legacy_snapshot_only`、`regrade_unavailable`、`material_snapshot`、`score_scheme_snapshot` | record lineage 局部覆盖 | 缺 API contract 锁定 |

### 3.4 后端优先命令

#### 本阶段必须进门禁

```bash
cd backend && pytest --no-cov \
  tests/unit/test_newcomer_training_path_config_revision.py \
  tests/unit/test_newcomer_training_path_permissions.py \
  tests/unit/test_sales_trainer_ai_coach.py \
  tests/unit/test_sales_trainer_ai_coach_chat.py \
  tests/unit/test_newcomer_training_path_record_lineage.py \
  tests/unit/test_sales_trainer_phase2_projection.py \
  tests/integration/test_newcomer_training_path_config_api.py \
  tests/integration/test_newcomer_training_path_rbac_api.py \
  tests/integration/test_business_etiquette_ai_coach_progress_api.py \
  tests/contract/test_sales_trainer_phase2_contract.py
```

#### 最终闭环门禁

```bash
cd backend && pytest \
  tests/unit/test_sales_trainer_journey*.py \
  tests/integration/test_newcomer_training_closed_loop_*.py \
  tests/integration/test_newcomer_training_realtime_*.py \
  tests/contract/test_newcomer_training_journey_contract.py \
  tests/contract/test_newcomer_training_admin_analytics_contract.py

cd backend && ruff check src/
cd backend && mypy src/
```

## 4. 前端测试矩阵

### 4.1 Unit / Presenter / API facade

| 页面/模块 | 要证明什么 | 现有锚点 | 缺口 | 建议新增测试 |
| --- | --- | --- | --- | --- |
| learner 首页 | 无 active path 时 fail-closed；path-first 展示；不暴露 legacy catalog | `page.test.tsx`、`page-newcomer-scope.test.tsx` | 缺 learner level / training stage / realtime ready 状态 | `page.test.tsx` 补三类等级与 realtime binding display cases |
| 文章/考试 | 阅读进度、exam 解锁、历史 attempt、异常态 | `business-skills/page.test.tsx`、`exam/page.test.tsx` | 缺 journey stage 与 admin remediation 跳转联动 | 新增 `journey presenter`/`next-step` 组合测试 |
| 录音评分 | pass threshold、结果三态、快照显示、失败恢复 | `audio/[unitId]/page.test.tsx`、`audio/result/[submissionId]/page.test.tsx` | 缺 history replay available / legacy snapshot only | 补结果页标记与回放入口测试 |
| AI Coach | stream、resume、recoverable error、disabled config | `business-skills/coach/page.test.tsx` | 缺必过模块完成后首页/看板联动 | 新增 `coach->journey summary` 适配测试 |
| realtime 模块卡片 | placeholder 与真实接入显示差异 | 首页已有 placeholder 断言 | 缺真实 binding + readiness 异常 | 新增 `module-path/learner-presenter` 测试 |
| admin training records | effective score、detail link、remediation | `training-records/page.test.tsx` | 缺 AI Coach / realtime / learner level / stage filter | 扩充记录列表 DTO 场景 |
| admin analytics | 总览图表与 manager-lite | `admin/analytics/page.test.tsx` | 不是新人训练专属；缺闭环 funnel/heatmap/risk queue | 新增 `admin/sales-trainer analytics` 页面测试 |
| permissions/capability | 五层 fail-closed：sidebar、card、module nav、button、直链页 | `module-nav.test.tsx` 等零散锚点 | 缺统一能力矩阵 | 新增 `sales-trainer capability projection` 组合测试 |

### 4.2 Component / Route 矩阵

| 路由 | 要证明什么 | 当前情况 | 设计建议 |
| --- | --- | --- | --- |
| `/sales-trainer` | 首页展示三类等级、阶段、下一步、未开放原因 | 已覆盖部分 path-first | 增加 stage chip、learner level badge、realtime ready/warn/disabled 三态 |
| `/sales-trainer/business-skills` | 章节、考试、AI Coach 串联 | 已有局部 | 增加“完成 AI Coach 后模块已通过/待补救”状态 |
| `/sales-trainer/audio/[unitId]` | 录音前置信息来自快照而非硬编码 | 已有 | 补 `legacy_snapshot_only` 和配置缺失态 |
| `/sales-trainer/audio/result/[submissionId]` | scored / processing / failed / replay available | 已有部分 | 补历史回放、管理员补救入口 |
| `/sales-trainer/business-skills/coach` | recoverable error 不弹窗，恢复动作明确 | 已有强覆盖 | 补 journey 同步提示、终止态 vs 暂时失败区分 |
| `/admin/sales-trainer/paths` | working revision、publish、rollback、diagnostics | 已有强覆盖 | 补 publish impact preview、realtime binding health |
| `/admin/sales-trainer/training-records` | 多 record type 列表一致 | 已有 quiz 为主 | 补 ai_coach_session、realtime_session、legacy records |
| `/admin/sales-trainer` 或新 analytics 页 | funnel、heatmap、risk queue、部门/等级对比 | 缺新人训练专页测试 | 新增页面与 presenter 测试 |

### 4.3 Playwright E2E 矩阵

| 场景 | 必测路径 | 目标 |
| --- | --- | --- |
| learner 首页 | 登录 -> `/sales-trainer` | active path 生效时展示路径；无 active path 时 fail-closed，不暴露旧 catalog |
| 文章/考试 | 首页 -> 商务技巧 -> 阅读章节 -> 进入考试 -> 提交 -> 结果页 | 证明文章/考试链路与状态推进 |
| 录音评分 | 首页 -> 音频模块 -> 上传音频 -> 结果页 -> 返回首页 | 证明 audio submission 与首页阶段状态联动 |
| AI Coach | 首页 -> 商务技巧 AI Coach -> 完成至少一轮互动 -> 返回首页 | 证明 AI Coach 进入闭环，不是孤立页 |
| realtime 占位 | 首页 realtime placeholder | disabled 原因明确，不能绕进 runtime |
| realtime 真实接入 | 首页 realtime module -> preflight -> 进入运行时 -> 完成/退出 -> 返回首页或记录页 | 证明 `sales_trainer` 到 runtime binding 的闭环 |
| admin analytics | admin 登录 -> 新人训练分析页 -> 筛选部门/等级/阶段 -> 下钻到记录详情 | 证明 analytics 连续下钻 |
| 权限不足 | content_admin / manager / learner 直链访问受限页面 | 五层 fail-closed，不吞成“无数据” |
| 配置异常 | path config 缺失、AI Coach 配置损坏、realtime readiness false | 明确 remediation，不伪成功 |
| 历史回放 | admin 或 learner 进入旧记录详情 -> 打开材料/结果回放 | archived 资产仍可只读回放或明确 `legacy_snapshot_only` |

### 4.4 前端优先命令

#### 本阶段必须进门禁

```bash
cd web && npx tsc --noEmit

cd web && npx vitest run \
  'src/app/(dashboard)/sales-trainer/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/business-skills/coach/page.test.tsx' \
  'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' \
  'src/app/admin/sales-trainer/paths/page.test.tsx' \
  'src/app/admin/sales-trainer/training-records/page.test.tsx'

cd web && npx eslint . --quiet
```

#### 最终闭环门禁

```bash
cd web && npx vitest run \
  'src/app/(dashboard)/sales-trainer/**/*.test.tsx' \
  'src/app/admin/sales-trainer/**/*.test.tsx' \
  'src/lib/sales-trainer/*.test.ts' \
  'src/lib/api/{sales-trainer,newcomer-training}.test.ts'

cd web && npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
```

## 5. CI Gate 建议

### 5.1 本阶段必须

把下面内容加入现有 `scripts/critical-quality-gate.sh` 或等价 workflow：

1. 后端最小闭环集合
   - `test_newcomer_training_path_config_revision.py`
   - `test_newcomer_training_path_permissions.py`
   - `test_sales_trainer_ai_coach.py`
   - `test_sales_trainer_ai_coach_chat.py`
   - `test_newcomer_training_path_record_lineage.py`
   - `test_sales_trainer_phase2_projection.py`
   - `test_newcomer_training_path_config_api.py`
   - `test_newcomer_training_path_rbac_api.py`
   - `test_business_etiquette_ai_coach_progress_api.py`
   - `test_sales_trainer_phase2_contract.py`
2. 前端最小闭环集合
   - learner 首页
   - AI Coach 页面
   - audio result 页
   - admin paths
   - admin training records
3. 类型与静态检查
   - `cd web && npx tsc --noEmit`
   - `cd web && npx eslint . --quiet`
   - `cd backend && ruff check src/`
4. 新增 Playwright newcomer smoke
   - 至少先覆盖：首页 -> 文章/考试 -> admin training records

### 5.2 最终门禁

1. 完整新人训练闭环 Playwright
   - `newcomer-training-closed-loop.spec.ts`
2. realtime 接入后新增两类门禁
   - placeholder fail-closed
   - real binding happy path + preflight fail path
3. 夜间 / release-only 门禁
   - 真实 provider 音频评分 smoke
   - 真实 realtime provider smoke
4. 契约门禁
   - `TrainingJourney` contract
   - admin analytics contract
   - history replay contract

### 5.3 不建议作为每次 PR 必跑

- 真实 provider 全量回归。
- 大规模性能测试。
- 需要真实凭证、真实语音时长、真实 WebSocket 外部依赖的完整链路。

这些更适合 nightly / release gate。

## 6. 当前缺口与推荐实现顺序

### 6.1 缺口清单

1. 没有 `TrainingJourney` 聚合权威测试。
2. 没有把三类等级写进 contract/test authority。
3. realtime 只在独立 sales runtime 有强测试，未覆盖 `sales_trainer` binding 闭环。
4. 没有新人训练闭环 Playwright。
5. admin analytics 没有新人训练专属 funnel / heatmap / risk queue 测试。
6. 历史回放缺“archived 资产仍可只读回放”的闭环证明。
7. 配置异常缺 provider readiness / impact preview / dependency graph 门禁。
8. 现有 release gate 没把 sales_trainer/newcomer 关键测试纳入硬门禁。

### 6.2 推荐实现顺序

1. 先补 contract：
   - `TrainingJourney`
   - `ModuleProgress/Outcome`
   - admin analytics 筛选字段
   - realtime binding / readiness
2. 再补后端 unit/integration：
   - journey state machine
   - journey source of truth
   - AI Coach outcome -> journey
   - history replay snapshot
3. 再补前端 Vitest：
   - learner 首页三类等级/阶段
   - admin training records 多 record type
   - admin analytics 闭环看板
4. 再补 Playwright：
   - 非 realtime 闭环
   - placeholder fail-closed
   - realtime 真接入闭环
5. 最后再收口 CI gate：
   - PR gate 最小闭环
   - nightly/release 真实 provider

## 7. 需要产品 / 外部系统 / 真实凭证人工决策的项

### 7.1 产品决策

- 学员等级首版枚举与来源：
  - 用户字段、组织字段、后台配置，还是规则计算。
- AI Coach “必过”定义：
  - 至少完成一次 session，还是要达到 `mastery_threshold`。
- realtime 模块完成标准：
  - 进入过 session 即算提交，还是要拿到 outcome/score。
- 历史回放对 learner 是否开放全部旧资产，还是仅 admin/ops 可看。

### 7.2 外部系统决策

- realtime provider readiness 的权威来源：
  - runtime config service、settings health，还是外部 provider 探活。
- AI Coach / 音频评分 prompt revision 的真实权威：
  - prompt template published head，还是固定 revision pin。

### 7.3 真实凭证与环境

- Playwright 新人训练闭环如果要覆盖真实录音/真实 realtime，需要：
  - 可用测试账号
  - backend + web 联通环境
  - provider 凭证
  - 可回收的测试数据种子
- 真实 provider smoke 应明确：
  - 是 nightly 还是 release only
  - 失败是否阻断发布

## 8. 建议的测试文件落点

### 后端建议新增

- `backend/tests/unit/test_sales_trainer_journey_source_of_truth.py`
- `backend/tests/unit/test_sales_trainer_journey_state_machine.py`
- `backend/tests/unit/test_sales_trainer_journey_permissions.py`
- `backend/tests/unit/test_sales_trainer_journey_levels.py`
- `backend/tests/unit/test_sales_trainer_realtime_binding_validation.py`
- `backend/tests/unit/test_sales_trainer_history_replay_snapshot.py`
- `backend/tests/integration/test_newcomer_training_closed_loop_article_exam_api.py`
- `backend/tests/integration/test_newcomer_training_closed_loop_audio_api.py`
- `backend/tests/integration/test_newcomer_training_ai_coach_journey_api.py`
- `backend/tests/integration/test_newcomer_training_realtime_binding_api.py`
- `backend/tests/integration/test_newcomer_training_history_replay_api.py`
- `backend/tests/contract/test_newcomer_training_journey_contract.py`
- `backend/tests/contract/test_newcomer_training_admin_analytics_contract.py`

### 前端建议新增

- `web/src/app/admin/sales-trainer/analytics/page.test.tsx`
- `web/src/lib/sales-trainer/journey-presenter.test.ts`
- `web/src/lib/sales-trainer/realtime-module-presenter.test.ts`
- `web/tests/e2e/newcomer-training-closed-loop.spec.ts`

## 9. 本次输出与阻塞

### 已完成

- 读完用户指定文档。
- 使用 CodeGraph 和现有测试文件核对 `active path revision`、权限、AI Coach、training record、frontend route、admin analytics、realtime 现状。
- 形成后端 / 前端 / E2E / CI 四层测试矩阵与缺口顺序。

### 未改动

- 未修改业务代码。
- 未修改现有测试代码。
- 未运行新增测试。

### 当前阻塞

- `TrainingJourney` 尚未成为现有代码中的明确权威对象，因此相关 contract/test 只能先设计落点，不能直接补齐实现。
- realtime 在 `sales_trainer` 的真实接入策略仍依赖后续 ADR、binding 设计和 provider readiness 权威来源。
- 新人训练 admin analytics 页面/DTO 是否独立于现有 `/admin/analytics` 仍需产品与实现层定版。
