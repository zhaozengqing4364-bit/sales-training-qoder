# PRD #55 Phase 2 Issues Closed-Loop Implementation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` recommended, or `superpowers:executing-plans`, before executing this plan. Execute issue-by-issue with TDD. Do not modify production code before the failing test exists. Keep commits atomic. Plan-mode note: this response is the complete plan content for conceptual path `docs/superpowers/plans/2026-05-13-prd55-phase2-issues-closed-loop-plan.md`.

**Goal:** Deliver the full PRD #55 Phase 2 curriculum sales training loop across issues `#56`-`#64`: backend baseline, `CurriculumPlan`, StepFun emotion/thinking/voice enhancements, learner path UI, content ops UI, supervisor certification review, and curriculum analytics.

**Architecture:** Extend the shipped PRD #46 Phase 1b foundation. Keep `curriculum_practice` as the content/orchestration domain, `PracticeSession` as the runtime fact anchor, `EvaluationRun` and `TrainingReportSnapshot` as evaluation/report facts, and StepFun logic isolated in narrow `backend/src/sales_bot/websocket/components/*` adapters. Do not create new root lifecycle models or expand existing status enums.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Alembic, pytest/pytest-asyncio, ruff, mypy, Next.js App Router, React 19, TypeScript, Vitest, Tailwind CSS, GitHub Issues, `gh`.

---

## Global Dependency Graph

```text
#56 backend baseline gate
  |
  +--> #57 CurriculumPlan multi-stage runtime
  |      |
  |      +--> #61 learner LearningPath UI and recommendations
  |      |      |
  |      |      +--> #63 supervisor certification review flow
  |      |             |
  |      |             +--> #64 curriculum analytics dashboard
  |      |
  |      +-------------------------------> #63
  |      +-------------------------------> #64
  |
  +--> #58 StepFun emotion signal scoring
  |
  +--> #59 RoleProfile voice clone support
  |      |
  |      +--> #62 CaseItem / RoleProfile Content Ops UI
  |             |
  |             +--> #63
  |
  +--> #60 StepFun thinking reviewer evidence
         |
         +--> #63
```

## Parallel Execution Strategy

```text
Wave 1:
  #56 only

Wave 2, after #56:
  #57, #58, #59, #60 in parallel if separate branches/worktrees exist

Wave 3:
  #61 after #57
  #62 after #59
  #61 and #62 can run in parallel

Wave 4:
  #63 after #57, #60, #61, #62

Wave 5:
  #64 after #57, #61, #63

Wave 6:
  full verification after #56-#64
```

Critical path:

```text
#56 -> #57 -> #61 -> #63 -> #64 -> final verification
```

## Global Invariants

- No `SessionV2`.
- No `TrainingTask.status` expansion.
- No `PracticeSession.status` expansion.
- No `User.role` DB constraint expansion.
- No `ConfigBundle` lifecycle expansion for `PracticeTemplate`, `CaseItem`, `RoleProfile`, or curriculum content assets.
- No historical `TrainingReportSnapshot` recalculation.
- No references to `base_sales_handler`, `enhanced_handler`, or `simple_handler` under `backend/src`.
- Runtime fields for curriculum stages must use `template_stage_*`, not `stage_*`.
- StepFun runtime only reads frozen snapshot payloads, not latest content rows.
- `CaseItem.hidden_information` must not enter StepFun initial prompt or `session.update`.
- New StepFun logic must live in components under `backend/src/sales_bot/websocket/components/`; `stepfun_realtime_handler.py` only wires events and persists outputs.
- `LearningPath` must wrap or call `NextPracticeRecommendationService`; it must not duplicate the recommendation rules engine.
- Raw StepFun thinking is visible only to admin or authorized reviewers.
- Cross-stage voice hot-switching is out of scope; publish gates must warn or reject incompatible adjacent voices.
- Analytics reads frozen lineage and review outcomes, not latest `PracticeTemplate` content.

---

## Atomic Commit Strategy

```bash
git commit -m "test(phase2): establish backend baseline gate"
git commit -m "feat(curriculum): add CurriculumPlan multi-stage runtime"
git commit -m "feat(runtime): add StepFun emotion signal scoring"
git commit -m "feat(curriculum): add RoleProfile voice clone support"
git commit -m "feat(runtime): capture StepFun thinking for reviewer evidence"
git commit -m "feat(curriculum): add learner LearningPath"
git commit -m "feat(web): add CaseItem and RoleProfile content ops UI"
git commit -m "feat(curriculum): add supervisor certification review flow"
git commit -m "feat(admin): add curriculum analytics dashboard"
```

Commit rules:

- One issue should land as one atomic commit, or a small local stack squashed before handoff.
- Do not mix unrelated dirty worktree changes.
- Do not commit secrets, `.env`, coverage HTML, local DB files, or generated artifacts not required by the repo.
- Do not amend unless explicitly requested or a hook modified files after a commit created by the same agent.
- Every commit message must match the actual issue scope.

---

## #56 Test Baseline Gate

### Objective

Establish a trustworthy backend test baseline before Phase 2 feature work starts, so later failures can be attributed to feature regressions rather than collection/env noise.

### Dependencies

- None.

### Files

- Inspect: `backend/pyproject.toml`
- Inspect: `backend/tests/`
- Inspect: `backend/tests/conftest.py`
- Inspect: `backend/src/`
- Optional create: `backend/tests/unit/test_backend_phase2_baseline.py`
- Do not modify production code unless fixing a concrete collection/import bug.

### TDD Steps

- [ ] Write the failing baseline import test if collection has import/module errors.

```python
def test_should_import_phase2_baseline_modules_without_side_effects() -> None:
    import curriculum_practice.models
    import curriculum_practice.schemas
    import curriculum_practice.services.snapshots
    import curriculum_practice.services.publishing_gates
    import evaluation.services.evaluation_run_service

    assert curriculum_practice.models.PracticeTemplate.__tablename__ == "practice_templates"
```

- [ ] Run the test to confirm failure if a real import bug exists.

```bash
cd backend && pytest tests/unit/test_backend_phase2_baseline.py::test_should_import_phase2_baseline_modules_without_side_effects -v
```

Expected failure before fix:

```text
FAIL or ERROR showing the exact broken import/module path.
```

- [ ] Run collection baseline.

```bash
cd backend && pytest --collect-only
```

Expected before fix/quarantine:

```text
Either full collection succeeds, or each collection-time failure is visible with file/module/error.
```

- [ ] Classify failures.

```text
env-only blocker: missing local binary, missing optional service, missing secret, unavailable external service
real collection bug: import error, syntax error, invalid fixture, broken module path, incompatible direct import
unknown blocker: treat as blocking until isolated
```

- [ ] Implement minimal fix for real collection bugs.

Allowed fixes:

```text
correct import path
guard optional test dependency
fix invalid fixture import
fix test package/module path
```

Disallowed fixes:

```text
delete tests
skip entire directories
hide unknown failures with broad xfail
change unrelated production behavior
```

- [ ] Re-run collection.

```bash
cd backend && pytest --collect-only
```

Expected after fix/quarantine:

```text
zero unexpected collection errors, or every remaining env-only blocker is documented with reason.
```

- [ ] Run existing curriculum/runtime regression surfaces.

```bash
cd backend && pytest tests/unit/test_curriculum_publish_gates.py -v
cd backend && pytest tests/unit/test_curriculum_runtime_snapshot_service.py -v
cd backend && pytest tests/unit/test_curriculum_lineage.py -v
cd backend && pytest tests/integration/test_curriculum_practice_session_snapshot.py -v
cd backend && pytest tests/integration/test_curriculum_snapshot_immutability.py -v
cd backend && pytest tests/integration/test_curriculum_report_lineage_immutability.py -v
cd backend && pytest tests/integration/test_curriculum_lineage_flow.py -v
```

Expected:

```text
All targeted tests pass, or only documented env-only blockers from the collection baseline remain.
```

### Interface / State Shape

Baseline note shape for issue/commit handoff:

```text
Backend baseline:
- pytest --collect-only collected: <N> tests
- unexpected collection errors: 0
- quarantined env-only blockers:
  - <path>: <error>; reason: <missing env>; impact: not a Phase 2 regression
- targeted curriculum/runtime surfaces: passed
```

