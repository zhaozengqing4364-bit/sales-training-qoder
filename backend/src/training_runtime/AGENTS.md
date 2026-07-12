# training_runtime — Unified Training Runtime Contracts

Shared runtime descriptor construction, closed scenario dispatch, and neutral realtime contracts.

## Local Structure

```
backend/src/training_runtime/
├── models.py            # TrainingRuntimeDescriptor
├── service.py           # Descriptor builder
├── plugins.py           # Scenario registry + closed handler selection
├── realtime/            # Engine, Provider, Grounding and adapter ports
└── stepfun_transport.py # StepFun transport helpers
```

## Where to Look

| Concern | Location |
|---------|----------|
| Runtime descriptor | `service.py`, `models.py` |
| Plugin registry & dispatch | `plugins.py` |
| Closed runtime keys | `plugins.py` (`RuntimeHandlerFactoryKey`) |
| Root Presentation factories | `backend/src/runtime_composition.py` |
| StepFun transport | `stepfun_transport.py` |
| Sales WS consumption | `backend/src/sales_bot/websocket/router.py` |
| Presentation WS consumption | `backend/src/websocket_routes.py` |

## Local Cautions

- Plugin selections are declarative and may contain only a closed factory key. Never add handler module/attribute
  strings, callables, classes, kwargs or dynamic imports.
- Sales owns its local delivery-root map; the top-level app root owns Presentation factories. Their key sets must
  be disjoint and exhaustive.
- Legacy sales websocket modules are explicitly banned; do not reintroduce `base_sales_handler` / `enhanced_handler` / `simple_handler`.
- Descriptor field sanitization in `service.py` strips unknown retry-focus keys.

## Hard Rules

- NEVER add scenario types without registering a `ScenarioTrainingPlugin` implementation.
- NEVER make a domain import `runtime_composition`; cross-domain composition points inward from the app root.
- ALWAYS run `tests/unit/test_training_runtime_plugins.py` after plugin wiring changes.

## References

- Sales runtime: `backend/src/sales_bot/AGENTS.md`
- Presentation runtime: `backend/src/presentation_coach/AGENTS.md`
