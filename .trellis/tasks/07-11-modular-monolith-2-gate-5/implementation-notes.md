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
- Task 2 moved all declarations into eight physical registry Modules. `common.db.models` is now a
  274-line explicit compatibility registry; all 65 class/enum exports plus `Base` keep object identity
  and `common.db.models.*` qualified names. The complete 98-table metadata digest, 52-table fresh import
  order and SQLite model tests are unchanged.
- The full backend unit+contract inventory after the move was `3290 passed, 1 skipped` plus the two
  intentional Gate 5 Red tests. It exposed one unrelated guard-parser defect: a relative
  `from .evaluation` inside `common` was incorrectly classified as the absolute top-level Evaluation
  package because the AST helper ignored `ImportFrom.level`. The existing reverse-dependency test was
  the Red reproduction; ignoring only relative imports made it Green without an allowlist.
- Model-focused cross-domain matrix was `189 passed`; full Ruff passed; full mypy passed for 671 source
  files; architecture guard passed. CodeGraph conservatively selected 512 tests because the compatibility
  registry has system-wide fan-in, so the full unit+contract run was used rather than a narrow claim.
- Task 3 introduced a frozen Journey read port plus a SQLAlchemy adapter that is the only owner of
  `User`/`PracticeSession` queries. Learner lists preserve the development-only admin exception, enforce
  active/role/department scope, return deterministic order, and recursively freeze roleplay snapshots.
- `TrainingJourneyService` no longer imports foreign ORM entities and dropped from 2,855 to about 2,000
  lines. `TrainingJourneyProjection` now owns stage/completion/next-action, journey progress/diagnostics,
  learner-level matching/defaults and all pure analytics rules; the service retains async reads, permission
  checks, transaction-facing orchestration and observation table access.
- Task 3 Red/Green evidence: repository contracts first failed on nondeterministic roleplay ordering, then
  passed after the adapter added an explicit session-id order. Journey characterization plus repository and
  locality contracts passed `25/25`; the CodeGraph-selected Journey/phase2/readiness/API/seed matrix passed
  `112/112`; Ruff, focused mypy and the architecture dependency guard passed. The two remaining Gate 5 Red
  assertions are intentionally isolated to Task 4 Readiness extraction.
- Task 4 reduced `ReadinessDossierService` from 1,284 to 336 lines. The application service now owns only
  viewer-scoped loading, Journey/record/log orchestration, validation before writes and the single commit;
  the 992-line pure `ReadinessDossierProjection` owns dossier evidence, summaries, competencies, state
  precedence, approval eligibility, realtime gate, next actions, workbench grouping and blocked snapshots.
- Readiness reuses the frozen Journey repository for learner and paged workbench reads. The repository keeps
  the former fallback semantics explicit: Journey lists may include the development login admin while the
  Readiness fallback sets `include_development_admin=False`; both use stable offset/order behavior.
- Task 4 differential evidence passed: pure projection `3/3`, Dossier/phase2/locality `28/28`, and Journey
  API/RBAC/audit/lineage/Journey/Dossier/phase2 `64/64`. Full focused Ruff/mypy and the architecture dependency
  guard passed. All backend Gate 5 locality contracts and new port/projection tests are Green `14/14`.
- Task 5 moved Journey/Readiness/realtime-entry/analytics contracts into `types/training-journey.ts` and the
  session evidence/report/replay/highlight/diagnostic/supervisor closure into `types/session-report.ts`. The
  global barrel remains a type-only compatibility surface and fell from 8,459 to about 7,000 lines; domain
  type files do not import that barrel. Structural local dependencies avoid a circular type authority.
- `createSessionsDomain` moved from the aggregation file into `domains/sessions.ts`; `client-domains.ts` now
  re-exports it and fell from 657 to 519 lines. The outward `api.sessions` façade, request/error/auth seams and
  URLs are unchanged. A new transport test proves report and replay requests still use their exact endpoints.
- The React/Next performance guidance kept pages on the outward façade and moved only erased type imports plus
  transport code, so no new client runtime barrel, component render dependency or async waterfall was added.
  TypeScript and changed-file ESLint passed; the Gate 5/domain and report/replay/readiness/team consumer matrix
  passed 10 files / `137 passed`.
- Task 6 extracted pure report score/status/trend/compliance/presentation/replay mapping into
  `report-view-model.ts`, route/query/retry/highlight-storage knowledge into `report-actions.ts`, and Readiness
  evidence/status/snapshot/retraining/default-selection mapping into `readiness-view-model.ts`. Reserved route
  identifiers are now encoded, unknown Readiness/report enum values use user-language fallbacks, and the pages
  retain their existing loading/error/permission/submitting/retry hierarchy.
- The report page fell from 3,350 to 2,965 lines and the Readiness detail page from 822 to 596 lines without a
  visual redesign. New pure tests cover route encoding, replay anchor degradation, score/tone mapping, internal
  diagnostic redaction, evidence defaults and retraining comparison. The first full Vitest run exposed one
  source-locality baseline that still expected date formatting in `page.tsx`; updating that executable baseline
  to the new ViewModel authority made the canonical rerun Green: 213 files, `1344 passed, 6 skipped`.
- Task 6 verification also passed strict TypeScript, changed-file ESLint (errors-only), focused route/pure tests
  `55/55`, and CodeGraph selected the report, Readiness detail and admin-user route tests. No runtime dependency
  or data-fetching waterfall was added by the extraction.
- Task 7 synchronized CodeGraph at 2,039 files / 39,362 nodes / 115,267 edges and confirmed the dependency
  graph remains 15 packages / 52 observed edges / one seven-package SCC with no new policy exception. Current
  compatibility inventories are 222 model-importing backend source files and 265 global-type-barrel frontend
  source files; these are explicit Gate 6 retirement inputs, not hidden Gate 5 debt claims.
- Backend/frontend seven-section specs now freeze model identity/import order/metadata, projection immutability,
  DTO/transport/ViewModel/action locality, user-language fallbacks and Gate 6 retirement conditions. The final
  design-artifact audit corrected two hard interface-name/signature mismatches plus three advisory evidence/
  command mismatches; its second pass reports 0 hard and 0 advisory findings.
- The added corrupt-highlight-storage/three-item-limit regression passed `4/4`; strict TypeScript,
  changed-file ESLint, architecture policy and `git diff --check` passed. Authority documents remain truthful:
  implementation is complete while independent audit, canonical gate and archival belong only to Task 8.
- Task 8 Brooks pass 1 found two residual interface-leakage symptoms: application services called underscored
  projection helpers as a de facto hidden API, and the report root still interpolated one historical session ID.
  Characterization tests reproduced both issues before remediation. Projection modules now expose an explicit
  non-underscored application interface, the architecture contract rejects future private-method coupling, and
  `buildSessionReportPath` owns the final report URL with reserved-ID encoding. Focused Red → Green evidence is
  `1 failed → 4 passed` for backend projection-interface contracts and `1 failed → 4 passed` for report actions;
  strict TypeScript, focused mypy/Ruff and changed-file ESLint errors-only pass.
- Brooks final rerun is 100/100 with Critical/Warning/Suggestion `0/0/0`. Independent Trellis check reports
  blocking finding=0: Gate 5 backend differential/contracts `58 passed`, OpenAPI/model parity `18 passed`, full
  Ruff, mypy for 675 source files, architecture policy, strict TypeScript, report/Readiness `55 passed`, task
  JSONL and artifact hygiene all pass. Full frontend lint exits 0 with 82 pre-existing repository warnings and
  none in changed Gate 5 files; no warning was suppressed to obtain closure.