### Verification Commands

```bash
git status --short
cd backend && pytest --collect-only
cd backend && pytest tests/unit/test_curriculum_publish_gates.py tests/unit/test_curriculum_runtime_snapshot_service.py tests/unit/test_curriculum_lineage.py -v
cd backend && pytest tests/integration/test_curriculum_practice_session_snapshot.py tests/integration/test_curriculum_snapshot_immutability.py tests/integration/test_curriculum_report_lineage_immutability.py tests/integration/test_curriculum_lineage_flow.py -v
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
```

Expected output:

```text
git status: unrelated changes identified and not mixed, or clean
pytest --collect-only: zero unexpected collection errors
targeted tests: passed
legacy handler grep: no output
```

### Commit Message

```bash
git commit -m "test(phase2): establish backend baseline gate"
```

### Completion Gate

- `pytest --collect-only` reports zero unexpected collection-time errors, or all remaining env-only blockers are documented.
- Baseline test count is recorded.
- Existing curriculum/runtime regression surfaces run.
- `git status --short` was checked.
- No new legacy sales handler references exist.

### Blocked / Rollback Handling

- If unknown collection blockers remain, stop all feature work and diagnose.
- If a blocker requires secrets/services, document the exact env var/service and quarantine reason.
- If a baseline fix causes unrelated tests to fail, revert only the agent’s own fix and re-diagnose.

---

## #57 CurriculumPlan Multi-Stage Runtime

### Objective

Add full multi-stage `CurriculumPlan` support: admin authoring, publish gates, `stage_snapshots`, runtime `template_stage_context`, bounded timeout handling, hidden-information protection, and lineage propagation.

### Dependencies

- Depends on `#56`.

### Files

- Modify: `backend/src/curriculum_practice/models.py`
- Modify: `backend/src/curriculum_practice/schemas.py`
- Modify: `backend/src/curriculum_practice/api.py`
- Modify: `backend/src/curriculum_practice/services/practice_templates.py`
- Modify: `backend/src/curriculum_practice/services/publishing_gates.py`
- Modify: `backend/src/curriculum_practice/services/snapshots.py`
- Modify: `backend/src/evaluation/services/evaluation_run_service.py`
- Modify: `backend/src/evaluation/services/training_report_snapshot_service.py`
- Modify: `backend/src/common/services/practice_session_service.py`
- Create: `backend/src/sales_bot/websocket/components/curriculum_stage_runtime.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Create: `backend/alembic/versions/<revision>_practice_template_curriculum_plan.py`
- Create: `backend/tests/unit/test_curriculum_plan_schema.py`
- Create: `backend/tests/unit/test_curriculum_plan_publish_gates.py`
- Create: `backend/tests/unit/test_curriculum_stage_runtime.py`
- Create: `backend/tests/integration/test_curriculum_plan_snapshot_lineage.py`
- Create: `backend/tests/integration/test_curriculum_plan_session_flow.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/app/admin/curriculum-practice/templates/page.tsx`
- Modify: `web/src/app/admin/curriculum-practice/templates/page.test.tsx`

### TDD Steps

- [ ] Write failing schema tests.

```python
def test_should_accept_valid_curriculum_plan_with_ordered_template_stages() -> None: ...
def test_should_reject_duplicate_template_stage_keys() -> None: ...
def test_should_reject_invalid_prerequisite_stage_key() -> None: ...
def test_should_reject_stage_duration_above_stepfun_safe_limit() -> None: ...
def test_should_reject_unreachable_curriculum_stage() -> None: ...
def test_should_reject_curriculum_plan_cycle() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_curriculum_plan_schema.py -v
```

Expected failure:

```text
FAIL because CurriculumPlanSchema and template stage validators do not exist.
```

- [ ] Add minimal schema/model fields.

Add to `PracticeTemplate`:

```python
curriculum_plan = Column(JSON, nullable=True)
max_stage_duration_seconds = Column(Integer, nullable=True)
```

Add matching Pydantic fields to create/update/response schemas.

- [ ] Run schema tests again.

```bash
cd backend && pytest tests/unit/test_curriculum_plan_schema.py -v
```

Expected:

```text
PASS for schema validation cases.
```

- [ ] Write failing publish gate tests.

```python
async def test_should_fail_publish_when_child_template_is_unpublished() -> None: ...
async def test_should_fail_publish_when_curriculum_plan_has_cycle() -> None: ...
async def test_should_fail_publish_when_stage_is_unreachable() -> None: ...
async def test_should_fail_publish_when_completion_policy_min_score_is_impossible() -> None: ...
async def test_should_fail_publish_when_stage_duration_exceeds_limit() -> None: ...
async def test_should_warn_or_fail_publish_when_adjacent_stages_have_different_voice_ids() -> None: ...
async def test_should_fail_publish_when_child_template_has_wrong_voice_mode() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_curriculum_plan_publish_gates.py -v
```

Expected failure:

```text
FAIL because curriculum_plan_valid gate does not exist.
```

- [ ] Implement minimal publish gate logic.

Required reason codes:

```text
child_template_unpublished
curriculum_plan_cycle
curriculum_stage_unreachable
completion_policy_impossible
stage_duration_exceeds_limit
child_template_wrong_voice_mode
cross_stage_voice_hot_switch_unsupported
```

- [ ] Run publish gate tests.

```bash
cd backend && pytest tests/unit/test_curriculum_plan_publish_gates.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing snapshot/lineage tests.

```python
async def test_should_include_stage_snapshots_in_runtime_snapshot() -> None: ...
async def test_should_freeze_child_template_versions_and_not_reread_latest_rows() -> None: ...
async def test_should_exclude_hidden_information_from_stepfun_runtime_payload() -> None: ...
async def test_should_propagate_stage_snapshots_to_evaluation_run_and_report() -> None: ...
async def test_should_keep_curriculum_snapshot_under_size_limit() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_curriculum_plan_snapshot_lineage.py -v
```

Expected failure:

```text
FAIL because CurriculumRuntimeSnapshot has no stage_snapshots.
```

- [ ] Implement `stage_snapshots` in `RuntimeSnapshotService`.

Rules:

```text
Resolve each child template at session creation.
Store version refs and minimal frozen runtime payload.
Do not store full child template body.
Do not include CaseItem.hidden_information in StepFun runtime payload.
Do not read latest child template rows during stage execution.
```

- [ ] Extend lineage extraction.

Update `extract_curriculum_lineage()` to preserve:

```text
practice_template
rubric
content_assets
llm_suggestions
stage_snapshots
```

- [ ] Run snapshot/lineage tests.

```bash
cd backend && pytest tests/integration/test_curriculum_plan_snapshot_lineage.py -v
cd backend && pytest tests/integration/test_curriculum_lineage_flow.py -v
```

Expected:

```text
PASS, and report lineage equals evaluation run curriculum_lineage including stage_snapshots.
```

- [ ] Write failing runtime component tests.

```python
def test_should_initialize_template_stage_context_with_first_stage() -> None: ...
def test_should_mark_completion_policy_passed_when_score_and_rounds_satisfied() -> None: ...
def test_should_keep_current_stage_when_retry_current_policy_applies() -> None: ...
def test_should_fallback_to_previous_stage_when_policy_requires() -> None: ...
def test_should_allow_skip_when_policy_requires() -> None: ...
def test_should_emit_timeout_warning_before_stage_limit() -> None: ...
def test_should_apply_bounded_grace_period_before_transition() -> None: ...
def test_should_increment_runtime_state_version_for_optimistic_locking() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_curriculum_stage_runtime.py -v
```

Expected failure:

```text
FAIL because curriculum_stage_runtime.py does not exist.
```

- [ ] Implement `curriculum_stage_runtime.py`.

- [ ] Wire `stepfun_realtime_handler.py` only as an adapter.

Allowed handler behavior:

```text
forward turn/timing events to CurriculumStageRuntime
persist returned runtime_state patch
send warning/transition websocket event
```

Disallowed handler behavior:

```text
inline completion policy algorithm
inline graph traversal
inline timeout/grace-period algorithm
inline hidden-information filtering
```

