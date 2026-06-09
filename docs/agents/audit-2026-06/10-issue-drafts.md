# GitHub Issue 草稿 (2026-06-03)

> **目标**：将 8 份 agent 报告中的 P0/P1 修复项整理为可直接 `gh issue create --body-file` 提交的草稿。
> **范围**：🔴 P0 阻断 24 项 + 🟡 关键 P1 15 项 = 共 39 个草稿。
> **标签规范**（CLAUDE.md 协作规则）：`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix` + `audit-2026-06` + 域标签
> **关联文档**：`docs/agents/audit-2026-06/00-executive-summary.md` + 各专题报告 + `09-doc-cleanup-checklist.md` + `12-code-issues-record.md`

---

## 0. 草稿索引

| # | 标题 | 严重 | Sprint | 关联 |
|---|------|------|--------|------|
| **P0-01** | 修复跨域继承：`PresentationStepFunRealtimeHandler` 继承 `sales_bot.StepFunRealtimeHandler` | 🔴 | 1 | 1 F-01 / 3 §10 |
| **P0-02** | WebSocket 鉴权补完：token 失败 `close(4401)` + `payload["sub"] == session.user_id` 强校验 | 🔴 | 1 | 6 P1-3/4 / 8 P1-4 |
| **P0-03** | `STEPFUN_API_KEY` 走 Fernet 加密（与 LLM/ASR/TTS 对称） | 🔴 | 1 | 4 F-SEC-1 / 6 P1 / 8 P1-1/2 |
| **P0-04** | 17 个 Prometheus 死指标接入或删除 | 🔴 | 1 | 4 F-OBS-1 / 8 P0-2 |
| **P0-05** | trace_id 自动注入：15 个 stdlib logger 文件 → `get_logger` | 🔴 | 1 | 8 P0-1 |
| **P0-06** | 销售训练 audio_submission 无 DELETE 路由 + 软删除字段 | 🔴 | 1 | 4/6/8 D-SEC-2 / P0-4 |
| **P0-07** | `bg-white` 526 处全量替换为设计系统 token | 🔴 | 1 | 7 §1.4 |
| **P0-08** | WebSocket 客户端 binaryType 缺 + 二进制 PCM 入站（R-1 P0） | 🔴 | 1 | 7 §10.3 |
| **P0-09** | CI 常规 PR 5 门禁工作流（lint / unit / contract / coverage-gate / secret-hygiene） | 🔴 | 1 | 8 P0-3 |
| **P0-10** | CLAUDE.md 文档纠错（main.py 行数、common/ 子目录、bg-white 强约束） | 🔴 | 1 | 1 F-04 / F-12 |
| **P0-11** | 3 处 `HTTPException(500)` 违宪修复 | 🔴 | 1 | 2 P0-1 |
| **P0-12** | `common/business_rules/validators.py` 80 处 raise 重构为 Result | 🔴 | 1 | 2 P0-4 |
| **P0-13** | `support/` + `supervisor/` 子系统引入 Result 范式（当前 0 引用） | 🔴 | 1 | 2 P0-5 |
| **P0-14** | `sales_trainer/services/*` 110+ raise 改 Result | 🔴 | 1 | 2 P0-6 |
| **P0-15** | `agent_service.py` 13 查询添加 `selectinload/joinedload` | 🔴 | 1 | 5 P0-3 |
| **P0-16** | `sales_trainer_*` 表 14 个 JSONB 列加 GIN 索引 | 🔴 | 1 | 5 P0-1 |
| **P0-17** | `pool_recycle` 配置补全（防 PgBouncer/NAT 1h 超时） | 🔴 | 1 | 5 P0-2 |
| **P0-18** | 销售训练 quiz/audio/operation_log 列表加 LIMIT 分页 | 🔴 | 1 | 5 P0-4 |
| **P0-19** | 项目级软删除标准字段（`deleted_at`）统一化 | 🔴 | 1 | 5 P0-5 |
| **P0-20** | admin audio_submission 列表脱敏 user_email | 🔴 | 1 | 6 P1-1 |
| **P0-21** | admin quiz_attempt 列表脱敏 user_email | 🔴 | 1 | 6 P1-2 |
| **P0-22** | `X-Forwarded-For` 信任链加固 | 🔴 | 1 | 6 P1-5 |
| **P0-23** | `ASRServiceWithFallback` / `TTSServiceWithFallback` 接入或删除（生产 0 引用） | 🔴 | 1 | 4 F-ASR-1 / F-TTS-1 |
| **P0-24** | CLAUDE.md 恢复事实（main.py 75 行、common/ 30 子目录、bg-white 0 容忍） | 🔴 | 1 | 1 F-04 / F-12 |
| **P1-01** | 错误码中心表 `docs/error-codes.md` 建立 + Result 升级（error_code/trace_id/and_then） | 🟡 | 2 | 2 §7 |
| **P1-02** | TTS 5 个必备 env 接入（`TTS_TIMEOUT/SAMPLE_RATE/CONNECTION_POOL_SIZE/ENABLE_WARMUP/FALLBACK_CHAIN`） | 🟡 | 2 | 4 F-CFG-1 |
| **P1-03** | 49 端点失败态测试 + 49 端点 contract test（sales-trainer 0 contract） | 🟡 | 2 | 7 §8.3 / 8 §6 |
| **P1-04** | 全局/用户级/IP 级限流中间件 | 🟡 | 2 | 1 F-06 / 4 D-LIMIT-1 |
| **P1-05** | TTS/LLM/StepFun/ChromaDB 熔断器补全 | 🟡 | 2 | 4 D-CB-1 |
| **P1-06** | JWT audience/issuer claim 校验 | 🟡 | 2 | 6 P1-7 |
| **P1-07** | 9 个 WS 错误码文档化 + `schema_version` 顶层字段 | 🟡 | 2 | 3 §3.3 / §8.5 |
| **P1-08** | 日志脱敏 marker 补全（api_key/apikey/secret/authorization） | 🟡 | 2 | 6 P1-9 |
| **P1-09** | sales-trainer 14 子段补 `error.tsx` + `loading.tsx` + 新增 `global-error.tsx` | 🟡 | 2 | 7 §2 |
| **P1-10** | React Query 接入 sales-trainer（消除 272 处 useState 抓数据） | 🟡 | 2 | 7 §4 |
| **P1-11** | `client.ts` 4648 行拆分 + 49 端点失败态测试 | 🟡 | 2 | 7 §3 |
| **P1-12** | `user-practice-websocket.ts` 1047 行拆 3 个 hook | 🟡 | 2 | 3 §9.4 |
| **P1-13** | `presentation_coach` 跨域继承修复（方案 A：抽 `common/websocket/stepfun_realtime_handler.py`） | 🟡 | 1（合并 P0-01） | 3 §10 |
| **P1-14** | `common/services/practice_session_service.py` 双向耦合业务域，拆 `practice_orchestrator` | 🟡 | 2 | 1 I-2 |
| **P1-15** | NFR 性能测试并发数统一 50（消除 5/10/200 三方错位） | 🟡 | 2 | 8 §4.5 |

