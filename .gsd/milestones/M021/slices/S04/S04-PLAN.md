# S04: AI quality/cost/failure events 与 knowledge path 收口

**Goal:** 把 AI runtime/control-plane 的质量、成本、失败事件显式化，并收敛 knowledge-answer 运行路径。
**Demo:** After this: AI 失败、降级、成本、知识问答路径会以显式质量事件落盘/出现在诊断面，默认分数和默认文案不再掩盖问题。

## Must-Haves

- quality/cost/failure events 有明确 schema 和 inspection surface。
- knowledge-answer 双轨/影子路径被收敛到一个可解释的 live+compat 模式。
- 默认分数、默认文案、静默 fallback 会被显式标成 degraded/failure，而不是伪装成功。

## Proof Level

- This slice proves: final-assembly

## Integration Closure

S04 是 M021 的 final assembly slice；完成后 M022 可以在真实 quality/cost/evidence 之上做销售产品化，而不是继续包装默认分数和静默 fallback。

## Verification

- future agents 可直接检查 cost/quality/failure events、knowledge-answer runs、claim-truth degradation，而不是反推默认分数。

## Tasks

- [x] **T01: 识别需要显式化的 quality/cost/failure events** `est:45m`
  - 盘点当前默认分数、默认报告文案、fallback 行为和粗粒度 cost tracking 的真实落点。
- 明确哪些 failure/degradation 需要成为质量事件（例如 kb lock、report generation failed、prompt compile failed、provider rejected、fallback answer）。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/ai/llm_service.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/common/knowledge_engine`, `backend/src/evaluation/services`
  - Verify: rg -n "default|fallback|NO_STAGE_RESULTS|cost|report_generation_failed|knowledge_answer|degraded|claim_truth" backend/src/common backend/src/sales_bot backend/src/evaluation

- [ ] **T02: 落地 unified quality/cost/failure events 与 knowledge path mode** `est:2.5h`
  - 设计并落地 quality/cost/failure event schema，让 runtime、report/read-side、knowledge-answer runs 共用同一条可检查的事件线。
- 收敛 knowledge-answer dual-run/shadow 路径到明确的 live+compat mode，并把 event 写入 diagnostics/run history。
- 保持不泄露 secret/base_url/token 等敏感信息。
  - Files: `backend/src/common/knowledge_engine`, `backend/src/common/ai/llm_service.py`, `backend/src/sales_bot/websocket/components`, `backend/src/support/api/runtime_status.py`, `backend/src/common/conversation/runtime_diagnostics.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/integration/test_knowledge_flow.py backend/tests/integration/test_websocket_status_contract.py -x -q

- [ ] **T03: 把 quality/cost/failure event 读法写回 support 与前端 proof** `est:45m`
  - 更新 support/runtime、report/replay docs、architecture scan，明确如何读这些事件以及如何区分 degraded / failure / compat。
- 前端如已展示对应降级状态，补 focused assertions，确保不是继续把失败翻译成‘低质量成功’。
  - Files: `docs/api-contract/support-runtime.md`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" && rg -n "quality|cost|failure|degraded|compat" docs/api-contract/support-runtime.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/ai/llm_service.py
- backend/src/sales_bot/websocket/stepfun_realtime_handler.py
- backend/src/common/knowledge_engine
- backend/src/evaluation/services
- backend/src/sales_bot/websocket/components
- backend/src/support/api/runtime_status.py
- backend/src/common/conversation/runtime_diagnostics.py
- docs/api-contract/support-runtime.md
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
