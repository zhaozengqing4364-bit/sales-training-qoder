---
id: S02
parent: M022
milestone: M022
provides:
  - One inspectable industry-pack/customer-pressure provenance seam for runtime, report, and replay.
  - An explicit operator contract that keeps industry-pack governance on existing admin entrypoints.
  - Documented operating rules that S03 manager/admin truth surfaces can reuse directly.
requires:
  []
affects:
  - S03
  - S04
key_files:
  - backend/src/agent/services/industry_pack_contract.py
  - backend/src/common/db/voice_policy_snapshot.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/knowledge/service.py
  - backend/src/common/services/practice_report_service.py
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/app/admin/agents/[id]/page.tsx
  - backend/tests/unit/test_audio_segment_api.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D244 — Treat industry pack as a composed asset over existing agent/persona/knowledge/scenario surfaces and expose read-only contract endpoints instead of introducing a standalone platform.
  - D245 — Freeze a compact `voice_policy_snapshot_ref.runtime_binding` summary and reuse it as the report/replay/detail provenance surface instead of creating a separate mutable evidence model.
patterns_established:
  - Reuse existing admin/persona/knowledge/scenario entrypoints as the asset governance seam; add inspectable read-only contracts instead of building a second content platform.
  - Freeze runtime provenance into `voice_policy_snapshot_ref.runtime_binding` and make downstream read surfaces consume that immutable ref rather than re-resolving live admin state.
  - When a broad lexical verification gate reaches beyond the slice seam, retire collateral failures at shared seams so the canonical gate can stay truthful instead of replacing it with a narrower custom-only pass.
observability_surfaces:
  - `GET /api/v1/admin/personas/industry-pack-contract`
  - `GET /api/v1/admin/agents/industry-pack-contract`
  - `GET /api/v1/scenarios/sales/runtime-contract`
  - `voice_policy_snapshot_ref.runtime_binding` on session detail/report/replay
  - Admin persona detail `Industry Pack 合同` card
  - Admin agent detail `Industry Pack 运行合同` card
drill_down_paths:
  - .gsd/milestones/M022/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M022/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M022/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T07:36:48.958Z
blocker_discovered: false
---

# S02: Persona / scenario / industry pack 运营化

**S02 closed the first composed industry-pack contract on the existing admin/runtime surfaces, froze runtime provenance in `voice_policy_snapshot_ref.runtime_binding`, and documented the operating rules future manager/admin work must reuse.**

## What Happened

This slice made `industry pack` real without creating a second content platform. On the backend, S02 introduced a shared industry-pack contract helper and exposed read-only contract surfaces on the existing admin agents/personas and sales scenario APIs. The contract now makes the ownership boundary explicit: agent keeps the runtime shell/capability defaults, persona policy carries customer pressure and role behavior, knowledge bundle stays the retrieval/evidence lever, and scenario package remains the entry/routing narrative layer instead of pretending to be runtime truth.

The slice also froze a compact `runtime_binding` summary into `voice_policy_snapshot_ref`, then reused that same frozen ref across session detail, report, and replay responses. That gives downstream slices one immutable provenance seam for customer-pressure source, sales focus, follow-up behavior, knowledge bindings, and affected surfaces. On the web, the existing admin persona detail page now shows an `Industry Pack 合同` card and the existing admin agent detail page now shows an `Industry Pack 运行合同` card, so operators can inspect what will influence runtime/report behavior without leaving the shipped admin entrypoints.

Finally, S02 wrote the operating rules back into the architecture scan and next-wave plan so future slices do not drift back into prompt-only or platform-sprawl thinking. The docs now state clearly that industry pack is a composed operating bundle, that changing customer pressure should change runtime/report/manager calibration together, that knowledge bundle changes must remain explainable from frozen runtime binding plus retrieval facts, and that scenario package is narrative-only. During close-out, I also retired two collateral verification blockers exposed by the broad slice gate: knowledge fallback now drops from non-positive BM25 results to a direct lexical scan instead of silently returning `[KNOWLEDGE_SEARCH_UNAVAILABLE]`, and the audio-segment API test fixture now overrides all live imported `get_db` references so route/auth tests stay on the intended in-memory DB even after startup/bootstrap reload tests.

The delivered boundary for downstream readers is intentionally narrow: industry pack is inspectable and runtime-visible today, but still manually authored through existing agent/persona/knowledge/scenario content ops. No new standalone industry-pack CRUD or manager-only taxonomy was introduced.

