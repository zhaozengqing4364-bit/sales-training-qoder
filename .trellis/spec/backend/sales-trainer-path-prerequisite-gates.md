# Sales Trainer Path Prerequisite Gates

> Executable backend contract for `unlock_after_unit_ids` in the governed newcomer training path.

## Scenario: Ordered Newcomer Path Prerequisites

### 1. Scope / Trigger

- Trigger: changing newcomer path module configuration, Training Journey completion or locking, legacy `/paths` projection, learner unit/material/audio/realtime access, or path-revision evidence lineage.
- Scope: `newcomer_training_path_v1` working/active revisions, `TrainingJourney.modules`, derived AI Coach modules, legacy learner path projection, and all learner direct-entry gates.
- Out of scope: a general DAG engine, learning-topic completion gates, database migrations, or Readiness permission changes.

### 2. Signatures

Configuration field:

```python
class NewcomerPathModuleConfig(BaseModel):
    unlock_after_unit_ids: list[str] = Field(default_factory=list)
```

Pure policy boundary:

```python
def validate_prerequisite_references(modules: Iterable[Any]) -> None: ...

def evaluate_prerequisites(
    states: list[PrerequisiteModuleState],
) -> dict[str, PrerequisiteDecision]: ...
```

Journey evidence identity:

```python
class TrainingJourneyModuleOutcome(BaseModel):
    target_unit_id: str | None
```

### 3. Contracts

- `unlock_after_unit_ids` references target unit IDs, not module keys.
- Every reference must resolve inside the same path payload to exactly one enabled, earlier, completable required-path module. An audio group may own several distinct target units; only duplicate ownership of the same target is ambiguous. Completion is evaluated for the referenced duration target, so evidence for another option in the same group cannot unlock it.
- Realtime modules and active learning-topic source modules cannot be prerequisite owners.
- New save/update requests reject blank or duplicate prerequisite IDs at the Pydantic boundary. Historical payload parsing preserves those values through an explicit validation context so runtime policy can fail closed instead of returning 500.
- `TrainingJourneyService` is the runtime authority. It applies the pure policy once after stronger learner/config locks and before public payload projection. Prerequisite policy may add a lock but must never remove an existing lock.
- Only passed/completion-satisfying evidence whose `path_revision_id` equals the current active revision can unlock an owner. Legacy snapshots, old revisions, other target units, and failed evidence do not unlock.
- AI Coach modules inherit the final decision of their `base_module_key`.
- Legacy `/paths` copies Journey status, lock, and current-revision outcome data; it must not recompute `completed_unit_ids` locally. `target_unit_id` aligns audio-group and regrade outcomes to exactly one legacy level.
- Learning topics remain `required=false` and `blocks_next=false`; they are projected separately and are not locked by required-path prerequisites.
- Learner unit/brief, audio submission, material download, and realtime start reuse Journey access decisions. Locked objects remain hidden: unit/audio/realtime return 404 `[SALES_TRAINER_UNIT_NOT_FOUND]`; material files return 404 `[MATERIAL_FILE_NOT_FOUND]`. No submission or session is created on denial.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Blank or duplicate `unlock_after_unit_ids` in path-config PUT | HTTP 422 `[NEWCOMER_PATH_PREREQUISITE_INVALID]`; no working revision written |
| Unknown, same/future-order, disabled, realtime, learning-topic, or ambiguously owned target | Reject save/publish with `[NEWCOMER_PATH_PREREQUISITE_INVALID]`; active pointer does not move |
| Valid owner has no current-revision completion evidence | Journey locked / `not_started`; nonterminal `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]` |
| Historical active revision contains an invalid reference | Journey locked / `error_terminal`; terminal `[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]`; no 500 |
| Owner has passed evidence from an old revision only | Keep dependent locked and direct entries hidden as 404 |
| Audio group has current evidence for a different duration target | Keep the exact referenced target locked |
| Owner has completion-satisfying evidence from current active revision | Unlock dependent unless another stronger lock remains |
| Existing learner/config/readiness lock exists | Preserve the existing lock; prerequisite evaluation cannot loosen it |
| Optional learning topic exists while required path has an unmet prerequisite | Topic remains accessible and excluded from required progress |

### 5. Good/Base/Bad Cases

- Good: `ppt_explanation` owns `ppt-unit`; later `company_product_demo.unlock_after_unit_ids=["ppt-unit"]`; a passed `ppt-unit` outcome frozen to the active revision unlocks the demo everywhere in the same request model.
- Good: an audio group owns three unique duration unit IDs; a later module may reference one of them because ownership is still unique, and only evidence for that exact target unlocks it.
- Base: `unlock_after_unit_ids=[]`; prerequisite policy leaves existing locks and completion semantics unchanged.
- Bad: a learner page unlocks from the latest global audio result without checking `path_revision_id`.
- Bad: material download checks only whether its version is bound to any active module and ignores the module's Journey lock.
- Bad: `business_skills` or another active learning-topic source is used as a required-path prerequisite owner.

### 6. Tests Required

- Policy unit tests: valid earlier owner; blank/duplicate/unknown/same/future references; disabled/realtime/learning-topic owner; duplicate target ownership; exact multi-target completion; historical invalid fail-closed; monotonic existing locks.
- Path-config API tests: exact PUT request maps prerequisite validation to HTTP 422 `[NEWCOMER_PATH_PREREQUISITE_INVALID]`; unrelated request validation keeps the default contract.
- Journey tests: unmet nonterminal lock; historical invalid terminal lock in both Journey and legacy `/paths`; old-revision evidence ignored; current-revision evidence unlocks; exact audio-group target completion; AI Coach inheritance; stronger locks preserved.
- Legacy path parity tests: Journey and `/paths` agree on locked/status/result; active evidence replaces stale global progress; multi-target outcome appears on exactly one level.
- Direct-entry tests: material, audio submission, and realtime each assert locked 404, old-revision 404, current-revision success, and zero write side effects while locked.
- Learning-topic integration test: a canonical active learning-topic revision remains GET/submit/list accessible while a required-path prerequisite is unmet.
- Release gate: include the pure policy, Journey, path projection, material, audio-lineage, learning-topic, and realtime regression targets.

### 7. Wrong vs Correct

#### Wrong

```python
completed_unit_ids = {level.unit_id for level in levels if level.status == "completed"}
level.locked = any(unit_id not in completed_unit_ids for unit_id in level.unlock_after_unit_ids)
```

This creates a second rule engine, ignores active-revision lineage, and can disagree with direct-entry access.

#### Correct

```python
journey = await TrainingJourneyService(db).get_journey(user_id, viewer=learner)
module = module_for_target_unit(journey["modules"], unit_id)
if module is None or module["locked"]:
    raise LearnerUnitAccessError(
        "[SALES_TRAINER_UNIT_NOT_FOUND]",
        "训练单元不存在或未开放。",
        status_code=404,
    )
```

The current active revision, completion policy, stronger locks, projections, and direct entries share one decision.
