# 测试、可观测性与 CI 治理严苛审计报告

- **审计日期**：2026-06-03
- **审计范围**：`/Users/zhaozengqing/github/销售训练qoder/`
- **审计对象**：后端 / 前端 / E2E 测试覆盖、可观测性（trace_id / log / metric / trace）、CI 工作流、死代码指标、缺失关键回归测试
- **审计基线**：`feat(sales-trainer): 落地销售训练 MVP 与配置资产中心` (3c14f5d5)
- **审计原则**：宪法原则 II（实时性）、IV（容错与恢复）、VII（可观测性：所有日志必须含 `trace_id`）；L0/L1/L2 文档；测试金字塔（unit → contract → integration → e2e）
- **审计人**：严苛架构师
- **方法**：只读检索 + 静态阅读；未运行任何服务；未运行任何测试；未修改任何代码或现有文档

---

## 严苛评级

| 严重度 | 描述 | 数量 |
|--------|------|------|
| **P0 - 阻断** | 观测性与 CI 治理失能：trace_id 覆盖率断崖、CI 主分支无单元/契约门禁、性能/契约门禁路径与生产实际不一致 | 4 |
| **P1 - 严苛** | 关键回归测试缺失；17 个 Prometheus 指标为死代码；CI 与生产负载差异巨大 | 6 |
| **P2 - 重要** | 前端核心文件 0 覆盖；契约测试与 API 文档不对齐；日志脱敏清单不闭环 | 5 |
| **P3 - 关注** | 工具链 / 文档同步 / 命名规范 | 4 |

> 现状：可观测性"看起来有，运行时没有"；测试套件"看起来全，关键路径未跑"；CI 三套工作流互不交叉，常规 PR 缺一道快速门禁。**这是治理失能，不是技术债**。

---

## 0. 数字速览（只读统计）

| 维度 | 数字 | 证据 |
|------|------|------|
| 后端 .py 文件（src） | 423 | `find backend/src -name "*.py" \| wc -l` |
| 后端 src LoC | 155 876 | `find backend/src -name "*.py" -exec cat {} \; \| wc -l` |
| 后端 .py 测试文件 | 338 | `find backend/tests -name "*.py" \| wc -l` |
| 后端测试 LoC | 100 782 | `find backend/tests -name "*.py" -exec cat {} \; \| wc -l` |
| 后端测试函数（`def test_*`） | 2 626 | grep 计数 |
| 后端 src LoC vs 测试 LoC | 1 : 0.65 | 155 876 vs 100 782（**接近 1:1 比例**） |
| 后端覆盖率（`coverage.json` 2026-02-12） | **48.66%**（8 638 / 17 752 statements） | `backend/coverage.json` |
| Backend `--cov-fail-under` 阈值 | **48** | `backend/pyproject.toml` |
| 前端 .ts(x) 文件（src） | 537 | `find web/src -name "*.ts*" \| wc -l` |
| 前端 src LoC | 130 088 | `find web/src -name "*.ts*" -exec cat {} \; \| wc -l` |
| 前端 .test.tsx | 107 | `find web -name "*.test.tsx" \| wc -l` |
| 前端 .test.ts | 59 | `find web -name "*.test.ts" \| wc -l` |
| 前端 Spec (Playwright E2E) | 4（3 个 `*.spec.ts` + `audit/audit.spec.ts`） | `find web/tests/e2e -name "*.spec.ts"` |
| 前端测试 LoC | 41 454 | `find web/src -name "*.test.*" -exec cat {} \; \| wc -l` |
| 前端测试函数 | 956 | grep 计数 |
| 前端覆盖率（`coverage-summary.json` 2026-05-18） | lines 56.66% / func 50.28% / branch 52.64% | `web/coverage/coverage-summary.json` |
| 前端 vitest 门槛 | lines 30 / func 30 / branch 25 / stmt 30 | `web/vitest.config.ts` |
| CI 工作流 | 3（nfr-performance / release-truth / roleplay-contract-eval） | `.github/workflows/` |
| 后端 `logger.*` 调用点 | **1 193** | grep |
| 后端文件用 `StructuredLogger`（自动注入 `trace_id`） | **149** | grep |
| 后端文件用 stdlib `logging.getLogger`（**不**自动注入） | **15**（共 116 个调用点） | grep |
| 实时 `trace_id` 注入关键字出现次数 | 6（仅 5 个文件） | grep |
| Prometheus 指标定义 | **21** | `common/monitoring/metrics.py` 全文 |
| Prometheus 指标生产调用（除 `MetricsMiddleware` 自动） | **4**（2 个文件） | grep |
| **Prometheus 死代码指标** | **17** | 见 §4.2 |
| OpenTelemetry 引用文件数 | **1**（`common/monitoring/otel.py`，且无业务代码使用 `tracer`/`span`） | grep |

---

## 1. 后端测试覆盖矩阵

### 1.1 测试规模与分布

```
backend/tests/
├── unit/         223 文件  (test_*.py 221)  — 单测（核心域）
├── integration/   76 文件  (test_*.py 76)   — 集成（HTTP+DB+中间件）
├── contract/      25 文件  (test_*.py 24)   — 契约（响应/状态/Schema）
├── performance/    6 文件                    — NFR（<300ms 延迟）
├── e2e/            3 文件  (test_*.py 2)     — 端到端
├── evaluation/     2 文件                    — 评分/触发器
├── fixtures/       7 文件  (含 JSON/脚本)   — 测试夹具
└── scripts/        1 文件  (run_nfr_tests.sh)
```

**Unit 子模块分布**（取 `find tests/unit/$d -name "test_*.py"`）：

| 子模块 | 数量 | 备注 |
|--------|------|------|
| `unit/`（根） | 150 | 多数为关键服务（stepfun_*、sales_trainer、examiner 等） |
| `unit/common` | 47 | 共享：cache、growth、recommendations、analytics、auth、knowledge、config |
| `unit/evaluation` | 9 | 评分触发器、报告服务 |
| `unit/prompt_templates` | 7 | 提示词系统 |
| `unit/admin` | 5 | 模型配置安全、PPT 上传、RAG profile |
| `unit/sales_bot/websocket` | 2 | WS 内部 |
| `unit/presentation_coach` | 1 | 唯一 PPT 单测 |

**Unit 体积 Top 10**（行数）：

```
5012  test_stepfun_realtime_handler.py
2457  contract/test_practice_evidence_contract.py
1696  integration/test_admin_users_api.py
1545  unit/test_replay_service.py
1369  unit/evaluation/test_comprehensive_report_service.py
1258  unit/test_sales_trainer_services.py      ← Agent 4 关键
1188  unit/test_session_evidence_service.py
1119  unit/common/test_admin_analytics_service.py
1113  integration/test_replay_api.py
1035  unit/test_presentation_handler_persistence.py
```

### 1.2 关键服务测试存在性

