# S04: 评测、debug API 与 rollout — UAT

**Milestone:** M011
**Written:** 2026-03-31T06:40:27.903Z

# S04: 评测、debug API 与 rollout — UAT

**Milestone:** M011  
**Written:** 2026-03-31

## UAT Type

- UAT mode: focused backend + compatibility-reader verification on the shipped knowledge-answer eval, debug, and rollout seams.
- Why this mode is sufficient: S04 shipped backend operational capabilities — deterministic eval fixtures, persisted-run inspection APIs, seed/bootstrap controls, and compat-layer rollout modes. Acceptance therefore depends on proving those exact seams on the live backend and on the existing learner-facing consumers they must not break.

## Preconditions

- Repo root: `/Users/zhaozengqing/github/销售训练qoder`
- Backend dependencies installed in `backend/venv` and web dependencies installed in `web/node_modules`.
- Run backend pytest commands **serially**, not in parallel, because repo-root focused pytest in this project shares the top-level `.coverage` SQLite file.
- Use the slice-plan verification commands from repo root:
  1. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q`
  2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q`
  3. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_internal_knowledge_searcher.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py backend/tests/unit/common/test_kb_lock_guard.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/common/test_knowledge_answer_control_plane_models.py backend/tests/unit/common/test_knowledge_answer_config_repo.py backend/tests/unit/common/test_knowledge_entity_resolver.py backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/common/test_knowledge_answerability.py backend/tests/unit/common/test_knowledge_answer_assembler.py backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py backend/tests/unit/common/test_seed_knowledge_answer_config.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py -q`
  4. `npm --prefix web test -- --run src/hooks/websocket/message-handlers.test.ts src/components/ui/chat-bubble.test.tsx "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`

## Smoke Test

1. Run the four verification commands above in order.
2. **Expected:** backend eval suite passes 6/6.
3. **Expected:** debug API suite passes 5/5.
4. **Expected:** focused backend compatibility + rollout suite passes 197/197.
5. **Expected:** focused web compatibility suite passes 68/68.
6. **Expected:** after these four gates, the slice goal is proven: deterministic eval coverage exists for product-introduction-class queries, recent runs are inspectable through a dedicated API, and rollout controls do not regress current learner-facing consumers.

## Test Cases

### 1. Deterministic eval fixtures cover the intended product-introduction query families

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q`.
2. Inspect the fixture-driven cases.
3. **Expected:** the suite covers intro, pricing, version comparison, coaching guidance, and blocked-timeout degradation behavior.
4. **Expected:** the harness runs the real `KnowledgeAnswerEngine` seam rather than a handler-local stub.
5. **Expected:** `final_text` expectations preserve exact multiline numbered formatting instead of whitespace-normalized snapshots.
6. **Expected:** the harness records executed queries from runtime diagnostics so early-stop behavior can be validated truthfully.

### 2. The debug API lists recent persisted runs in latest-first order

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q`.
2. Inspect the list-route case.
3. **Expected:** `GET /api/v1/knowledge-debug/runs` returns recent runs in latest-first order.
4. **Expected:** each run item exposes the persisted audit identity and summary fields needed to pick a run for inspection.
5. **Expected:** the route reads the persisted audit rows directly rather than reconstructing results from runtime-local StepFun state.

### 3. The debug API returns one run’s canonical audit detail

1. In the same integration suite, inspect the detail-route case.
2. **Expected:** `GET /api/v1/knowledge-debug/runs/{run_id}` returns a normalized payload for that exact persisted run.
3. **Expected:** the response includes the run’s query, answerability/result context, and stored summary metadata.
4. **Expected:** unknown `run_id` returns the project’s structured not-found error shape rather than a generic 500.

### 4. The debug API exposes ordered execution steps for the selected run

1. In the same integration suite, inspect the steps-route case.
2. **Expected:** `GET /api/v1/knowledge-debug/runs/{run_id}/steps` returns the persisted steps in execution order.
3. **Expected:** the step payloads preserve enough detail to inspect resolve/classify/plan/retrieve/rank/answerability/assemble flow without replaying the request.
4. **Expected:** step order is stable and matches the stored `KnowledgeAnswerRunStep` sequence.

### 5. The debug API remains read-only and admin/support scoped

1. Still in the same integration suite, inspect the RBAC case.
2. **Expected:** the route family is accessible to admin/support and denied to unauthorized roles.
3. **Expected:** no mutation endpoint is introduced alongside the inspection surface.
4. **Expected:** this keeps the debug seam operationally useful without turning it into a second control plane.

### 6. Seed bootstrap creates or reactivates canonical starter config versions idempotently

