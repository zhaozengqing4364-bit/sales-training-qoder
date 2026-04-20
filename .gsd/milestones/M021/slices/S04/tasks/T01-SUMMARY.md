---
id: T01
parent: S04
milestone: M021
key_files:
  - backend/src/common/ai/llm_service.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_ai_quality_event_inventory.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Use code-owned runtime inventory constants as the durable T01 output instead of leaving S04 discovery only in planner prose or one-off notes.
  - Keep knowledge-answer rollout/mode truth anchored to `common.knowledge_engine.compat` and document that S04 must extend that seam rather than invent a second engine-only truth line.
duration: 
verification_result: passed
completed_at: 2026-04-14T04:06:06.000Z
blocker_discovered: false
---

# T01: Cataloged hidden AI fallback, default-score, and cost/degradation paths into code-owned S04 event inventories.

**Cataloged hidden AI fallback, default-score, and cost/degradation paths into code-owned S04 event inventories.**

## What Happened

I executed T01 as a discovery-and-authority pass rather than a behavioral rewrite. First I re-ran the task’s grep contract and read the live `common.ai.llm_service`, `sales_bot.websocket.stepfun_realtime_handler`, `evaluation/services/*`, and `common.knowledge_engine.compat` seams to confirm where the shipped runtime still hides failures behind defaults or fallback copy. That audit showed three concrete blind spots that future S04 work should stop inferring indirectly: `LLMService.evaluate()` silently returns a successful 60/60/60/60/60 evaluation when model JSON parsing fails; `LLMService.generate()` and `generate_report()` still collapse multiple provider/config/report failures into filler text or coarse fallback strings; and the StepFun runtime already emits meaningful degradation signals (`KB lock warmup degraded`, `capability_pipeline_failed`, `browser_tts`, `blocked_transcription_timeout`, knowledge-answer rollout mode) but spreads them across logs, payload flags, and state-machine fields.

Following a fail-first TDD pass, I added `backend/tests/unit/test_ai_quality_event_inventory.py`, watched it fail because the runtime inventory constants did not exist yet, then introduced two code-owned discovery surfaces: `LLM_RUNTIME_EVENT_INVENTORY` in `backend/src/common/ai/llm_service.py` and `STEPFUN_RUNTIME_EVENT_INVENTORY` in `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`. These inventories do not invent new runtime behavior; they pin the currently shipped hiding spots to stable event ids, phases, triggers, current surfaces, and hidden risks so T02 can build one explicit event schema on top of known seams instead of re-researching them. I also wrote the same conclusions back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` as a dedicated M021/S04 inventory baseline, and added a focused `.gsd/KNOWLEDGE.md` gotcha noting that the 60-point evaluation path is a parse-default fallback, not a real mediocre score.

The key implementation decision was to treat this task as an authority write-back: code-owned inventories in the runtime files plus an architecture note, not yet a new event sink. That keeps the change low-blast-radius while still making the hidden failure/degradation/cost surfaces grep-discoverable for future agents and for the next task’s unified eventization work.

## Verification

I used a fail-first focused unit test to prove the new inventory surfaces exist and carry the intended event ids, then re-ran the task’s exact grep gate to ensure the broader backend fallback/degraded/cost/knowledge seams remain discoverable, and finally ran a focused architecture grep plus LSP diagnostics to confirm the write-back is durable and type-clean. Specifically: (1) `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_ai_quality_event_inventory.py -q` failed first because the inventory constants were missing, then passed after the implementation landed; (2) `rg -n "default|fallback|NO_STAGE_RESULTS|cost|report_generation_failed|knowledge_answer|degraded|claim_truth" backend/src/common backend/src/sales_bot backend/src/evaluation` completed successfully and still exposes the real runtime/default/fallback surfaces named by the plan; (3) `rg -n "quality / cost / failure inventory baseline|LLM_RUNTIME_EVENT_INVENTORY|STEPFUN_RUNTIME_EVENT_INVENTORY|default score 不等于真实低分|knowledge-answer path truth 仍必须沿 compat seam 读取" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/ai/llm_service.py backend/src/sales_bot/websocket/stepfun_realtime_handler.py` proved the code constants and architecture write-back are grep-discoverable; and (4) LSP diagnostics returned clean results for the touched Python files and the new unit test.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_ai_quality_event_inventory.py -q` | 0 | ✅ pass | 5877ms |
| 2 | `rg -n "default|fallback|NO_STAGE_RESULTS|cost|report_generation_failed|knowledge_answer|degraded|claim_truth" backend/src/common backend/src/sales_bot backend/src/evaluation` | 0 | ✅ pass | 38ms |
| 3 | `rg -n "quality / cost / failure inventory baseline|LLM_RUNTIME_EVENT_INVENTORY|STEPFUN_RUNTIME_EVENT_INVENTORY|default score 不等于真实低分|knowledge-answer path truth 仍必须沿 compat seam 读取" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/ai/llm_service.py backend/src/sales_bot/websocket/stepfun_realtime_handler.py` | 0 | ✅ pass | 29ms |

## Deviations

None. I stayed within the task’s discovery/write-back scope and did not start event-schema implementation early.

## Known Issues

None. The inventories intentionally document that unified eventization still remains for T02, but no new blocker or plan-invalidating mismatch was discovered.

## Files Created/Modified

- `backend/src/common/ai/llm_service.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_ai_quality_event_inventory.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
