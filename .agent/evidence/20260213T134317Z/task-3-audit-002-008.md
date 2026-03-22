# task-3-audit-002-008.md

RUN_ID: 20260213T134317Z

## AUDIT-002
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "api.auth.login" "web/src/app/(auth)/login/page.tsx"; grep -n "/auth/login" "backend/src/common/auth/api.py"`
- code_refs: web/src/app/(auth)/login/page.tsx, backend/src/common/auth/api.py
- db_refs: users
- expected: Login button triggers auth API and backend exposes login/logout endpoints with users persistence path.
- actual: Frontend handleLogin calls api.auth.login; backend exposes /auth/login and /auth/logout handlers.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-003
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "api.dashboard.getStats" "web/src/app/(dashboard)/page.tsx"; grep -n "/dashboard/stats" "backend/src/common/api/dashboard.py"`
- code_refs: web/src/app/(dashboard)/page.tsx, backend/src/common/api/dashboard.py
- db_refs: practice_sessions, scenarios, users
- expected: Dashboard actions resolve to backend stats/recommendation/history APIs.
- actual: Dashboard page invokes stats/recommendation/history calls; backend implements stats and recommendation routes.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-004
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "api.training.getCategories" "web/src/app/(dashboard)/training/page.tsx"; grep -n "/training-categories" "backend/src/common/api/training.py"`
- code_refs: web/src/app/(dashboard)/training/page.tsx, backend/src/common/api/training.py
- db_refs: scenarios
- expected: Training category buttons map to category API and scenario-backed data.
- actual: Training page requests getCategories; backend exposes /training-categories and session listing logic.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-005
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getSalesAgents" "web/src/app/(dashboard)/training/sales/page.tsx"; grep -n "/scenarios/sales/personas" "backend/src/sales_bot/api/scenarios.py"`
- code_refs: web/src/app/(dashboard)/training/sales/page.tsx, backend/src/sales_bot/api/scenarios.py, backend/src/common/api/training.py
- db_refs: scenarios, agents, personas, agent_personas
- expected: Sales training filters and persona retrieval map to DB-backed scenario/agent/persona relations.
- actual: Sales page calls scenario+persona APIs; backend persona API queries AgentPersona+Persona join.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-006
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "api.agents.getList" "web/src/app/(dashboard)/training/presentation/page.tsx"; grep -n "prefix="/agents"" "backend/src/agent/api/agents.py"`
- code_refs: web/src/app/(dashboard)/training/presentation/page.tsx, backend/src/agent/api/agents.py
- db_refs: agents, scenarios
- expected: Presentation training list maps to published agent listing API.
- actual: Presentation page calls getList("presentation") and routes to agent detail pages.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-007
- verdict: PASS
- passes: true
- confidence: medium
- command: `grep -n "getCustomerAgents" "web/src/app/(dashboard)/training/customer-service/page.tsx"; grep -n "customer" "backend/src/common/api/training.py"`
- code_refs: web/src/app/(dashboard)/training/customer-service/page.tsx, backend/src/common/api/training.py
- db_refs: agents, scenarios
- expected: Customer-service training entry resolves to backend-filtered agent data.
- actual: Customer-service page invokes getCustomerAgents and navigates to selected agent detail.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path

## AUDIT-008
- verdict: FAIL
- passes: false
- confidence: medium
- command: `grep -n "createSession" "web/src/app/(dashboard)/agents/[agentId]/page.tsx"; python3 test_websocket.py`
- code_refs: web/src/app/(dashboard)/agents/[agentId]/page.tsx, backend/src/common/api/practice.py, .agent/evidence/20260213T134317Z/task-8-ws-smoke.log
- db_refs: practice_sessions, agents, personas
- expected: Enhanced start-practice flow should create session and emit capability messages consistently.
- actual: Code path includes agent/persona/voice_mode persistence, but WS smoke test reports enhanced capability message failure.
- repro_steps:
  1. Run recorded command
  2. Inspect referenced FE/BE code paths
  3. Compare expected vs actual and persist output path
- unblock_condition: Fix enhanced sales WS capability message chain and verify with `python3 test_websocket.py` capability checks.