- [ ] Write failing admin UI tests.

```typescript
it("renders a CurriculumPlan editor inside the PracticeTemplate admin surface", async () => {});
it("serializes template_stage_key prerequisites and completion policy", async () => {});
it("shows stage-level validation errors returned by publish gates", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/admin/curriculum-practice/templates/page.test.tsx
```

Expected failure:

```text
FAIL because CurriculumPlan editor fields are absent.
```

- [ ] Implement admin editor and TypeScript types.

- [ ] Run UI tests and typecheck.

```bash
cd web && npx vitest run src/app/admin/curriculum-practice/templates/page.test.tsx
cd web && npx tsc --noEmit
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```python
class CurriculumStagePrerequisite(BaseModel):
    template_stage_key: str
    required_result: Literal["completed"]

class CurriculumCompletionPolicy(BaseModel):
    min_score: float = Field(ge=0.0)
    min_rounds: int = Field(ge=0)
    max_duration_seconds: int = Field(ge=1, le=1500)

class CurriculumPlanStage(BaseModel):
    template_stage_key: str
    order: int
    name: str
    template_ref: CurriculumVersionRef
    completion_policy: CurriculumCompletionPolicy
    failure_policy: Literal["retry_current", "fallback_to_previous", "allow_skip"] = "retry_current"
    prerequisites: list[CurriculumStagePrerequisite] = Field(default_factory=list)

class CurriculumPlanSchema(BaseModel):
    name: str
    description: str | None = None
    stages: list[CurriculumPlanStage]

class TemplateStageSnapshot(BaseModel):
    template_ref: CurriculumVersionRef
    runtime_payload: dict[str, object]
    content_assets: list[CurriculumVersionRef]
    rubric: CurriculumVersionRef
    runtime: CurriculumRuntimeRef
```

```json
{
  "template_stage_context": {
    "current_template_stage_key": "standard_roleplay",
    "template_stage_progress": {
      "rounds_completed": 2,
      "current_score": 7.5,
      "elapsed_seconds": 480,
      "attempt_count": 1
    },
    "version": 3,
    "last_transition_reason": "completion_policy_passed"
  }
}
```

### Verification Commands

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/unit/test_curriculum_plan_schema.py -v
cd backend && pytest tests/unit/test_curriculum_plan_publish_gates.py -v
cd backend && pytest tests/unit/test_curriculum_stage_runtime.py -v
cd backend && pytest tests/integration/test_curriculum_plan_snapshot_lineage.py -v
cd backend && pytest tests/integration/test_curriculum_plan_session_flow.py -v
cd backend && pytest tests/integration/test_curriculum_lineage_flow.py -v
cd backend && ruff check src/curriculum_practice src/sales_bot/websocket/components src/evaluation
cd backend && mypy src/curriculum_practice src/sales_bot/websocket/components src/evaluation
cd web && npx vitest run src/app/admin/curriculum-practice/templates/page.test.tsx
cd web && npx tsc --noEmit
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
```

Expected output:

```text
Alembic upgrade succeeds.
All targeted backend tests pass.
ruff and mypy pass on touched backend paths.
Vitest and TypeScript pass.
Legacy handler grep has no output.
```

### Commit Message

```bash
git commit -m "feat(curriculum): add CurriculumPlan multi-stage runtime"
```

### Completion Gate

- Admin can create/edit `CurriculumPlan` in existing template admin UI.
- Publish gates reject or warn on all invalid plan cases.
- `RuntimeSnapshotService` writes `stage_snapshots`.
- Stage execution does not reread latest child template rows.
- `hidden_information` is excluded from StepFun runtime payload.
- `EvaluationRun` and `TrainingReportSnapshot` preserve `stage_snapshots`.
- Runtime uses `template_stage_context`.
- StepFun handler delegates only to `curriculum_stage_runtime.py`.
- Status/lifecycle invariants remain unchanged.

### Blocked / Rollback Handling

- If `#56` is incomplete, block.
- If migration conflicts, rebase and regenerate only this issue’s migration.
- If StepFun handler conflicts with `#58` or `#60`, preserve all adapter calls and move any algorithms back into components.
- Rollback removes only `curriculum_plan` and `max_stage_duration_seconds` columns and code paths introduced by this issue.

---

## #58 StepFun Emotion Signal Scoring

### Objective

Extract emotion-related speech signals from existing StepFun VAD/transcript events and make them optional scoring inputs without external API calls.

### Dependencies

- Depends on `#56`.
- Can run in parallel with `#57`, `#59`, and `#60`.

### Files

- Create: `backend/src/sales_bot/websocket/components/stepfun_emotion_analyzer.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/agent/capabilities/realtime_scoring.py`
- Create: `backend/tests/unit/test_emotion_analyzer.py`
- Create: `backend/tests/integration/test_emotion_flow.py`

### TDD Steps

- [ ] Write failing analyzer tests.

```python
def test_should_measure_response_latency_between_ai_stop_and_user_start() -> None: ...
def test_should_measure_speaking_rate_from_transcript_words_and_duration() -> None: ...
def test_should_count_chinese_hesitation_markers() -> None: ...
def test_should_ignore_incomplete_event_sequences_without_crashing() -> None: ...
def test_should_emit_empty_signal_for_empty_transcript() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_emotion_analyzer.py -v
```

Expected failure:

```text
FAIL because stepfun_emotion_analyzer.py does not exist.
```

- [ ] Implement minimal analyzer.

- [ ] Run analyzer tests.

```bash
cd backend && pytest tests/unit/test_emotion_analyzer.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing integration tests.

```python
async def test_should_persist_emotion_log_in_practice_session_runtime_state() -> None: ...
async def test_should_allow_realtime_scoring_to_consume_optional_emotion_dimensions() -> None: ...
async def test_should_skip_emotion_dimensions_when_template_disables_them() -> None: ...
async def test_stepfun_handler_delegates_emotion_events_without_inline_algorithm() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_emotion_flow.py -v
```

Expected failure:

```text
FAIL because runtime_state.emotion_log and scoring integration are missing.
```

- [ ] Implement runtime persistence and optional scoring integration.

- [ ] Wire handler only as an event adapter.

- [ ] Run integration tests.

```bash
cd backend && pytest tests/integration/test_emotion_flow.py -v
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```python
@dataclass(frozen=True)
class EmotionSignal:
    turn_id: str
    signal_type: Literal["response_latency_ms", "speaking_rate", "hesitation_count"]
    value: float
    source_event_ids: tuple[str, ...]
    captured_at: str

class StepFunEmotionAnalyzer:
    def on_speech_started(self, event: dict[str, object]) -> list[EmotionSignal]: ...
    def on_speech_stopped(self, event: dict[str, object]) -> list[EmotionSignal]: ...
    def on_audio_transcript_done(self, event: dict[str, object]) -> list[EmotionSignal]: ...
    def flush_turn(self, turn_id: str) -> list[EmotionSignal]: ...
```

```json
{
  "emotion_log": [
    {
      "turn_id": "turn-3",
      "template_stage_key": "standard_roleplay",
      "response_latency_ms": 820,
      "speaking_rate": 3.4,
      "hesitation_count": 2,
      "captured_at": "2026-05-13T10:00:00Z"
    }
  ]
}
```

Optional scoring config:

```json
{
  "emotion_scoring": {
    "enabled": true,
    "dimensions": {
      "response_confidence": true,
      "fluency": true
    }
  }
}
```

### Verification Commands

```bash
cd backend && pytest tests/unit/test_emotion_analyzer.py -v
cd backend && pytest tests/integration/test_emotion_flow.py -v
cd backend && ruff check src/sales_bot/websocket/components src/agent/capabilities
cd backend && mypy src/sales_bot/websocket/components src/agent/capabilities
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
```

Expected output:

```text
Emotion analyzer tests pass.
Emotion integration tests pass.
ruff/mypy pass.
Legacy handler grep has no output.
```

### Commit Message

```bash
git commit -m "feat(runtime): add StepFun emotion signal scoring"
```

### Completion Gate

- VAD/transcript events produce `response_latency_ms`, `speaking_rate`, and `hesitation_count`.
- `PracticeSession.runtime_state.emotion_log` is bounded and testable.
- Realtime scoring consumes emotion signals only as optional dimensions.
- Templates can disable emotion-derived dimensions.
- Handler only forwards events to analyzer.