| 服务 | 测试文件 | 状态 | 严苛评估 |
|------|----------|------|----------|
| `agent/services/agent_service.py` (475 行) | `unit/test_agent_service.py` | **✅ 30 个 test function** | 充分 |
| `sales_trainer/services/*` (6 026 行) | `unit/test_sales_trainer_services.py` (1 258 行) | **⚠️ 19 个 test function** | 单文件覆盖整个服务域；服务有 18 个文件，命中率低 |
| `sales_trainer/services/paraformer_file_asr.py` | `unit/test_sales_trainer_paraformer_file_asr.py` | ✅ 专项 | 充分 |
| `sales_trainer/services/audio_submission_service.py` (1 036 行) | 唯一在 `test_sales_trainer_services.py` 与 `test_sales_trainer_api.py` 触及 | **⚠️ 无专项文件**，1 036 行只被 5 个 test 间接覆盖 | 缺专项 |
| `sales_trainer/services/material_service.py` (740 行) | 同上 | **⚠️ 0 专项** | 风险 |
| `sales_trainer/services/question_service.py` (495 行) | `integration/test_sales_trainer_api.py` 中 `test_sales_trainer_question_api_should_validate_business_question_shapes` | ⚠️ 仅 1 个集成测试 | 缺 |
| `sales_trainer/services/unit_service.py` (472 行) | `test_sales_trainer_services.py` | ⚠️ 间接 | 缺 |
| `sales_trainer/services/quiz_service.py` (403 行) | `test_sales_trainer_services.py` | ⚠️ 间接 | 缺 |
| `common/auth/service.py` (含 `JWT_SECRET` 默认值) | `unit/test_jwt_auth_security.py` / `integration/test_auth_login_api.py` | ✅ 集成测试 850 行 | 充分 |
| `common/ai/encryption.py` (Fernet) | `unit/admin/test_rag_profile_security.py`、`integration/test_admin_model_configs_api.py` | ✅ 4 + 2 个测试 | **但仅 RAG / OpenAI 域**，未见 StepFun 模型加密回归 |
| `common/websocket/base_handler.py` | `unit/test_websocket_handler.py`、`test_websocket_on_connect.py` | ✅ | 充分 |
| `common/monitoring/metrics.py` | 0 单元测试 | **❌ 无** | 17 个指标没人验证 |
| `common/monitoring/otel.py` | 0 单元测试 | **❌ 无** | 死代码 OTel 包装 |
| `common/monitoring/logger.py` | `unit/test_logger.py` 1 个 | ⚠️ 单测试 | 不足 |

### 1.3 集成测试 76 个分布（按主题）

| 主题 | 文件数 | 关键样本 |
|------|--------|----------|
| Admin 域 | ~16 | `test_admin_users_api.py` (1 696 行)、`test_admin_business_rules_api.py`、`test_admin_knowledge_answer_config_api.py` |
| Auth / Login | 1 | `test_auth_login_api.py` (850 行) |
| RBAC | 3 | `test_rbac_access_control_api.py`、`test_newcomer_training_path_rbac_api.py`、`test_prompt_templates_api_rbac.py` |
| Sales Trainer | 2 | `test_sales_trainer_api.py` (781 行, 11 tests)、`test_sales_trainer_real_providers.py` (78 行) |
| 实时链路 | 1 | `test_sales_realtime_reconnect_flow.py` |
| 知识库 | 4 | `test_knowledge_api.py`、`test_knowledge_upload_persistence.py`、`test_rag_profiles_api.py` |
| Presentation | 5 | `test_presentation_flow.py`、`test_presentation_thumbnail_api.py`、`test_presentation_delete_permissions.py`、`test_presentation_report_flow.py`、`test_admin_presentation_upload_api.py` |
| Curriculum | 5 | `test_curriculum_plan_snapshot_lineage.py`、`test_curriculum_analytics_api.py`、`test_curriculum_snapshot_immutability.py`、`test_curriculum_report_lineage_immutability.py`、`test_curriculum_certification_review_flow.py` |
| 可观测性 | 1 | `test_observability_surfaces.py`（验证 `/api/v1/analytics/*` + `/metrics` 端点） |
| 其他 | ~25 | websocket、score、retraining、agent、persona、test_bank、release_gate、starter_or_bootstrap_authority、highlights、learning、prompt、snapshot、support、voice_clone、staged_evaluation |

### 1.4 端到端 (E2E) 覆盖

| 文件 | 测试数 | 范围 |
|------|--------|------|
| `e2e/test_sales_training_learning_examiner_flow.py` | 4 | 销售训练学习→考试全链路（issue-77 seed manifest 验证） |
| `e2e/test_websocket_flow.py` | 2 | WebSocket 基础流 |
| **合计** | **6** | **极薄** |

E2E 集中在销售训练学习链路，**无课件演练 E2E、无 RBAC 端到端、无删除/合规流程 E2E**。

### 1.5 coverage.json 历史快照（2026-02-12）

| 维度 | 数值 |
|------|------|
| 覆盖行 / 总行 | 8 638 / 17 752 |
| 总体覆盖率 | **48.66%** |
| 0 覆盖文件数 | 3（`migrate_personas.py` migration、`evaluation/websocket/__init__.py`、`evaluation/websocket/broadcaster.py`） |
| < 30% 覆盖文件数 | 34 |

**关键问题**：
- 后端总体覆盖率 **48.66%** → 远低于宪章"能力完整"标准。
- `coverage.json` 时间戳 `2026-02-12T21:01:06`，距今 ≈ 4 个月未刷新。
- 34 个文件 < 30% 覆盖 → 多数为 admin API 模块（如 `admin.py` 26%）与 presentation 域。

### 1.6 P0 / P1 测试缺失（严苛指出）

| 缺失 | 关联 Agent 报告 | 严苛度 |
|------|------------------|--------|
| **销售训练 RBAC 端到端**（学员→admin 跨域角色继承） | Agent 6 / 04 | **P0**：宪法原则 VI 演练记录仅本人/管理员；当前仅单测、缺跨域集成 |
| **跨域继承 (Agent 1 F-01) 回归**（`PresentationStepFunRealtimeHandler` 继承 `StepFunRealtimeHandler`） | Agent 1 F-01 | **P0**：场景隔离原则破坏但无 E2E 防退化 |
| **WebSocket 鉴权失败 `close(4001)` 回归**（已发现 4001/4003/4410 测试，**但 4401 缺失**） | Agent 6 P1 | **P0**：4401 关闭码未覆盖 |
| **`STEPFUN_API_KEY` 加密字段读取**（`stepfun_realtime_handler.py:291` 直接 `os.getenv("STEPFUN_API_KEY", "")` 明文读取） | Agent 4 F-SEC-1 | **P0**：明文落内存 + 日志 + WS payload |
| **销售训练 audio_submission 删除（个保法合规）**（`/api/v1/admin/sales-trainer/audio-submissions` 全为 GET/POST retry，**无 DELETE 路由**） | Agent 4 个保法 | **P0**：用户无法行使"被遗忘权" |
| **JWT_SECRET 默认值兜底**（`'your-super-secret-key-change-in-production-min-32-chars'`） | Agent 6 | **P0**：测试中用真实密钥签 token，**有 CI 密钥泄露风险**；无针对默认密钥的拒绝启动测试 |
| **trace_id 注入回归**（`StructuredLogger` 与 stdlib `logging` 双轨） | 本次 §3 | **P0**：1 193 调用点只有 149 文件走 `StructuredLogger` |
| **17 个 Prometheus 指标死代码** | Agent 4 F-OBS-1 | **P1**：21 个指标定义，4 个有调用，其余 17 个永远 0 |
| **OTel 接入** | 本次 §4.3 | **P1**：1 个文件 0 业务 span |
| **日志脱敏闭环**（`api_key`/`secret`/`apikey` 缺 marker） | Agent 6 P1 | **P1**：`SENSITIVE_LOG_FIELD_MARKERS` 仅含 `token/password/cookie/email`，缺 `api_key/apikey/secret` |
| **SalesTrainerRealProviderConfig 真实跑** | integration 仅 78 行 | **P2**：`test_sales_trainer_real_providers.py` 极薄；只校验 config 存在性 |
| **`paper_api.py` / `article_api.py` 端点测试** | 仅 1 个 article test | **P2**：admin paper/article API 缺单测 |

