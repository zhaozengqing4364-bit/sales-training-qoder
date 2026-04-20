---
id: T01
parent: S02
milestone: M022
key_files:
  - backend/src/agent/services/industry_pack_contract.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - backend/src/agent/api/agents.py
  - backend/src/agent/api/personas.py
  - backend/src/sales_bot/api/scenarios.py
  - backend/tests/unit/test_sales_scenarios_api.py
  - backend/tests/integration/test_agent_api.py
  - backend/tests/integration/test_persona_api.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Keep industry pack as a composed asset over existing agent/persona/knowledge/scenario surfaces and expose inspectable read-only contract endpoints instead of creating a standalone content platform in T01.
duration: 
verification_result: passed
completed_at: 2026-04-14T05:54:10.740Z
blocker_discovered: false
---

# T01: Added inspectable industry-pack contract surfaces across agent/persona/scenario APIs and documented their runtime mapping.

**Added inspectable industry-pack contract surfaces across agent/persona/scenario APIs and documented their runtime mapping.**

## What Happened

I introduced a new shared helper at `backend/src/agent/services/industry_pack_contract.py` to make the first-round industry-pack/customer-pressure contract explicit instead of leaving it implicit across persona policy, scenario metadata, and knowledge bindings. Using that helper, I added `GET /api/v1/admin/agents/industry-pack-contract` to expose the composed-asset authority model, `GET /api/v1/admin/personas/industry-pack-contract` to expose field ownership and runtime targets, and `GET /api/v1/scenarios/sales/runtime-contract` to expose the sales-scenario runtime mapping. I also extended `GET /api/v1/scenarios/sales/personas` with a `runtime_binding` summary so future agents can inspect which customer-pressure source, objection axes, questions, and knowledge bindings a persona will push into runtime surfaces. Finally, I updated `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with the M022/S02 contract rules and wrote the composed-asset decision/knowledge back to GSD artifacts.

## Verification

Fresh focused backend tests passed for the new agent/persona/scenario contract surfaces and the augmented sales persona payload. I then reran the task-plan verification command `rg -n "persona_policy|customer_pressure|scenario|knowledge_base|agent|industry" backend/src/agent backend/src/sales_bot backend/src/common/knowledge` and confirmed the new contract endpoints and helper are discoverable in the expected code surfaces. I also ran LSP diagnostics on `backend/src/agent/api/agents.py`, `backend/src/agent/api/personas.py`, `backend/src/sales_bot/api/scenarios.py`, and `backend/src/agent/services/industry_pack_contract.py`; all returned no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_sales_scenarios_api.py backend/tests/integration/test_agent_api.py backend/tests/integration/test_persona_api.py -q` | 0 | ✅ pass | 8478ms |
| 2 | `rg -n "persona_policy|customer_pressure|scenario|knowledge_base|agent|industry" backend/src/agent backend/src/sales_bot backend/src/common/knowledge` | 0 | ✅ pass | 37ms |

## Deviations

None.

## Known Issues

Focused pytest still emits pre-existing coverage/no-data warnings under the repository’s current pytest-cov configuration; the task’s contract surfaces and tests passed despite those warnings.

## Files Created/Modified

- `backend/src/agent/services/industry_pack_contract.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/agent/api/agents.py`
- `backend/src/agent/api/personas.py`
- `backend/src/sales_bot/api/scenarios.py`
- `backend/tests/unit/test_sales_scenarios_api.py`
- `backend/tests/integration/test_agent_api.py`
- `backend/tests/integration/test_persona_api.py`
- `.gsd/KNOWLEDGE.md`
