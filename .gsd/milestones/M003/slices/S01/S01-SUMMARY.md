---
id: S01
parent: M003
milestone: M003
provides:
  - A confirmed admin Persona/knowledge -> session create -> learner practice/report/replay authority chain on current routes.
  - The locked learner/admin-visible knowledge-status vocabulary for M003: `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, `hit`.
  - A proof boundary that keeps knowledge-check/report on `practice.py` and replay on the conversation API/replay service over `SessionEvidenceService`.
  - A blocker rule that forces inventory/spike when required entrypoints are missing or non-runnable.
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - .gsd/milestones/M003/M003-ROADMAP.md
  - .gsd/milestones/M003/slices/S01/S01-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-VERIFY.json
  - .gsd/KNOWLEDGE.md
  - .gsd/REQUIREMENTS.md
  - .gsd/PROJECT.md
key_decisions:
  - Treat `web/src/app/admin/personas/[id]/page.tsx` + `web/src/app/admin/knowledge/[id]/page.tsx` + `POST /api/v1/practice/sessions` + `web/src/app/(user)/practice/[sessionId]/page.tsx` as the canonical M003 business entry chain.
  - Keep the learner/admin-visible knowledge contract on exactly seven statuses: `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, and `hit`; keep KB-lock `blocked_*` states and retrieval detail like `hit_keyword_fallback` in diagnostics only.
  - Keep replay proof bound to `backend/src/common/conversation/api.py` + `backend/src/common/conversation/replay.py` over `SessionEvidenceService`, not `backend/src/common/api/practice.py`.
  - Treat shell-safe Next.js path quoting/escaping and stale VERIFY artifact refreshes as part of the verification contract, not optional cleanup.
patterns_established:
  - Inventory the current admin/user entrypoints and owning backend modules before planning richer realism behavior; if the seam is missing, stop at inventory/spike instead of designing forward from assumptions.
  - Keep public learner/admin status vocabularies small and current-contract only; expose richer blocked/detail states on diagnostic fields instead of inflating the report contract early.
  - When a verifier syntax bug was already captured into `T##-VERIFY.json`, fixing the plan text alone is insufficient; refresh the VERIFY artifact so later gates execute the corrected command set.
observability_surfaces:
  - `GET /api/v1/practice/sessions/{id}/knowledge-check` with `knowledge-check.status` and `knowledge-check.summary`
  - `runtime_metrics.knowledge_retrieval.*` on runtime diagnostics
  - `kb_lock_status` and `kb_lock_last_status` on runtime diagnostics
  - `last_query` and `recent_queries` on runtime diagnostics
  - `voice_policy_snapshot_ref` on practice/report surfaces
drill_down_paths:
  - .gsd/milestones/M003/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T02:10:01.359Z
blocker_discovered: false
---

# S01: 真实入口 inventory 与 current knowledge 真值线

**Locked M003 to the real admin→session→practice knowledge chain, the live seven-status knowledge contract, and one current-route proof boundary.**

## What Happened

S01 stayed inside the current business chain instead of inventing new product surfaces. T01 verified the live admin Persona detail page, admin knowledge detail page, `POST /api/v1/practice/sessions`, the voice-policy authority modules, and the learner practice/report/replay routes that already move user value. The roadmap and slice/task plans were rewritten so M003 now points only at those runnable entrypoints and explicitly keeps Silence / Conda / `.env` / lockfile work out of scope.