---

## 2. 前端测试覆盖矩阵

### 2.1 测试规模

```
web/src/**/*.test.tsx  : 107 文件
web/src/**/*.test.ts   :  59 文件
web/tests/e2e/*.spec.ts:   4 文件
                            ──
                           166 个 vitest + 4 个 playwright
```

> 注：用户提示"164 个 .test.tsx"为 tsx 单数；实际 `.test.tsx + .test.ts = 166`，外加 4 个 `.spec.ts`。

### 2.2 测试函数与覆盖

- 956 个 vitest `it/test(...)` 块。
- 4 个 Playwright spec（`smoke.spec.ts`、`sales-phase4.spec.ts`、`presentation-phase4.spec.ts`、`audit/audit.spec.ts`）。
- `web/coverage/coverage-summary.json`（2026-05-18）总体：
  - **lines 56.66%**（2 845 / 5 021）
  - **functions 50.28%**（703 / 1 398）
  - **branches 52.64%**（2 917 / 5 541）

### 2.3 sales-trainer 前端测试（11 admin + 9 学员）

**Admin 域（15 个 page.test.tsx）**：

```
admin/sales-trainer/
├── settings/page.test.tsx
├── materials/page.test.tsx
├── score-results/page.test.tsx
├── papers/page.test.tsx
├── articles/page.test.tsx
├── paths/page.test.tsx
├── units/page.test.tsx
├── training-records/page.test.tsx
├── audio-submissions/page.test.tsx
├── score-standards/page.test.tsx
├── questions/page.test.tsx
├── papers/new/page.test.tsx
├── quiz-attempts/[attemptId]/page.test.tsx
├── questions/categories/page.test.tsx
└── papers/[paperId]/edit/page.test.tsx
```

**学员域（9 个 page.test.tsx）**：

```
(dashboard)/sales-trainer/
├── page.test.tsx
├── page-newcomer-scope.test.tsx
├── business-skills/page.test.tsx
├── quiz/[unitId]/page.test.tsx
├── quiz/result/[attemptId]/page.test.tsx
├── audio/[unitId]/page.test.tsx
├── business-skills/exam/page.test.tsx
├── learn/hub/page.test.tsx
└── audio/result/[submissionId]/page.test.tsx
```

**库/组件（7 + 7）**：

- `web/src/lib/sales-trainer/`: `operational-diagnostics.test.ts`、`module-path.test.ts`、`coo-learn-navigation.test.ts`、`draft-copy.test.ts`、`admin-display.test.ts`、`config-center.test.ts`、`learner-presenter.test.ts`
- `web/src/components/admin/sales-trainer/`: 7 个组件测试（unit-form / question-form / unit-form-model / module-template / score-prompt-form / unit-audio-config-sections / module-nav）

### 2.4 前端覆盖率死角（严重）

| 文件 | LoC | 覆盖率 | 严苛评估 |
|------|-----|--------|----------|
| `web/src/lib/api/client.ts` | **4 648** | **3.24%** | **灾难**。API 客户端（统一封装）是所有页面输入；3% 覆盖意味着一旦方法签名变更，无测试拦截 |
| `web/src/lib/api/client-domains.ts` | 147 | **8.16%** | 同上 |
| `web/src/lib/auth/current-user.ts` | 15 | **0%** | 用户态 |
| `web/src/lib/observability/trace-context.ts` | 35 | **0%** | 前端 trace 上下文生成（`sharedTraceId`） |
| `web/src/lib/performance.ts` | 116 | **18.10%** | 性能上报工具 |
| `web/src/lib/utils.ts` | 15 | **6.66%** | 通用工具 |
| `web/src/components/ui/glass-card.tsx` | 1 | 0% branch | 设计系统 |
| `web/src/components/ui/glass-modal.tsx` | 58 | **36.20%** | 模态 |
| `web/src/app/admin/settings/page.tsx` | 351 | **41.59%** | 管理设置 |
| `web/src/lib/admin/read-models.ts` | 72 | **20.83%** | admin 读取模型 |
| `web/src/lib/admin/runtime-faults.ts` | 15 | **33.33%** | 运行时故障 |
| `web/src/components/audio/AudioAuditCard.tsx` | 72 | **56.94%** | 音频审计 |
| `web/src/components/ui/confirm-dialog.tsx` | 6 | 33.33% functions | 确认对话框 |

> **P1**：`client.ts` 4 648 行 / 3.24% 覆盖是治理事故。所有页面测试都走 mock，无法证明 API 客户端的契约稳定。

### 2.5 Playwright E2E 现状

| Spec | describe 名称 | 评估 |
|------|---------------|------|
| `smoke.spec.ts` | "full-stack smoke baseline" | 基线烟雾，3 个 test block |
| `sales-phase4.spec.ts` | "Issue #43 Phase 4 Sales real WebSocket E2E" | 销售对练 4 期 |
| `presentation-phase4.spec.ts` | "Issue #44 Phase 4 Presentation real WebSocket E2E" | PPT 演练 4 期 |
| `audit/audit.spec.ts` | （审计脚本） | 独立目录 |

**E2E 仅覆盖两个 4 期场景，缺：**
- 登录 / 鉴权 / 角色切换
- 销售训练学员端 → 后台评分全链路
- 错误降级（KB 锁、模型不可用、TTS 降级、WS 断线）
- 主题/多端响应式

---

## 3. 可观测性矩阵

### 3.1 trace_id 覆盖率（**P0 失能**）

| 指标 | 数字 | 评估 |
|------|------|------|
| `logger.*` 总调用点 | **1 193** | - |
| 文件使用 `StructuredLogger`（自动注入） | **149**（约 90% 文件） | 良好 |
| 文件使用 stdlib `logging.getLogger`（**不**自动注入） | **15**（共 116 调用） | **9.7% 调用点失守** |
| 显式 `get_trace_id()` / `set_trace_id()` 调用文件 | ~5（只在 `curriculum_practice/api.py` + stepfun_* + http_routes.py） | 仅 4 文件主动使用 trace_id 上下文 |

