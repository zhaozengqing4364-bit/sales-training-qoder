# S07: PPT 对练会后统一复盘可用化

**Goal:** 让完成一轮 PPT 对练的学员从共享 `/practice/{sessionId}/report` 入口拿到基于真实课件/页级证据的统一复盘，而不是 sales 语义 fallback 或只靠可缺失的 enhanced report。
**Demo:** 对一个 completed presentation session，`GET /api/v1/practice/sessions/{id}/report` 返回 `scenario_type="presentation"` 与 canonical `presentation_review` payload；legacy 与 StepFun 两条 runtime 都能稳定沉淀 `transcript_metadata.page_number`；`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 渲染六维 PPT 评分、逐页总结、要点覆盖/缺失与建议，同时不再显示 `销售推进结果`、`销售推进基线`、`知识库命中检测` 这类 sales-only 区块，并保留带 `presentation_id` 的再练入口。
**Requirements:** Advances active `R005` and `R011`; retires the roadmap’s S07 risk by making PPT post-session review canonical, material-aware, and usable from the shared report entrypoint instead of a second truth surface.

## Must-Haves

- `backend/src/common/api/practice.py` 的共享 `/practice/sessions/{id}/report` 必须成为 presentation 会后复盘的权威读入口：顶层暴露 `scenario_type`，并附带从真实 PPT/page evidence 构建的 `presentation_review`，而不是继续让 PPT core facts 只存在于 `/evaluation/sessions/{id}/report`。
- `backend/src/presentation_coach/websocket/presentation_handler.py` 与 `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` 必须都能稳定落 `transcript_metadata.page_number`；S07 不能默默把 proof 缩成 StepFun-only，也不能让 legacy completed sessions继续因为缺页码而退回 sales 语义。
- `backend/src/presentation_coach/services/presentation_report_service.py` 必须继续做 PPT 评分/逐页总结/建议的唯一 authority；不要在前端或共享 API 再发明第二套 PPT scorer，也不要把 presentation 语义硬塞进 sales `pass_flags.pass_3min_flow` 之类既有 key。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 必须按 `scenario_type` 分支渲染：presentation 场景展示 PPT 复盘并跳过 knowledge-check/sales-only cards；sales 场景保持现状，不引入 unrelated churn。
- 缺少历史页码 evidence 的旧 presentation session 仍要保持 presentation-shaped degraded contract：允许 overall score/建议存在，但必须显式提示逐页总结/coverage 不完整，不能掉回销售问题/下一轮目标文案。

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py -k degrades_without_page_metadata`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_presentation_report_flow.py -k degraded`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
- Runtime/UAT — 在本地 stack 完成一次带翻页的 presentation session，打开 `/practice/{sessionId}/report`，确认页面展示 PPT 评分/逐页总结/覆盖提示与建议，隐藏 `销售推进结果`、`销售推进基线`、`知识库命中检测`，且“按目标再练一轮”沿用同一 `presentation_id`。

## Observability / Diagnostics

- Runtime signals: `practice_session_evidence_projection_built` 需要能暴露 scenario-aware completeness；presentation report builder / report route 需要记录 `scenario_type=presentation`、page metadata completeness 与 degraded fallback 原因；前端 report page 需要保留 scenario-aware load/skip diagnostics（presentation 不发 knowledge-check 请求）。
- Inspection surfaces: `GET /api/v1/practice/sessions/{id}/report`, `backend/tests/contract/test_presentation_report_contract.py`, `backend/tests/integration/test_presentation_report_flow.py`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`.
- Failure visibility: 缺页码或缺逐页 evidence 时，API 返回显式 degraded `presentation_review` completeness/coverage 状态；页面显示 presentation-specific 降级文案，而不是退回 sales cards 或静默缺块。
- Redaction constraints: 只复用已存在的 session / page / required talking point / forbidden-word事实，不把 transcript 原文、知识库全文或其他敏感内容额外暴露到新 contract。

## Integration Closure

- Upstream surfaces consumed: `backend/src/presentation_coach/services/presentation_report_service.py`, `backend/src/presentation_coach/websocket/presentation_handler.py`, `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`, `backend/src/common/conversation/storage.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/db/schemas.py`, `backend/src/common/api/practice.py`, `web/src/lib/api/types.ts`, `web/src/lib/session-evidence.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`.
- New wiring introduced in this slice: `PresentationReportService` normalized review payload -> shared `SessionReport` / `PracticeSessionReport` scenario-aware contract -> shared report page presentation branch with request gating and degraded fallback copy.
- What remains before the milestone is truly usable end-to-end: single-session PPT postmortem should be canonical after S07; milestone-level final assembly, broader launch diagnostics, and release proof still belong to S08.