> 共 39 个草稿（24 P0 + 15 P1）。**P1-13** 与 **P0-01** 重复（合并处理），实际新增 38 个独立 issue。

---

## 1. Issue 草稿正文（核心 P0 样本）

> 每个 issue 草稿包含：标题、labels、body（背景 + 验收标准 + 关联报告 + 估计 + owner）
> 以下给出 5 个最关键 P0 的完整 body 文本，可直接 `gh issue create --title "..." --body-file issue-XXX.md` 提交。

### P0-01 · 修复跨域继承

```markdown
# [P0-01] 修复跨域继承：PresentationStepFunRealtimeHandler → StepFunRealtimeHandler

## 摘要
`presentation_coach/websocket/presentation_stepfun_realtime_handler.py:47` 单向继承 `sales_bot/websocket/stepfun_realtime_handler.py:238` 的 `StepFunRealtimeHandler`，违反 AGENTS.md §III 场景隔离原则。

## 现状
- 反向 `_disable_sales_capabilities()` (line 73) 每次重写 sales 配置
- `__init__` 60+ 字段，PP 域 60% 用不到
- 加新场景需 copy-paste 8244 行 mixin 链
- 缺失 E2E 防退化测试

## 验收标准
- [ ] 新建 `backend/src/common/websocket/stepfun_realtime_handler.py`，将 `StepFunRealtimeHandler` + 5 个 mixin + `StepFunRealtimeStateBase` 抽到此
- [ ] `sales_bot/websocket/stepfun_sales_handler.py` 继承 common 基类，启用 sales-stage/fuzzy/scoring
- [ ] `presentation_coach/websocket/stepfun_presentation_handler.py` 继承 common 基类，禁用 sales 能力
- [ ] 12 个 `from sales_bot.websocket.stepfun_realtime_handler import` 全部更新到新位置
- [ ] 新增 E2E 测试 `tests/e2e/test_cross_domain_inheritance_regression.py`，断言 PP handler 不再 import sales 包
- [ ] 删除 `presentation_coach` 内 `_disable_sales_capabilities` 反向方法
- [ ] `_STEPFUN_RUNTIME_EVENT_INVENTORY` 注释重新定位
- [ ] `docs/adr/2026-06-03-cross-domain-inheritance-fix.md` 新增

## 关联
- 报告：docs/agents/audit-2026-06/01-architecture-boundary.md §3.2 I-1
- 报告：docs/agents/audit-2026-06/03-websocket-realtime.md §10
- 报告：docs/agents/audit-2026-06/08-testing-observability-ci.md P1-5
- ADR：新建

## 估计
3 工作日（1 抽基类 + 1 迁移 mixin + 1 测试 + 文档）

## Owner
@sales-bot-maintainer / @presentation-coach-maintainer

## Labels
needs-triage, audit-2026-06, backend, websocket, p0
```