1. Run the full backend verification command from the slice plan.
2. Inspect `backend/tests/unit/common/test_seed_knowledge_answer_config.py` coverage in the result.
3. **Expected:** the seed script creates starter profiles for product overview, pricing, version comparison, and coaching guidance.
4. **Expected:** rerunning the script does not duplicate versions; it reactivates existing rows by `version_name`.
5. **Expected:** the script can bootstrap from repo root using its own sync session path even though the shared DB helpers are async-only.

### 7. Rollout mode selection stays on the compat seam and preserves current user-visible behavior by default

1. In the same full backend verification command, inspect `backend/tests/unit/common/test_knowledge_answer_feature_flag.py` and the related StepFun search/runtime tests.
2. **Expected:** when both rollout env vars are unset/false, the system stays on the legacy path.
3. **Expected:** when `KNOWLEDGE_ANSWER_ENGINE_ENABLED=true`, the compat seam uses the engine result as the shipped path.
4. **Expected:** when `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN=true`, the visible payload remains on the legacy contract while the engine runs in shadow.
5. **Expected:** rollout logic lives in `common.knowledge_engine.compat` rather than being duplicated in multiple handler branches.

### 8. Dual-run mode persists shadow audits only when the request is tied to a real session

1. In the same full backend verification command, inspect the dual-run focused cases.
2. **Expected:** shadow or enabled audit rows are only persisted when a real `session_id` is available.
3. **Expected:** session-less invocations do not fabricate persisted run history.
4. **Expected:** this prevents debug/API history from filling with untraceable noise while preserving truthful shadow comparisons on real runtime traffic.

### 9. Runtime diagnostics expose the chosen rollout mode for inspection

1. In the same full backend verification command, inspect the StepFun internal search/runtime diagnostics cases.
2. **Expected:** compat execution surfaces `_diagnostics.knowledge_answer_rollout` on the existing runtime inspection seam.
3. **Expected:** operators can tell whether the request ran in legacy, enabled, or dual-run mode without diffing output payloads manually.
4. **Expected:** the existing runtime metric ledger is still preserved.

### 10. Existing learner-facing consumers remain green after rollout/seeding/debug additions

1. Run `npm --prefix web test -- --run src/hooks/websocket/message-handlers.test.ts src/components/ui/chat-bubble.test.tsx "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`.
2. **Expected:** websocket message handlers still accept the current backend contracts.
3. **Expected:** report page tests remain green, proving the backend additions did not regress the canonical learner report path.
4. **Expected:** replay page tests remain green, including the explicit completion-gated blocked state.
5. **Expected:** the slice improves backend observability/rollout without silently breaking existing learner report/replay consumers.

## Edge Cases

### Exact assembler formatting
- **Expected:** eval fixtures fail if numbered multiline `final_text` formatting drifts; this is intentional and should not be weakened to whitespace-only matching.

### In-memory integration DB setup
- **Expected:** debug API integration tests import `agent.models` so shared metadata creation can resolve foreign keys; otherwise a `NoReferencedTableError` is a fixture setup issue, not a product regression.

### Repo-root focused pytest warnings
- **Expected:** repo-root focused backend runs may still emit existing pytest-cov warnings (`Module src was never imported` / `No data was collected`) while the functional gate still passes.

### Replay-suite warning noise
- **Expected:** the current replay-focused backend suite may still emit the known `AsyncMockMixin._execute_mock_call` runtime warning from the graceful audio-audit fallback path; it is visible technical debt, not an S04 behavior regression.

## Failure Signals

- Eval fixtures start passing only after whitespace normalization or stop covering one of the seeded query families.
- `/api/v1/knowledge-debug/runs` stops returning the persisted recent-run truth line.
- `/api/v1/knowledge-debug/runs/{run_id}/steps` no longer preserves ordered execution payloads.
- Dual-run mode changes learner-visible payloads instead of staying shadow-only.
- Shadow audits are persisted without a real `session_id`, polluting recent-run history.
- `_diagnostics.knowledge_answer_rollout` disappears from compat diagnostics, making rollout-state inspection opaque.
- Web report/replay or websocket message-handler tests regress after rollout/debug changes.

## Requirements Proved By This UAT

- None change status at S04 close-out. This UAT proves the operational/debug/eval and rollout safety needed for M011 milestone closure.

## Not Proved By This UAT

- A milestone-level rollout dashboard beyond the new debug API and compat diagnostics.
- Canonical completed-session report parity that directly surfaces the full knowledge-answer audit/debug seam.
- Production traffic volume or long-horizon rollout success metrics.

## Notes For The Next Slice / Milestone Close-out

- Use the persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` rows and `/api/v1/knowledge-debug` as the inspection authority for any further rollout or audit work.
- Reuse `_diagnostics.knowledge_answer_rollout` if milestone validation needs to prove which mode actually executed.
- Keep backend verification serial during auto-mode close-out unless coverage output is isolated first.

