# S08: 桌面端发布验收与可观测性收口

**Goal:** 把 `/support/runtime` 收成可信的桌面端发布健康面，并用它重新串起 sales runtime、canonical report、主管趋势页、PPT 会后复盘这四条已完成能力，给出“可以真实给团队用”的最后发布证明。
**Demo:** support/admin 用户打开 `/support/runtime` 时，看到的不是粗粒度日志计数，而是基于 persisted session evidence、knowledge/runtime diagnostics、presentation degraded reasons 的 blocking/warning 发布健康摘要；`status="scoring"` 不再被算作已完成；支持页能列出最近需要处理的异常类型与会话标识。随后按 S08 UAT 波次重跑 sales runtime reconnect/end-failure、canonical sales report、`/admin/users/{id}`、PPT postmortem happy/degraded、`/support/runtime` 五条真实路径，且 support/runtime 上看到的 blocking/warning 语义与这些真实路径中的 failure mode 一致。
**Requirements:** 本 slice 不推进新的 Active requirement；它重新证明已验证的 `R001`、`R002`、`R003`、`R005`、`R007`、`R008` 在同一桌面端发布故事下仍然成立，并继续强化 `R011` 的“单一 evidence truth line”约束。

## Must-Haves

- `/api/v1/support/runtime/overview` 与 `/api/v1/support/runtime/faults` 必须改为基于 `PracticeSession`、`ConversationMessage`、`SessionEvidenceService`、`voice_policy_snapshot.runtime_metrics` 与 `presentation_review` 语义聚合发布健康，而不是继续把 `SystemLog` 计数当成主要事实源。
- support runtime health 必须把 `status="scoring"` 从“已完成”里拆出来，并能区分普通 scoring 与 stuck scoring；不能再用 completion rate 假装终态健康。
- support runtime 的异常分类必须复用 canonical 读面已有语义：knowledge-check 的 `search_failed` / `kb_not_ready` / `kb_lock_status` / `upstream_unstable`，以及 presentation report 的 `missing_page_metadata` degraded reason，避免再发明第二套支持面分类。
- `web/src/app/(dashboard)/support/runtime/page.tsx` 必须把 blocking vs warning 明确分层，并展示 typed anomaly list、局部 empty/error 状态与只读刷新行为；不要新增会绕过 RBAC 的 learner report 直链。
- S08 的完成证明必须是 fresh release proof：backend/web 回归套件通过，且本地真实波次验证覆盖 sales runtime、canonical report、主管趋势、PPT report、support runtime 五个面，并写入 `.gsd/milestones/M001/slices/S08/S08-UAT.md`。

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts'`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'`
- `cd backend && venv/bin/alembic upgrade head`
- Runtime/UAT — 按 `.gsd/milestones/M001/slices/S08/S08-UAT.md` 重新完成五波本地验证：sales runtime reconnect/end-failure、canonical sales report（含 optional enhancement degraded 只算 warning）、`/admin/users/{id}` supervisor trend、PPT report happy/degraded、`/support/runtime` blocking/warning anomaly surfacing；浏览器与 backend 均保持 `localhost` 对齐，并在需要时先补 `python-socks`。

## Observability / Diagnostics

- Runtime signals: `practice_session_evidence_projection_built`、`practice_session_report_built`、`practice_history_projection_query` 继续作为 canonical evidence signals；support runtime 新增 typed release-health counters 与 anomaly severity/kind summary，用 persisted session data 暴露 `stuck_scoring`、`projection_failed`、`not_evaluable_completed`、`presentation_degraded_missing_page_metadata`、`knowledge_search_failed`、`kb_not_ready`、`kb_lock_blocked_*`、`upstream_unstable`、`optional_report_failed`。
- Inspection surfaces: `/api/v1/support/runtime/overview`、`/api/v1/support/runtime/faults`、`GET /api/v1/practice/sessions/{id}/report`、`GET /api/v1/practice/sessions/{id}/knowledge-check`、`GET /api/v1/admin/users/{id}/progress`、`/practice/{sessionId}`、`/practice/{sessionId}/report`、`/admin/users/{id}`、`/support/runtime`。
- Failure visibility: support runtime anomaly items 必须包含 severity、kind、summary、detected_at，以及必要的 `session_id` / `scenario_type` / compact diagnostic fields；前端页面必须保留局部加载失败和 empty state，而不是整页白屏或假绿。
- Redaction constraints: support/runtime 只能暴露会话标识、场景、状态、compact diagnostics 与 degraded reasons；不得把 transcript 原文、知识库正文、PII 或敏感上游错误栈直接展开到支持页。

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/conversation/session_evidence.py`, `backend/src/common/analytics/history_service.py`, `backend/src/common/api/practice.py`, `backend/src/presentation_coach/services/presentation_report_service.py`, `backend/src/support/api/runtime_status.py`, `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/app/(dashboard)/support/runtime/page.tsx`.
- New wiring introduced in this slice: shared runtime diagnostics helper from canonical practice semantics -> support runtime backend service -> typed support runtime API contract -> release-health support page -> slice-close S08 UAT wave that composes S01/S03/S05/S06/S07 live surfaces.
- What remains before the milestone is truly usable end-to-end: nothing inside M001 if this slice’s verification and live release waves pass; later milestones may optionally backfill durable release-candidate recording into the generic `release_verification` subsystem, but S08 itself should close the launch story.

