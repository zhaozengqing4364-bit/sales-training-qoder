# ULW Read-Only Multi-Auditor Audit and Report Plan

## TL;DR

> **Quick Summary**: Execute a no-code-change, multi-auditor audit across all baseline checks (`AUDIT-001` ~ `AUDIT-029`), with explicit evidence chains and a final contradiction-checked report.
>
> **Deliverables**:
> - `.agent/evidence/{RUN_ID}/audit-index.json` (machine-readable evidence index)
> - `.agent/evidence/{RUN_ID}/audit-regression-matrix.md` (prior P0/P1 verification)
> - `docs/audit-report-{RUN_ID}.md` (final detailed report)
> - `.agent/progress.md` update reflecting completion state
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 0 -> Task 1 -> Task 3/4/5/6/7/8/9 -> Task 10 -> Task 11 -> Task 12

---

## Context

### Original Request
User requested arranging multiple people to audit-test the project, focusing on weak human-like roleplay quality, odd bugs, and unimplemented features, with no code modification and a detailed report.

### Interview Summary
**Key Discussions**:
- Use read-only audit mode only (no source code edits, no migration/refactor work).
- Reuse fixed baseline from `.agent/tasks.json` (`AUDIT-001` ~ `AUDIT-029`).
- Keep verdict schema `PASS | FAIL | BLOCKED` with reproducible evidence chain.

**Research Findings**:
- Baseline tasks and evidence requirements are already formalized in `.agent/tasks.json`.
- Prior report exists at `docs/audit-report-2026-02-13.md` and must be treated as historical input, not truth.
- Test and verification entrypoints are available across backend/frontend/ws scripts.

### Metis Review
**Identified Gaps** (addressed in this plan):
- Missing frozen target metadata (branch/SHA/timestamp) -> added mandatory preflight freeze.
- Risk of stale findings reuse -> added regression verification matrix.
- Scope creep risk -> hard lock to `AUDIT-001` ~ `AUDIT-029`.
- Weak report quality criteria -> added machine-readable completeness checks + contradiction pass.

---

## Work Objectives

### Core Objective
Produce a high-confidence, evidence-backed, read-only audit report that covers all 29 baseline audit tasks and clearly distinguishes fixed, regressed, failing, and blocked areas.

### Concrete Deliverables
- Full task-by-task verdicts for `AUDIT-001` ~ `AUDIT-029`.
- Evidence artifacts per task (commands, outputs, code refs, DB refs, expected vs actual).
- Roleplay-quality rubric results (persona consistency, challenge quality, stage logic, scoring coherence).
- Prior-risk regression matrix (P0/P1 from last report).
- Final prioritized remediation queue (P0/P1/P2) with reproducibility.

### Definition of Done
- [ ] All 29 audit IDs have exactly one verdict and one evidence bundle.
- [ ] Every `FAIL`/`BLOCKED` has explicit reproduction and unblock condition.
- [ ] Final report passes contradiction/completeness checks.
- [ ] No source code files are modified.

### Must Have
- Read-only execution discipline.
- Parallel lane execution by non-overlapping modules.
- Machine-verifiable evidence index.
- Dedicated roleplay realism evaluation section.

### Must NOT Have (Guardrails)
- No implementation, refactor, dependency changes, or migration changes.
- No unverifiable claims copied from old reports.
- No report sections without attached evidence path.
- No audit IDs skipped.
- No unbounded exploratory loops (max 2 retries per failing check before `BLOCKED`).

### Defaults Applied
- External dependency unavailable (StepFun/Aliyun/third-party) => classify as `BLOCKED`, not `FAIL`, with explicit unblock condition.
- Audit scope lock: exactly `AUDIT-001` ~ `AUDIT-029`.
- Timebox: each audit lane performs one full pass + max two targeted retries.

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> All acceptance criteria must be agent-executable via commands/tools. Human-only checks are forbidden.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after (verification-only; no feature implementation)
- **Frameworks**: pytest, Vitest, ruff, mypy, websocket scripts, jq checks

