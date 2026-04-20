# S01: Live AI authority inventory — UAT

**Milestone:** M021
**Written:** 2026-04-14T01:57:58.587Z

# S01 UAT — Live AI authority inventory

## Preconditions
- Repository is on the M021/S01 close-out state.
- `backend/venv` exists and can run pytest.
- Reviewer has read access to `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `docs/api-contract/`, and `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`.

## Test Case 1 — Confirm the live AI runtime authority is explicit
1. Open `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` and navigate to section `7.3.1 M021/S01 live AI authority inventory`.
2. Verify the table labels `sales_bot/websocket/router.py -> stepfun_realtime_handler.py` as **live** and `voice_runtime_policy.py + voice_instruction_compiler.py` as the **live** compiled prompt/runtime contract seam.
3. Verify `PromptTemplateService` is labeled **live governance + compat runtime helper**, not live sales runtime prompt authority.
4. Verify legacy evaluation/report surfaces are labeled **compat enhancement / retire candidate** instead of canonical report truth.

**Expected outcome**
- A reviewer can answer “what is the current live AI mainline?” without guessing from file names.
- The answer points to StepFun runtime + compiled session snapshot, not to prompt templates or `/evaluation/*`.

## Test Case 2 — Confirm the shipped knowledge-answer authority split is explicit
1. In the same section, verify `stepfun_internal_knowledge_searcher.py + common.knowledge_engine.compat` is labeled **live rollout seam**.
2. Verify `common.knowledge_engine.engine.py` is labeled **shadow by default; live only when enabled**.
3. Verify the text explains that `KNOWLEDGE_ANSWER_ENGINE_ENABLED=true` promotes the engine to learner-visible live behavior and `KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN=true` keeps learner-visible legacy payloads while the engine remains shadow audit.

**Expected outcome**
- A reviewer can distinguish the shipped rollout seam from the raw engine implementation.
- Downstream work clearly knows to extend the compat seam rather than bypassing it.

## Test Case 3 — Confirm contract docs tell the same authority story
1. Open `docs/api-contract/sessions.md`.
2. Confirm the `Authority boundary (M021/S01 inventory sync)` block says session create freezes `voice_policy_snapshot`, the persisted `voice_mode` selects runtime, and report/knowledge-check/replay all read the same snapshot/evidence line.
3. Open `docs/api-contract/prompt-templates.md`.
4. Confirm its authority block says prompt templates are live governance/control-plane surfaces with runtime-adjacent compat consumers, but **not** the live sales StepFun prompt authority.
5. Open `docs/api-contract/support-runtime.md`.
6. Confirm it still presents `/api/v1/support/runtime/*` as release-health / fault summary and does **not** claim to be the live AI control-plane authority.

**Expected outcome**
- Consumer-facing docs agree with the architecture scan instead of restating old assumptions.
- The reviewer does not find a second contradictory authority line in API docs.

## Test Case 4 — Confirm focused proof files protect the intended seams
1. Run:
   - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py::test_start_session_persists_voice_policy_snapshot backend/tests/integration/test_voice_runtime_session_snapshot.py::test_snapshot_baseline_is_immutable_and_report_replay_refer_same_baseline backend/tests/unit/common/test_knowledge_answer_feature_flag.py backend/tests/unit/test_report_generation_trigger.py -q`
2. Review the test docstrings / assertions in those files.
3. Confirm they map to these authority claims:
   - live StepFun/session-snapshot path
   - compat-owned knowledge rollout seam with enabled/dual-run behavior
   - enhanced report sidecar as compatibility/enhancement, not canonical report authority

**Expected outcome**
- The focused backend proof bundle passes.
- The proof files themselves are explicit enough that a future agent can tell what authority path each suite is locking.

## Test Case 5 — Confirm downstream slices have an execution matrix instead of a prose-only note
1. Run:
   - `rg -n "must keep|compat|retire candidate|consumer" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md`
2. Verify both files contain:
   - a **must keep** bucket for StepFun runtime / compiled snapshot / knowledge compat seam
   - a **compat** bucket for PromptTemplateService and classic scoring
   - a **retire candidate** bucket for staged/comprehensive evaluation + report trigger + `/evaluation/*` + `common/ai/llm_service.py::evaluate/generate_report`
3. Verify the matrix also names the legacy consumers that block brute-force deletion.

**Expected outcome**
- S02-S04 can execute against a concrete keep/compat/retire matrix instead of rediscovering the same seam status.
- The reviewer sees explicit guardrails for the legacy consumers that still matter.

## Edge Case — CONTEXT gate remains truthful
1. Check that `M021-CONTEXT-DRAFT.md` exists and contains the authority-inventory handoff material.
2. Confirm there is no false claim that final `M021-CONTEXT.md` was produced without depth verification.

**Expected outcome**
- Downstream slices have a usable draft context artifact.
- The slice remains honest about the still-blocked final context promotion step.