**`logger = logging.getLogger` 的 15 个文件**（116 调用点，**全部在生产关键路径**）：

```
backend/src/sales_bot/services/context_manager.py          (11 calls)
backend/src/sales_bot/services/bot_service.py               (10 calls)
backend/src/sales_bot/services/vagueness_detector.py        ( 2 calls)
backend/src/sales_bot/services/summary_service.py           ( 3 calls)
backend/src/common/cache/response_cache.py                  ( 5 calls)
backend/src/common/ppt/version_manager.py                   ( 8 calls)
backend/src/common/ppt/ocr_processor.py                     ( 6 calls)
backend/src/common/jobs/audio_archival.py                   (18 calls)  ← Agent 6 提到的音频生命周期
backend/src/common/monitoring/metrics.py                    ( 2 calls)
backend/src/common/analytics/release_verification_service.py(12 calls)
backend/src/common/analytics/leaderboard_service.py         ( 7 calls)
backend/src/common/analytics/runtime_metrics_service.py     ( 8 calls)
backend/src/common/analytics/admin_analytics_service.py     (11 calls)
backend/src/common/analytics/analytics_service.py           ( 8 calls)
backend/src/presentation_coach/services/point_extraction.py ( 5 calls)
```

**严苛结论**：
- 任何依赖 stdlib `logger.warning/info/error` 的调用，**将不会**自动注入 `trace_id`。
- `audio_archival.py` 是 **Agent 4/6 关心的音频生命周期**（GDPR / 个保法重点），恰恰是 stdlib 写法。
- 4 个 `analytics_service*` 文件是 Prometheus / 业务可观测性来源，没有 trace_id 关联 → 排障无法跨日志/指标/链路。

### 3.2 Prometheus 矩阵（**P0 失能 - 17 死指标**）

`common/monitoring/metrics.py` 定义 **21** 个 metric 对象：

| Metric | 类型 | 生产调用 | 状态 |
|--------|------|----------|------|
| `http_requests_total` | Counter | `MetricsMiddleware`（`app_factory.py:137`） | ✅ |
| `http_request_duration_seconds` | Histogram | `MetricsMiddleware` | ✅ |
| `application_info` | Info | `initialize_metrics` 在 `app_factory.py` | ✅（隐式） |
| `situation_pack_dual_read_mismatch` | Counter | `track_situation_pack_dual_read_mismatch()` × 1（`dual_read_observability.py:62`） | ✅ |
| `frontend_analytics_events_total` | Counter | `track_frontend_analytics_event()` × 3（`common/api/analytics.py`） | ✅ |
| **`websocket_connections_active`** | Gauge | 0 | **❌ DEAD** |
| **`websocket_messages_total`** | Counter | 0 | **❌ DEAD** |
| **`websocket_message_duration_seconds`** | Histogram | 0 | **❌ DEAD** |
| **`practice_sessions_total`** | Counter | 0 | **❌ DEAD** |
| **`practice_session_duration_seconds`** | Histogram | 0 | **❌ DEAD** |
| **`practice_scores`** | Histogram | 0 | **❌ DEAD** |
| **`llm_requests_total`** | Counter | 0 | **❌ DEAD** |
| **`llm_request_duration_seconds`** | Histogram | 0 | **❌ DEAD** |
| **`llm_tokens_total`** | Counter | 0 | **❌ DEAD** |
| **`asr_requests_total`** | Counter | 0 | **❌ DEAD** |
| **`asr_request_duration_seconds`** | Histogram | 0 | **❌ DEAD** |
| **`tts_requests_total`** | Counter | 0 | **❌ DEAD** |
| **`tts_request_duration_seconds`** | Histogram | 0 | **❌ DEAD** |
| **`voice_policy_rollbacks_total`** | Counter | 0 | **❌ DEAD** |
| **`voice_policy_state_changes_total`** | Counter | 0 | **❌ DEAD** |
| **`errors_total`** | Counter | 0 | **❌ DEAD** |

**说明**：
- `track_*` 函数（10 个）全部定义在 `metrics.py`，**生产代码零调用**。
- 17 个 DEAD 指标持续消耗 `prometheus_client` 内存 + 暴露为 `/metrics`（外部看到但永远是 0）。
- 唯一被调用的是 `MetricsMiddleware`（HTTP）、`track_frontend_analytics_event`、`track_situation_pack_dual_read_mismatch`。
- Agent 4 `F-OBS-1` "13 个指标 0 调用"为低估；实测 **21 个中 17 个死**。

**与 F-OBS-1 串证**（来自 `04-audio-and-ai-capabilities.md`）：
> F-OBS-1 | `track_asr_request` / `track_tts_request` / `track_llm_request` 13 个 Prometheus 指标全代码库 0 调用 | common/monitoring/metrics.py:201-222

### 3.3 OpenTelemetry 接入

| 项 | 数字 | 状态 |
|----|------|------|
| `opentelemetry` 引用文件 | 1（`common/monitoring/otel.py`） | **孤立** |
| `from opentelemetry` 导入 | 0（除 `otel.py` 内部） | **未注入** |
| 业务代码 `tracer`/`span` 使用 | 0 | **未应用** |
| OTel SDK 是否注册 | `OTEL_ENABLED=1/true` 才启用 | 默认关闭 |

**`otel.py` 行为**：尝试 lazy import + `BatchSpanProcessor` + `FastAPIInstrumentor.instrument_app(app)`，**仅当 `OTEL_ENABLED=true` 时**才执行；任何导入失败都降级为 warning，不抛错。

> **严苛结论**：OTel 是"代码里有、包装好、运行时不工作"。**生产** trace 链路无 OTLP export。`/metrics` 也没有 trace → metrics bridge。

### 3.4 日志脱敏（与 Agent 6 P1 串证）

`common/monitoring/logger.py` 的 `SENSITIVE_LOG_FIELD_MARKERS`：

```python
SENSITIVE_LOG_FIELD_MARKERS = ("token", "password", "cookie", "email")
```

**问题**（与 Agent 6 P1 一致）：
- `api_key`、`apikey`、`secret`、`authorization`、JWT `Bearer` 头均**不在 marker 中**。
- `log_safety_inventory.py` 仅 6 个 `SensitiveLogSurface` 条目，**未覆盖**：
  - `common.audio.asr_alibaba.asr_with_fallback`（阿里云 ASR Key）
  - `common.audio.tts_factory`（DashScope Key）
  - `training_runtime.stepfun_transport`（StepFun `STEPFUN_API_KEY`）
  - `sales_trainer.services.deucate_scoring_service`（`DEUCATE_API_KEY`）
  - `common.ai.config_manager`（`MODEL_CONFIG_ENCRYPTION_KEY` 在 Fernet 失败日志中）
  - `admin.api.model_configs`（admin 配置接口）
  - WebSocket payload（`stepfun_realtime_handler.py:860` 的 `"未配置 STEPFUN_API_KEY"` 错误体）

### 3.5 可观测性矩阵总结

