---
estimated_steps: 5
estimated_files: 7
skills_used:
  - safe-grow
  - best-practices
  - code-refactoring
  - test
  - verification-before-completion
---

# T01: 用统一 evidence truth line 重写 support runtime 后端健康读模型

**Slice:** S08 — 桌面端发布验收与可观测性收口
**Milestone:** M001

## Description

当前 `/api/v1/support/runtime/*` 的最大问题不是字段少，而是事实源不对：overview 仍把 `status="scoring"` 算进 completed，faults 主要来自 `SystemLog`，导致 support 面可能显示健康，但真正的 milestone-critical failure（projection 构建失败、knowledge 检索失败、PPT `missing_page_metadata`、completed but not evaluable、optional report failed）根本不在这条读线上。这个任务要先把 support/runtime 的后端 truth model 收稳：复用 `SessionEvidenceService.build_projection(...)`、knowledge-check 的 runtime diagnostics 语义、以及 presentation degraded reasons，产出 typed release health summary 与 anomaly list，再让路由层只做 RBAC 和 response shaping。

## Steps

1. 先在 `backend/tests/unit/test_support_runtime_service.py`、`backend/tests/contract/test_support_runtime.py`、`backend/tests/integration/test_support_runtime_api.py` 写 failing tests，锁住 overview/faults 的新 contract：`scoring` 单独计数、不再混进 completed、anomaly 有 severity/kind/summary/session identifiers，且 blocking/warning 分类明确。
2. 从 `backend/src/common/api/practice.py` 提取共享 runtime diagnostics helper 到 `backend/src/common/conversation/runtime_diagnostics.py`，让 knowledge-check 现有 `status` / `kb_lock_status` / `upstream_disconnect_count_5m` / `upstream_unstable` 语义可被 support runtime 复用，而不是复制一份分叉逻辑。
3. 新增 `backend/src/support/services/runtime_status_service.py`，批量读取 recent sessions 与其 `ConversationMessage`，通过 `SessionEvidenceService.build_projection(...)`、`voice_policy_snapshot.runtime_metrics`、`report_status`、presentation degraded reasons 分类 release anomalies：`stuck_scoring`、`projection_failed`、`not_evaluable_completed`、`presentation_degraded_missing_page_metadata`、`knowledge_search_failed`、`kb_not_ready`、`kb_lock_blocked_*`、`upstream_unstable`、`optional_report_failed`。
4. 改造 `backend/src/support/api/runtime_status.py` 使用新 service 返回 typed overview/fault items，保留 support/admin 只读 RBAC，并让旧 `SystemLog` 数据最多作为补充 warning source，而不是主 truth line。
5. 跑 backend unit/contract/integration suites，并补一条 `tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses` 回归，确认 helper 抽取没有把 S05/S08 共用的 knowledge-check contract 带偏。

## Must-Haves

- [ ] `backend/src/support/services/runtime_status_service.py` 必须以 persisted session evidence 为主事实源，不能退回逐条 `SystemLog` 拼发布健康。
- [ ] `backend/src/common/conversation/runtime_diagnostics.py` 必须复用 knowledge-check 既有语义，让 support runtime 与 `/practice/sessions/{id}/knowledge-check` 在 `search_failed`、`kb_not_ready`、`kb_lock_status`、`upstream_unstable` 上保持同义。
- [ ] `status="scoring"` 必须从完成率里剥离，并能区分短暂 scoring 与 stuck scoring；support 面不能再把它误判为健康完成。
- [ ] presentation degraded anomalies 必须沿用 `missing_page_metadata` 这类 canonical degraded reason，不得重新发明 PPT 支持面错误码。

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses`

## Observability Impact

- Signals added/changed: support runtime overview/faults 改为 typed release-health counters 与 anomaly severity/kind summary；knowledge/runtime diagnostics helper 从 `practice.py` 抽出后成为 support/runtime 与 report/knowledge-check 共用的分类面。
- How a future agent inspects this: 先看 `/api/v1/support/runtime/overview` 与 `/api/v1/support/runtime/faults`，再对照 `GET /api/v1/practice/sessions/{id}/knowledge-check`、`GET /api/v1/practice/sessions/{id}/report` 与 backend 测试文件确认 anomaly 语义来源。
- Failure state exposed: stuck scoring、projection 失败、knowledge 检索失败、PPT page metadata 缺失、optional report failed 等都会以 typed anomaly 项直接可见，而不是只剩 completion rate 或模糊系统日志。

## Inputs

- `backend/src/support/api/runtime_status.py` — 当前 coarse runtime overview/faults 实现，仍以 `SystemLog` 和 `status="scoring"` completion 统计为主。
- `backend/src/common/api/practice.py` — 已有 canonical knowledge-check 与 report 语义；support runtime 需要复用而不是重写。
- `backend/src/common/conversation/session_evidence.py` — authoritative projection builder，support runtime 应基于它判断 completed/evaluable/degraded。
- `backend/src/common/analytics/history_service.py` — 已有批量加载 messages + projection 的模式，support runtime service 应复用这条实现思路而不是逐 session 查询。
- `backend/src/presentation_coach/services/presentation_report_service.py` — PPT degraded semantics 的 authority，尤其 `missing_page_metadata`。
- `backend/tests/contract/test_support_runtime.py` — support runtime contract guardrail，需要扩成 typed release-health contract。
- `backend/tests/integration/test_support_runtime_api.py` — support runtime integration baseline，最适合锁住 scoring/anomaly/severity 行为。
- `backend/tests/integration/test_knowledge_flow.py` — knowledge-check 语义回归，防止 helper 提取引入分类漂移。

## Expected Output

- `backend/src/common/conversation/runtime_diagnostics.py` — support runtime 与 knowledge-check 共用的 runtime diagnostics helper。
- `backend/src/support/services/runtime_status_service.py` — evidence-backed release health aggregation 与 anomaly classification service。
- `backend/src/support/api/runtime_status.py` — 变薄的 support runtime route，返回 typed overview/fault contract。
- `backend/tests/unit/test_support_runtime_service.py` — 锁住 anomaly 分类、severity、summary 与 stuck scoring 行为。
- `backend/tests/contract/test_support_runtime.py` — 锁住新的 support runtime response contract。
- `backend/tests/integration/test_support_runtime_api.py` — 锁住 support/admin 可读、typed anomaly 读面与 scoring handling。
- `backend/tests/integration/test_knowledge_flow.py` — 保持 knowledge-check 语义与 support runtime 共用 helper 后仍然稳定。
