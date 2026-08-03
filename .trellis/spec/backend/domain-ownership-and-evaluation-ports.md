# Domain Ownership and Evaluation Ports

> Executable Gate 4 contract for neutral Roleplay, Configuration Governance,
> Evaluation Evidence/Scenario ports, and shared realtime helper ownership.

> **Scope status (updated 2026-07-17):** the Gate 4 text below remains current runtime truth for existing Roleplay/Realtime/Presentation code. For newcomer foundation training, Slices 2–5 implement the accepted `newcomer_training`, `learning`, `audio_assessment`, `ai_coach`, `competency_evidence`, and `readiness` ownership split. Existing Roleplay/Realtime code is not a newcomer launch dependency.

## Newcomer Foundation Target Addendum

- `newcomer_training` owns Path/Revision/Stage/ActivityDefinition, Cohort/Enrollment, generic Attempt and Journey only.
- `learning`, `audio_assessment`, and `ai_coach` own their detailed records and normalized Outcome implementations.
- `competency_evidence` is the only writer of immutable competency facts; `readiness` is the only writer of Dossier, ReviewDecision, Appeal, and RetrainingAssignment.
- Evaluation/Readiness consume ports and versioned events; they never import activity ORM or recompute historical activity snapshots.
- `CompetencyEvidenceWriter.append()` is the write seam; Evidence query is a separate read seam. Both return immutable DTOs, never ORM rows.
- Current `sales_trainer` multi-ownership is a Legacy exception with owner/deadline in `docs/architecture/newcomer-foundation-guard-policy.yaml`, not permission to add new cross-domain writes.

Implemented newcomer seams: `newcomer_training` invokes activity behavior only through published-resource/runtime ports; activity domains record normalized completion through `ActivityOutcomeWriterPort`. The production Outcome writer calls the root `FoundationReadinessProjection`, which maps immutable Outcome DTOs to `competency_evidence` and then projects `readiness` in the same transaction. Runtime composition lives in `newcomer_foundation_composition.py`, `foundation_readiness_composition.py`, and the application delivery modules. No activity domain imports Evidence/Readiness ORM or writes those tables directly. Future activity domains must follow the same port direction rather than copying either model.

## 1. Scope / Trigger

Apply this contract when a change touches:

- `roleplay/`, Roleplay Contract compilation/hash/disclosure/turn context or Situation Packs;
- `configuration_governance/`, Admin ConfigBundle lifecycle, rollout or immutable version binding;
- `evaluation/ports`, session evidence, scenario registration, comprehensive reports or report lineage;
- Presentation/Sales scenario adapters registered by `scenario_composition.py`; or
- `training_runtime/realtime/{events,text_payloads,message_persistence}.py` and their compatibility exports.

The goal is dependency inversion inside one deployable modular monolith. It does not add a service,
database, network hop, second writer or recomputation of historical snapshots.

## 2. Signatures

```python
class RoleplayContractCompiler:
    async def compile_from_template_data(...) -> dict[str, object]: ...
    def compile_from_persona_sync(...) -> dict[str, object]: ...

def roleplay_contract_hash(payload: object) -> str: ...
def situation_pack_content_hash(snapshot: SituationPackSnapshot) -> str: ...

class ConfigBundleLifecycleService:
    async def create_draft(...) -> ConfigLifecycleResult: ...
    async def validate(...) -> ConfigLifecycleResult: ...
    async def preview(...) -> ConfigLifecycleResult: ...
    async def publish(...) -> ConfigLifecycleResult: ...
    async def rollback(...) -> ConfigLifecycleResult: ...
    async def disable(...) -> ConfigLifecycleResult: ...

@dataclass(frozen=True, slots=True)
class ConfigVersionRecord:
    version_id: str
    source_config_id: str | None
    version_number: int | None
    snapshot: Mapping[str, FrozenJson]

class ConfigLifecyclePersistence(Protocol):
    async def load_active_version(...) -> ConfigVersionRecord | None: ...
    async def publish_version(...) -> ConfigVersionRecord: ...
    async def append_audit(decision: ConfigAuditDecision) -> ConfigAuditRecord: ...

@dataclass(frozen=True, slots=True)
class SessionEvidence:
    session_id: str
    scenario_type: str | None
    transcript: str
    turns: tuple[EvidenceTurn, ...]
    missing_reasons: tuple[str, ...]

class EvaluationScenarioRegistry:
    def register(self, scenario_type: str, factory: EvaluationScenarioFactory) -> None: ...
    def freeze(self) -> None: ...
    async def evaluate(...) -> Result[EvaluationScenarioResult]: ...
```