---

### P0-02 · WebSocket 鉴权补完

```markdown
# [P0-02] WebSocket 鉴权补完：close(4401) + sub↔session 强校验

## 摘要
WS handler 在 token 验证失败时仅 `logger.warning` 而不主动 `close(4401)`；token `payload["sub"]` 与 session 拥有者未强绑定，学员可接入他人 session。

## 漏洞证据
- `backend/src/common/websocket/base_handler.py:253-255`：token 失败不关闭
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:832-834`：同上
- `backend/src/curriculum_practice/websocket/router.py:184`：仅辅助函数返回 user_id
- 重连时**不重新比对** `payload["sub"]` 与 `session.user_id`

## 验收标准
- [ ] `BaseWebSocketHandler.handle_connection` 在 `verify_token` 失败时立即 `await self.close(code=4401)` 不再 return None
- [ ] `StepFunRealtimeHandler.handle_connection` 同步行为
- [ ] 新增 `_validate_session_ownership(session_id, user_id)` helper，校验 `payload["sub"] == str(session.user_id)`，失败 `close(4403)` ACCESS_DENIED
- [ ] 紧跟 token 验证步骤调用
- [ ] 增加单元测试 `tests/unit/test_ws_4401_on_token_failure.py` 覆盖 4 个 handler
- [ ] 增加回归测试 `tests/unit/test_ws_sub_session_binding.py`
- [ ] 更新 `docs/api-contract/websocket.md` 关闭码表

## 关联
- 报告：docs/agents/audit-2026-06/06-security-and-privacy.md P1-3/4
- 报告：docs/agents/audit-2026-06/03-websocket-realtime.md §7
- 报告：docs/agents/audit-2026-06/08-testing-observability-ci.md P1-4
- 测试：当前无 4401 / sub binding 回归

