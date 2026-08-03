# Compatibility Retirement and Root Composition

> Executable Gate 6 contract for consumer-proven compatibility deletion, closed runtime factories,
> root-only cross-domain composition, and evidence-backed retention.

> **Newcomer target status (2026-07-16):** existing Gate 6 retention rules remain current runtime truth. New foundation migration follows `docs/architecture/newcomer-foundation-clean-cut.md`; Slice 0 performs no deletion.

## Newcomer Foundation Clean-Cut Addendum

- Each slice establishes and verifies one new writer, then removes the corresponding Legacy writer in that slice. Permanent dual-write, dual-read, forwarding API facade, and unbounded flags are forbidden.
- A temporary read-only comparison needs owner, exact consumers, `retire_when`, expiry, metrics, and a deletion test; it cannot write or repair business data.
- Phase/Module payloads, realtime newcomer registration, automatic Enrollment rollout, subtype routes, the v1 seed, direct Provider calls, and duplicate frontend entrances are migration inventory—not retained target surfaces.
- Historical data may use a named read-only Legacy Adapter only when the migration matrix records audit value. Development-only data is rebuilt through guarded launch reset.
- Root composition explicitly registers five target ActivityRuntime adapters and AI/Task adapters; target domain modules never import current `sales_trainer` concrete implementations.

## 1. Scope / Trigger

Apply this contract when a change:

- modifies `training_runtime.plugins`, scenario runtime selection, or a WebSocket handler factory;
- composes Presentation behavior with the retained StepFun transport;
- adds, removes, or redirects a compatibility façade, import re-export, rollout flag, or cache;
- changes `common.db.models`, the frontend API type/client façades, or their deprecation policy;
- removes an architecture-policy edge or temporary exception; or
- claims that a migration, compatibility surface, or Modular Monolith gate is complete.

Deletion requires production-consumer proof and rollback/deprecation evidence. A passing test suite
alone is not proof that a compatibility path is unused.

## 2. Signatures

```python
class RuntimeHandlerFactoryKey(StrEnum):
    SALES_STEPFUN = "sales_stepfun"
    PRESENTATION_LEGACY = "presentation_legacy"
    PRESENTATION_STEPFUN_ROLLBACK = "presentation_stepfun_rollback"
    PRESENTATION_REALTIME_ENGINE = "presentation_realtime_engine"


@dataclass(frozen=True)
class ScenarioRuntimeHandlerSelection:
    scenario_type: str
    runtime_mode: str
    websocket_route: str
    factory_key: RuntimeHandlerFactoryKey


class StepFunRuntimeAdapterPort:
    """Explicit cooperative-MRO bridge required by Presentation behavior."""


class PresentationStepFunRuntimeMixin(StepFunRuntimeAdapterPort): ...


class PresentationStepFunRealtimeAdapter(
    PresentationStepFunRuntimeMixin,
    StepFunRealtimeSharedHandler,
): ...


PRESENTATION_RUNTIME_HANDLER_FACTORIES: Mapping[
    RuntimeHandlerFactoryKey, Callable[[], Any]
]
```

The Sales-local and top-level Presentation factory maps are disjoint. Their union is exactly the
closed `RuntimeHandlerFactoryKey` set.

## 3. Contracts

### Closed selection and construction

- A selection contains exactly `scenario_type`, `runtime_mode`, `websocket_route`, and one mandatory
  closed factory key. It contains no module path, attribute name, callable, class, kwargs, or runtime object.
- Sales resolves only `SALES_STEPFUN` in its delivery root. The application root resolves the three
  Presentation keys. Unknown or context-inappropriate keys fail before any handler is constructed.
- Domain packages do not import the application root. Cross-domain concrete composition exists only in
  `runtime_composition.py`; neither Presentation nor Sales owns the other domain's behavior.
- Runtime plugin descriptors expose selection and sanitized diagnostics only. They do not simulate service
  locators through lifecycle, evidence, evaluation, or report method-name strings.

### Explicit compatibility bridge

- `PresentationStepFunRuntimeMixin` owns Presentation behavior and imports no Sales module.
- `StepFunRuntimeAdapterPort` makes the existing cooperative-MRO state and hook requirements inspectable.
  It does not use `__getattr__`, service location, repository access, or a second writer.
- The root concrete adapter composes Presentation behavior before the retained shared transport. The Engine
  façade receives that adapter factory explicitly; it has no domain-level default import.
- Wire events, close codes, binary audio, snapshots, persistence, reconnect, Grounding/evidence projection,
  scoring, and report single-writer behavior remain covered by Golden/affected tests.

### Retirement and policy truth

- Delete a forwarding façade only after all production consumers import its owner directly and identity/Golden
  parity passes. Do not replace it with another global barrel.