Constructor-time rollout keys are `ROLEPLAY_NEUTRAL_OWNER_ENABLED` and
`CONFIGURATION_GOVERNANCE_ENABLED`. Both default to `true`; unknown values fail safe to the named
Legacy authority. A request constructs exactly one authority and never shadow-writes.

## 3. Contracts

### Roleplay

- `roleplay` owns schema constants, canonical hashes, bundled Situation Packs, compiler,
  disclosure state, visible payload, turn context and compliance decisions.
- Consumers import canonical Roleplay contracts from `roleplay`; the former
  `common.roleplay_contracts` forwarding module is retired and must remain absent.
- Persisted Roleplay hashes, frozen references and historical reports are never recomputed.
- Curriculum Pydantic gate DTO conversion stays at the Curriculum adapter boundary.

### Configuration Governance

- The neutral package owns lifecycle sequencing, projection invocation, audit decisions, rollout and
  recursively immutable result/binding DTOs. A frozen dataclass containing mutable `list`/`dict`
  fields does not satisfy this contract.
- Admin is the delivery/composition and SQLAlchemy adapter. The neutral package imports no Admin,
  ORM or `common`, which keeps it outside the legacy SCC.
- The persistence port returns `ConfigVersionRecord` / `ConfigAuditRecord`, never an ORM row or an
  `Any` entity handle. Admin's SQLAlchemy adapter flushes version/audit/projection rows; API routes own
  commit/rollback and preserve existing response envelopes without refreshing domain records.
- Curriculum and Evaluation resolve immutable `bundle_id/version_id` projections through local read
  adapters; neither imports Admin lifecycle.

### Evaluation and realtime

- Evaluation consumes persisted `SessionEvidence`, neutral Roleplay/Ruleset data and a frozen
  scenario registry. It imports no Admin, Curriculum, Presentation or Sales implementation.
- The application root registers Presentation and the Sales-only legacy evidence fallback. Duplicate
  or post-freeze registration is rejected.
- Missing transcript is non-evaluable (`[EVALUATION_EVIDENCE_INSUFFICIENT]`), never a zero score.
- `ComprehensiveReportService` remains the only comprehensive-report writer; a scenario adapter
  returns `EvaluationScenarioResult`, which Evaluation maps once and persists once.
- The public scoring ruleset path remains `/api/v1/evaluation/admin/scoring-rulesets`; root mounting
  removes the reverse import without changing OpenAPI. When replacing a nested router with root
  composition, preserve both registration order and inherited tags; URL parity alone is insufficient.
- Neutral event/text/message helpers live in `training_runtime.realtime`. Sales compatibility modules
  forward the same function objects. Presentation owns a neutral-port behavior mixin; only the app root
  combines it with the retained Sales shared transport, so no Presentation-to-Sales package edge remains.
- Tests that replace a forwarded function's module globals (session factory, storage service or logger)
  must patch `training_runtime.realtime`, where `function.__globals__` lives; adding look-alike globals
  to a compatibility export does not create a real seam.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Roleplay neutral flag missing | Select Neutral compiler |