### Blocked / Rollback Handling

- If event names differ in local StepFun fixtures, adapt component input normalization, not handler algorithms.
- If signal quality is low, keep dimensions disabled by config.
- Rollback removes analyzer wiring and optional scoring consumption; existing scoring remains unchanged.

---

## #59 RoleProfile Voice Clone Support

### Objective

Add optional StepFun custom voice support to `RoleProfile`, including `voice_id`, `voice_sample_url`, voice clone service, session initialization, and fallback behavior.

### Dependencies

- Depends on `#56`.
- Blocks `#62`.

### Files

- Modify: `backend/src/curriculum_practice/models.py`
- Modify: `backend/src/curriculum_practice/schemas.py`
- Modify: `backend/src/curriculum_practice/api.py`
- Modify: `backend/src/curriculum_practice/services/content_assets.py`
- Create: `backend/src/curriculum_practice/services/voice_clone.py`
- Modify: `backend/src/curriculum_practice/services/publishing_gates.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Create: `backend/alembic/versions/<revision>_role_profile_voice.py`
- Create: `backend/tests/unit/test_voice_clone_service.py`
- Create: `backend/tests/integration/test_voice_clone_flow.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/app/admin/curriculum-practice/templates/page.tsx`

### TDD Steps

- [ ] Write failing RoleProfile schema/model tests.

```python
def test_should_accept_role_profile_voice_id_and_voice_sample_url() -> None: ...
def test_should_include_voice_fields_in_role_profile_response() -> None: ...
def test_should_include_voice_fields_in_role_profile_hash_payload() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_case_item_role_profile_assets.py -v
```

Expected failure:

```text
FAIL because RoleProfile does not expose voice_id or voice_sample_url.
```

- [ ] Add model/schema fields and migration.

- [ ] Run RoleProfile tests.

```bash
cd backend && pytest tests/unit/test_case_item_role_profile_assets.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing voice clone service tests.

```python
async def test_should_return_voice_id_when_stepfun_voice_clone_succeeds() -> None: ...
async def test_should_return_retryable_failure_on_timeout() -> None: ...
async def test_should_return_retryable_failure_on_5xx() -> None: ...
async def test_should_return_non_retryable_failure_on_4xx() -> None: ...
async def test_should_fallback_to_default_voice_when_clone_unavailable() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_voice_clone_service.py -v
```

Expected failure:

```text
FAIL because VoiceCloneService does not exist.
```

- [ ] Implement `VoiceCloneService` with mocked HTTP transport support.

- [ ] Run voice clone unit tests.

```bash
cd backend && pytest tests/unit/test_voice_clone_service.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing integration tests.

```python
async def test_should_register_voice_and_update_role_profile() -> None: ...
async def test_should_initialize_stepfun_session_with_role_profile_voice_id() -> None: ...
async def test_should_fallback_to_default_voice_when_role_voice_unavailable() -> None: ...
async def test_should_warn_or_reject_cross_stage_voice_id_changes_in_publish_gate() -> None: ...
async def test_should_not_attempt_voice_hot_switching_during_runtime() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_voice_clone_flow.py -v
```

Expected failure:

```text
FAIL because API/session initialization integration is missing.
```

- [ ] Implement API and runtime initialization wiring.

- [ ] Run integration tests.

```bash
cd backend && pytest tests/integration/test_voice_clone_flow.py -v
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```python
class RoleProfile(Base):
    voice_id = Column(String(64), nullable=True)
    voice_sample_url = Column(String(512), nullable=True)
```

```python
@dataclass(frozen=True)
class VoiceCloneResult:
    ok: bool
    voice_id: str | None
    retryable: bool
    fallback_voice: str | None
    reason_code: str | None

class VoiceCloneService:
    async def create_voice(
        self,
        *,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
    ) -> VoiceCloneResult: ...
```

API response:

```json
{
  "voice_id": "custom_voice_xxxx",
  "voice_sample_url": "oss://role-voices/sample.wav",
  "fallback_voice": null,
  "reason_code": null
}
```

### Verification Commands

```bash
cd backend && alembic upgrade head
cd backend && pytest tests/unit/test_voice_clone_service.py -v
cd backend && pytest tests/unit/test_case_item_role_profile_assets.py -v
cd backend && pytest tests/integration/test_voice_clone_flow.py -v
cd backend && ruff check src/curriculum_practice src/sales_bot/websocket
cd backend && mypy src/curriculum_practice src/sales_bot/websocket
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
```

Expected output:

```text
Migration succeeds.
Voice clone tests pass.
Content asset tests pass.
ruff/mypy pass.
Legacy handler grep has no output.
```

### Commit Message

```bash
git commit -m "feat(curriculum): add RoleProfile voice clone support"
```

### Completion Gate

- `RoleProfile` supports `voice_id` and `voice_sample_url`.
- Voice clone service handles success, timeout, retryable failure, non-retryable failure, and fallback.
- Admin/API can associate returned `voice_id` with a `RoleProfile`.
- Session initialization uses `RoleProfile.voice_id` when present.
- Runtime falls back safely when absent/unavailable.
- Cross-stage voice mismatch warns/rejects at publish gate.
- Runtime does not hot-switch voice.

### Blocked / Rollback Handling

- If StepFun credentials are unavailable, tests must use mocked HTTP transport.
- If `#57` publish gate code is not merged, implement mismatch detection as a standalone helper and reconcile later.
- Rollback removes voice columns, API endpoint, service, and session initialization branch.

---

## #60 StepFun Thinking Reviewer Evidence

### Objective

Capture StepFun `response.thinking.delta` and `response.thinking.done` events as per-turn reviewer evidence, persist them in `runtime_state`, feed evaluation context, and expose raw thinking only to authorized reviewers.

### Dependencies

- Depends on `#56`.
- Blocks `#63`.

### Files

- Create: `backend/src/sales_bot/websocket/components/stepfun_thinking_capture.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/evaluation/services/evaluation_run_service.py`
- Modify: `backend/src/supervisor/api.py`
- Modify: `backend/src/supervisor/schemas.py`
- Modify: `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- Modify: `web/src/app/admin/supervisor-training/page.tsx`
- Create: `backend/tests/unit/test_thinking_capture.py`
- Create: `backend/tests/integration/test_thinking_scoring_flow.py`
- Create: `backend/tests/contract/test_thinking_visibility_contract.py`

### TDD Steps

- [ ] Write failing capture tests.

```python
def test_should_assemble_delta_chunks_until_done_event() -> None: ...
def test_should_group_thinking_by_response_id_and_stage_key() -> None: ...
def test_should_ignore_empty_delta_without_crashing() -> None: ...
def test_should_flush_bounded_per_turn_thinking_entry() -> None: ...
def test_should_not_mix_chunks_from_parallel_response_ids() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_thinking_capture.py -v
```

Expected failure:

```text
FAIL because stepfun_thinking_capture.py does not exist.
```

- [ ] Implement capture component.

- [ ] Run unit tests.

```bash
cd backend && pytest tests/unit/test_thinking_capture.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing visibility contract tests.

```python
async def test_learner_report_contract_should_not_include_raw_thinking() -> None: ...
async def test_reviewer_contract_should_include_thinking_evidence_when_authorized() -> None: ...
async def test_supervisor_without_scope_should_not_access_thinking_evidence() -> None: ...
async def test_admin_should_access_thinking_evidence() -> None: ...
```

Run:

```bash
cd backend && pytest tests/contract/test_thinking_visibility_contract.py -v
```

Expected failure:

```text
FAIL because thinking visibility filtering is missing.
```

- [ ] Implement API visibility filter.

- [ ] Write failing integration tests.

```python
async def test_should_persist_thinking_log_in_runtime_state() -> None: ...
async def test_should_attach_thinking_context_to_evaluation_input_without_learner_exposure() -> None: ...
async def test_stepfun_handler_delegates_thinking_events_without_inline_chunk_assembly() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_thinking_scoring_flow.py -v
```

Expected failure:

```text
FAIL because runtime_state.thinking_log is missing.
```