T02 then locked the learner/admin-visible knowledge vocabulary to the current code. The slice now treats `build_session_runtime_diagnostics(...).status` as the only live contract for `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, and `hit`. KB-lock `blocked_*` states and retrieval detail like `hit_keyword_fallback` remain diagnostic-only on `kb_lock_status`, `kb_lock_last_status`, and `runtime_metrics.knowledge_retrieval.last_status` instead of being promoted into report status vocabulary. During that work the slice also retired stale verifier fallout by hardening the shell-safe Next.js path checks and refreshing the old task VERIFY artifact that had captured broken bare paths.

T03 bound the accepted proof line for the rest of M003 to current routes only. Session creation, knowledge-check, and report remain on `backend/src/common/api/practice.py`, while replay is explicitly owned by `backend/src/common/conversation/api.py` plus `backend/src/common/conversation/replay.py` over `SessionEvidenceService`. The roadmap now carries one focused backend boundary, one focused web boundary, one later live-UAT boundary, and one blocker rule: if any required entrypoint is missing or non-runnable, execution stops and becomes inventory/spike instead of continuing on placeholders.

During slice close-out, the remaining gate failure turned out to be a stale `.gsd/milestones/M003/slices/S01/tasks/T03-VERIFY.json` artifact still replaying unescaped `web/src/app/(user)/...` commands. Refreshing that artifact to the escaped command form retired the false shell error and brought the close-out gate back into line with the already-hardened plan docs.

## Verification

Fresh slice verification passed in this close-out turn. I ran the full file-existence gate across the confirmed backend authority modules and the admin/practice/report/replay entrypoints, using escaped literal Next.js paths so shell parsing could not fail before the file check. I then ran the live-status vocabulary grep across `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/common/knowledge/kb_lock_guard.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, and the M003 roadmap/slice/task plans; the out-of-scope / inventory-spike boundary grep across the roadmap and S01 plans; the focused-backend/focused-web/live-UAT/replay-route grep across the roadmap and T03 plan; and an observability grep that confirmed `kb_lock_status`, `kb_lock_last_status`, `last_query`, `recent_queries`, and `voice_policy_snapshot_ref` remain on the claimed diagnostic surfaces. All commands exited 0. I also refreshed `.gsd/milestones/M003/slices/S01/tasks/T03-VERIFY.json` so the auto gate no longer replays the stale unescaped path commands that had been failing with shell syntax errors.

## Requirements Advanced

- R010 — Locked the current admin Persona/knowledge -> `POST /api/v1/practice/sessions` -> learner practice/knowledge-check/report/replay chain and the live seven-status knowledge vocabulary to verified routes/modules, so downstream M003 slices now build on current product seams instead of guessed surfaces.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Extended the slice close-out to refresh a stale `T03-VERIFY.json` artifact because auto-mode was still replaying the pre-fix bare Next.js path commands even though the plan docs had already been hardened. Also corrected the proof-ownership wording so replay stays on the conversation API/replay service seam instead of generic `practice.py` wording.

## Known Limitations

S01 is a contract/inventory slice only. It does not yet prove frozen Persona pressure inside `voice_policy_snapshot`, multi-turn unresolved objection persistence, unsupported/evidence-backed claim-truth semantics, or one live objection-heavy admin→practice→report/replay run.

## Follow-ups

S02 should freeze Persona pressure into the session snapshot and reconnect path. S03 should keep unresolved price / competitor / proof objections alive across topic drift. S04 should align unsupported / evidence-pending / evidence-backed truth on the same report/replay evidence line. S05 should run one real objection-heavy admin→practice→knowledge-check/report/replay proof on the locked S01 surfaces.

## Files Created/Modified

- `.gsd/milestones/M003/M003-ROADMAP.md` — Locked M003 to the current admin Persona/knowledge -> session create -> practice/report/replay chain, the seven live knowledge statuses, and the focused proof boundary.
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — Recorded the accepted proof surfaces, status ownership, observability signals, blocker rule, and slice-level verification commands on current routes only.
- `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md` — Pinned the slice start point to the real admin/runtime/learner chain and excluded environment/tooling-only scope.
- `.gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md` — Defined the live learner/admin-visible knowledge vocabulary and kept blocked/detail states inside diagnostics.
- `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` — Bound later M003 proof to current report/knowledge-check/replay routes and documented the inventory/spike blocker.
- `.gsd/milestones/M003/slices/S01/tasks/T01-VERIFY.json` — Refreshed the earlier stale task verifier to the shell-safe escaped Next.js path form during slice execution.
- `.gsd/milestones/M003/slices/S01/tasks/T03-VERIFY.json` — Refreshed the close-out task verifier so the auto gate stops replaying unescaped `web/src/app/(user)/...` shell commands.
- `.gsd/DECISIONS.md` — Recorded the replay proof-ownership split as a durable project decision for downstream M003 work.
- `.gsd/KNOWLEDGE.md` — Captured the recurring verifier gotchas: quote/escape Next.js literal paths, refresh stale VERIFY artifacts, and keep replay proof bound to the conversation API seam.
- `.gsd/REQUIREMENTS.md` — Advanced R010 with the completed S01 proof: real entry chain, live status vocabulary, replay ownership line, and inventory/spike blocker.
- `.gsd/PROJECT.md` — Updated current-state project context so future slices can see that M003/S01 is complete and what boundaries it locked.