### Evidence Standard
- Verdict fields: `verdict` (`PASS|FAIL|BLOCKED`) + `passes` (`true|false`).
- Evidence path root: `.agent/evidence/{RUN_ID}/`.
- Mandatory per finding:
  - Executed command
  - Output artifact path
  - Code references (frontend + backend + db/table when relevant)
  - Expected vs actual
  - Confidence (`high|medium|low`)

### Global Command Baseline
Use these in relevant tasks:
- Backend quality: `ruff check src/`, `mypy src/`, `pytest tests/unit/`, `pytest tests/contract/`, `pytest tests/integration/`
- Frontend quality: `npm run lint`, `npm run test`, `npm run build`
- WebSocket flows: `python test_websocket.py`, `python test_websocket_detailed.py`
- Completeness gate:

```bash
jq '.tasks | length' .agent/tasks.json
# Expected: 29
```

```bash
jq -e '(.tasks|length==29) and all(.tasks[]; (.id|test("^AUDIT-[0-9]{3}$")) and (.verdict|test("PASS|FAIL|BLOCKED")) and (.passes|type=="boolean") and (.evidence.command|length>0) and (.evidence.code_refs|length>0))' \
  .agent/evidence/{RUN_ID}/audit-index.json
# Expected: exit code 0
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation):
├── Task 0: Freeze audit target + evidence scaffold
└── Task 1: Build AUDIT-001 template and task registry

Wave 2 (Parallel Audit Lanes):
├── Task 2: Prior-risk regression sweep
├── Task 3: Lane A (AUDIT-002~008)
├── Task 4: Lane B (AUDIT-009~014)
├── Task 5: Lane C (AUDIT-015~020)
├── Task 6: Lane D (AUDIT-021~028)
├── Task 7: Roleplay realism deep audit
├── Task 8: Realtime/ws fault-latency audit
└── Task 9: Contract/type/DB drift audit

Wave 3 (Consolidation):
└── Task 10: Consolidate evidence into index and draft report

Wave 4 (Finalization):
├── Task 11: AUDIT-029 prioritization + retest matrix
└── Task 12: Contradiction/completeness gate + publish report
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|----------------------|
| 0 | None | 1-12 | 1 (prep-only) |
| 1 | 0 | 2-12 | None |
| 2 | 1 | 10-12 | 3,4,5,6,7,8,9 |
| 3 | 1 | 10-12 | 2,4,5,6,7,8,9 |
| 4 | 1 | 10-12 | 2,3,5,6,7,8,9 |
| 5 | 1 | 10-12 | 2,3,4,6,7,8,9 |
| 6 | 1 | 10-12 | 2,3,4,5,7,8,9 |
| 7 | 1 | 10-12 | 2,3,4,5,6,8,9 |
| 8 | 1 | 10-12 | 2,3,4,5,6,7,9 |
| 9 | 1 | 10-12 | 2,3,4,5,6,7,8 |
| 10 | 2-9 | 11-12 | None |
| 11 | 10 | 12 | None |
| 12 | 11 | None | None |

### Auditor Assignment Matrix

| Auditor | Scope | Primary Tasks |
|---------|-------|---------------|
| Auditor-A | User auth/dashboard/training flows | 3 |
| Auditor-B | Practice session/replay/report/history/profile | 4 |
| Auditor-C | Support runtime + admin core pages | 5 |
| Auditor-D | Admin domain modules (agents/personas/knowledge/prompt/model/voice) | 6 |
| Auditor-E | Roleplay quality dimensions (persona/stage/scoring realism) | 7 |
| Auditor-F | WebSocket/realtime robustness and latency | 8 |
| Auditor-G | Contract/type/db consistency | 9 |
| Consolidator | Index/report/priority/retest/final gate | 10,11,12 |

---

## TODOs

- [ ] 0. Freeze Target and Create Evidence Scaffold

  **What to do**:
  - Capture branch, commit SHA, timestamp into `.agent/evidence/{RUN_ID}/run-meta.json`.
  - Initialize evidence directories and empty `audit-index.json` skeleton.
  - Record execution policy for `BLOCKED` classification.
  - Record retry/timebox policy in run metadata (one pass + max two retries).

  **Must NOT do**:
  - No code edits.
  - No DB schema mutations.

  **Recommended Agent Profile**:
  - **Category**: `quick` (deterministic setup)
  - **Skills**: `verification-before-completion`, `Coding Standards`
  - **Skills Evaluated but Omitted**: `test-driven-development` (no implementation)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1
  - **Blocks**: 1-12
  - **Blocked By**: None

  **References**:
  - `.agent/tasks.json` - authoritative audit scope and IDs.
  - `.agent/progress.md` - progress sync target.

  **Acceptance Criteria**:
  - [ ] `run-meta.json` contains `branch`, `sha`, `run_id`, `started_at`.
  - [ ] `audit-index.json` initialized with 29 task slots.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Freeze target metadata
    Tool: Bash
    Steps:
      1. git rev-parse --abbrev-ref HEAD
      2. git rev-parse HEAD
      3. date -u +"%Y-%m-%dT%H:%M:%SZ"
      4. Assert all values written into .agent/evidence/{RUN_ID}/run-meta.json
    Expected Result: Metadata file exists with non-empty values
    Evidence: .agent/evidence/{RUN_ID}/task-0-run-meta.json
  ```

  **Commit**: NO

