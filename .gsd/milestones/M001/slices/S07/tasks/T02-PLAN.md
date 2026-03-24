---
estimated_steps: 5
estimated_files: 6
skills_used:
  - safe-grow
  - test-driven-development
  - best-practices
  - code-refactoring
  - verification-before-completion
---

# T02: 把 shared session report contract 扩成 scenario-aware presentation baseline

**Slice:** S07 — PPT 对练会后统一复盘可用化
**Milestone:** M001

## Description

这个任务把 T01 的 PPT review authority 真正接到 S02 的统一事实线里。当前 `GET /api/v1/practice/sessions/{id}/report` 只会把 `SessionEvidenceService` 的 sales-shaped top line 填进 `SessionReport`，presentation session 即使已经有 `presentation_id` 和 enhanced report，也仍然只能拿到 generic `pass_flags` / `main_issue` / `next_goal`。S07 要改的是 canonical contract，而不是再开一个 presentation-only 页面或 API：shared report response 需要顶层 `scenario_type`，并在 presentation 场景下附带 `presentation_review` payload；sales contract 继续保持现状。这样 PPT postmortem 的 core facts 才能沿同一证据线走到 shared page，而不是只存在于 optional enhancement。

## Steps

1. 新建/补齐 `backend/tests/contract/test_presentation_report_contract.py` 与 `backend/tests/integration/test_presentation_report_flow.py` 的 failing tests，锁住 shared `/practice/sessions/{id}/report` 在 presentation happy-path 和 degraded historical-path 下的 canonical contract：`scenario_type`、`presentation_review` 字段、retry `presentation_id`、以及 sales-only fields 不再被误用为 PPT 结论。
2. 扩展 `backend/src/common/db/schemas.py` 的 `SessionReport` 与 `web/src/lib/api/types.ts` 的 `PracticeSessionReport` / `SessionEvidenceContract`，新增 top-level `scenario_type` 和 `presentation_review` 类型；presentation-specific 事实必须放进新 payload，而不是重映射到 sales `pass_flags` / `main_issue` / `next_goal` key 名。
3. 在 `backend/src/common/conversation/session_evidence.py` 引入 scenario-aware branch：识别 presentation session，复用 T01 的 builder 注入 `presentation_review`，并让 evidence completeness 明确暴露 page metadata / coverage 是否完整；sales session 仍维持现有 projection semantics。
4. 更新 `backend/src/common/api/practice.py` 的 shared report route，把 `scenario_type`、`presentation_review` 和 existing `retry_entry.presentation_id` 一起返回；如果 enhanced report path 仍需 presentation facts，也要沿同一 builder 读，避免 shared report 与 `/evaluation/.../report` 再次各算各的。
5. 跑 backend contract / integration suites，确认 historical presentation sessions 在缺页码时仍返回 presentation-shaped degraded payload，且 API failure visibility 明确告诉后续 agent 是 evidence 不完整，而不是前端回退问题。

## Must-Haves

- [ ] `GET /api/v1/practice/sessions/{id}/report` 必须在 top-level 返回 `scenario_type`，并在 presentation session 返回 canonical `presentation_review`；PPT core facts 不能继续只存在于 `/evaluation/sessions/{id}/report`。
- [ ] `backend/src/common/db/schemas.py` 和 `web/src/lib/api/types.ts` 需要用新字段承载 presentation 语义；不能把 PPT 结论硬塞进 sales `pass_flags.pass_3min_flow` / `main_issue` / `next_goal` 的既有名字。
- [ ] 缺历史页码 evidence 的旧 presentation session 必须返回显式 degraded `presentation_review`（例如 coverage 不完整、逐页总结缺失），但整体 contract 仍保持 `scenario_type="presentation"`，不能掉回 sales fallback。

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_presentation_report_flow.py -k degraded`

## Observability Impact

- Signals added/changed: shared report route 需要记录 `scenario_type`、presentation review completeness / degraded reason，以及 projection 是否缺 page metadata；`practice_session_evidence_projection_built` 应能帮助定位是 builder 缺事实还是 route/consumer 没接线。
- How a future agent inspects this: 直接请求 `GET /api/v1/practice/sessions/{id}/report`，并对照 `backend/tests/contract/test_presentation_report_contract.py` 与 `backend/tests/integration/test_presentation_report_flow.py`。
- Failure state exposed: historical presentation sessions 的 page-level evidence 缺失会以 `presentation_review` completeness/coverage 降级体现，而不是静默回退到 sales `main_issue` / `next_goal`。

## Inputs

- `backend/src/presentation_coach/services/presentation_report_service.py` — T01 产出的 normalized `presentation_review` authority。
- `backend/src/common/conversation/session_evidence.py` — S02 统一 evidence projection 的现有实现，当前仍是 sales-first。
- `backend/src/common/db/schemas.py` — `SessionReport` 当前缺少 `scenario_type` 和 presentation-specific payload。
- `backend/src/common/api/practice.py` — shared `/practice/sessions/{id}/report` 当前只映射 sales-shaped projection 字段。
- `web/src/lib/api/types.ts` — shared report contract 的前端类型边界，需要和 backend schema 同步演进。
- `backend/tests/contract/test_practice_evidence_contract.py` — 现有 sales contract baseline，可作为新 presentation contract 的参照。

## Expected Output

- `backend/src/common/conversation/session_evidence.py` — scenario-aware projection，presentation session 可附带 canonical `presentation_review`。
- `backend/src/common/db/schemas.py` — `SessionReport` 新增 `scenario_type` 与 `presentation_review` schema。
- `backend/src/common/api/practice.py` — shared report route 返回 scenario-aware presentation baseline。
- `backend/tests/contract/test_presentation_report_contract.py` — 锁住 canonical presentation report contract。
- `backend/tests/integration/test_presentation_report_flow.py` — 锁住 shared report happy-path / degraded-path 的端到端证明。
- `web/src/lib/api/types.ts` — shared report contract 的前端类型更新，与 backend schema 保持一致。