- [ ] Wire handler as adapter and persist bounded runtime state.

- [ ] Run integration and contract tests.

```bash
cd backend && pytest tests/integration/test_thinking_scoring_flow.py -v
cd backend && pytest tests/contract/test_thinking_visibility_contract.py -v
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```python
@dataclass(frozen=True)
class ThinkingEntry:
    turn_index: int
    template_stage_key: str | None
    thinking_text: str
    captured_at: str
    response_id: str

class StepFunThinkingCapture:
    def on_delta(self, event: dict[str, object]) -> None: ...
    def on_done(self, event: dict[str, object]) -> ThinkingEntry | None: ...
    def flush_response(self, response_id: str) -> ThinkingEntry | None: ...
```

```json
{
  "thinking_log": [
    {
      "turn_index": 3,
      "template_stage_key": "standard_roleplay",
      "thinking_text": "Reviewer-only reasoning text",
      "captured_at": "2026-05-13T10:00:00Z",
      "response_id": "resp_001"
    }
  ]
}
```

Reviewer-only response:

```json
{
  "thinking_evidence": [
    {
      "turn_index": 3,
      "template_stage_key": "standard_roleplay",
      "response_id": "resp_001",
      "thinking_text": "Reviewer-only reasoning text",
      "captured_at": "2026-05-13T10:00:00Z"
    }
  ]
}
```

Learner response must not include:

```text
thinking_log
thinking_text
thinking_evidence
```

### Verification Commands

```bash
cd backend && pytest tests/unit/test_thinking_capture.py -v
cd backend && pytest tests/integration/test_thinking_scoring_flow.py -v
cd backend && pytest tests/contract/test_thinking_visibility_contract.py -v
cd backend && ruff check src/sales_bot/websocket/components src/evaluation src/supervisor
cd backend && mypy src/sales_bot/websocket/components src/evaluation src/supervisor
cd web && npx vitest run src/app/"(user)"/practice src/app/admin/supervisor-training
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
```

Expected output:

```text
Thinking unit/integration/contract tests pass.
Learner forbidden and reviewer allowed visibility pass.
Frontend tests pass.
ruff/mypy pass.
Legacy handler grep has no output.
```

### Commit Message

```bash
git commit -m "feat(runtime): capture StepFun thinking for reviewer evidence"
```

### Completion Gate

- Delta and done events assemble per response/stage.
- `runtime_state.thinking_log` is persisted.
- Evaluation can consume thinking context.
- Learners never see raw thinking.
- Admin/authorized reviewers can see thinking evidence.
- Handler only forwards thinking events to capture component.

### Blocked / Rollback Handling

- If supervisor API shape changes before `#63`, keep evidence API narrow and typed.
- If frontend report page is dense, implement minimal visibility filtering without refactoring the page.
- Rollback removes capture component wiring and reviewer evidence exposure; learner report remains unchanged.

---

## #61 Learner LearningPath UI and Recommendations

### Objective

Deliver `LearningPath` as a learner-visible capability: cross-report weak-dimension aggregation, reuse of `NextPracticeRecommendationService`, next-task API/card, and full learner path page.

### Dependencies

- Depends on `#57`.
- Blocks `#63` and `#64`.

### Files

- Create: `backend/src/curriculum_practice/services/learning_path.py`
- Modify: `backend/src/curriculum_practice/api.py`
- Modify: `backend/src/evaluation/services/training_report_snapshot_service.py`
- Modify: `backend/src/common/training_tasks/service.py`
- Create: `backend/tests/unit/test_learning_path_engine.py`
- Create: `backend/tests/integration/test_learning_path_flow.py`
- Create: `backend/tests/contract/test_learning_path_api_contract.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/lib/api/client-domains.ts`
- Modify: `web/src/app/(dashboard)/page.tsx`
- Create: `web/src/app/(user)/learning-path/page.tsx`
- Create: `web/src/app/(user)/learning-path/page.test.tsx`

### TDD Steps

- [ ] Write failing backend unit tests.

```python
async def test_should_aggregate_weak_dimensions_across_recent_reports() -> None: ...
async def test_should_trace_recommendation_reason_to_report_dimension_and_score() -> None: ...
async def test_should_reuse_next_practice_recommendation_service() -> None: ...
async def test_should_deduplicate_templates_by_highest_severity() -> None: ...
async def test_should_return_role_default_path_for_cold_start_user() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_learning_path_engine.py -v
```

Expected failure:

```text
FAIL because LearningPathService does not exist.
```

- [ ] Implement `LearningPathService` that wraps `NextPracticeRecommendationService`.

- [ ] Run unit tests.

```bash
cd backend && pytest tests/unit/test_learning_path_engine.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing contract tests.

```python
async def test_next_task_api_contract_returns_recommendation_reason_and_cta() -> None: ...
async def test_learning_path_api_contract_returns_ordered_stages_and_prerequisites() -> None: ...
async def test_learning_path_api_contract_returns_failure_reason() -> None: ...
async def test_learning_path_api_contract_returns_pending_review_placeholder() -> None: ...
```

Run:

```bash
cd backend && pytest tests/contract/test_learning_path_api_contract.py -v
```

Expected failure:

```text
FAIL because learner LearningPath APIs are missing.
```

- [ ] Implement learner APIs.

Endpoints:

```text
GET /api/v1/curriculum-practice/learning-path/me
GET /api/v1/curriculum-practice/learning-path/me/next-task
```

- [ ] Run contract and integration tests.

```bash
cd backend && pytest tests/contract/test_learning_path_api_contract.py -v
cd backend && pytest tests/integration/test_learning_path_flow.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing frontend tests.

```typescript
it("renders next-task card with recommendation reason and primary CTA", async () => {});
it("renders full learning path stages with prerequisites", async () => {});
it("renders failure reason and retry action", async () => {});
it("renders pending review placeholder for certification path", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/"(user)"/learning-path/page.test.tsx src/app/"(dashboard)"/page.test.tsx
```

Expected failure:

```text
FAIL because learner path page and dashboard next-task card are missing.
```

- [ ] Implement frontend page, dashboard card, API types, and API client methods.

- [ ] Run frontend tests.

```bash
cd web && npx vitest run src/app/"(user)"/learning-path/page.test.tsx src/app/"(dashboard)"/page.test.tsx
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```python
@dataclass(frozen=True)
class LearningPathRecommendationReason:
    source_report_id: str
    dimension_name: str
    score: float
    recommended_template_id: str

class LearningPathService:
    async def build_for_user(self, user_id: str, *, lookback: int = 3) -> dict[str, object]: ...
```

```typescript
export type LearningPathStageState =
  | "locked"
  | "available"
  | "in_progress"
  | "completed"
  | "failed"
  | "pending_review"
  | "retraining_required";

export interface LearningPathStage {
  template_stage_key: string;
  name: string;
  state: LearningPathStageState;
  prerequisites: Array<{ template_stage_key: string; required_result: "completed" }>;
  completion_policy: Record<string, unknown>;
  report_url?: string | null;
  failure_reason?: string | null;
}

export interface LearningPathResponse {
  user_id: string;
  path_type: "weakness_driven" | "role_default";
  recommended_template_ids: string[];
  recommendation_reasons: Array<{
    dimension_name: string;
    score: number;
    source_report_id: string;
    recommended_template_id: string;
  }>;
  next_task: {
    title: string;
    state: LearningPathStageState;
    primary_cta: string;
    estimated_duration_minutes?: number | null;
    failure_reason?: string | null;
  };
  stages: LearningPathStage[];
}
```

### Verification Commands

```bash
cd backend && pytest tests/unit/test_learning_path_engine.py -v
cd backend && pytest tests/integration/test_learning_path_flow.py -v
cd backend && pytest tests/contract/test_learning_path_api_contract.py -v
cd backend && ruff check src/curriculum_practice src/common/training_tasks
cd backend && mypy src/curriculum_practice src/common/training_tasks
cd web && npx vitest run src/app/"(user)"/learning-path/page.test.tsx src/app/"(dashboard)"/page.test.tsx
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
```

Expected output:

```text
LearningPath backend tests pass.
LearningPath contract tests pass.
Dashboard and learner path tests pass.
TypeScript and ESLint pass.
```

### Commit Message

```bash
git commit -m "feat(curriculum): add learner LearningPath"
```

### Completion Gate

- Recent report weakness aggregation works.
- Recommendation reasons trace to report ID, dimension, and score.
- `NextPracticeRecommendationService` is reused.
- Cold-start users get a role/default path.
- Dashboard shows next-task card.
- Full path page shows stages, prerequisites, policy, report links, failure reason, and pending review placeholder.
- No type suppression is introduced.

### Blocked / Rollback Handling

- If `#57` stage shape changes, update only DTO mapping.
- If default path source is unavailable, use deterministic configured fallback.
- Rollback removes learner APIs and UI, leaving existing dashboard behavior unchanged.