- [ ] 1. Execute AUDIT-001 Template and Registry Normalization

  **What to do**:
  - Build reusable audit record template using fields from `AUDIT-001`.
  - Normalize verdict schema and evidence fields for all 29 IDs.
  - Pre-populate `.agent/evidence/{RUN_ID}/audit-index.json` task registry.

  **Must NOT do**:
  - Do not alter baseline task semantics in `.agent/tasks.json`.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `verification-before-completion`
  - **Skills Evaluated but Omitted**: `webapp-testing` (no runtime UI yet)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1
  - **Blocks**: 2-12
  - **Blocked By**: 0

  **References**:
  - `.agent/tasks.json` - contains `AUDIT-001` field definitions and evidence constraints.
  - `docs/audit-report-2026-02-13.md` - prior report format baseline.

  **Acceptance Criteria**:
  - [ ] `audit-index.json` has exactly 29 entries with ids `AUDIT-001`~`AUDIT-029`.
  - [ ] Each entry includes placeholders: `verdict`, `passes`, `evidence.command`, `evidence.output_path`, `evidence.code_refs`.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Validate registry completeness
    Tool: Bash
    Steps:
      1. jq '.tasks | length' .agent/evidence/{RUN_ID}/audit-index.json
      2. Assert output equals 29
      3. jq -e 'all(.tasks[]; has("id") and has("verdict") and has("passes") and has("evidence"))' .agent/evidence/{RUN_ID}/audit-index.json
    Expected Result: Completeness checks pass
    Evidence: .agent/evidence/{RUN_ID}/task-1-registry-validation.log
  ```

  **Commit**: NO

- [ ] 2. Regression Sweep of Prior P0/P1 Findings

  **What to do**:
  - Re-verify prior high-severity findings from `docs/audit-report-2026-02-13.md`.
  - Classify each as `fixed`, `regressed`, `still failing`, or `unverifiable`.
  - Save matrix in `.agent/evidence/{RUN_ID}/audit-regression-matrix.md`.

  **Must NOT do**:
  - Do not copy old verdicts without fresh evidence.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `systematic-debugging`, `Code Reviewer`
  - **Skills Evaluated but Omitted**: `frontend-ui-ux` (not design task)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `docs/audit-report-2026-02-13.md` - prior P0/P1 source.
  - `backend/src/presentation_coach/websocket/presentation_handler.py` - PPT realtime path.
  - `backend/src/sales_bot/api/scenarios.py` - sales persona source.
  - `backend/src/common/api/practice.py` + `backend/src/common/db/schemas.py` + `web/src/lib/api/types.ts` - runtime field mapping.

  **Acceptance Criteria**:
  - [ ] Matrix includes all prior P0/P1 items and current status.
  - [ ] Every status row cites current evidence artifact path.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Prior finding re-verification
    Tool: Bash
    Steps:
      1. Extract prior P0/P1 list from docs/audit-report-2026-02-13.md
      2. Run targeted tests/scripts for each item
      3. Update regression matrix row with fresh verdict + evidence path
    Expected Result: No prior item remains unclassified
    Evidence: .agent/evidence/{RUN_ID}/task-2-regression-matrix.md
  ```

  **Commit**: NO