## Verification

Fresh slice-close verification reran the exact plan gates plus the added admin agent focused proof. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q` passed with 352 tests green (2 skipped, 1244 deselected). `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"` passed (5/5), and `npm --prefix web test -- --run "src/app/admin/agents/[id]/page.test.tsx"` passed (1/1). The two required grep gates also passed: the code inventory command found the industry-pack/persona/scenario/knowledge seams, and the doc inventory command found the operating-rule write-back in both the architecture scan and the next-wave plan.

Because the broad backend gate previously surfaced collateral failures outside the feature seam, I also reran the focused remediation gates that proved those close-out fixes before trusting the assembled pass: `backend/tests/unit/common/test_knowledge_service_fallback.py` passed after restoring lexical fallback when BM25 returns non-positive scores on tiny collections, and `backend/tests/unit/test_audio_segment_api.py` passed after making the local ASGI fixture override all live imported `get_db` callables.

### Operational Readiness (Q8)
- Health signal: completed sales sessions now expose one stable `voice_policy_snapshot_ref.runtime_binding` provenance line, and admin persona/agent detail pages render the same contract boundary for operators.
- Failure signal: if runtime provenance disappears, the broad backend gate catches report/detail/replay contract regressions, while the focused admin page suites catch missing contract cards or broken fetch/render paths.
- Recovery procedure: verify the contract helper + snapshot ref first (`industry_pack_contract.py`, `voice_policy_snapshot.py`, `conversation/schemas.py`), then re-check the existing admin detail pages and the shared report/replay/detail readers before touching prompt copy.
- Monitoring gaps: S02 still relies on focused tests and inspectable admin/runtime surfaces rather than a dedicated production metric for contract-card fetch health or runtime-binding population rate; S03 can extend manager/admin truth surfaces if runtime-binding observability needs a summarized dashboard view.

## Requirements Advanced

- R012 — keeps long-term content governance on inspectable existing admin surfaces instead of a one-off prompt-only setup, but requirement status remains validated from earlier milestone proof.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice stayed on the planned existing admin/persona/scenario/knowledge entrypoints, but close-out required fixing two collateral verification seams outside the core feature files: keyword fallback now handles non-positive BM25 scores on tiny corpora, and the standalone audio-segment API unit fixture now overrides all live imported `get_db` references so broader suite order does not leak requests to the wrong DB.

## Known Limitations

Industry pack is still a composed operating bundle, not a standalone authoring platform. Persona writing, pressure-axis curation, knowledge-bundle selection, and scenario narrative remain manual content-ops work. There is still no dedicated production dashboard for runtime-binding population health; inspection today is through the frozen session ref and focused admin/runtime surfaces.

## Follow-ups

S03 should reuse `voice_policy_snapshot_ref.runtime_binding` directly when building manager/admin truth surfaces instead of inventing a manager-only asset taxonomy. S04 can build organization/team/tenant planning on the same composed-asset model and should not reopen the question of a second content platform.

## Files Created/Modified

- `backend/src/agent/services/industry_pack_contract.py` — Added the shared composed-asset contract helper used by admin and runtime surfaces.
- `backend/src/common/db/voice_policy_snapshot.py` — Extended the frozen snapshot ref so sessions carry a compact immutable `runtime_binding` provenance summary.
- `backend/src/common/conversation/schemas.py` — Kept report/replay readers aligned to the new frozen runtime-binding contract.
- `web/src/app/admin/personas/[id]/page.tsx` — Added the admin persona `Industry Pack 合同` read surface on the existing detail page.
- `web/src/app/admin/agents/[id]/page.tsx` — Added the admin agent `Industry Pack 运行合同` read surface on the existing detail page.
- `backend/src/common/knowledge/service.py` — Restored lexical fallback when BM25 yields non-positive scores on tiny collections so embedding-failure retrieval remains truthful.
- `backend/src/common/services/practice_report_service.py` — Refreshed the audio-segment failure path so the session snapshot is reloaded after commit.
- `backend/tests/unit/test_audio_segment_api.py` — Hardened the local ASGI fixture to override all live imported `get_db` callables after app/auth reload tests.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Recorded the industry-pack operating rules and manager-calibration handoff.
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` — Updated the next-wave plan so the slice completion bar matches the shipped composed-asset contract.
- `.gsd/KNOWLEDGE.md` — Captured the BM25 non-positive-score fallback gotcha for future verification/debugging.
