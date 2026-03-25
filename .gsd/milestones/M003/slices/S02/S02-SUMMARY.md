---
id: S02
parent: M003
milestone: M003
provides:
  - A frozen per-session Persona pressure contract in `PracticeSession.voice_policy_snapshot` that downstream runtime work can trust after admin edits.
  - Current admin Persona list/detail surfaces that can audit, edit, and persist the structured pressure model without a new management surface.
  - A stable runtime/compiler seam for S03-S05 to build multi-turn objection persistence and truth semantics on top of the existing session snapshot chain.
requires:
  - slice: S01
    provides: The locked admin Persona/admin knowledge -> session create -> practice/knowledge-check/report/replay entry chain and the accepted live learner/admin inspection vocabulary for M003 proof surfaces.
affects:
  - S03
  - S04
  - S05
key_files:
  - backend/src/agent/services/persona_policy.py
  - backend/src/agent/services/persona_service.py
  - backend/src/sales_bot/services/voice_runtime_policy.py
  - backend/src/sales_bot/services/voice_instruction_compiler.py
  - backend/src/common/api/practice.py
  - web/src/app/admin/personas/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/lib/api/client.ts
  - web/src/lib/api/types.ts
  - backend/tests/integration/test_knowledge_flow.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - web/src/app/admin/personas/[id]/page.test.tsx
key_decisions:
  - Canonicalize Persona pressure behavior as nested `persona_policy.customer_pressure` while keeping flat sales-focus fields as derived compatibility projections.
  - Mirror `customer_pressure` onto the effective runtime policy/session snapshot and inspect `source.customer_pressure_source` instead of inferring Persona behavior from compiled instruction prose.
  - Reuse the current admin Persona list/detail surfaces and `/api/v1/admin/personas/policy-health` for pressure-model editing and audit instead of adding a second management surface.
patterns_established:
  - When migrating legacy prompt-era behavior to a durable contract, normalize to one canonical nested model and project legacy flat keys outward for compatibility instead of maintaining two write paths.
  - For realism features that must survive later config edits, freeze the resolved contract into `PracticeSession.voice_policy_snapshot` and treat that persisted snapshot as the runtime/read-side truth.
  - Keep operator audit and editing on the current admin route pair: list page for policy-health drift, detail page for structured contract edits and re-save canonicalization.
observability_surfaces:
  - `/api/v1/admin/personas/policy-health` with `pressure_model_legacy_only` issue signaling for rows that still lack the nested pressure model.
  - `PracticeSession.voice_policy_snapshot.customer_pressure` plus `voice_policy_snapshot.source.customer_pressure_source` as the authoritative frozen pressure-contract inspection surface.
  - `practice_session_voice_policy_resolved` structured log fields in `backend/src/common/api/practice.py`, including pressure source/focus/question strategy/evidence flags and instruction contract hash.
drill_down_paths:
  - .gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T03:09:08.015Z
blocker_discovered: false
---

# S02: Persona 压力模型 snapshot 化

**Persona pressure behavior is now a structured `customer_pressure` contract that admins can edit on current Persona pages and that session creation freezes into `voice_policy_snapshot` for stable downstream runtime inspection.**

## What Happened

This slice moved Persona from loose prompt flavor to a structured runtime contract on the existing admin/runtime chain.

T01 normalized Persona pressure behavior into a canonical nested `persona_policy.customer_pressure` model with `pressure_direction` and `follow_up_behavior`, while still projecting `sales_focus` / `value_axes` / `objection_axes` / `expected_customer_questions` back out for compatibility. The Persona service policy-health audit now distinguishes truly legacy rows with `pressure_model_legacy_only` instead of silently treating every flat row as healthy.

T02 threaded that contract through the existing runtime authority path. `VoiceRuntimePolicyService.resolve_effective_policy(...)` now mirrors the nested pressure model onto the effective policy, tags `source.customer_pressure_source`, and passes the result to `VoiceInstructionCompiler` and the practice session create flow. `POST /api/v1/practice/sessions` freezes the resolved contract into `PracticeSession.voice_policy_snapshot`, and the existing runtime/session snapshot readers keep the frozen baseline stable even after later admin edits or runtime-metrics appends.

T03 kept the operator workflow on the shipped admin Persona surfaces. The current Persona detail page now renders and edits the pressure model directly, the list/audit surface explains legacy-only pressure rows, and the web API client/types normalize the nested payload instead of flattening it back into prompt-only fields.

For slice closeout, I reran all three planned verification gates and added one extra snapshot-persistence integration sanity pass so the summary reflects the actual frozen-snapshot behavior rather than only the admin editing path.

## Verification

Fresh slice verification passed.