- [ ] 3. Lane A Audit: AUDIT-002 ~ AUDIT-008

  **What to do**:
  - Execute button->frontend->api->db consistency checks for auth/dashboard/training/agent entry flows.
  - Cover login success/failure paths and session creation entrypoint.

  **Must NOT do**:
  - No UI behavior assumptions without request/response evidence.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `webapp-testing`, `systematic-debugging`
  - **Skills Evaluated but Omitted**: `writing-skills` (not content authoring)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `.agent/tasks.json` (AUDIT-002..008 notes)
  - `web/src/app/(auth)/login/page.tsx`
  - `web/src/app/(dashboard)/page.tsx`
  - `web/src/app/(dashboard)/training/page.tsx`
  - `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
  - `backend/src/common/auth/api.py`
  - `backend/src/common/api/practice.py`

  **Acceptance Criteria**:
  - [ ] `AUDIT-002..008` each has verdict + reproduction + evidence.
  - [ ] Session creation chain includes persisted `agent_id/persona_id/voice_mode` verification.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Login and start-practice chain
    Tool: Bash + API checks
    Steps:
      1. Run auth endpoint checks for valid/invalid credentials
      2. Trigger practice session creation payload validation
      3. Assert API response + DB persistence alignment
    Expected Result: Complete evidence-backed verdicts for AUDIT-002..008
    Evidence: .agent/evidence/{RUN_ID}/task-3-audit-002-008.md

  Scenario: Dependency unavailable handling
    Tool: Bash
    Steps:
      1. Simulate missing external dependency case during lane checks
      2. Assert verdict recorded as BLOCKED with unblock condition
    Expected Result: BLOCKED classification policy is applied consistently
    Evidence: .agent/evidence/{RUN_ID}/task-3-blocked-policy.log
  ```

  **Commit**: NO

- [ ] 4. Lane B Audit: AUDIT-009 ~ AUDIT-014

  **What to do**:
  - Audit lifecycle controls, replay/report consistency, history/leaderboard/profile logic.
  - Validate session state transitions and report readiness behavior.

  **Must NOT do**:
  - No manual-only report conclusions.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `webapp-testing`, `verification-before-completion`
  - **Skills Evaluated but Omitted**: `algorithmic-art` (irrelevant domain)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `.agent/tasks.json` (AUDIT-009..014 notes)
  - `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(dashboard)/history/page.tsx`
  - `web/src/app/(dashboard)/leaderboard/page.tsx`
  - `backend/src/common/api/practice.py`
  - `backend/src/common/conversation/replay.py`

  **Acceptance Criteria**:
  - [ ] `AUDIT-009..014` complete with reproducible lifecycle/replay/report evidence.
  - [ ] State transitions align across FE, API, and DB artifacts.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Practice lifecycle and report chain
    Tool: Bash + API checks
    Steps:
      1. Create/retrieve session
      2. Trigger pause/resume/end lifecycle actions
      3. Validate replay/report endpoints and state consistency
    Expected Result: Evidence-backed verdicts for AUDIT-009..014
    Evidence: .agent/evidence/{RUN_ID}/task-4-audit-009-014.md
  ```

  **Commit**: NO

- [ ] 5. Lane C Audit: AUDIT-015 ~ AUDIT-020

  **What to do**:
  - Audit support runtime and admin core pages (users/records/analytics).
  - Verify filtering, pagination, export, and metrics consistency.

  **Must NOT do**:
  - No assumptions on analytics formulas without query/response evidence.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `systematic-debugging`
  - **Skills Evaluated but Omitted**: `frontend-design` (not redesign task)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `.agent/tasks.json` (AUDIT-015..020 notes)
  - `web/src/app/(dashboard)/support/runtime/page.tsx`
  - `web/src/app/admin/page.tsx`
  - `web/src/app/admin/users/page.tsx`
  - `web/src/app/admin/users/[id]/page.tsx`
  - `web/src/app/admin/records/page.tsx`
  - `web/src/app/admin/analytics/page.tsx`
  - `backend/src/admin/api/users.py`
  - `backend/src/admin/api/analytics.py`

  **Acceptance Criteria**:
  - [ ] `AUDIT-015..020` each has endpoint and DB-consistency evidence.
  - [ ] Export and filter behavior includes expected-vs-actual proof.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Admin analytics and records consistency
    Tool: Bash + API checks
    Steps:
      1. Execute overview/trends/leaderboard endpoints
      2. Compare metrics and list entries for consistency
      3. Validate export output matches active filters
    Expected Result: Verdict coverage for AUDIT-015..020
    Evidence: .agent/evidence/{RUN_ID}/task-5-audit-015-020.md
  ```

  **Commit**: NO