---

## #62 CaseItem / RoleProfile Content Ops UI

### Objective

Give content operators self-service admin pages for `CaseItem` and `RoleProfile`, plus CSV bulk import with row-level errors and template-editor asset attachment.

### Dependencies

- Depends on `#59`.
- Blocks `#63`.

### Files

- Create: `web/src/app/admin/curriculum-practice/case-items/page.tsx`
- Create: `web/src/app/admin/curriculum-practice/case-items/page.test.tsx`
- Create: `web/src/app/admin/curriculum-practice/role-profiles/page.tsx`
- Create: `web/src/app/admin/curriculum-practice/role-profiles/page.test.tsx`
- Modify: `web/src/app/admin/curriculum-practice/templates/page.tsx`
- Modify: `web/src/components/layout/admin-sidebar.tsx`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`
- Modify: `web/src/lib/api/client-domains.ts`
- Modify: `backend/src/curriculum_practice/api.py`
- Modify: `backend/src/curriculum_practice/services/content_assets.py`
- Modify: `backend/tests/unit/test_case_item_role_profile_assets.py`
- Create: `backend/tests/integration/test_content_asset_bulk_import.py`

### TDD Steps

- [ ] Write failing bulk import backend tests.

```python
async def test_should_bulk_import_valid_case_items() -> None: ...
async def test_should_return_row_level_errors_for_invalid_case_items() -> None: ...
async def test_should_not_silently_drop_invalid_csv_rows() -> None: ...
async def test_should_reuse_content_asset_service_for_bulk_import() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_content_asset_bulk_import.py -v
```

Expected failure:

```text
FAIL because bulk import endpoint/service method does not exist.
```

- [ ] Implement bulk import using existing `ContentAssetService`.

- [ ] Run bulk import tests.

```bash
cd backend && pytest tests/integration/test_content_asset_bulk_import.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing CaseItem page tests.

```typescript
it("lists and filters CaseItems", async () => {});
it("creates and edits a draft CaseItem", async () => {});
it("shows publish gate errors", async () => {});
it("archives a CaseItem", async () => {});
it("shows row-level CSV import errors", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/admin/curriculum-practice/case-items/page.test.tsx
```

Expected failure:

```text
FAIL because CaseItem page is missing.
```

- [ ] Implement CaseItem admin page.

- [ ] Write failing RoleProfile page tests.

```typescript
it("lists and filters RoleProfiles", async () => {});
it("creates and edits a RoleProfile with persona reuse", async () => {});
it("shows voice_id and voice_sample_url fields", async () => {});
it("publishes and archives RoleProfiles", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/admin/curriculum-practice/role-profiles/page.test.tsx
```

Expected failure:

```text
FAIL because RoleProfile page is missing.
```

- [ ] Implement RoleProfile admin page.

- [ ] Extend template editor tests for asset search/attachment.

```typescript
it("searches and attaches a published CaseItem from the template editor", async () => {});
it("searches and attaches a published RoleProfile from the template editor", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/admin/curriculum-practice/templates/page.test.tsx
```

Expected failure before implementation:

```text
FAIL because asset search/attachment controls are missing.
```

- [ ] Implement template editor attachment.

- [ ] Run all content ops tests.

```bash
cd web && npx vitest run src/app/admin/curriculum-practice
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```typescript
export interface CaseItemRecord {
  case_item_id: string;
  industry: string;
  company_profile: string;
  customer_role: string;
  pain_points: string[];
  objections: string[];
  hidden_information: string;
  success_criteria: string[];
  allowed_disclosure_policy: Record<string, unknown>;
  version: number;
  content_hash: string;
  status: "draft" | "published" | "archived" | string;
}

export interface RoleProfileRecord {
  role_profile_id: string;
  role_type: "customer" | string;
  role_name: string;
  persona_ref?: string | null;
  communication_style: string;
  pressure_level: "low" | "medium" | "high";
  knowledge_boundary: string[];
  behavior_rules: string[];
  voice_style_hint: string;
  voice_id?: string | null;
  voice_sample_url?: string | null;
  version: number;
  content_hash: string;
  status: "draft" | "published" | "archived" | string;
}
```

Bulk import response:

```json
{
  "created_count": 3,
  "failed_count": 2,
  "row_errors": [
    {
      "row_number": 4,
      "field": "allowed_disclosure_policy",
      "message": "phases must contain at least one phase"
    }
  ]
}
```

### Verification Commands

```bash
cd backend && pytest tests/unit/test_case_item_role_profile_assets.py -v
cd backend && pytest tests/integration/test_content_asset_bulk_import.py -v
cd backend && pytest tests/integration/ -k "case_item or role_profile or content_asset" -v
cd web && npx vitest run src/app/admin/curriculum-practice
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
```

Expected output:

```text
Backend asset and bulk import tests pass.
Admin page tests pass.
TypeScript and ESLint pass.
No type suppression is introduced.
```

### Commit Message

```bash
git commit -m "feat(web): add CaseItem and RoleProfile content ops UI"
```

### Completion Gate

- CaseItem admin page supports list/search/filter/create/edit/publish/archive.
- RoleProfile page supports list/search/filter/create/edit/publish/archive, Persona reuse, `voice_id`, and `voice_sample_url`.
- CSV import reports row-level errors.
- Template editor can search and attach published CaseItems and RoleProfiles.
- Backend reuses existing content asset service.
- No `as any`, `@ts-ignore`, or `@ts-expect-error`.

### Blocked / Rollback Handling

- If `#59` voice fields are missing, block RoleProfile page completion.
- If CSV parsing requires new dependency, prefer standard library/simple parser first.
- Rollback removes new pages and bulk import endpoint; existing CRUD APIs remain.

---

## #63 Supervisor Certification Review Flow

### Objective

Add certification/onboarding review loop: high-stakes sessions enter supervisor queue, ordinary practice remains AI auto-report, reviewers can approve/reject/calibrate/retrain, and outcomes update `LearningPath` and feed analytics.

### Dependencies

- Depends on `#57`, `#60`, `#61`, and `#62`.
- Blocks `#64`.

### Files

- Modify: `backend/src/supervisor/service.py`
- Modify: `backend/src/supervisor/api.py`
- Modify: `backend/src/supervisor/schemas.py`
- Modify: `backend/src/curriculum_practice/services/learning_path.py`
- Modify: `backend/src/common/training_tasks/service.py`
- Create: `backend/tests/unit/test_curriculum_supervisor_review.py`
- Create: `backend/tests/integration/test_curriculum_certification_review_flow.py`
- Create: `backend/tests/contract/test_curriculum_review_visibility_contract.py`
- Modify: `web/src/app/admin/supervisor-training/page.tsx`
- Modify: `web/src/app/admin/supervisor-training/page.test.tsx`
- Modify: `web/src/app/(user)/learning-path/page.tsx`
- Modify: `web/src/app/(user)/learning-path/page.test.tsx`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`

### TDD Steps

- [ ] Write failing supervisor review unit tests.

```python
async def test_should_create_review_queue_item_for_certification_session() -> None: ...
async def test_should_not_create_review_queue_item_for_ordinary_practice() -> None: ...
async def test_should_prioritize_borderline_or_failed_certification_items() -> None: ...
async def test_should_persist_approve_outcome_with_audit_metadata() -> None: ...
async def test_should_persist_reject_outcome_with_reason() -> None: ...
async def test_should_persist_calibration_scores_with_reason() -> None: ...
async def test_should_create_retraining_task_when_retrain_requested() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_curriculum_supervisor_review.py -v
```

Expected failure:

```text
FAIL because certification review queue wiring does not exist.
```

- [ ] Implement minimal service queue/outcome logic.

- [ ] Run unit tests.

```bash
cd backend && pytest tests/unit/test_curriculum_supervisor_review.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing integration tests.