## 估计
1.5 工作日

## Owner
@auth-maintainer / @websocket-maintainer

## Labels
needs-triage, audit-2026-06, backend, security, websocket, p0
```

---

### P0-03 · STEPFUN_API_KEY 走 Fernet 加密

```markdown
# [P0-03] STEPFUN_API_KEY 走 Fernet 加密（与 LLM/ASR/TTS 对称）

## 摘要
`backend/src/sales_bot/websocket/stepfun_realtime_handler.py:291` `self._stepfun_api_key = os.getenv("STEPFUN_API_KEY", "")` 直接读 env 落内存，与 LLM/ASR/TTS 走 `ModelConfig.api_key_encrypted` Fernet 加密链路不对称。

## 现状
- `agent/models.py:VoiceRuntimeProfile` 无 `api_key_encrypted` 列
- handler 错误体 / WS payload 可能含明文（`stepfun_realtime_handler.py:860-866` "未配置 STEPFUN_API_KEY" 错误）
- 日志 marker 不含 `api_key` / `secret`（Agent 6 P1-9 串证）→ 加密失败日志可能裸入栈

## 验收标准
- [ ] 在 `agent/models.py:VoiceRuntimeProfile` 新增 `api_key_encrypted: Text` 字段（Fernet）
- [ ] 在 `common/ai/encryption.py` 新增 `encrypt_stepfun_api_key(plain) -> Result[bytes]` 与 `decrypt_stepfun_api_key(cipher) -> Result[str]`
- [ ] 仿 `RagProfile` 模式：admin API 写入加密、handler 启动时 decrypt 到 `_stepfun_api_key`
- [ ] 修改 `stepfun_realtime_handler.py:291` 改用 decrypt 路径
- [ ] alembic 新增迁移 `2026MMDD_NNN_stepfun_api_key_encrypted.py`
- [ ] 单元测试 `tests/unit/test_stepfun_api_key_encryption.py` 覆盖加密/解密/缺 key fallback
- [ ] 集成测试 `tests/integration/test_admin_voice_runtime_stepfun.py` 覆盖 admin 写密文→handler 解密读取
- [ ] `backend/.env.example` 标注 "STEPFUN_API_KEY 仅 admin UI 配置（自动 Fernet 加密），env 直读模式 deprecated"

## 关联
- 报告：docs/agents/audit-2026-06/04-audio-and-ai-capabilities.md F-SEC-1
- 报告：docs/agents/audit-2026-06/06-security-and-privacy.md §4 加密字典
- 报告：docs/agents/audit-2026-06/08-testing-observability-ci.md P1-1/2
- ADR：新建 docs/adr/2026-06-03-stepfun-key-encryption.md

## 估计
1.5 工作日

## Owner
@stepfun-integrator / @encryption-maintainer

## Labels
needs-triage, audit-2026-06, backend, security, encryption, p0
```

---

### P0-04 · 17 个 Prometheus 死指标接入或删除

```markdown
# [P0-04] 17 个 Prometheus 死指标接入或删除

## 摘要
`backend/src/common/monitoring/metrics.py` 定义 21 个指标，**17 个生产 0 调用**（Agent 4 报 13，实测 17），`/metrics` 端点持续暴露永远为 0 的指标，误导 Grafana。

## 死指标清单
websocket_connections_active / websocket_messages_total / websocket_message_duration_seconds / practice_sessions_total / practice_session_duration_seconds / practice_scores / llm_requests_total / llm_request_duration_seconds / llm_tokens_total / asr_requests_total / asr_request_duration_seconds / tts_requests_total / tts_request_duration_seconds / voice_policy_rollbacks_total / voice_policy_state_changes_total / errors_total / （application_info 半活）