| 维度 | 工具 | 启用 | 严苛度 |
|------|------|------|--------|
| 结构化日志 | structlog + JSONRenderer | ✅ | 优 |
| **trace_id 自动注入** | `StructuredLogger` 注入 + `ContextVar` | **🟡 部分** | **P0**：stdlib logger 失守 |
| HTTP 指标 | `MetricsMiddleware` | ✅ | 优 |
| WebSocket 指标 | 5 个定义 | **❌ 0 调用** | **P0** |
| ASR/TTS/LLM 指标 | 8 个定义 | **❌ 0 调用** | **P0** |
| 业务会话/分数指标 | 3 个定义 | **❌ 0 调用** | **P0** |
| 错误计数 | `errors_total` | **❌ 0 调用** | **P0** |
| Frontend analytics | `frontend_analytics_events_total` | ✅ | 良 |
| Situation pack 观测 | `situation_pack_dual_read_mismatch` | ✅ | 良 |
| OpenTelemetry | `otel.py` 包装 | **❌ 默认关闭 + 0 span** | **P0** |
| 日志脱敏 | `sanitize_log_kwargs` + 4 marker | **🟡 不闭环** | **P1** |
| `prometheus.yml` | `/prometheus.yml` 静态配置 + 后端 `/metrics` 端点 | ✅ 静态存在 | 缺 Grafana 仪表盘 / 告警规则 |
| Grafana 仪表盘 | 仓库**无**任何 `*.json` 仪表盘文件 | **❌** | **P1** |
| 告警规则 | 仓库**无** `alerts.yml` | **❌** | **P1** |

---

## 4. CI 流水线现状

### 4.1 三套工作流

```
.github/workflows/
├── nfr-performance-check.yml      (9471 B, 4 jobs: NFR 性能 + 50 并发负载)
├── release-truth-gate.yml        (2860 B, 1 job: 完整 critical-quality-gate.sh)
└── roleplay-contract-eval.yml    (3250 B, 1 job: 角色扮演契约)
```

### 4.2 触发矩阵

| 工作流 | push (main) | push (001-ai) | PR (main) | PR (001-ai) | schedule | dispatch | paths filter |
|--------|-------------|---------------|-----------|-------------|----------|----------|--------------|
| nfr-performance | ✅ | ✅ | ✅ | ✅ | - | ✅ | 无 |
| release-truth | ✅ | ✅ | ✅ | ✅ | - | ✅ | 无 |
| roleplay-contract | ✅ | ✅ | ✅ | ✅ | 17:19 UTC 每日 | ✅ | **有**（限定 roleplay/sales_bot/voice_runtime 等域） |

### 4.3 工作流实际跑什么

#### nfr-performance-check.yml

```yaml
jobs:
  nfr-performance-validation:
    steps:
      - pytest tests/performance/test_nfr_metrics.py --no-cov --junitxml
      - 生成 NFR JSON 报告
      - 检查 failed_metrics == 0，sys.exit(1)
  load-testing:
    needs: nfr-performance-validation
    env: LOAD_TEST_USERS: 50, LOAD_TEST_DURATION: 60
    steps:
      - pytest tests/performance/ -k "concurrent"  # 跑 "concurrent" 关键字的所有测试
```

**问题**：
- **NFR 实际只跑 `test_nfr_metrics.py` 一个文件**（869 行）；6 个性能测试文件中 5 个被忽略。
- **50 并发负载是** `LOAD_TEST_USERS=50` 注入环境变量，但 `tests/performance/test_e2e_latency.py:167` 写死 `Test 10 concurrent session creations`、`test_vagueness_detection.py:115` 写死 `Test 5 concurrent conversations`、`test_nfr_metrics.py:699` 写死 `Run 10 concurrent requests`。
- **`-k concurrent` 过滤 5 个文件**：`test_e2e_latency.py`、`test_vagueness_detection.py`、`test_nfr_metrics.py`（均只跑 5-10 并发），另外 `test_interruption_latency.py`、`test_examiner_runtime_performance.py`、`test_curriculum_analytics_performance.py` **无 `concurrent` 关键字** 全部被跳。
- **NFR 5 套指标跳过分级**：`NFR_PROVIDER_UNAVAILABLE` / `NFR_INFRA_MISSING` / `NFR_EXTERNAL_UNAVAILABLE` 自动 skip → **CI 通过但真实指标未验证**。

#### release-truth-gate.yml

```yaml
steps:
  - Secret hygiene scan           # scripts/check_secret_hygiene.py
  - Critical full-stack quality gate   # bash scripts/critical-quality-gate.sh
```

`critical-quality-gate.sh` 实际跑：

```bash
1. npx tsc --noEmit                         (web typecheck)
2. npx vitest run --coverage 17 个文件       (VITEST_GATE_TARGETS)
3. npx playwright test tests/e2e/smoke.spec.ts
4. npx playwright test tests/e2e/presentation-phase4.spec.ts
5. npx playwright test tests/e2e/sales-phase4.spec.ts
6. pytest 12 个后端文件 (BACKEND_GATE_TARGETS) --no-cov -q
7. pytest 4 个后端文件 (BACKEND_SMOKE_REGRESSION_TARGETS) --no-cov -q
```

**问题**：
- **`pytest --cov=src --cov-report=html --cov-fail-under=48`** 全部被 `--no-cov` 关闭，**没有覆盖率门禁**（仅在 `pyproject.toml` 默认运行）。
- **Vitest 仅跑 17 个 target**，**非全量 166 文件**。
- **后端仅跑 12 + 4 = 16 个文件**（非全量 338）；其中包括 4 个 smoke regression。**238 个 unit 测试在 release gate 之外**。
- **`scripts/critical-quality-gate.sh` 启动** Docker + Redis + Postgres + Playwright browser install，**单 job 45 分钟 timeout**。

#### roleplay-contract-eval.yml

```yaml
steps:
  - python backend/scripts/run_roleplay_contract_eval.py \
    --output-json ... --output-junit ... --enable-llm-grader
```

**问题**：
- **依赖 LLM grader**：`--enable-llm-grader` 真实 LLM 评判 → 不可重复、不可审计、CI 费用高。
- **paths filter 限定 14 个文件**，意味着修改其他文件（admin/api、common/ai、sales_trainer）**不触发**。
- **schedule 17:19 UTC** 单次/日 → 不替代常规回归。

### 4.4 **P0 缺失：常规 PR 门禁**

| 期望门禁 | 实际状态 | 严苛度 |
|----------|----------|--------|
| **PR 触发 `ruff check`** | ❌ 无 | **P0** |
| **PR 触发 `ruff format --check`** | ❌ 无 | **P0** |
| **PR 触发 `mypy src`** | ❌ 无 | **P0** |
| **PR 触发 backend 单元测试** | ❌ 无（仅 release gate 跑 16 个文件） | **P0** |
| **PR 触发 contract 测试** | ❌ 无 | **P0** |
| **PR 触发前端 lint** | ❌ 无 | **P0** |
| **PR 触发前端 typecheck** | 仅在 release-truth-gate 跑（且要求服务启动） | **P1** |
| **PR 触发覆盖率门禁** | ❌ 无（`--no-cov` 一票否决） | **P0** |
| **PR 触发 secret hygiene** | ✅（仅 release） | P2 |
| **PR 触发 lighthouse / a11y** | ❌ 无 | P2 |
| **PR 触发 50 并发 / 200 并发负载** | ❌ 错位（实际 5-10） | P1 |

