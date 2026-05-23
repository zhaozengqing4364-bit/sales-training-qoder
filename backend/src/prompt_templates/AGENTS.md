# prompt_templates — Prompt Template Governance

Versioned prompt templates, scenario assignments, rendering, and compiled prompt contracts for runtime LLM consumers.

## Local Structure

```
backend/src/prompt_templates/
├── api/routes.py         # REST + scenario-prompts
├── service.py            # Template CRUD, render, governance
├── loader.py, renderer.py, taxonomy.py
└── compiled_contract.py  # Hashable runtime contract
```

## Where to Look

| Concern | Location |
|---------|----------|
| Template CRUD / render API | `api/routes.py` |
| Business logic | `service.py` |
| Compiled artifact contract | `compiled_contract.py` |
| Taxonomy / types | `taxonomy.py`, `models.py` |
| Sales scope restrictions | `service.py` (`SALES_PROMPT_SCOPE_ALLOWED_TYPES`) |

## Local Cautions

- Changing `PROMPT_CONTRACT_VERSION` affects evaluation and runtime scoring hash parity.
- Governance operations (rollback, quarantine) are audited — preserve audit trails.
- Scenario prompt assignments bind templates to agents/scenarios consumed at session start.

## Hard Rules

- NEVER render templates without passing through `PromptTemplateService` governance checks.
- ALWAYS add contract tests under `tests/unit/prompt_templates/` for schema/render changes.

## References

- Evaluation: `backend/src/evaluation/AGENTS.md`
- API contract: `docs/api-contract/`
