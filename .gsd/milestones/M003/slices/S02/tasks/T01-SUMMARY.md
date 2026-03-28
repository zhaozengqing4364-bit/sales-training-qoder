---
id: T01
parent: S02
milestone: M003
provides: []
requires: []
affects: []
key_files: ["backend/src/agent/services/persona_policy.py", "backend/src/agent/services/persona_service.py", "backend/tests/unit/test_persona_policy.py", "backend/tests/integration/test_persona_api.py", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Canonicalize Persona pressure behavior as a nested `customer_pressure` model while projecting the existing flat sales-focus fields for compatibility.", "Treat `pressure_model_legacy_only` as an audit-only signal for raw DB rows that still lack the nested pressure model; create/update paths persist the derived nested model so later reads are canonical."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh verification ran with `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py`, and all 18 focused unit/integration checks passed. I also ran LSP diagnostics on `backend/src/agent/services/persona_policy.py`, `backend/src/agent/services/persona_service.py`, `backend/tests/unit/test_persona_policy.py`, and `backend/tests/integration/test_persona_api.py`; all returned `No diagnostics`. This task’s slice-level verification command is the same focused backend pytest gate, so the current slice verification is passing for T01."
completed_at: 2026-03-25T02:23:27.654Z
blocker_discovered: false
---

# T01: Normalize Persona policies into a structured customer-pressure model with legacy audit coverage.

> Normalize Persona policies into a structured customer-pressure model with legacy audit coverage.

## What Happened
---
id: T01
parent: S02
milestone: M003
key_files:
  - backend/src/agent/services/persona_policy.py
  - backend/src/agent/services/persona_service.py
  - backend/tests/unit/test_persona_policy.py
  - backend/tests/integration/test_persona_api.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Canonicalize Persona pressure behavior as a nested `customer_pressure` model while projecting the existing flat sales-focus fields for compatibility.
  - Treat `pressure_model_legacy_only` as an audit-only signal for raw DB rows that still lack the nested pressure model; create/update paths persist the derived nested model so later reads are canonical.
duration: ""
verification_result: passed
completed_at: 2026-03-25T02:23:27.655Z
blocker_discovered: false
---

# T01: Normalize Persona policies into a structured customer-pressure model with legacy audit coverage.

**Normalize Persona policies into a structured customer-pressure model with legacy audit coverage.**

## What Happened

I added a canonical nested `customer_pressure` contract to `backend/src/agent/services/persona_policy.py` and kept the existing flat `sales_focus` / `value_axes` / `objection_axes` / `expected_customer_questions` fields as derived compatibility projections. The normalizer now derives a structured pressure direction plus follow-up behavior from raw legacy extension fields, preserves explicit nested pressure models, and keeps forward-compatible nested extras instead of dropping them.

On the service side, `PersonaService.get_by_id(...)` now normalizes stored policy rows before returning them so old Personas can still be inspected through the current admin detail API, and `audit_policy_health(...)` now reports `pressure_model_legacy_only` when a database row still lacks the nested pressure model even though the legacy flat fields can be derived. That gives T02/T03 one snapshot-ready shape to build on while keeping old rows diagnosable.

I added a new focused unit suite in `backend/tests/unit/test_persona_policy.py` for legacy derivation and explicit nested-pressure precedence, and extended `backend/tests/integration/test_persona_api.py` to verify both the canonical GET payload and the admin policy-health audit behavior for raw legacy rows. I also recorded the compatibility decision in `.gsd/DECISIONS.md` and the read-vs-audit source rule in `.gsd/KNOWLEDGE.md`.

## Verification

Fresh verification ran with `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py`, and all 18 focused unit/integration checks passed. I also ran LSP diagnostics on `backend/src/agent/services/persona_policy.py`, `backend/src/agent/services/persona_service.py`, `backend/tests/unit/test_persona_policy.py`, and `backend/tests/integration/test_persona_api.py`; all returned `No diagnostics`. This task’s slice-level verification command is the same focused backend pytest gate, so the current slice verification is passing for T01.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py` | 0 | ✅ pass | 6710ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/src/agent/services/persona_policy.py`
- `backend/src/agent/services/persona_service.py`
- `backend/tests/unit/test_persona_policy.py`
- `backend/tests/integration/test_persona_api.py`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
None.

## Known Issues
None.