### 4.5 **P0/P1 性能数字错位**

| 维度 | CLAUDE.md / 文档宣称 | 实际代码 | 实际 CI |
|------|---------------------|----------|---------|
| 性能目标 | "<300ms 端到端" | ✅ `test_nfr_metrics.py` 测 P95 < 300ms | ✅ |
| 并发负载 | "50 并发"（nfr workflow 默认） | `test_e2e_latency.py:167` 写死 **10** 并发 | **错位** |
| 学员负载 | "200 并发" | 无 200 测试 | 无 200 CI |
| 负载用户 | 50 | 50（env）→ 实际跑 `concurrent` 关键字 → 5-10 | **错位** |

---

## 5. 死代码 / 死指标清单

### 5.1 Prometheus 死指标（17 个）

| 指标 | 定义位置 | 严重度 |
|------|----------|--------|
| `websocket_connections_active` | `metrics.py:36-38` | P0（核心实时链路） |
| `websocket_messages_total` | `metrics.py:40-44` | P0 |
| `websocket_message_duration_seconds` | `metrics.py:46-50` | P0 |
| `practice_sessions_total` | `metrics.py:53-55` | P0 |
| `practice_session_duration_seconds` | `metrics.py:57-62` | P0 |
| `practice_scores` | `metrics.py:64-69` | P0 |
| `llm_requests_total` | `metrics.py:72-74` | P0 |
| `llm_request_duration_seconds` | `metrics.py:76-81` | P0 |
| `llm_tokens_total` | `metrics.py:83-85` | P0 |
| `asr_requests_total` | `metrics.py:87` | P0 |
| `asr_request_duration_seconds` | `metrics.py:89-93` | P0 |
| `tts_requests_total` | `metrics.py:95` | P0 |
| `tts_request_duration_seconds` | `metrics.py:97-102` | P0 |
| `voice_policy_rollbacks_total` | `metrics.py:105-109` | P0 |
| `voice_policy_state_changes_total` | `metrics.py:111-115` | P0 |
| `errors_total` | `metrics.py:118` | P0 |
| `application_info` | `metrics.py:133` | P2（Info 类型，初始化后无业务更新） |

### 5.2 死函数 / 死路径

| 项 | 位置 | 说明 |
|----|------|------|
| `track_practice_session` | `metrics.py:180-198` | 0 调用 |
| `track_llm_request` | `metrics.py:201-210` | 0 调用 |
| `track_asr_request` | `metrics.py:213-216` | 0 调用 |
| `track_tts_request` | `metrics.py:219-222` | 0 调用 |
| `track_websocket_connection` | `metrics.py:225-227` | 0 调用 |
| `track_websocket_message` | `metrics.py:230-240` | 0 调用 |
| `track_error` | `metrics.py:243-245` | 0 调用 |
| `track_voice_policy_rollback` | `metrics.py:263-280` | 0 调用 |
| `track_voice_policy_state_change` | `metrics.py:283-300` | 0 调用 |
| `initialize_otel` | `otel.py:42-96` | 默认 `OTEL_ENABLED=false`，无业务 span 注入 |

### 5.3 死 / 薄弱日志调用点（stdlib 写法）

15 文件 116 调用（见 §3.1 列表）。建议：所有 `logger = logging.getLogger(__name__)` 改为 `logger = get_logger(__name__)`，让 `StructuredLogger` 自动注入 `trace_id`。

### 5.4 死路由 / 死接口

| 模块 | 路径 | 状态 |
|------|------|------|
| Release Verification | `/api/v1/admin/release-verification/*` 9 端点 | **0 前端调用**（`api-audit-anomaly-report.md §1.1` 已记） |
| Runtime Metrics | `/api/v1/admin/analytics/runtime-metrics` 等 4 端点 | **0 前端调用**（§1.2） |
| Training Tasks | `/api/v1/training-tasks/{id}/{complete,cancel,expire}` | **0 前端调用**（§1.3） |
| 学员画像 | 2 端点 | 0 调用（§1.4） |
| 成长中心 | 2 端点 | 0 调用（§1.5） |
| Sales Trainer DELETE | `/api/v1/admin/sales-trainer/audio-submissions/{id}` | **路由不存在**（P0 个保法） |
| Sales Trainer DELETE | `/api/v1/admin/sales-trainer/units/{id}` | 路由不存在（用 archive POST 代替） |
| Sales Trainer DELETE | `/api/v1/admin/sales-trainer/materials/{id}` | 路由不存在（用 archive POST 代替） |

---

## 6. 契约测试 ↔ API 文档对齐矩阵

### 6.1 数字对比

```
Contract 测试 (24 个文件, 200+ test cases)
API 文档         (18 份 .md)
交集            : 2 (analytics, sessions)
仅测试无文档     : 22
仅文档无测试     : 14
```

| 类别 | Contract 测试 | API 文档 | 重合度 |
|------|---------------|----------|--------|
| Sales Trainer | **0** | `sales-trainer.md` (1 146 行) | **0** |
| Voice Runtime | **0** | `voice-runtime.md` | **0** |
| Agents | **0** | `agents.md` | **0** |
| Replay | **0** | `replay.md` | **0** |
| Prompt Templates | **0** | `prompt-templates.md` | **0** |
| Model Configs | **0** | `model-configs.md` | **0** |
| Knowledge | **0** | `knowledge.md` | **0** |
| Effectiveness | **0** | `effectiveness.md` | **0** |
| Analytics | `test_analytics.py` (19 tests) | `analytics.md` | ✅ |
| Sessions | `test_sessions.py` (16 tests) | `sessions.md` | ✅ |

**最大缺失**：销售训练（11 个 admin 子页面、3 个 learner 子页面、6 个 service 文件）**没有任何 contract 测试**——意味着 1 146 行的 `sales-trainer.md` **契约只活在文档里，不在 CI 里**。

### 6.2 api-audit-anomaly-report.md 摘要

`docs/api-contract/api-audit-anomaly-report.md`（358 行，2026-05-18）记录：

1. **后端定义但前端未调用**：22 类（共 50+ 端点）
   - Release Verification 9 端点（最低优先级）
   - Runtime Metrics 4 端点
   - Training Tasks 终态 3 端点（高优先级）
   - 学员画像 2 端点
   - 成长中心 2 端点
   - 配置验证与审计 2 端点
   - 练习会话诊断与报告 3 端点
2. **前端定义了方法但无页面调用**：30+ 个 API 域
3. **前后端重复实现**：知识库别名 18 个、音频分段 3 个、adminPresentations 13 个
4. **前端绕过 API Client 的直接调用**：已修复项
5. **HTTP 方法不一致**：已修复项