- [ ] 6. Lane D Audit: AUDIT-021 ~ AUDIT-028

  **What to do**:
  - Audit admin domain modules: agents, personas, knowledge, presentations, prompts, model config, voice runtime.
  - Validate state transitions and binding persistence.

  **Must NOT do**:
  - No direct DB manipulation to force pass.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `verification-before-completion`
  - **Skills Evaluated but Omitted**: `theme-factory` (visual theming not relevant)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `.agent/tasks.json` (AUDIT-021..028 notes)
  - `web/src/app/admin/agents/page.tsx`
  - `web/src/app/admin/agents/[id]/page.tsx`
  - `web/src/app/admin/personas/page.tsx`
  - `web/src/app/admin/personas/[id]/page.tsx`
  - `web/src/app/admin/knowledge/page.tsx`
  - `web/src/app/admin/presentations/page.tsx`
  - `web/src/app/admin/prompts/page.tsx`
  - `web/src/app/admin/settings/page.tsx`
  - `web/src/app/admin/voice-runtime/page.tsx`
  - `backend/src/agent/api/agents.py`
  - `backend/src/agent/api/personas.py`
  - `backend/src/agent/api/agent_personas.py`
  - `backend/src/common/knowledge/api.py`
  - `backend/src/admin/api/model_configs.py`
  - `backend/src/admin/api/voice_runtime.py`

  **Acceptance Criteria**:
  - [ ] `AUDIT-021..028` all resolved with evidence.
  - [ ] Binding/state transitions verified against db tables noted in tasks.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Agent-persona-policy state flow
    Tool: Bash + API checks
    Steps:
      1. Query agent/persona bindings and voice policy data
      2. Validate lifecycle transitions (publish/unpublish/archive)
      3. Verify persisted state reflected in list/detail endpoints
    Expected Result: Evidence-backed verdicts for AUDIT-021..028
    Evidence: .agent/evidence/{RUN_ID}/task-6-audit-021-028.md
  ```

  **Commit**: NO

- [ ] 7. Roleplay Realism Deep Audit (Cross-Cutting)

  **What to do**:
  - Evaluate human-like roleplay quality with explicit rubric:
    - Scale per dimension: `1` (poor) -> `5` (excellent)
    - Persona consistency
    - Challenge realism and pressure progression
    - Sales-stage coherence
    - Realtime scoring narrative alignment
    - Language consistency (CN/EN/mixed)
  - Use transcript/evaluation artifacts and runtime outputs only.

  **Must NOT do**:
  - Do not rate realism without transcript-linked evidence.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `learning-coach`, `Code Reviewer`
  - **Skills Evaluated but Omitted**: `paper-xray` (not paper analysis)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `backend/src/sales_bot/websocket/enhanced_handler.py`
  - `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - `backend/src/sales_bot/services/context_manager.py`
  - `backend/src/sales_bot/services/summary_service.py`
  - `backend/src/evaluation/services/staged_evaluation.py`
  - `backend/src/evaluation/services/realtime_scoring.py`
  - `backend/src/prompt_templates/service.py`
  - `web/src/components/practice/ScorePanel.tsx`
  - `web/src/components/practice/realtime-feedback.tsx`

  **Acceptance Criteria**:
  - [ ] Rubric scores are produced with transcript evidence links.
  - [ ] Each dimension includes 1-5 score + reason + transcript snippet reference.
  - [ ] At least 1 positive and 1 negative realism case per persona style.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Persona realism scoring
    Tool: Bash + transcript analysis pipeline
    Steps:
      1. Collect conversation transcripts and stage/score outputs
      2. Apply rubric dimensions with explicit scoring rationale
      3. Save per-case evidence and aggregate summary
    Expected Result: Roleplay realism section ready for final report
    Evidence: .agent/evidence/{RUN_ID}/task-7-roleplay-rubric.md
  ```

  **Commit**: NO

- [ ] 8. Realtime WebSocket Fault/Latency Audit

  **What to do**:
  - Stress interruption/reconnect/cancel/fallback flows.
  - Validate realtime message ordering, persistence, and error handling.
  - Run websocket smoke + detailed scripts and targeted integration tests.

  **Must NOT do**:
  - No hidden retries that mask failures in evidence.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `systematic-debugging`, `webapp-testing`
  - **Skills Evaluated but Omitted**: `frontend-ui-ux` (behavioral audit only)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `test_websocket.py`
  - `test_websocket_detailed.py`
  - `backend/tests/integration/test_websocket_status_contract.py`
  - `backend/tests/e2e/test_websocket_flow.py`
  - `backend/src/sales_bot/websocket/router.py`
  - `docs/api-contract/websocket.md`

  **Acceptance Criteria**:
  - [ ] Fault scenarios captured with verdict and latency evidence.
  - [ ] `BLOCKED` only used for dependency constraints with proof.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: WebSocket interruption storm
    Tool: Bash
    Steps:
      1. Run python test_websocket_detailed.py
      2. Parse interruption/cancel/recovery events
      3. Assert message ordering and final state consistency
    Expected Result: Deterministic verdict with log evidence
    Evidence: .agent/evidence/{RUN_ID}/task-8-ws-detailed.log

  Scenario: WS smoke baseline
    Tool: Bash
    Steps:
      1. Run python test_websocket.py
      2. Capture pass-rate summary
      3. Classify failures by root cause bucket
    Expected Result: Smoke summary attached to audit index
    Evidence: .agent/evidence/{RUN_ID}/task-8-ws-smoke.log
  ```

  **Commit**: NO

