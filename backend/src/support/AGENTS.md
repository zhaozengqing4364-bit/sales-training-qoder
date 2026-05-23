# support — Support Release-Health Surfaces

Read-only operational APIs for support role: runtime status, anomalies, and asset governance indexes.

## Local Structure

```
backend/src/support/
├── api/runtime_status.py
└── services/
    ├── runtime_status_service.py
    └── asset_registry.py
```

## Where to Look

| Concern | Location |
|---------|----------|
| Support REST | `api/runtime_status.py` |
| Release-health aggregation | `services/runtime_status_service.py` |
| Asset registry / governance | `services/asset_registry.py` |
| RBAC mount | `backend/src/router_registry.py` |

## Local Cautions

- Service reads cross-domain state (sessions, logs, voice policies, presentations) — avoid write side effects.
- Aggregations can be expensive; respect query limits already enforced in API.
- Asset registry indexes must stay aligned with supported asset types across domains.

## Hard Rules

- NEVER expose support routes to plain `user` role.
- ALWAYS return structured envelopes with `trace_id` (see `api/runtime_status.py`).

## References

- Contract tests: `tests/contract/test_support_runtime.py`
- Runtime diagnostics: `backend/src/common/conversation/runtime_diagnostics.py`
