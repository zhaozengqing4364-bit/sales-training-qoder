---
id: T02
parent: S02
milestone: M001
provides:
  - Shared session evidence projection for completed-session report/replay reads, with legacy `score_snapshot.overall` normalization, stage rollups, and evaluability/completeness diagnostics
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - D014: Session-level overall is always projected from logic/accuracy/completeness, while legacy/new turn snapshots are normalized behind one reader contract with explicit completeness diagnostics
patterns_established:
  - Consumers that need session evidence read `SessionEvidenceService` instead of reassembling `PracticeSession` and `ConversationMessage` separately
  - Projection responses expose `evaluable`, `not_evaluable_reason`, `stage_summary`, and `evidence_completeness` so drift can be localized to write-layer vs reader-layer vs consumer bypass
observability_surfaces:
  - `practice_session_evidence_projection_built`
  - `/api/v1/practice/sessions/{id}/report` evidence fields
  - `/api/v1/sessions/{id}/replay` evidence fields
  - `backend/tests/unit/test_session_evidence_service.py`
duration: 15m
verification_result: passed
completed_at: 2026-03-23T04:54:55+08:00
blocker_discovered: false
---

# T02: 建立共享会话证据读模型并收口报告/回放

**Added a shared `SessionEvidenceService` that projects one normalized evidence view for completed sessions, then switched quick report and replay to read that same projection.**

## What Happened

新增了 `backend/src/common/conversation/session_evidence.py`，把 `PracticeSession` + ordered `ConversationMessage` 的读取、legacy `score_snapshot.overall` 兼容、session-level overall 计算、阶段汇总、逐轮证据序列化、effectiveness snapshot 补齐，以及 `evidence_completeness` 诊断都收进一个显式读模型里。

`ReplayService.get_replay_data()` 已改为通过这层 projection 组装返回值，不再自己直接算 stage summary / total duration / top-line metadata；replay 响应现在直接带出 `overall_score`、`main_issue`、`next_goal`、`evaluable`、`not_evaluable_reason`、`evidence_completeness`，并对逐轮 `score_snapshot` 统一输出 canonical `overall_score` 读形。

`GET /practice/sessions/{id}/report` 也改成读取同一 projection，quick report 不再直接从 `PracticeSession` 顶层字段手拼 evidence。为了承接这个 contract，同步扩了 replay/report 的 schema，并补了 unit / contract / integration tests，锁住 report/replay 在同一 completed session 上的 overall、stage summary、result metadata 对齐，以及 replay 的 completed-session gate / access control 不回退。

## Verification

Passed:
- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py`
- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py`

Slice-level downstream checks still pending later tasks and were run truthfully:
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py` → failed because `tests/unit/test_history_service_evidence_projection.py` does not exist yet (owned by T03)
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'` → failed because those page test files do not exist yet (owned by T04)

Additional behavior locked by tests:
- report/replay align on `overall_score`, `main_issue`, `next_goal`, `not_evaluable_reason`
- legacy `score_snapshot.overall` still reads correctly without backfill
- replay keeps completed-session gating and owner-only access semantics
- projection emits `practice_session_evidence_projection_built` with session/message/completeness diagnostics

## Diagnostics

后续排查先看：
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_session_evidence_service.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

关键诊断面：
- 结构化日志 `practice_session_evidence_projection_built`：`session_id`、`message_count`、`legacy_score_key_used`、`projection_complete`、`projection_missing_fields`
- report / replay 响应里的 `evaluable`、`not_evaluable_reason`、`stage_summary`、`evidence_completeness`

如果后续 history/trends 仍漂，先确认它们是否真的改成消费 `SessionEvidenceService`，再看 `evidence_completeness` 是缺 session scores、缺 effectiveness snapshot，还是 legacy turn evidence 在回退。

## Deviations

None.

## Known Issues

- S02 的 T03/T04 验证命令仍然失败，因为对应 backend/web test files 还未创建；这不是本任务回归，而是后续任务尚未落地。
- Web types/page tests 还没切到新的 evidence fields，留待 T04 收口。

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py` — 新增共享 session evidence projection service 与 completeness / legacy fallback diagnostics
- `backend/src/common/conversation/replay.py` — replay 改读共享 projection，并对外暴露统一 evidence metadata
- `backend/src/common/api/practice.py` — quick report 改读共享 projection
- `backend/src/common/conversation/schemas.py` — 扩展 replay/score snapshot schema 以承接 canonical score + evidence fields
- `backend/src/common/db/schemas.py` — 扩展 quick report schema 的 stage/evaluable/completeness 字段
- `backend/tests/unit/test_session_evidence_service.py` — 锁定 projection build、legacy fallback 与 observability log
- `backend/tests/unit/test_replay_service.py` — 锁定 replay 对 projection metadata/legacy snapshot normalization 的消费
- `backend/tests/contract/test_practice_evidence_contract.py` — 锁定 report/replay contract 对齐及 gating/access control 不变
- `backend/tests/integration/test_practice_evidence_flow.py` — 锁定 completed session 的 legacy evidence fallback 端到端行为
- `.gsd/DECISIONS.md` — 追加 D014，记录共享 projection 的 reader contract
- `.gsd/milestones/M001/slices/S02/S02-PLAN.md` — 标记 T02 完成