- [ ] 9. Contract/Type/DB Drift Audit

  **What to do**:
  - Verify naming and field consistency across backend schema, API, and frontend types.
  - Focus on known risk points (`runtime_profile_id` mapping, leaderboard naming shims).
  - Validate contract docs vs implemented payloads.

  **Must NOT do**:
  - No contract drift conclusions without payload evidence.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `Code Reviewer`, `Coding Standards`
  - **Skills Evaluated but Omitted**: `ui-ux-pro-max` (not UI styling work)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 10-12
  - **Blocked By**: 1

  **References**:
  - `backend/src/common/db/models.py`
  - `backend/src/common/db/schemas.py`
  - `backend/src/common/api/practice.py`
  - `backend/src/admin/api/analytics.py`
  - `web/src/lib/api/types.ts`
  - `web/src/lib/api/client.ts`
  - `docs/api-contract/*.md`

  **Acceptance Criteria**:
  - [ ] All detected drifts include contract reference + payload sample + risk level.
  - [ ] Drift report merged into index entries for impacted audit IDs.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Runtime profile field mapping check
    Tool: Bash + payload inspection
    Steps:
      1. Collect sample session/report payloads
      2. Compare external and internal field names across layers
      3. Record mismatch or mapping evidence
    Expected Result: Explicit PASS/FAIL for mapping integrity
    Evidence: .agent/evidence/{RUN_ID}/task-9-contract-drift.md
  ```

  **Commit**: NO

- [ ] 10. Consolidate Lane Outputs Into Unified Evidence Index

  **What to do**:
  - Merge outputs from Tasks 2-9 into `audit-index.json`.
  - Ensure each `AUDIT-XXX` has one final verdict and evidence links.
  - Deduplicate overlapping findings by root cause.

  **Must NOT do**:
  - No duplicate findings with different IDs unless evidence differs.

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: `Code Reviewer`, `verification-before-completion`
  - **Skills Evaluated but Omitted**: `systematic-debugging` (already completed upstream)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: 11-12
  - **Blocked By**: 2-9

  **References**:
  - `.agent/evidence/{RUN_ID}/task-*.md`
  - `.agent/evidence/{RUN_ID}/task-*.log`
  - `.agent/tasks.json`

  **Acceptance Criteria**:
  - [ ] `audit-index.json` passes schema validation command.
  - [ ] No audit ID missing or duplicated.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Index schema and completeness validation
    Tool: Bash
    Steps:
      1. Run jq completeness check on audit-index.json
      2. Assert all 29 ids present and unique
      3. Assert each entry has verdict, passes, evidence links
    Expected Result: Validation exits 0
    Evidence: .agent/evidence/{RUN_ID}/task-10-index-validation.log
  ```

  **Commit**: NO

