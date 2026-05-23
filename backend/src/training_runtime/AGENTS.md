# training_runtime — Unified Training Runtime Descriptors

Shared runtime descriptor construction and scenario plugin dispatch for all practice scenario types.

## Local Structure

```
backend/src/training_runtime/
├── models.py            # TrainingRuntimeDescriptor
├── service.py           # Descriptor builder
├── plugins.py           # Scenario plugin registry + dispatch
└── stepfun_transport.py # StepFun transport helpers
```

## Where to Look

| Concern | Location |
|---------|----------|
| Runtime descriptor | `service.py`, `models.py` |
| Plugin registry & dispatch | `plugins.py` |
| Legacy handler guard | `plugins.py` (`LEGACY_SALES_HANDLER_MODULES`) |
| StepFun transport | `stepfun_transport.py` |
| Sales WS consumption | `backend/src/sales_bot/websocket/router.py` |
| Presentation WS consumption | `backend/src/websocket_routes.py` |

## Local Cautions

- Plugin entrypoints reference domain service paths dynamically — broken paths fail at runtime, not import time.
- Legacy sales websocket modules are explicitly banned; do not reintroduce `base_sales_handler` / `enhanced_handler` / `simple_handler`.
- Descriptor field sanitization in `service.py` strips unknown retry-focus keys.

## Hard Rules

- NEVER add scenario types without registering a `ScenarioTrainingPlugin` implementation.
- ALWAYS run `tests/unit/test_training_runtime_plugins.py` after plugin wiring changes.

## References

- Sales runtime: `backend/src/sales_bot/AGENTS.md`
- Presentation runtime: `backend/src/presentation_coach/AGENTS.md`
