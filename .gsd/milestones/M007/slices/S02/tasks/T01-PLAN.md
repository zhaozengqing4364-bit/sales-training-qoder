---
estimated_steps: 3
estimated_files: 8
skills_used:
  - fastapi-python
  - systematic-debugging
  - verification-before-completion
---

# T01: Unify live same-session conclusion authority across StepFun, classic, and `/knowledge-check`

Lock the highest-risk seam first: backend live runtime, websocket emission, and `/knowledge-check` must all speak the same same-session issue/goal/claim-truth language before any learner-page rendering work. Steps: 1. Reuse the existing evaluator family authority to define one live conclusion summary shape for the active session instead of inventing a route-local mapping. 2. Route both `StepFunRealtimeHandler` and `EnhancedSalesHandler` through that shared authority and make the existing runtime diagnostics / score-update path expose it for the current session. 3. Extend focused backend coverage so StepFun, classic, and `/knowledge-check` all prove the same family/claim-truth semantics on the same session. Must-haves: classic reaches parity with StepFun on live same-session conclusion data; `/api/v1/practice/sessions/{id}/knowledge-check` stays the inspection surface instead of adding a new endpoint; missing or partial live summary fields fail soft without reviving stale prior-session state. Failure modes: StepFun and classic emit different family labels; live runtime summary drifts from completed-session alignment; `/knowledge-check` prefers stale persisted data while a live handler is active. Load profile: keep per-turn scoring and reconnect O(1) with no extra DB queries, polling loop, or duplicate projection pass. Negative tests: malformed or partial live summary payloads, classic objection-handling/evidence-gap cases, and active-session diagnostics overriding stale snapshot fallback only when a live handler is present.

## Inputs

- ``backend/src/common/effectiveness/evaluator.py``
- ``backend/src/common/conversation/runtime_diagnostics.py``
- ``backend/src/sales_bot/websocket/stepfun_realtime_handler.py``
- ``backend/src/sales_bot/websocket/enhanced_handler.py``
- ``backend/src/sales_bot/websocket/components/capability_processor.py``

## Expected Output

- ``backend/src/common/effectiveness/evaluator.py``
- ``backend/src/common/conversation/runtime_diagnostics.py``
- ``backend/src/sales_bot/websocket/stepfun_realtime_handler.py``
- ``backend/src/sales_bot/websocket/enhanced_handler.py``
- ``backend/tests/contract/test_practice_evidence_contract.py``

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_enhanced_handler_coach_health.py
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k 'knowledge_check or replay or report'

## Observability Impact

Keeps live same-session conclusion drift diagnosable on the current runtime surfaces by making websocket emission and `/knowledge-check` read the same backend authority instead of hiding semantics inside page-local formatting.