## 决策（每项二选一）
- 接入：调用现成 `track_*(...)` 函数
- 删除：移除定义 + `track_*` 包装

## 验收标准
- [ ] `docs/observability/dead-metrics-action-plan.md` 新增，列出 17 项每项的最终决策（接入 owner / 删除理由）
- [ ] 接入路径（每项在关键调用点加 `track_*(...)`）：
  - `track_asr_request` / `track_tts_request` → `common/audio/asr_alibaba.py` `tts_factory.py` 关键路径
  - `track_llm_request` / `track_llm_tokens` → `common/ai/llm_service.py` 4 个生成入口
  - `track_websocket_connection` / `track_websocket_message` → `common/websocket/base_handler.py` + stepfun_realtime_handler
  - `track_practice_session` / `track_practice_scores` → `sales_bot/services/voice_runtime_policy.py` + practice_session_service
  - `track_error` → 各 WS handler `except` 分支
  - `track_voice_policy_rollback` / `track_voice_policy_state_change` → `sales_bot/services/voice_policy_monitor.py`
- [ ] 接入后 `tests/unit/test_metrics_registration.py` 验证 17 个指标 `collect()` 非零
- [ ] Grafana 仪表盘 JSON 新增 4 个（HTTP/WS/AI/Practice），`docs/observability/grafana/` 目录
- [ ] 告警规则 `docs/observability/alerts.yml` 5 条（5xx>1%、P95>300ms、TTS 降级率>5%、错误率>0.1%、StepFun close 4000>0）

## 关联
- 报告：docs/agents/audit-2026-06/04-audio-and-ai-capabilities.md F-OBS-1
- 报告：docs/agents/audit-2026-06/08-testing-observability-ci.md P0-2 / §5.1

## 估计
2 工作日（接入）+ 1 工作日（Grafana + 告警）

## Owner
@observability-maintainer

## Labels
needs-triage, audit-2026-06, backend, observability, p0
```

---

### P0-09 · CI 常规 PR 5 门禁

```markdown
# [P0-09] CI 常规 PR 5 门禁工作流

## 摘要
`.github/workflows/` 仅有 3 个工作流（nfr / release / roleplay），**常规 PR 零门禁**。任何 PR 合并到 main 之前不跑 ruff / mypy / unit / contract / coverage 门禁；release-truth-gate 45min timeout 才跑全量。覆盖率门禁 `pyproject.toml` `--cov-fail-under=48` 被 `--no-cov` 关闭。

## 验收标准
- [ ] 新增 `.github/workflows/lint.yml`（< 2 min）
  - backend: `ruff check src/` + `ruff format --check src/` + `mypy src/`
  - frontend: `npm run lint` + `npx tsc --noEmit`
- [ ] 新增 `.github/workflows/unit-tests.yml`（< 5 min）
  - backend: `pytest tests/unit/ tests/contract/ --cov=src --cov-fail-under=48`（**去掉 --no-cov**）
  - frontend: `npm run test`（vitest 全量 166 文件）
- [ ] 新增 `.github/workflows/contract-tests.yml`（< 3 min）
  - backend: `pytest tests/contract/` 全量
  - sales-trainer 0 contract 必须补 ≥ 30 case
- [ ] 新增 `.github/workflows/coverage-gate.yml`（< 5 min）
  - 验证 backend coverage ≥ 48%、frontend coverage ≥ 30% (lines/funcs)
  - coverage.json / coverage-summary.json 写入 `evidence/coverage-{date}.json`
- [ ] 新增 `.github/workflows/secret-hygiene.yml`（< 1 min）
  - 抽 `scripts/check_secret_hygiene.py` 到 PR 必过
- [ ] release-truth-gate.yml **删除** `--no-cov` flag
- [ ] 5 个工作流都触发 PR（`on: pull_request: branches: [main, 001-ai]`）