> 严苛结论：API 文档与契约测试**结构性不对齐**是治理失能。任何"按合同做"的工作流都会失败。

### 6.3 Contract 测试 function 数（按文件 Top 10）

| 文件 | test functions |
|------|----------------|
| `test_practice_evidence_contract.py` | 33 |
| `test_analytics.py` | 19 |
| `test_sessions.py` | 16 |
| `test_admin_governance_contract.py` | 10 |
| `test_release_verification_contract.py` | 8 |
| `test_conclusion_evidence_parity.py` | 8 |
| `test_audio_audit_contract.py` | 7 |
| `test_thinking_visibility_contract.py` | 6 |
| `test_presentations.py` | 6 |
| `test_ppt_upload.py` | 6 |

---

## 7. Fixture / Seed / 数据治理

### 7.1 测试夹具

```
backend/tests/fixtures/
├── __init__.py
├── config_asset_export_v1_example.json       — 配置资产导出样例
├── examiner_final_gate.py                    — 考试终态门夹具
├── knowledge_answer_eval_cases.json          — 知识可答性评测
└── roleplay_contract_eval_cases.json         — 角色扮演契约评测
```

`backend/tests/e2e/fixtures/`:

```
├── presentation-phase4-corrupted.v1.pptx     (52 字节 - corrupted)
├── presentation-phase4-normal.v1.pptx        (29 382 字节)
├── presentation-provider-script.v1.json
└── sales-provider-script.v1.json
```

### 7.2 种子脚本（生产域）

```
backend/scripts/seed_*.py  (10 个)
├── seed_presales_mvp.py
├── seed_presales_cio_first_visit.py
├── seed_newcomer_training_path.py            — 已被 e2e/test_sales_training_learning_examiner_flow 引用
├── seed_sales_trainer_goal_path_demo.py
├── seed_coo_questions.py
├── seed_sales_trainer_three_modules.py
├── seed_knowledge_answer_config.py
└── seed_coo_path_extension.py
```

> 严苛结论：10 个 seed 脚本，但**没有任何 seed 自动化冒烟测试**（`tests/scripts/run_nfr_tests.sh` 仅 1 个文件，且不跑 seed）。CI 启动后端若没有 seed，业务流就空跑。

### 7.3 数据库 / Redis fixture

`backend/tests/conftest.py`：

```python
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
# 强制使用 SQLite 内存
# 实际生产用 PostgreSQL（asyncio + asyncpg）
```

**严重问题**：
- 单测在 SQLite 上跑，**集成测试却用 PostgreSQL**（`nfr-performance-check.yml`、`release-truth-gate.yml` 都启动 `postgres:16`）→ 单测覆盖率不能验证 PG 特定行为（JSONB、partial index、generated column）。
- Redis **fixture 未自动启动**，所有 `redis_cache` 测试可能绕过真实 Redis（70 个 mock 文件中有部分使用 `fakeredis`）。

---

## 8. 严苛评级详表

### 8.1 P0 — 阻断

| ID | 描述 | 证据 |
|----|------|------|
| P0-1 | **trace_id 自动注入断崖**：15 个 stdlib `logger` 文件 116 个调用点不注入 trace_id；其中含 `audio_archival.py`（个保法重点） | `common/monitoring/logger.py:78-84` + grep |
| P0-2 | **17 个 Prometheus 指标为死代码**：`/metrics` 端点持续暴露永远为 0 的指标，误导 Grafana | `common/monitoring/metrics.py:36-130` + grep |
| P0-3 | **常规 PR 缺门禁**：无 ruff / mypy / 单测 / 契约 / 覆盖率门禁，PR 合并到 main 才触发 release-truth（45 min timeout） | `.github/workflows/` 全部 + `pyproject.toml` |
| P0-4 | **销售训练 audio_submission 无 DELETE 路由**：个保法"被遗忘权"不可行使，admin GET 仍可下载历史 | `sales_trainer/api.py:901-1010` 全文（仅 GET / POST retry） |

### 8.2 P1 — 严苛

| ID | 描述 | 证据 |
|----|------|------|
| P1-1 | **`STEPFUN_API_KEY` 明文读取**：`os.getenv("STEPFUN_API_KEY", "")` 直接落 `_stepfun_api_key` 属性 + 错误体 + WS payload | `stepfun_realtime_handler.py:291, 860-866`、`stepfun_realtime_connection.py` 全文 |
| P1-2 | **`STEPFUN_API_KEY` 加密测试缺失**：仅 `RagProfile` 与 OpenAI 模型配置有 Fernet 加密测试，**StepFun 模型配置无独立回归** | `test_rag_profile_security.py` + `test_admin_model_configs_api.py` 全文（仅 OpenAI / Cohere） |
| P1-3 | **OTel 接入名存实亡**：`OTEL_ENABLED` 默认 false、0 业务 span、0 trace → metrics 桥接 | `otel.py:42-96` + grep |
| P1-4 | **WebSocket `close(4401)` 回归缺失**：已发现 4001 / 4003 / 4410 测试，**4401 鉴权失败**无 | `test_sales_websocket_router.py:183, 286`、`test_stepfun_realtime_handler.py` 全文 |
| P1-5 | **跨域继承 (Agent 1 F-01) 无 E2E 防退化**：`PresentationStepFunRealtimeHandler` 继承 `StepFunRealtimeHandler` 但无回归测试 | `03-websocket-realtime.md` 评级 D + 全文 grep |
| P1-6 | **NFR 5 并发 vs CI 50 并发 vs 文档 200 并发 三方数字错位**：`LOAD_TEST_USERS=50` 注入但代码 `assert latency < 5000` 5-10 并发 | `test_e2e_latency.py:175`、`test_vagueness_detection.py:123`、`test_nfr_metrics.py:699` vs nfr-performance-check.yml |

### 8.3 P2 — 重要

| ID | 描述 |
|----|------|
| P2-1 | **前端 `client.ts` (4 648 行) 覆盖 3.24%**：所有页面测试走 mock，API 客户端契约不在 CI |
| P2-2 | **契约测试 24 个 / API 文档 18 份 结构性不对齐**：sales-trainer、voice-runtime、agents、replay、prompt-templates、model-configs、knowledge、effectiveness **0 contract 测试** |
| P2-3 | **日志脱敏 4 marker 不闭环**：`api_key` / `apikey` / `secret` / `authorization` 缺；`log_safety_inventory.py` 仅 6 surfaces |
| P2-4 | **`coverage.json` 4 个月未刷新**（2026-02-12）；`htmlcov/` 体积 100MB 在仓库内但 gitignore 排除 |
| P2-5 | **无 Grafana 仪表盘 / 告警规则**：`/prometheus.yml` 静态 scrape config，无 `dashboards/` 或 `alerts.yml` |

### 8.4 P3 — 关注

