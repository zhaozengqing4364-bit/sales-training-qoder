# Gate 5 implementation notes

## Baseline

- Gate 4 is archived at commit `e8c4c331`; journal commit is `6be88ef7`.
- User-owned unrelated change remains:
  `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`.
- CodeGraph baseline: `TrainingJourneyService` affects 150 symbols;
  `ReadinessDossierService` affects 47 symbols.
- Backend Journey/Dossier baseline: `31 passed`.
- Backend models/Gate4 ownership/architecture baseline: `39 passed` from the required `backend/` cwd.
- Frontend report/Journey/readiness/domain baseline: 6 files / `91 passed`.
- Architecture dependency guard: satisfied.
- Physical model truth: 65 public enum/entity classes plus `Base`, 52 mapped tables declared in the
  compatibility file, 98 tables in the complete shared metadata,
  224 backend source files importing the compatibility path.

## Decisions and deviations

- The approved Gate 5 design replaces a fresh user approval round. The Goal prohibits blocking
  questions and the user prohibits sub-agent dispatch, so Trellis research/design/implementation runs
  inline and records conservative assumptions here.
- Design artifact audit pass 1 corrected an inaccurate model count (51 → 65 public enum/entity classes,
  52 mapped tables declared locally) and aligned the frontend interface name with the existing
  `createSessionsDomain`. No remaining hard or advisory mismatch was found in pass 2.
- Task 1 Red exposed a second baseline distinction: importing the full application model graph registers
  98 tables on the shared metadata, while 52 are declared in `common.db.models`. The metadata contract
  now records both numbers instead of conflating local ownership with registry completeness.
- Task 1 executable Red is intentional and restricted to target architecture: backend `3 failed,
  2 passed` (missing model registry, direct foreign ORM imports, missing projection modules) while public
  class inventory and the canonical 98-table metadata SHA-256 pass; frontend `2 failed, 1 passed`
  (definitions and sessions transport still global) while UI callers already stay on the outward client
  façade. Existing behavior baselines remain `31/39/91 passed`.