## Tasks

- [x] **T01: 用统一 evidence truth line 重写 support runtime 后端健康读模型** `est:3h`
  - Why: S08 的核心风险不是“少一个页面”，而是 support/runtime 现在会把 `scoring` 算成完成、把 `SystemLog` 算成健康真相，导致发布验收可能出现假绿。
  - Files: `backend/src/support/services/runtime_status_service.py`, `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/support/api/runtime_status.py`, `backend/tests/unit/test_support_runtime_service.py`, `backend/tests/contract/test_support_runtime.py`, `backend/tests/integration/test_support_runtime_api.py`, `backend/tests/integration/test_knowledge_flow.py`
  - Do: 先写 failing backend tests 锁住 release-health summary、typed anomaly severity 与 knowledge/presentation semantics；从 `backend/src/common/api/practice.py` 抽共享 runtime diagnostics helper，复用 knowledge-check 的 `status` / `kb_lock_status` / upstream instability 语义；新增 support runtime service，批量读取 recent sessions + messages，通过 `SessionEvidenceService.build_projection(...)` 与 persisted runtime/report data 分类 `stuck_scoring`、`projection_failed`、`not_evaluable_completed`、`presentation_degraded_missing_page_metadata`、`knowledge_search_failed`、`kb_not_ready`、`kb_lock_blocked_*`、`upstream_unstable`、`optional_report_failed`；最后让 `runtime_status.py` 只做 RBAC + response shaping，并停止把 `status="scoring"` 计为已完成。
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py && cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses`
  - Done when: support runtime overview/faults 改为 evidence-backed typed release health，knowledge-check / presentation degraded 语义不漂移，且 `scoring` 不再伪装成成功完成。
- [x] **T02: 把 `/support/runtime` 升级成 blocking/warning 发布健康面板** `est:2h`
  - Why: backend 即使已经给出可信 anomaly contract，如果 support/admin 页还只显示三张粗粒度卡片和原始 fault list，S08 仍然没有真正可用的运营可观测面。
  - Files: `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/app/(dashboard)/support/runtime/page.tsx`, `web/src/app/(dashboard)/support/runtime/page.test.tsx`
  - Do: 先写 focused page tests，覆盖 success、blocking-heavy、warning-only、load-failure 与 empty state；再扩展 typed API types/client，按新 contract 在页面上渲染发布健康摘要、blocking/warning 分层卡片、typed anomaly list、局部错误提示与刷新行为，并保持 support/admin 只读定位，不新增会绕过 `_can_read_session(...)` 的 learner report 深链。
  - Verify: `cd web && npm test -- --run 'src/app/(dashboard)/support/runtime/page.test.tsx'`
  - Done when: support/admin 用户能从 `/support/runtime` 直接判断“是否能发、为什么不能发、是哪类会话/场景出问题”，而不是再去猜 completion rate 或翻系统日志。
- [x] **T03: 复用既有 UAT 路径完成桌面端发布波次验收并落盘 S08 证据** `est:2h`
  - Why: S08 是 milestone final-assembly slice；如果不把 S01/S03/S05/S06/S07 的 live proof 重新串起来，support/runtime 再漂亮也不等于真正达到首发门槛。
  - Files: `.gsd/milestones/M001/slices/S01/S01-UAT.md`, `.gsd/milestones/M001/slices/S06/S06-UAT.md`, `.gsd/milestones/M001/slices/S07/S07-UAT.md`, `.gsd/milestones/M001/slices/S08/S08-UAT.md`
  - Do: 基于 S01/S06/S07 的现有 UAT 资产编写 S08 波次脚本，明确前置约束（`alembic upgrade head`、`localhost` host alignment、`python-socks`、presentation 禁用 websocket `type:"text"` shortcut）；按五波顺序重跑 sales runtime reconnect/end-failure、canonical sales report、`/admin/users/{id}`、PPT report happy/degraded、`/support/runtime`；把每波的 expected/actual、关键 session/user IDs、console/network/backend diagnostics、以及 support runtime 是否正确映射 blocking/warning 写入 `S08-UAT.md`。
  - Verify: `cd backend && venv/bin/alembic upgrade head && cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py && cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'`
  - Done when: `S08-UAT.md` 记录了 fresh 五波发布验收与 blocker/warning 结论，且 support/runtime 上看到的异常语义与真实链路观察一致。

## Files Likely Touched

- `backend/src/support/services/runtime_status_service.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/support/api/runtime_status.py`
- `backend/tests/unit/test_support_runtime_service.py`
- `backend/tests/contract/test_support_runtime.py`
- `backend/tests/integration/test_support_runtime_api.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `web/src/lib/api/types.ts`
- `web/src/lib/api/client.ts`
- `web/src/app/(dashboard)/support/runtime/page.tsx`
- `web/src/app/(dashboard)/support/runtime/page.test.tsx`
- `.gsd/milestones/M001/slices/S08/S08-UAT.md`