| Roleplay/config flag invalid | Select named Legacy only; no raw value in diagnostics |
| Missing/unpublished Situation Pack | Typed compile failure; no fallback to latest unrelated pack |
| Frozen hash/version mismatch | Fail publishing/runtime gate; do not rewrite the snapshot |
| ConfigBundle key unknown | HTTP 404 `[CONFIG_BUNDLE_NOT_FOUND]` |
| Config payload invalid | HTTP 400 `[CONFIG_BUNDLE_SCHEMA_INVALID]`; rollback |
| Projection sync fails | Lifecycle audit exposes `projection_sync.status=failed`; no false success |
| Duplicate scenario registration | `ValueError`; original factory unchanged |
| Registration after freeze | `RuntimeError`; registry unchanged |
| Registry not frozen | `[EVALUATION_SCENARIO_REGISTRY_NOT_FROZEN]` |
| Scenario unknown | `[EVALUATION_SCENARIO_NOT_CONFIGURED]` |
| Transcript/evidence missing | `[EVALUATION_EVIDENCE_INSUFFICIENT]`; no report row |
| Same report trigger runs twice | Existing run/report returned; no duplicate writer |
| Compatibility helper differs from neutral function | Architecture/identity test failure |

## 5. Good / Base / Bad Cases

- **Good**: Admin composes one neutral lifecycle over its SQL adapter; Curriculum binds the persisted
  version ID; Evaluation loads persisted turns and dispatches Presentation through a frozen registry;
  one report is stored with unchanged wire fields.
- **Base**: a rollout flag is false; the named Legacy authority runs alone and produces byte-equal
  contracts/audit rows without rewriting historical data.
- **Bad**: Evaluation imports Presentation to branch on scenario, Curriculum invokes Admin lifecycle
  to read a version, a missing transcript becomes score 0, both rollout paths write, or a Presentation
  domain module imports Sales transport/helper implementations.

## 6. Tests Required

- Roleplay Golden/hash/compiler/disclosure: `test_gate4_domain_ownership.py`,
  `test_roleplay_contracts.py`, `test_frozen_asset_ref_compilation.py`.
- Config lifecycle/HTTP/RBAC/audit/projection: `test_config_bundle_roleplay_situation_packs.py`,
  `test_config_bundle_lifecycle_contract.py`, `test_situation_pack_projection_sync.py`.
- Lifecycle ownership: a fake persistence port must prove the neutral core orders
  `ensure -> before -> mutate -> projection -> audit`; immutable-result tests must reject nested
  collection mutation.
- Registry/Evidence/Presentation/report single writer: `test_gate4_domain_ownership.py`,
  `test_comprehensive_report_service.py`, `test_presentation_report_flow.py`,
  `test_report_generation_trigger.py`.
- Realtime helper parity and retained seam: `test_stepfun_payload_snapshots.py`,
  `test_stepfun_realtime_handler.py`, `test_presentation_realtime_engine_handler.py`.
- Every ownership change runs Ruff, focused mypy, architecture guard and the clean-start canonical
  quality gate. Assertions must compare complete payloads/writes, not only selected fields.

## 7. Wrong vs Correct

### Wrong: concrete reverse imports and invented evidence

```python
from presentation_coach.services.presentation_report_service import PresentationReportService

if not transcript:
    return ComprehensiveReport(overall_score=0.0)  # invents an evaluation
```

### Correct: frozen port dispatch and explicit non-evaluable result

```python
evidence = await evidence_port.load(session_id)
result = await scenario_registry.evaluate(
    scenario_type,
    db=db,
    scenario_input=EvaluationScenarioInput(evidence=evidence),
)
if not result.is_success:
    return Result.fail(result.fallback or "[EVALUATION_SCENARIO_FAILED]")
```

### Wrong: neutral package imports delivery persistence

```python
# configuration_governance/lifecycle.py
from admin.config_bundles.adapters import list_config_bundle_adapters
```

### Correct: application composition supplies one adapter

```python
backend = SqlAlchemyConfigLifecycleAdapter(db, adapters=list_config_bundle_adapters())
service = ConfigBundleLifecycleService(backend)
```
