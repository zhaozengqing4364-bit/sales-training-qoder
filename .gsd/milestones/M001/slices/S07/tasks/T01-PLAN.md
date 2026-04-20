---
estimated_steps: 5
estimated_files: 5
skills_used:
  - safe-grow
  - test-driven-development
  - systematic-debugging
  - code-refactoring
  - verification-before-completion
---

# T01: 收稳 PPT 页级证据写入并抽出统一 presentation review builder

**Slice:** S07 — PPT 对练会后统一复盘可用化
**Milestone:** M001

## Description

这个任务先把 presentation evidence authority 收稳。当前 StepFun 路径已经会把 `transcript_metadata.page_number` 写进消息，但 legacy `PresentationWebSocketHandler` 在 `_update_message_analysis(...)` 时没有把页码透传给 `MessageStorageService.update_analysis(...)`，导致同一类 completed presentation session 在不同 runtime 下会有不同的逐页证据能力。与此同时，`PresentationReportService` 虽然已经能生成六维分数、逐页总结、优势/改进点和建议，但这些 facts 还没有一个明确的 normalized payload builder 可供 shared `/practice/sessions/{id}/report` 直接复用。T01 的目标是把这两个前提收成一条线：不论 legacy 还是 StepFun，都能稳定沉淀 page evidence；不论 shared report 还是 enhanced report，都能从同一个 PPT review builder 取事实。

## Steps

1. 先在 `backend/tests/unit/test_presentation_handler_persistence.py`、`backend/tests/unit/test_presentation_stepfun_realtime_handler.py` 和 `backend/tests/unit/evaluation/test_comprehensive_report_service.py` 写/补 failing tests，分别锁住 legacy 页码持久化、StepFun 现有页码 contract 不回退、以及 normalized presentation review payload 的字段形状与 degraded 行为。
2. 在 `backend/src/presentation_coach/services/presentation_report_service.py` 增加一个可复用的 normalized review payload builder，至少覆盖：六维评分、逐页总结、required talking point coverage、forbidden/missing/vague 计数、strengths/improvements/recommendations，以及 `has_page_metadata` / degradation diagnostics。
3. 保持 `build_report(...)` 继续服务现有 enhanced report，但让它复用新的 normalized builder，而不是并行维护另一套 metrics/summary 计算。
4. 在 `backend/src/presentation_coach/websocket/presentation_handler.py` 把 `self.current_page` 通过 `transcript_metadata.page_number` 传入 `_update_message_analysis(...)`，沿用 `backend/src/common/conversation/storage.py` 现有 `update_analysis(...)` 参数，不新增第二条持久化通路。
5. 跑 backend unit suites，确认 legacy 与 StepFun 都能落页码，且 presentation review builder 在缺历史页码时输出显式 degraded payload，而不是抛异常或静默补 sales 语义。

## Must-Haves

- [ ] `backend/src/presentation_coach/services/presentation_report_service.py` 必须成为 PPT 评分、逐页总结、coverage/diagnostics 与建议的唯一 authority；不能在 shared report path 或前端再写第二套 heuristics。
- [ ] `backend/src/presentation_coach/websocket/presentation_handler.py` 必须像 StepFun 路径一样持久化 `transcript_metadata.page_number`，保证 legacy presentation session 不会因为 runtime 差异丢掉逐页 evidence。
- [ ] normalized presentation review payload 必须自带 degraded 诊断（例如 `has_page_metadata=false` / 缺 coverage 说明），以便后续 contract 和 UI 显式降级，而不是回退到 sales 文案。

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/evaluation/test_comprehensive_report_service.py tests/unit/test_presentation_handler_persistence.py tests/unit/test_presentation_stepfun_realtime_handler.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_handler_persistence.py -k page_number`

## Observability Impact

- Signals added/changed: presentation review builder 需要输出可区分 happy-path / degraded-path 的 completeness diagnostics；legacy handler page metadata persistence 需要让后续 projection 能从 `ConversationMessage.transcript_metadata.page_number` 读到统一事实。
- How a future agent inspects this: 查看 `backend/tests/unit/test_presentation_handler_persistence.py`、`backend/tests/unit/test_presentation_stepfun_realtime_handler.py`、`backend/tests/unit/evaluation/test_comprehensive_report_service.py`，并从数据库里的 `conversation_messages.transcript_metadata` 校验页码。
- Failure state exposed: 缺页码历史数据时 builder 返回显式 degraded presentation review，而不是抛出空 payload 或掉回 sales semantics。

## Inputs

- `backend/src/presentation_coach/services/presentation_report_service.py` — 当前已经计算六维分数、逐页总结与建议，但还没有 shared report 可直接消费的 normalized payload。
- `backend/src/presentation_coach/websocket/presentation_handler.py` — legacy presentation runtime，当前 `_update_message_analysis(...)` 还没传 `transcript_metadata.page_number`。
- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py` — StepFun presentation runtime，已是 page metadata 正确写入的对照面。
- `backend/src/common/conversation/storage.py` — `update_analysis(...)` 已支持 `transcript_metadata`，说明 legacy 修复应止于 handler。
- `backend/tests/unit/evaluation/test_comprehensive_report_service.py` — 现有 presentation report authority 的 unit guardrail。
- `backend/tests/unit/test_presentation_handler_persistence.py` — 最适合补 legacy page metadata persistence proof 的单测文件。
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` — StepFun page context/persistence parity 的现有 unit baseline。

## Expected Output

- `backend/src/presentation_coach/services/presentation_report_service.py` — 可复用的 normalized `presentation_review` builder，并让 existing report path 共用这套事实。
- `backend/src/presentation_coach/websocket/presentation_handler.py` — legacy runtime 持久化 `transcript_metadata.page_number`。
- `backend/tests/unit/evaluation/test_comprehensive_report_service.py` — 锁住 normalized presentation review payload 与 degraded 行为。
- `backend/tests/unit/test_presentation_handler_persistence.py` — 锁住 legacy page metadata persistence。
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py` — 继续锁住 StepFun page metadata / review parity，不让修复把现有正确路径带坏。