| ID | 描述 |
|----|------|
| P3-1 | **Vitest 仅跑 17 / 166 个 target**：4 648 行的 `client.ts` 等关键文件不在 critical-quality-gate 范围 |
| P3-2 | **`roleplay-contract-eval` 依赖 LLM grader**：不可重复、不可审计、CI 费用高 |
| P3-3 | **`roleplay-contract-eval` paths filter**：仅 14 个文件触发，其他修改不评估 |
| P3-4 | **`scripts/secret-scan.sh` 二次封装 check_secret_hygiene.py**：存在但 `release-truth-gate.yml` 用 `python scripts/...` 直接调用，未走统一入口 |

---

## 9. 严苛修复建议（按 ROI 排序）

### Sprint-1（必须立即修）

1. **`logger = logging.getLogger(...)` → `logger = get_logger(...)`**：15 文件 116 调用点批量替换（机械 sed + 测试），恢复 trace_id 100% 覆盖。
2. **删除或接入 17 个死 Prometheus 指标**：每个指标需明确"接入路径 + 责任 owner + Sprint"，否则 24h 内清空定义。
3. **新增 `api/v1/admin/sales-trainer/audio-submissions/{id}` DELETE 路由 + 软删除字段 `deleted_at`**：个保法合规最低成本。
4. **新增 `STEPFUN_API_KEY` 加密读取路径**：仿 `RagProfile` 模式，存 DB 时 Fernet 加密；handler 启动时 decrypt 到内存；附回归测试。

### Sprint-2（重要）

5. **新增 `lint.yml` / `unit-tests.yml` / `contract-tests.yml` / `coverage-gate.yml` 4 个 PR 工作流**：< 5 min timeout，PR 必过。
6. **将 16 个 BACKEND_GATE_TARGETS 替换为 `pytest tests/unit/ tests/contract/` 全量**：去掉 `--no-cov`，让 `pyproject.toml` 的 `--cov-fail-under=48` 真正生效。
7. **`client.ts` 单元测试覆盖到 ≥ 60%**：先拆分 4 648 行 → 8 个域，再为每个域加 happy/sad path。
8. **新增 `sales-trainer.md` 契约测试**：14 个 admin 端点 + 6 个 learner 端点 → ≥ 30 个 contract test。
9. **`track_*` 函数批量接入**：在 asr_alibaba、tts_factory、bot_service、presentation_handler 关键路径上调用现成的 17 个死指标。

### Sprint-3（治理）

10. **统一 `coverage.json` 时效**：CI 必产 `coverage.json` + `coverage-summary.json`，写入 `evidence/coverage-{date}.json`，过期 7 天告警。
11. **新增 `Otel-Enabled` 开关的样例 deployment**（`deploy/k8s/otel-enabled.yaml`）+ 业务代码 `tracer.start_as_current_span` 注入 WebSocket / LLM / ASR / TTS 关键 span。
12. **NFR 测试统一为 50 并发**：把 `test_e2e_latency.py:167` 写死的 10 改为 env `LOAD_TEST_USERS`，CI 才与"50 并发"对账。
13. **Grafana 仪表盘 + 告警**：4 个仪表盘（HTTP、WS、ASR/TTS/LLM、Practice）+ 5 条告警（5xx > 1%、P95 > 300ms、TTS 降级率 > 5%、错误率 > 0.1%、StepFun close 4000 > 0）。

---

## 10. 关键证据路径索引

| 主题 | 关键文件 |
|------|----------|
| 测试覆盖 | `backend/coverage.json`、`backend/pyproject.toml`、`web/vitest.config.ts`、`web/coverage/coverage-summary.json` |
| 监控 | `backend/src/common/monitoring/{metrics,logger,otel,log_safety_inventory,latency_tracker,nfr_reporter,health,trace_context}.py` |
| 死代码 | `backend/src/common/monitoring/metrics.py:36-130` |
| Logger 双轨 | `backend/src/common/monitoring/logger.py:60-67, 237-253` |
| 销售训练 API | `backend/src/sales_trainer/{api.py,article_api.py,paper_api.py,permissions.py}` |
| 鉴权测试 | `backend/tests/unit/test_jwt_auth_security.py`、`backend/tests/integration/test_auth_login_api.py` |
| 加密 | `backend/src/common/ai/encryption.py`、`backend/tests/unit/admin/test_rag_profile_security.py`、`backend/tests/integration/test_admin_model_configs_api.py` |
| WebSocket 关闭码 | `backend/tests/unit/test_sales_websocket_router.py:183, 286`、`backend/tests/unit/test_examiner_websocket_router.py` |
| CI 工作流 | `.github/workflows/nfr-performance-check.yml`、`release-truth-gate.yml`、`roleplay-contract-eval.yml` |
| 关键脚本 | `scripts/critical-quality-gate.sh`、`scripts/check_secret_hygiene.py` |
| 文档 vs 测试 | `docs/api-contract/*.md` (18 份) ↔ `backend/tests/contract/test_*.py` (24 个) |
| 审计报告 | `docs/agents/audit-2026-06/01-architecture-boundary.md`、`03-websocket-realtime.md`、`04-audio-and-ai-capabilities.md`、`06-security-and-privacy.md` |

---

## 11. 与其他审计的串证

| 项 | 涉及 Agent | 本审计交叉证据 |
|----|------------|----------------|
| F-OBS-1（13 指标 0 调用） | 04-audio-and-ai-capabilities | **升级**：实测 21 指标中 17 个死，3 个活的（http/situation_pack/frontend_analytics），1 个 Info 半活 |
| F-SEC-1（StepFun 加密） | 01-architecture-boundary / 04-audio-and-ai-capabilities | **未修**：`os.getenv("STEPFUN_API_KEY", "")` 仍明文 |
| 个保法音频删除 | 04-audio-and-ai-capabilities D-SEC-2 | **确认无 DELETE 路由** |
| 4401 关闭码 | 06-security-and-privacy | **确认缺失** |
| 跨域继承 (F-01) | 01-architecture-boundary / 03-websocket-realtime | **确认无 E2E 回归** |
| 日志脱敏 | 06-security-and-privacy / 04-audio-and-ai-capabilities | **确认** `SENSITIVE_LOG_FIELD_MARKERS` 仅 4 marker，且 15 个文件不脱敏 |

---

## 12. TL;DR

- **可观测性"看起来有，运行时没有"**：trace_id 仅 90% 文件有、Prometheus 17/21 死、OTel 形同虚设。
- **CI"看起来全，常规 PR 不跑"**：3 套工作流都非 PR 必过；覆盖率门禁用 `--no-cov` 关闭。
- **契约"文档有，测试没"**：24 contract / 18 docs，结构性不对齐，sales-trainer 全域 0 contract test。
- **前端 `client.ts` 灾难**：4 648 行 3% 覆盖。
- **死指标 17 个 + 死函数 9 个**：持续消耗资源 + 暴露误导数据。
- **缺 5 个关键回归**：销售训练 RBAC 端到端、跨域继承、4401 close、StepFun 加密、audio DELETE。

**结论**：测试、可观测性、CI 治理三轴均处于"治理失能"边缘。Sprint-1 必须 4 项全修，否则 6.18 / 6.30 两次发版都可能因观测盲区翻车。
