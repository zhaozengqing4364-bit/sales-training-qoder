# Expansion Log

## Phase 0

Core question: define a comprehensive, healthy, sustainable governance refactor plan for the current project so a later Ultra Loop can execute for many hours without drifting.

Axes:
- A backend composition roots and domain boundary dependencies.
- B frontend route ownership, API facade, and UI state coupling.
- C configuration governance, domain contracts, status, permission, audit, and AI prompt boundaries.
- D tests, CI gates, migrations, scripts, release and execution workflow.

Codebase relevant: yes. External: no, because repo already contains project-specific architecture constitution, ADRs, audits, and plans. Browsing: no. Verification likely: yes, through CodeGraph, shell inventory, and existing tests/contracts. Report requested: Markdown plan plus research synthesis.

## Team wave 1

Created durable team state under `.omo/teams/019ee483-f9de-7092-ba58-61131b087ec8` and four Codex member threads:
- A backend composition roots and domain boundary dependencies.
- B frontend route ownership, API facade, and UI state coupling.
- C configuration governance, domain contracts, status, permission, audit, and AI prompt boundaries.
- D tests, CI gates, migrations, scripts, release and execution workflow.

A parallel `add-member` mistake temporarily overwrote team state; fixed by re-adding members serially and binding all four threads.

## Direct verification

Commands run by leader:
- CodeGraph explore of app/router/websocket/runtime/API/frontend hotspots.
- `test_runtime_dependency_contract.py` line-number read.
- file line counts for backend composition roots and frontend/API hotspots.
- backend script line-count inventory.
- Alembic head check.
- audit/roadmap/architecture docs line-number sampling.

## Leads opened

- LEAD: existing dependency contract test already pins reverse dependencies and adapter export leakage. WHY: plan should tighten existing guardrail rather than invent a new one. ANGLE: make allowlist shrink over waves.
- LEAD: backend composition roots are small but carry too much bootstrap authority. WHY: file size is not the risk; responsibility mixing is. ANGLE: split route mounting vs contributor registration only after tests.
- LEAD: frontend API facade mixes learner/admin/newcomer-training flows. WHY: confuses module hierarchy and increases change blast radius. ANGLE: split behind compatibility exports.
- LEAD: two configuration governance tracks coexist. WHY: ConfigBundle/BusinessRuleConfig and SalesTrainerAssetRevision should be harmonized by interface before data migration. ANGLE: unified lifecycle/audit facade.
- LEAD: verification gates are weaker than refactor risk. WHY: long Ultra Loop can drift without gates. ANGLE: front-load contract, type, lint, and targeted smoke gates.