## 关联
- 报告：docs/agents/audit-2026-06/08-testing-observability-ci.md P0-3 / §4.4
- ADR：新建 docs/adr/2026-06-03-pr-ci-gates.md

## 估计
1 工作日

## Owner
@devops-maintainer

## Labels
needs-triage, audit-2026-06, ci, infrastructure, p0
```

---

## 2. 提交命令模板

```bash
# 在仓库根目录
gh issue create \
  --repo zhaozengqing4364-bit/sales-training-qoder \
  --label "needs-triage,audit-2026-06,backend,websocket,p0" \
  --title "[P0-01] 修复跨域继承：PresentationStepFunRealtimeHandler → StepFunRealtimeHandler" \
  --body-file docs/agents/audit-2026-06/issues/p0-01-cross-domain-inheritance.md

# 批量提交脚本（建议）
for f in docs/agents/audit-2026-06/issues/p0-*.md; do
  title=$(grep "^# \[" "$f" | head -1 | sed 's/^# //')
  gh issue create --label "needs-triage,audit-2026-06" --title "$title" --body-file "$f"
done
```

> ⚠️ **本审计阶段不直接执行 `gh issue create`**。所有 issue 正文写入 `docs/agents/audit-2026-06/issues/` 目录作为草稿。

---

## 3. Issue 草稿落地建议

| 阶段 | 动作 | 负责 |
|------|------|------|
| **1. 草稿评审** | 您审阅 38 个草稿标题/优先级/owner | 您 |
| **2. 创建目录** | 在 `docs/agents/audit-2026-06/issues/` 下建 38 个 markdown（每个对应一个 issue body） | 主 agent（本批不执行） |
| **3. 批量提交** | 用 `gh issue create --body-file` 批量提交 | 您 |
| **4. 看板** | 在 GitHub Project 看板按 Sprint 分组（Sprint-1 / Sprint-2 / Sprint-3） | 您 |
| **5. 链接回写** | 提交后回填 issue 编号到 `12-code-issues-record.md` 对应项 | 主 agent |

---

## 4. 与 Sprint 对齐

| Sprint | Issue 范围 | 估计工作量 |
|--------|----------|----------|
| **Sprint-1（1-2 周）** | P0-01 ~ P0-24（24 个） | ~14 人天 |
| **Sprint-2（2-4 周）** | P1-01 ~ P1-15（15 个） | ~18 人天 |
| **Sprint-3（1-3 月）** | P2/P3 项（在 12-code-issues-record.md 中详列） | ~25 人天 |

---

## 5. 不在本次 issue 范围

按用户决策"代码相关问题创建一个文档记录"（即 `12-code-issues-record.md`），本文件**不**重复枚举所有 P0/P1/P2/P3 issue 全文。**只**给出：
- P0 24 项的标题、严重度、Sprint 归属、关联报告
- P1 15 项的标题、严重度、Sprint 归属、关联报告
- 5 个最关键 P0 的完整 body 文本（可直接 `gh issue create --body-file`）
- 其余 P0/P1 的标题 + 关键验收点（`12-code-issues-record.md` 详列）

完整 issue body 文本的**最终落地**建议在评审通过后由主 agent 在下一轮会话生成到 `docs/agents/audit-2026-06/issues/p*.md`。

---

## 6. 标签使用规范

每个 issue 至少包含 3 类标签：

```yaml
# 1. triage 标签（必填）
needs-triage                # 初次提交
# 或 ready-for-agent          # 已指派给 agent
# 或 ready-for-human          # 需人工决策

# 2. 审计批次（必填）
audit-2026-06

# 3. 域标签（必填）
backend / frontend / ci / infrastructure / docs

# 4. 子域标签（按需）
websocket / security / database / observability / encryption / design-system / test

# 5. 严重度（必填）
p0 / p1 / p2 / p3
```

---

**本文件未调用 `gh` CLI，未创建任何 GitHub Issue**。所有 issue 内容仅作为草稿。