```python
async def test_certification_session_enters_review_queue_after_report_generation() -> None: ...
async def test_ordinary_practice_still_auto_generates_report_without_review() -> None: ...
async def test_retrain_action_creates_followup_training_task_and_learning_path_state() -> None: ...
async def test_review_outcomes_are_available_for_analytics_consumption() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_curriculum_certification_review_flow.py -v
```

Expected failure:

```text
FAIL because report-to-review flow is not wired.
```

- [ ] Implement report-to-review flow and retraining link.

- [ ] Write failing RBAC/visibility contract tests.

```python
async def test_admin_can_view_all_certification_reviews() -> None: ...
async def test_supervisor_can_view_only_authorized_team_reviews() -> None: ...
async def test_learner_cannot_access_reviewer_only_evidence() -> None: ...
async def test_unauthorized_supervisor_cannot_take_review_action() -> None: ...
async def test_authorized_reviewer_can_view_thinking_evidence() -> None: ...
```

Run:

```bash
cd backend && pytest tests/contract/test_curriculum_review_visibility_contract.py -v
```

Expected failure:

```text
FAIL because certification review endpoints or action-level RBAC are missing.
```

- [ ] Implement API actions and RBAC checks.

Actions:

```text
approve
reject
calibrate
retrain
```

- [ ] Run backend tests.

