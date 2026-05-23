# agent — Agent Platform Domain

Agent, Persona, and capability-module management for configurable practice scenarios.

## Local Structure

```
backend/src/agent/
├── api/           # agents, personas, agent-persona bindings
├── services/      # CRUD, persona policy, industry pack contracts
├── capabilities/  # Runtime capability modules + runner
├── models.py      # Agent platform ORM tables
└── migrations/    # One-off persona data migrations (not Alembic)
```

## Where to Look

| Concern | Location |
|---------|----------|
| Agent CRUD (admin/user) | `api/agents.py` |
| Persona admin | `api/personas.py` |
| Agent-persona binding | `api/agent_personas.py` |
| Capability orchestration | `capabilities/runner.py` |
| Capability registry | `capabilities/registry.py` |
| Persona policy normalization | `services/persona_policy.py` |
| Industry pack contract | `services/industry_pack_contract.py` |

## Local Cautions

- Persona policy shapes are consumed by sales and presentation websocket runtimes.
- Capability modules run in parallel during turns; keep `CapabilityResult` contracts stable.
- `migrations/` scripts are operational one-offs — schema changes still go through Alembic.

## Hard Rules

- NEVER break admin/user router separation in `api/agents.py`.
- ALWAYS register new ORM tables in tests via `import agent.models` pattern in `conftest.py`.

## References

- API contract: `docs/api-contract/agents.md`
- Sales runtime: `backend/src/sales_bot/AGENTS.md`
- Shared kernel: `backend/src/common/AGENTS.md`
