# admin — Admin Control Plane

Admin-only REST surfaces: users, config governance, analytics, voice runtime, RAG, scoring rulesets, and operational tooling.

## Local Structure

```
backend/src/admin/
├── api/              # Admin REST routers (20+ modules)
├── config_bundles/   # ConfigBundle adapters + lifecycle
└── services/         # Manager intervention helpers
```

## Where to Look

| Concern | Location |
|---------|----------|
| Router mounting + RBAC | `backend/src/router_registry.py` |
| Config bundle lifecycle | `config_bundles/lifecycle.py` |
| Model / voice runtime config | `api/model_configs.py`, `api/voice_runtime.py` |
| RAG profiles | `api/rag_profiles.py` |
| Scoring rulesets | `api/scoring_rulesets.py` |
| Business rules admin | `api/business_rules.py` |
| Curriculum analytics | `api/analytics_curriculum.py` |
| Release verification | `api/release_verification.py` |
| Knowledge admin (shared) | `backend/src/common/knowledge/api.py` |

## Local Cautions

- RBAC is enforced at mount time in `router_registry.py`, not inside each route file.
- ConfigBundle changes can affect runtime voice policy, business rules, and evaluation bindings.
- Legacy presentation admin routes in `api/admin.py` overlap with `presentation_coach/api/` — check both before editing upload flows.

## Hard Rules

- NEVER expose admin routes without appropriate `Depends(get_current_admin_user*)` in registry.
- ALWAYS treat config publish/rollback as audited operations (`ConfigBundleAuditLog`).

## References

- API contracts: `docs/api-contract/`
- Shared kernel: `backend/src/common/AGENTS.md`
