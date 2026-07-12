# Gate 5 final design-artifact audit

Date: 2026-07-11 UTC

## Scope and method

This audit compares the Gate 5 PRD, implementation plan, research, executable Trellis specs, approved design,
ADR, roadmap and production source. It checks file existence, exported interface names and signatures, ownership
claims, verification commands, rollback claims, line/import counts and completion state. Canonical-gate and
independent-closure claims remain explicitly pending until Task 8.

## Round 1 findings and corrections

| Severity | Mismatch | Correction |
|---|---|---|
| Hard | PRD and plan named nonexistent `RoleplayOutcomeQuery` / `RoleplayOutcomeProjection` interfaces. Production exposes `roleplay_sessions(...)->tuple[JourneyRoleplaySessionProjection, ...]`. | Replaced the proposed names and copied the actual keyword-only repository signature. |
| Hard | PRD advertised public `dossier(...)` / `workbench(...)` projection methods and a nonexistent aggregate action builder. Production deliberately exposes service orchestration plus `_dossier_payload`, `_workbench_groups`, focused ViewModel functions and focused action builders. | Replaced snippets with the implemented signatures; no fictitious façade is claimed. |
| Advisory | The frontend executable spec required corrupt-storage and limit assertions, but the action test covered only route construction. | Added one regression test proving corrupt payload removal and the three-item persistence/read limit. |
| Advisory | The backend spec used a less canonical pytest launcher and omitted the architecture guard's explicit `--check`. | Aligned commands with the repository virtualenv and canonical guard invocation. |
| Advisory | The first post-change note used an unrepeatable global-type importer count. | Recounted exact compatibility-barrel references with a negative subpath match: 265 current, 278 baseline. |

## Round 2 verification

- Every production path listed in the plan exists. No stale `RoleplayOutcomeProjection`,
  `RoleplayOutcomeQuery`, `ReadinessProjectionSource`, `WorkbenchQuery`, or
  `buildSessionReportActions` reference remains in the Gate 5 artifact set.
- Repository and service signatures match source exactly. `Base` is owned by
  `common/db/model_registry/base.py`; the registry and compatibility façade preserve object identity.
- Current source facts are repeatable: Journey service 1,991 lines, Dossier service 336, global type barrel
  6,936, client-domain composition 519, report page 2,965 and Readiness detail page 596.
- Exact compatibility inventory is explicit rather than treated as closure: 222 backend source importers use
  the model compatibility import forms; 265 frontend source files reference the global type barrel. Gate 6
  owns evidence-based retirement.
- The dependency graph remains 15 packages / 52 observed edges / one seven-package SCC. The architecture
  policy passes without a new exception, so no policy edit is justified in Gate 5.
- The report action regression passes 4/4; strict TypeScript and changed-file ESLint pass. Existing Task 2–6
  evidence covers metadata parity, projection differential behavior, full mypy and full Vitest.
- Approved design, ADR, roadmap and architecture docs all state the same boundary:
  **Gate 5 implementation complete / canonical audit and closure pending**.
- Rollback remains a rule-free compatibility registry/re-export. No artifact claims schema change, migration,
  paid-provider run, production write, push, PR or deployment.

Round 2 result: **0 hard findings, 0 advisory findings**. Task 8 remains the sole authority for Brooks/Trellis
independent audit, clean-start canonical-gate evidence and Trellis archival.