## Tasks

- [x] **T01: 收稳 PPT 页级证据写入并抽出统一 presentation review builder** `est:3h`
  - Why: 如果 legacy runtime 继续漏写 `page_number`，或者 PPT 评分/逐页总结还散在 report builder 里没有可复用 payload，后面的 canonical report contract 只能继续猜测或退回 StepFun-only。
  - Files: `backend/src/presentation_coach/services/presentation_report_service.py`, `backend/src/presentation_coach/websocket/presentation_handler.py`, `backend/src/common/conversation/storage.py`, `backend/tests/unit/evaluation/test_comprehensive_report_service.py`, `backend/tests/unit/test_presentation_handler_persistence.py`, `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
  - Do: 先写 failing unit tests 锁住 legacy/StepFun page metadata parity 与 presentation review payload shape；在 `PresentationReportService` 中抽出可复用的 normalized review payload builder（六维评分、逐页总结、coverage/forbidden/vague counts、strengths/improvements/recommendations）；然后补 `presentation_handler.py` 把 `transcript_metadata.page_number` 传入 `MessageStorageService.update_analysis(...)`，保持 StepFun 和 legacy 共用同一页级事实前提。
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py`
  - Done when: legacy 和 StepFun 两条 presentation runtime 都能稳定持久化页码证据，且 `PresentationReportService` 能产出可被 shared report contract 直接复用的 normalized PPT review payload。
- [x] **T02: 把 shared session report contract 扩成 scenario-aware presentation baseline** `est:4h`
  - Why: 只有把 PPT 复盘事实接入 S02 的 canonical `/practice/sessions/{id}/report`，R005/R011 才是真正前进；否则用户一旦 enhanced report 缺失，页面仍会回到 sales snapshot。
  - Files: `backend/src/common/conversation/session_evidence.py`, `backend/src/common/db/schemas.py`, `backend/src/common/api/practice.py`, `backend/tests/contract/test_presentation_report_contract.py`, `backend/tests/integration/test_presentation_report_flow.py`, `web/src/lib/api/types.ts`
  - Do: 先写 failing contract/integration tests，锁住 presentation happy-path 与 degraded historical-path；随后扩展 `SessionReport` / `PracticeSessionReport` 合同，新增 top-level `scenario_type` 与 `presentation_review` payload，复用 T01 的 builder 在 `SessionEvidenceService` / `practice.py` 中注入 scenario-aware facts，并保持 sales contract 不变；degraded presentation sessions 必须继续返回 presentation-shaped payload，而不是复用 sales `main_issue` / `next_goal` 语义。
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
  - Done when: `GET /api/v1/practice/sessions/{id}/report` 对 presentation session 返回 `scenario_type="presentation"` + canonical `presentation_review`，且缺页码历史数据只会触发 presentation-specific degraded contract，不会回退到 sales baseline。
- [ ] **T03: 让共享 report page 按 scenario_type 渲染 PPT 会后复盘** `est:3h`
  - Why: backend 即使已经返回 canonical `presentation_review`，如果 report page 继续无条件拉 knowledge-check 并渲染 sales cards，学员实际仍看不到 slice demo。
  - Files: `web/src/lib/api/types.ts`, `web/src/lib/session-evidence.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - Do: 先写 failing presentation-focused page tests，锁住 PPT 评分/逐页总结/coverage/recommendations 展示、sales-only affordances 缺席、retry 继续带 `presentation_id`；再把页面加载/渲染改成基于 `report.scenario_type` 分支，在 presentation 场景跳过 knowledge-check 请求并展示 canonical `presentation_review`，同时保留 existing `GlassCard`/`Button` 体系和 enhanced report/highlights 的 optional layering。
  - Verify: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
  - Done when: `/practice/{sessionId}/report` 的 presentation 分支展示真实 PPT 复盘且不再出现 sales-only cards/knowledge diagnostics，即使 enhanced report 暂不可用也不会掉回 sales UI。

## Files Likely Touched

- `backend/src/presentation_coach/services/presentation_report_service.py`
- `backend/src/presentation_coach/websocket/presentation_handler.py`
- `backend/src/common/conversation/storage.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/evaluation/test_comprehensive_report_service.py`
- `backend/tests/unit/test_presentation_handler_persistence.py`
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
- `backend/tests/contract/test_presentation_report_contract.py`
- `backend/tests/integration/test_presentation_report_flow.py`
- `web/src/lib/api/types.ts`
- `web/src/lib/session-evidence.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
