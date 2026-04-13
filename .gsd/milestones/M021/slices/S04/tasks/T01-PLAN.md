---
estimated_steps: 2
estimated_files: 5
skills_used: []
---

# T01: 识别需要显式化的 quality/cost/failure events

- 盘点当前默认分数、默认报告文案、fallback 行为和粗粒度 cost tracking 的真实落点。
- 明确哪些 failure/degradation 需要成为质量事件（例如 kb lock、report generation failed、prompt compile failed、provider rejected、fallback answer）。

## Inputs

- `S01-S03 outputs`
- `current fallback behaviors`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/common/ai/llm_service.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`

## Verification

rg -n "default|fallback|NO_STAGE_RESULTS|cost|report_generation_failed|knowledge_answer|degraded|claim_truth" backend/src/common backend/src/sales_bot backend/src/evaluation
