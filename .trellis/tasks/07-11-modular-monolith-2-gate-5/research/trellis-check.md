# Gate 5 independent Trellis check

Date: 2026-07-11 UTC

## Result

**Blocking findings: 0.** The check was run after the Brooks pass-1 remediations and before the unique
clean-start canonical gate.

## Spec and data-flow compliance

- Read flow is explicit: shared `Base.metadata` → owner registry model → SQLAlchemy Journey adapter → frozen
  projection DTO → Journey/Readiness application orchestration → unchanged API contract → domain TypeScript DTO
  → route-local ViewModel/action → page state.
- Write flow is unchanged: report/Readiness UI → outward `api` → existing application service → validation before
  the existing single transaction/audit write. Gate 5 adds no write path, schema or migration.
- Error propagation remains fail closed for missing active revision, configuration blockers, invalid evidence,
  object scope and insufficient approval evidence. ViewModels translate unknown/internal values to user language.
- The new model registry, Journey repository, projection, sessions transport, domain types and route actions have
  one authority each. Compatibility façades re-export/compose only; no duplicate business rule was introduced.
- Production source contains no private projection calls, projection ORM/FastAPI imports, report-root URL
  interpolation, sessions endpoint literals in `client-domains.ts`, or moved DTO redeclarations in the global
  type barrel.

## Verification evidence

| Dimension | Command/result |
|---|---|
| Gate 5 backend differential/contracts | 58 passed, 1 existing dependency warning |
| OpenAPI/model parity | 18 passed, including runtime route contract and model metadata tests |
| Backend lint/types/architecture | Ruff pass; mypy 675 source files pass; dependency policy satisfied |
| Frontend report/Readiness routes | 6 files / 55 passed |
| Frontend types | strict TypeScript pass |
| Frontend lint | exit 0; 82 repository-baseline warnings, none in changed Gate 5 files |
| Trellis context | implement 10 entries, check 8 entries, JSONL validation pass |
| Artifact hygiene | `git diff --check` and Brooks history JSON parse pass |

The first canonical attempt later exposed a stale critical-branch floor after the Journey extraction. The
follow-up governance check added a pure projection branch suite and migrated the service/projection floors as a
non-regressing pair: 340/426 combined versus 290/434 before extraction. Isolated guard evidence is 90.93%
changed executable coverage with zero changed missing critical branch; final authority still belongs to the
clean-start rerun.

The existing lint warning inventory is non-blocking repository debt and was not suppressed or expanded. One
pre-existing report-page hook warning became visible because the page was in scope; the audit removed it by using
the actual `latestSupervisorReview` dependency. The canonical gate remains the final proof for full pytest,
Vitest, Playwright families, selected backend tests and changed coverage.