- `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_persona_policy.py tests/integration/test_persona_api.py` → 18 passed. This covered nested pressure-model normalization, legacy compatibility backfill, admin Persona GET/update behavior, and `/api/v1/admin/personas/policy-health` audit signaling for `pressure_model_legacy_only`.
- `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/unit/test_voice_instruction_compiler.py tests/integration/test_knowledge_flow.py` → 12 passed. This covered compiler output from structured pressure contracts, per-persona snapshot freezing in `PracticeSession.voice_policy_snapshot`, distinct `instruction_contract_hash` values per pressure direction, and unchanged snapshots after later Persona edits.
- `cd web && /usr/bin/time -p npm test -- --run 'src/app/admin/personas/[id]/page.test.tsx'` → 1 targeted test file / 2 tests passed. The Vitest output explicitly matched `src/app/admin/personas/[id]/page.test.tsx`, so the quoted Next.js path executed correctly.
- Additional slice-close sanity: `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_voice_runtime_session_snapshot.py` → 8 passed. This confirmed that the existing snapshot baseline remains immutable across later detail/report/replay reads and runtime-metrics updates.

Observability/drift-detector surfaces were exercised inside those green runs: `/api/v1/admin/personas/policy-health`, persisted `voice_policy_snapshot.customer_pressure` plus `source.customer_pressure_source`, and the structured `practice_session_voice_policy_resolved` log fields emitted by session creation.

## Requirements Advanced

- R010 — The current admin Persona surfaces, runtime compiler chain, and session-create path now share one structured `customer_pressure` contract that is frozen into `PracticeSession.voice_policy_snapshot` and auditable through policy-health, snapshot fields, and existing report/replay snapshot references.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Raw legacy Persona rows are not auto-migrated in place; they remain visible as `pressure_model_legacy_only` in policy-health until an operator saves them through the current admin surface. This slice also stops at freezing and auditing the pressure contract — unresolved objections surviving topic drift, claim-truth semantics, and objection-heavy live UAT remain for S03-S05.

## Follow-ups

Use `/api/v1/admin/personas/policy-health` to find and resave remaining legacy-only Persona rows before live objection-heavy UAT. Build S03’s multi-turn objection ledger directly on `PracticeSession.voice_policy_snapshot.customer_pressure` and `source.customer_pressure_source` instead of re-reading live Persona config or inferring behavior from compiled instruction text.

## Files Created/Modified

- `backend/src/agent/services/persona_policy.py` — Normalized Persona pressure behavior into canonical nested `customer_pressure` fields and projected flat compatibility keys back out.
- `backend/src/agent/services/persona_service.py` — Extended Persona policy-health auditing so legacy-only pressure rows surface as `pressure_model_legacy_only` instead of blending into healthy rows.
- `backend/tests/unit/test_persona_policy.py` — Added focused normalization coverage for legacy flat fields and explicit nested pressure contracts.
- `backend/tests/integration/test_persona_api.py` — Proved current admin Persona GET/update/policy-health routes expose, persist, and audit the structured pressure model.
- `backend/src/sales_bot/services/voice_runtime_policy.py` — Mirrored `customer_pressure` into the effective runtime policy and tagged `source.customer_pressure_source` for downstream snapshot inspection.
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — Compiled structured pressure direction, evidence requirements, and follow-up behavior into the base runtime instruction contract.
- `backend/src/common/api/practice.py` — Froze the resolved pressure contract into `PracticeSession.voice_policy_snapshot` during session creation and emitted structured pressure-resolution logs.
- `backend/tests/unit/test_voice_instruction_compiler.py` — Guarded the new compiler behavior so structured pressure contracts produce stable runtime directives.
- `backend/tests/integration/test_knowledge_flow.py` — Verified that different Personas freeze different pressure contracts into sales-session snapshots and stay unchanged after later admin edits.
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — Confirmed the broader session snapshot baseline remains stable across detail/report/replay reads and runtime-metrics appends.
- `web/src/app/admin/personas/page.tsx` — Surfaced policy-health messaging for legacy-only pressure-model rows on the current Persona list surface.
- `web/src/app/admin/personas/[id]/page.tsx` — Added pressure-model inspection and editing controls to the current admin Persona detail page.
- `web/src/lib/api/client.ts` — Normalized nested admin Persona pressure payloads on the current web API client.
- `web/src/lib/api/types.ts` — Typed the nested admin Persona `customer_pressure` contract for the current admin surfaces.
- `web/src/app/admin/personas/[id]/page.test.tsx` — Verified that the Persona detail page renders the frozen pressure model and saves nested pressure edits back into `persona_policy`.
- `.gsd/REQUIREMENTS.md` — Updated R010 to record the slice’s new frozen-pressure-model proof and remaining downstream work.
- `.gsd/PROJECT.md` — Refreshed current-state project continuity to show M003/S02 as complete and to point S03 at the frozen snapshot contract.
