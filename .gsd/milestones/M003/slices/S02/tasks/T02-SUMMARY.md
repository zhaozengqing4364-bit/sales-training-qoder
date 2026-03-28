---
id: T02
parent: S02
milestone: M003
provides: []
requires: []
affects: []
key_files: ["backend/src/sales_bot/services/voice_instruction_compiler.py", "backend/src/sales_bot/services/voice_runtime_policy.py", "backend/src/common/api/practice.py", "backend/src/sales_bot/websocket/stepfun_realtime_handler.py", "backend/tests/unit/test_voice_instruction_compiler.py", "backend/tests/integration/test_knowledge_flow.py", "backend/tests/unit/test_stepfun_realtime_handler.py", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Mirror the normalized Persona `customer_pressure` contract onto the top-level effective policy and persisted session snapshot while keeping `persona_policy.customer_pressure` as the canonical nested source.", "Compile structured `customer_pressure` directly into the runtime instruction contract, including evidence and revisit-on-evasion directives, instead of relying only on legacy flat sales-focus fields.", "When a StepFun session already has a persisted voice-policy snapshot, reconnect must trust that frozen snapshot rather than re-resolving live policy from admin config."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Followed a red-green cycle on the new behavior: the initial focused pytest run failed because the compiler ignored top-level structured pressure data and the created session snapshot had no `customer_pressure` field. After the implementation, the focused compiler/integration rerun passed. I then ran a focused StepFun unit test to verify reconnect now prefers the frozen session snapshot over live policy resolution. Finally, I ran the task’s planned verification gate exactly as written: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py`, and all 12 tests passed. LSP diagnostics on `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/common/api/practice.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, and the touched test files all returned `No diagnostics`."
completed_at: 2026-03-25T02:38:27.686Z
blocker_discovered: false
---

# T02: Freeze Persona pressure contracts into runtime snapshots and StepFun reconnects

> Freeze Persona pressure contracts into runtime snapshots and StepFun reconnects

## What Happened
---
id: T02
parent: S02
milestone: M003
key_files:
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - backend/src/sales_bot/services/voice_runtime_policy.py
  - backend/src/common/api/practice.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_voice_instruction_compiler.py
  - backend/tests/integration/test_knowledge_flow.py
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Mirror the normalized Persona `customer_pressure` contract onto the top-level effective policy and persisted session snapshot while keeping `persona_policy.customer_pressure` as the canonical nested source.
  - Compile structured `customer_pressure` directly into the runtime instruction contract, including evidence and revisit-on-evasion directives, instead of relying only on legacy flat sales-focus fields.
  - When a StepFun session already has a persisted voice-policy snapshot, reconnect must trust that frozen snapshot rather than re-resolving live policy from admin config.
duration: ""
verification_result: mixed
completed_at: 2026-03-25T02:38:27.688Z
blocker_discovered: false
---

# T02: Freeze Persona pressure contracts into runtime snapshots and StepFun reconnects

**Freeze Persona pressure contracts into runtime snapshots and StepFun reconnects**

## What Happened

I executed this task test-first. First I added a focused compiler unit test proving `VoiceInstructionCompiler` still ignored the structured `customer_pressure` contract when only the nested pressure model was present, and an integration test proving newly created sales sessions still lacked a runtime-level frozen `customer_pressure` snapshot even when two Personas shared the same knowledge base but carried different pressure behavior. Both checks failed for the expected reasons.

I then updated `backend/src/sales_bot/services/voice_instruction_compiler.py` so the base contract prefers the structured pressure model from `policy.customer_pressure` and falls back to `persona_policy.customer_pressure` / legacy projections. The compiled prompt now emits explicit pressure-direction, evidence, and revisit-on-evasion instructions instead of relying only on legacy flat sales-focus fields.

In `backend/src/sales_bot/services/voice_runtime_policy.py`, I mirrored the normalized nested `persona_policy.customer_pressure` onto the top-level effective policy and tagged `source.customer_pressure_source`, so the runtime and persisted session snapshot have one explicit pressure contract to inspect. In `backend/src/common/api/practice.py`, I preserved that contract through session creation and added a safe structured log line that records pressure-source/focus metadata and the instruction hash without logging prompt bodies.

While verifying the runtime chain, I found a real reconnect seam outside the planner snapshot: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` still re-resolved live policy on `_load_effective_policy()` whenever a session snapshot existed. That would have violated the slice goal of one frozen Persona contract per session across reconnects. I fixed the handler to trust the persisted session snapshot when present and only resolve live policy for sessions that do not yet have a snapshot. I added `backend/tests/unit/test_stepfun_realtime_handler.py` coverage proving reconnect now prefers the frozen snapshot over live resolution.

I also recorded the new runtime-contract choice in `.gsd/DECISIONS.md` (D051) and appended a knowledge note in `.gsd/KNOWLEDGE.md` telling future work to inspect `voice_policy_snapshot.customer_pressure` and `source.customer_pressure_source` instead of reverse-engineering pressure behavior from compiled instruction text.

## Verification

Followed a red-green cycle on the new behavior: the initial focused pytest run failed because the compiler ignored top-level structured pressure data and the created session snapshot had no `customer_pressure` field. After the implementation, the focused compiler/integration rerun passed. I then ran a focused StepFun unit test to verify reconnect now prefers the frozen session snapshot over live policy resolution. Finally, I ran the task’s planned verification gate exactly as written: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py`, and all 12 tests passed. LSP diagnostics on `backend/src/sales_bot/services/voice_instruction_compiler.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/common/api/practice.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, and the touched test files all returned `No diagnostics`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py -k 'structured_customer_pressure_contract or freezes_customer_pressure_contract_per_persona'` | 1 | ❌ fail | 3240ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py -k 'structured_customer_pressure_contract or freezes_customer_pressure_contract_per_persona'` | 0 | ✅ pass | 2990ms |
| 3 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py -k 'prefers_frozen_session_snapshot_over_live_resolution'` | 0 | ✅ pass | 3410ms |
| 4 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py` | 0 | ✅ pass | 6810ms |


## Deviations

Minor local adaptation: I also updated `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` and added a focused unit test in `backend/tests/unit/test_stepfun_realtime_handler.py` because the live reconnect path still re-resolved policy from admin config, which would have invalidated the task’s frozen-snapshot goal. Otherwise the task followed the written plan.

## Known Issues

None.

## Files Created/Modified

- `backend/src/sales_bot/services/voice_instruction_compiler.py`
- `backend/src/sales_bot/services/voice_runtime_policy.py`
- `backend/src/common/api/practice.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/unit/test_voice_instruction_compiler.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Minor local adaptation: I also updated `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` and added a focused unit test in `backend/tests/unit/test_stepfun_realtime_handler.py` because the live reconnect path still re-resolved policy from admin config, which would have invalidated the task’s frozen-snapshot goal. Otherwise the task followed the written plan.

## Known Issues
None.