- [ ] 11. Execute AUDIT-029 (Prioritization + Retest Plan + Final Report Draft)

  **What to do**:
  - Rank findings into P0/P1/P2 using impact + reproducibility + confidence.
  - Add explicit retest checklist for all FAIL/BLOCKED.
  - Produce `docs/audit-report-{RUN_ID}.md` with full details.

  **Must NOT do**:
  - No severity assignment without evidence-based rationale.

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: `internal-comms`, `Code Reviewer`
  - **Skills Evaluated but Omitted**: `doc-coauthoring` (not collaborative live drafting)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: 12
  - **Blocked By**: 10

  **References**:
  - `.agent/tasks.json` (AUDIT-029)
  - `.agent/evidence/{RUN_ID}/audit-index.json`
  - `docs/audit-report-2026-02-13.md` (historical baseline)

  **Acceptance Criteria**:
  - [ ] Final report includes all mandatory sections: summary, per-ID findings, realism section, regression matrix, priority queue, retest plan.
  - [ ] Every report claim links to evidence artifact path.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Report-evidence linkage verification
    Tool: Bash
    Steps:
      1. Parse report for all verdict entries
      2. Verify each verdict references an existing evidence artifact
      3. Fail if any orphan claim exists
    Expected Result: Zero orphan claims
    Evidence: .agent/evidence/{RUN_ID}/task-11-report-link-check.log
  ```

  **Commit**: NO

- [ ] 12. Final Contradiction and Completeness Gate

  **What to do**:
  - Run contradiction scan across report, index, and regression matrix.
  - Validate that all 29 tasks have final status and confidence.
  - Publish final audit package and update `.agent/progress.md`.

  **Must NOT do**:
  - Do not publish if contradiction gate fails.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `verification-before-completion`, `Code Reviewer`
  - **Skills Evaluated but Omitted**: `writing-skills` (focus is gatekeeping)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: 11

  **References**:
  - `.agent/evidence/{RUN_ID}/audit-index.json`
  - `.agent/evidence/{RUN_ID}/audit-regression-matrix.md`
  - `docs/audit-report-{RUN_ID}.md`
  - `.agent/progress.md`

  **Acceptance Criteria**:
  - [ ] Contradiction checks pass.
  - [ ] Completeness checks pass (29/29 IDs).
  - [ ] Progress file reflects completion.

  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Final release gate
    Tool: Bash
    Steps:
      1. Run jq completeness schema validation on audit-index.json
      2. Run contradiction check script/command over report + index
      3. Assert final package paths exist
    Expected Result: Gate passes and package is publishable
    Evidence: .agent/evidence/{RUN_ID}/task-12-final-gate.log
  ```

  **Commit**: NO

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| All tasks | NO COMMIT (unless user explicitly requests) | Audit evidence/report artifacts only | Final gate commands |

---

## Success Criteria

### Verification Commands
```bash
jq '.tasks | length' .agent/evidence/{RUN_ID}/audit-index.json
# Expected: 29
```

```bash
jq -e 'all(.tasks[]; (.verdict|test("PASS|FAIL|BLOCKED")) and (.passes|type=="boolean"))' .agent/evidence/{RUN_ID}/audit-index.json
# Expected: exit code 0
```

```bash
grep -c "AUDIT-" docs/audit-report-{RUN_ID}.md
# Expected: >= 29 (all tasks represented)
```

### Final Checklist
- [ ] All 29 baseline tasks executed and classified.
- [ ] Regression section distinguishes fixed/regressed/unverifiable clearly.
- [ ] Human-like roleplay quality section includes rubric and transcript evidence.
- [ ] No source code file changed.
- [ ] Final report is contradiction-checked and evidence-linked.