```bash
cd backend && pytest tests/unit/test_curriculum_supervisor_review.py -v
cd backend && pytest tests/integration/test_curriculum_certification_review_flow.py -v
cd backend && pytest tests/contract/test_curriculum_review_visibility_contract.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing frontend tests.

```typescript
it("renders certification review queue items with learner curriculum and submitted time", async () => {});
it("renders stage snapshots and thinking evidence for authorized reviewer", async () => {});
it("submits approve reject calibrate and retrain actions", async () => {});
it("shows retraining_required state on learner path after retrain outcome", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/admin/supervisor-training/page.test.tsx src/app/"(user)"/learning-path/page.test.tsx
```

Expected failure:

```text
FAIL because certification review UI and learner retraining state are missing.
```

- [ ] Implement supervisor and learner UI.

- [ ] Run frontend tests.

```bash
cd web && npx vitest run src/app/admin/supervisor-training/page.test.tsx src/app/"(user)"/learning-path/page.test.tsx
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

```python
class CurriculumReviewOutcome(BaseModel):
    action: Literal["approve", "reject", "calibrate", "retrain"]
    reason: str
    calibrated_scores: dict[str, float] | None = None
```

Review queue item:

```json
{
  "review_id": "review-1",
  "session_id": "session-1",
  "report_id": "report-1",
  "learner_id": "learner-1",
  "curriculum": {
    "practice_template": {},
    "stage_snapshots": {}
  },
  "score": 72,
  "evidence": {
    "transcript_anchors": [],
    "stage_snapshots": {},
    "thinking_evidence": []
  },
  "submitted_at": "2026-05-13T10:00:00Z",
  "outcome": "pending"
}
```

Persisted action metadata:

```json
{
  "reviewer_id": "reviewer-1",
  "reviewed_at": "2026-05-13T10:30:00Z",
  "reason": "Needs retraining on objection handling",
  "report_id": "report-1",
  "calibrated_scores": {
    "objection_handling": 4.5
  }
}
```

### Verification Commands

```bash
cd backend && pytest tests/unit/test_curriculum_supervisor_review.py -v
cd backend && pytest tests/integration/test_curriculum_certification_review_flow.py -v
cd backend && pytest tests/contract/test_curriculum_review_visibility_contract.py -v
cd backend && pytest tests/contract/test_thinking_visibility_contract.py -v
cd backend && ruff check src/supervisor src/curriculum_practice src/common/training_tasks
cd backend && mypy src/supervisor src/curriculum_practice src/common/training_tasks
cd web && npx vitest run src/app/admin/supervisor-training/page.test.tsx src/app/"(user)"/learning-path/page.test.tsx
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
```

Expected output:

```text
Supervisor review tests pass.
Thinking visibility still passes.
Supervisor and learner UI tests pass.
TypeScript and ESLint pass.
```

### Commit Message

```bash
git commit -m "feat(curriculum): add supervisor certification review flow"
```

### Completion Gate

- Certification/onboarding sessions enter supervisor review queue.
- Ordinary practice remains AI auto-report.
- Queue shows learner, curriculum, stage, score, evidence, submitted time, `stage_snapshots`, and reviewer-visible thinking evidence.
- Approve/reject/calibrate/retrain actions persist audit metadata.
- Retrain creates or links follow-up `TrainingTask`.
- `LearningPath` shows `retraining_required`.
- RBAC is action-level; no `User.role` DB constraint expansion.
- Analytics can consume review outcomes.

### Blocked / Rollback Handling

- If `#60` thinking evidence is missing, block reviewer evidence completion.
- If `#61` learner states are missing, block learner retraining state completion.
- If supervisor domain already has equivalent model/service, extend it rather than creating a parallel supervisor root.
- Rollback disables certification queue creation and action endpoints; ordinary reports remain unchanged.

---

## #64 Curriculum Analytics Dashboard

### Objective

Add curriculum analytics dashboard using frozen session/report/review data: completion, weak dimensions, score trend, heatmap, supervisor outcomes, retraining conversion, RBAC, and performance limits.

### Dependencies

- Depends on `#57`, `#61`, and `#63`.

### Files

- Create: `backend/src/admin/api/analytics_curriculum.py`
- Create: `backend/tests/unit/test_curriculum_analytics_service.py`
- Create: `backend/tests/integration/test_curriculum_analytics_api.py`
- Create: `backend/tests/performance/test_curriculum_analytics_performance.py`
- Create: `web/src/app/admin/analytics/curriculum/page.tsx`
- Create: `web/src/app/admin/analytics/curriculum/page.test.tsx`
- Create: `web/src/components/analytics/curriculum-heatmap.tsx`
- Create: `web/src/components/analytics/curriculum-score-trend.tsx`
- Modify: `web/src/app/admin/page.tsx`
- Modify: `web/src/components/layout/admin-sidebar.tsx`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/client.ts`

### TDD Steps

- [ ] Write failing analytics unit tests.

```python
async def test_should_calculate_completion_count_and_rate() -> None: ...
async def test_should_find_top_weak_dimension_from_report_snapshots() -> None: ...
async def test_should_calculate_average_score_delta() -> None: ...
async def test_should_build_dimension_by_template_heatmap_from_stage_snapshots() -> None: ...
async def test_should_calculate_30_day_score_trend() -> None: ...
async def test_should_include_supervisor_review_outcome_distribution() -> None: ...
async def test_should_include_retraining_conversion_metrics() -> None: ...
async def test_should_not_read_latest_practice_template_content() -> None: ...
```

Run:

```bash
cd backend && pytest tests/unit/test_curriculum_analytics_service.py -v
```

Expected failure:

```text
FAIL because curriculum analytics service/API does not exist.
```

- [ ] Implement aggregation service.

Allowed sources:

```text
TrainingReportSnapshot.report_payload.lineage.stage_snapshots
PracticeSession.curriculum_snapshot
PracticeSession.runtime_state.template_stage_context
SupervisorReview outcomes
TrainingTask retraining/follow-up links
```

Disallowed sources:

```text
latest PracticeTemplate content
latest CaseItem content
latest RoleProfile content
historical report recalculation
```

- [ ] Run unit tests.

```bash
cd backend && pytest tests/unit/test_curriculum_analytics_service.py -v
```

Expected:

```text
PASS.
```

- [ ] Write failing API integration tests.

```python
async def test_admin_curriculum_analytics_returns_summary_heatmap_trend_and_review_outcomes() -> None: ...
async def test_supervisor_scope_returns_only_authorized_team_data() -> None: ...
async def test_query_requires_date_range_or_applies_safe_default() -> None: ...
async def test_cache_path_is_used_only_when_existing_cache_is_available() -> None: ...
async def test_no_cache_path_uses_query_limits_without_new_infrastructure() -> None: ...
```

Run:

```bash
cd backend && pytest tests/integration/test_curriculum_analytics_api.py -v
```

Expected failure:

```text
FAIL because curriculum analytics endpoint is missing.
```

- [ ] Implement API endpoint and RBAC scope.

- [ ] Write performance tests.

```python
@pytest.mark.performance
async def test_curriculum_analytics_initial_load_under_two_seconds() -> None: ...

@pytest.mark.performance
async def test_curriculum_analytics_cache_hit_under_500ms_when_cache_enabled() -> None: ...
```

Run:

```bash
cd backend && pytest tests/performance/test_curriculum_analytics_performance.py -v
```

Expected failure before performance implementation:

```text
FAIL because endpoint/service timing behavior is not implemented.
```

- [ ] Implement bounded date range/query limits and optional existing-cache path.

- [ ] Write failing frontend tests.

```typescript
it("renders summary cards for completion weak dimension and score delta", async () => {});
it("renders dimension by template heatmap", async () => {});
it("renders 30 day score trend", async () => {});
it("renders supervisor review outcome distribution", async () => {});
it("shows safe empty state when analytics has no data", async () => {});
```

Run:

```bash
cd web && npx vitest run src/app/admin/analytics/curriculum/page.test.tsx
```

Expected failure:

```text
FAIL because curriculum analytics dashboard page is missing.
```

- [ ] Implement dashboard page, heatmap, trend components, admin entry, and sidebar link.

- [ ] Run frontend tests.

```bash
cd web && npx vitest run src/app/admin/analytics/curriculum/page.test.tsx
```

Expected:

```text
PASS.
```

### Interface / Schema / State Shape

API response:

```json
{
  "summary": {
    "completed_count": 23,
    "assigned_count": 25,
    "completion_rate": 0.92,
    "top_weak_dimension": "objection_handling",
    "average_score_delta": 2.6
  },
  "heatmap": [
    {
      "template_id": "template-1",
      "template_name": "Onboarding",
      "dimension": "objection_handling",
      "average_score": 5.1,
      "sample_count": 12
    }
  ],
  "score_trend": [
    {
      "date": "2026-05-01",
      "average_score": 6.2,
      "sample_count": 5
    }
  ],
  "review_outcomes": {
    "approved": 8,
    "rejected": 2,
    "calibrated": 3,
    "retraining_required": 4
  },
  "retraining_conversion": {
    "created": 4,
    "started": 3,
    "completed": 2
  },
  "cache": {
    "enabled": false,
    "hit": false,
    "ttl_seconds": null
  }
}
```

### Verification Commands

```bash
cd backend && pytest tests/unit/test_curriculum_analytics_service.py -v
cd backend && pytest tests/integration/test_curriculum_analytics_api.py -v
cd backend && pytest tests/performance/test_curriculum_analytics_performance.py -v
cd backend && ruff check src/admin
cd backend && mypy src/admin
cd web && npx vitest run src/app/admin/analytics/curriculum/page.test.tsx
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
```

Expected output:

```text
Analytics unit/integration/performance tests pass.
Dashboard tests pass.
Initial load target <= 2s.
Cache hit target <= 500ms when cache is enabled.
TypeScript and ESLint pass.
```

### Commit Message

```bash
git commit -m "feat(admin): add curriculum analytics dashboard"
```

### Completion Gate

- Admin analytics shows completion count/rate, top weak dimension, average score delta, heatmap, and 30-day score trend.
- Dashboard includes supervisor review outcomes and retraining conversion.
- Analytics uses frozen `TrainingReportSnapshot`, `PracticeSession` snapshot data, and review outcomes.
- No historical fact query reads latest `PracticeTemplate` content.
- RBAC scope is enforced.
- Cache is reused only if existing infrastructure supports it.
- No-cache path uses date range and query limits.

### Blocked / Rollback Handling

- If `#63` review outcomes are unavailable, block outcome/conversion metrics.
- If no reusable cache exists, ship bounded no-cache aggregation with explicit limits.
- Rollback removes analytics endpoint/page/sidebar entry; existing analytics remain unchanged.

---

## Final Full Verification Commands

Run after all issues land:

```bash
git status --short
cd backend && alembic upgrade head
cd backend && pytest
cd backend && ruff check src tests
cd backend && mypy src
cd web && npx vitest run
cd web && npx tsc --noEmit
cd web && npx eslint . --quiet
grep -R "base_sales_handler\|enhanced_handler\|simple_handler" backend/src || true
grep -R "SessionV2" backend/src web/src || true
grep -R "status IN ('assigned', 'in_progress', 'completed', 'expired', 'cancelled'" backend/src/common/db/models.py
grep -R "status IN ('preparing', 'in_progress', 'paused', 'completed', 'scoring'" backend/src/common/db/models.py
```

Expected output:

```text
git status: only intentional changes, or clean after commits
alembic upgrade: succeeds
backend pytest: passes, except #56-documented env-only quarantines if any
ruff: passes
mypy: passes
vitest: passes
tsc: passes
eslint: passes
legacy handler grep: no output
SessionV2 grep: no output
TrainingTask and PracticeSession status constraints remain unchanged
```

Targeted Phase 2 matrix:

```bash
cd backend && pytest tests/unit/test_curriculum_plan_schema.py tests/unit/test_curriculum_plan_publish_gates.py tests/unit/test_curriculum_stage_runtime.py -v
cd backend && pytest tests/unit/test_emotion_analyzer.py tests/unit/test_voice_clone_service.py tests/unit/test_thinking_capture.py tests/unit/test_learning_path_engine.py -v
cd backend && pytest tests/unit/test_curriculum_supervisor_review.py tests/unit/test_curriculum_analytics_service.py -v
cd backend && pytest tests/integration/test_curriculum_plan_snapshot_lineage.py tests/integration/test_curriculum_plan_session_flow.py -v
cd backend && pytest tests/integration/test_emotion_flow.py tests/integration/test_voice_clone_flow.py tests/integration/test_thinking_scoring_flow.py -v
cd backend && pytest tests/integration/test_learning_path_flow.py tests/integration/test_curriculum_certification_review_flow.py tests/integration/test_curriculum_analytics_api.py -v
cd backend && pytest tests/contract/test_learning_path_api_contract.py tests/contract/test_thinking_visibility_contract.py tests/contract/test_curriculum_review_visibility_contract.py -v
```

Expected output:

```text
All targeted Phase 2 tests pass.
```

---

## Self-Review Matrix

| Issue | PRD Key Capability | Plan Coverage |
|-------|--------------------|---------------|
| `#56` | Clean baseline before Phase 2 feature work | Collection gate, targeted regression tests, quarantine note, legacy handler grep |
| `#57` | Multi-stage `CurriculumPlan`, frozen `stage_snapshots`, stage runtime, timeout | Schema, migration, publish gates, snapshot service, runtime adapter, admin editor, lineage tests |
| `#58` | StepFun emotion signal scoring | Analyzer component, runtime_state emotion log, optional scoring dimensions, no handler algorithms |
| `#59` | RoleProfile voice clone support | Voice fields, migration, API/service, fallback, session initialization, no hot-switching |
| `#60` | StepFun thinking reviewer evidence | Capture component, runtime_state thinking log, reviewer-only API, learner-hidden contract |
| `#61` | Learner LearningPath UI and recommendations | Service wrapping `NextPracticeRecommendationService`, APIs, dashboard card, full path page |
| `#62` | CaseItem / RoleProfile Content Ops UI | Admin pages, typed API, bulk import row errors, template asset attachment |
| `#63` | Supervisor certification review flow | Queue, approve/reject/calibrate/retrain, RBAC, thinking evidence, LearningPath retraining state |
| `#64` | Curriculum analytics dashboard | Frozen-lineage aggregation, heatmap, score trend, review outcomes, retraining conversion, RBAC/performance |
| All | PRD #23 invariants and closed loop | Global invariant list, final verification commands, atomic commit strategy, rollback handling |