- Remove a dependency-policy target only after the AST graph no longer contains the edge. An active source keeps
  its governed edge even if an adjacent compatibility source was deleted.
- Each retained surface records owner, reason, `retire_when`, and verification evidence:

| Surface | State / owner | Reason | `retire_when` | Verification |
|---|---|---|---|---|
| `common.db.models` registry | retained / Data platform | 222 production importers and shared SQLAlchemy metadata/import order | one release deprecation window has elapsed and importer migration plus Alembic identity tests pass | importer scan, model identity and migration tests |
| frontend API `types.ts` / `client-domains.ts` façades | retained / Frontend platform | 262 source importers; no complete external/generated-client inventory | consumers have domain-local contracts, external inventory is complete, and a release window passes | importer scan, TypeScript, Vitest, build |
| `LegacyRealtimeGroundingAdapter` / `LegacyToolResultCache` | retained / Realtime platform | constructed by the false Grounding flag path | rollout telemetry and a release window prove rollback unused | 2x2/2x2x2 matrix and Golden differential |
| Presentation Engine, Provider Port, Grounding Module flags | retained / Realtime platform | active constructor-time rollback controls | release evidence satisfies each ADR retirement condition | flag matrix, diagnostics and Golden tests |
| `common -> roleplay` business-rule defaults edge | follow-up / Business rules owner | active registry import at `common/business_rules/defaults.py` | defaults authority migrates without changing hashes or frozen snapshots | graph source locations and business-rule tests |

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Selection carries a string module/attribute locator | AST/contract failure |
| Factory key is unknown or belongs to the other root | `ValueError("unknown_runtime_handler_factory_key")`; construct nothing |
| Root maps overlap or omit an enum value | Gate 6 contract failure |
| Presentation imports Sales or the application root | architecture failure |
| Domain code dynamically imports a selected handler | architecture/contract failure |
| Engine façade omits adapter injection | constructor failure; no hidden fallback import |
| Forwarding façade still has a production consumer | retain and document; do not delete |
| Policy edge is removed while an AST source remains | architecture guard failure |
| Rollback path still has a constructor selection | retain until release evidence satisfies `retire_when` |
| Compatibility deletion changes wire/snapshot/write order | Golden differential failure |
| Benefit claim lacks comparable before/after measure | keep claim pending; do not mark the gate complete |

## 5. Good / Base / Bad Cases

- **Good**: the plugin emits a closed key, the correct root resolves it from a read-only map, Presentation behavior
  composes with the shared transport only at the app root, and an unknown key creates no object.
- **Base**: a consumer-backed rollback/cache/model/type façade remains, with a named owner and executable retirement
  condition; its continued existence is not reported as migration completion.
- **Bad**: a selection carries `handler_factory_path`, a domain imports a global service locator, a hidden
  `__getattr__` bridge masks MRO requirements, a façade is deleted by line count alone, or an allowlist target is
  removed while its source edge remains.

## 6. Tests Required

- Closed factory, root-map exhaustiveness, import absence, retain floors and dependency graph:
  `backend/tests/unit/test_gate6_compatibility_retirement.py`.
- Plugin and route construction: `test_training_runtime_plugins.py`,
  `test_main_presentation_ws_runtime.py`, and Sales router tests.
- Presentation adapter/Engine/Golden/snapshot/persistence/reconnect/evidence:
  `test_presentation_stepfun_realtime_handler.py`, `test_presentation_realtime_engine_handler.py`,
  and `test_practice_evidence_contract.py` plus their CodeGraph-affected matrix.
- Roleplay owner parity: `test_roleplay_contracts.py`, `test_roleplay_observability_contract.py`, and
  `test_gate4_domain_ownership.py`.
- Always run Ruff, full mypy, architecture dependency guard, OpenAPI parity, affected tests, and one clean-start
  `bash scripts/critical-quality-gate.sh` before declaring retirement complete.

## 7. Wrong vs Correct

### Wrong: executable locator and domain-owned cross-domain construction

```python
selection = ScenarioRuntimeHandlerSelection(
    ...,
    handler_factory_path="sales_bot.websocket.stepfun_realtime_handler",
    handler_factory_name="StepFunRealtimeSharedHandler",
)
handler = getattr(import_module(selection.handler_factory_path), selection.handler_factory_name)()
```

### Correct: closed selection and application-root map

```python
selection = ScenarioRuntimeHandlerSelection(
    scenario_type="presentation",
    runtime_mode="stepfun_realtime",
    websocket_route="/ws/presentation/{session_id}",
    factory_key=RuntimeHandlerFactoryKey.PRESENTATION_REALTIME_ENGINE,
)

factory = PRESENTATION_RUNTIME_HANDLER_FACTORIES.get(selection.factory_key)
if factory is None:
    raise ValueError("unknown_runtime_handler_factory_key")
handler = factory()
```
