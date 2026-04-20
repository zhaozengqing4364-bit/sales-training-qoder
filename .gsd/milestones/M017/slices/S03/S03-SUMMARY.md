---
id: S03
parent: M017
milestone: M017
provides:
  - A canonical code-adjacent discovery artifact for presentation upload/replace/delete mutation risk.
  - A focused proof bundle that distinguishes real replace/delete problems from unproved upload suspicion.
  - A narrowed next-step boundary for future concurrency mitigation: serialize replace first, decide delete policy next, defer upload-wide lock work.
requires:
  []
affects:
  - future concurrency mitigation on presentation replace/delete surfaces
key_files:
  - backend/src/presentation_coach/api/presentations.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_flow.py
  - backend/tests/integration/test_presentation_delete_permissions.py
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D201 — keep presentation upload/resource-race discovery code-adjacent in `backend/src/presentation_coach/api/presentations.py` and prioritize proving in-place replace before broad lock work.
  - D202 — use a per-request `get_db` override on a shared file-backed SQLite engine for truthful concurrent presentation replace proofs; do not use the shared `async_client` session for race reproduction.
patterns_established:
  - Keep presentation mutation discovery conclusions in the live route file and pin them with focused contract assertions.
  - Separate confirmed writer races from route-guard/policy gaps before adding locks or retries.
  - Use fresh per-request DB sessions on one shared database when reproducing backend API races.
observability_surfaces:
  - `backend/src/presentation_coach/api/presentations.py` discovery constants: `PRESENTATION_RESOURCE_RACE_INVENTORY`, `PRESENTATION_RESOURCE_RACE_FOCUS`, `PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS`.
  - Focused contract seam: `backend/tests/contract/test_presentations.py::test_resource_race_inventory_marks_replace_as_first_confirmed_proof_target`.
  - Focused integration seams: `backend/tests/integration/test_presentation_flow.py::test_concurrent_replace_requests_share_one_version_slot_and_lose_an_update`, `backend/tests/integration/test_presentation_flow.py::test_delete_presentation_has_no_route_level_active_session_blocker`, and `backend/tests/integration/test_presentation_delete_permissions.py::test_delete_presentation_enforces_owner_or_admin`.
drill_down_paths:
  - .gsd/milestones/M017/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M017/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M017/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-11T22:13:35.257Z
blocker_discovered: false
---

# S03: S03: 文件上传 / 资源竞争 / 分布式锁风险 discovery

**Converted presentation upload/replace/delete concurrency suspicion into a code-adjacent discovery baseline: replace is now a proved concurrent-writer race, delete is a proved route-guard gap, and upload remains inventory-only until evidence says otherwise.**

## What Happened

# S03: 文件上传 / 资源竞争 / 分布式锁风险 discovery

**Converted presentation upload/replace/delete risk from audit suspicion into a code-adjacent discovery baseline, with focused proof showing one real replace race, one real delete guard gap, and one lower-priority upload surface that still does not justify lock work.**

## What Happened

## Delivered
- Added `PRESENTATION_RESOURCE_RACE_INVENTORY`, `PRESENTATION_RESOURCE_RACE_FOCUS`, and `PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS` directly beside the live authority in `backend/src/presentation_coach/api/presentations.py`, so future agents can read the current mutation-risk truth from the route file instead of re-auditing or relying on stale prose.
- Locked the discovery artifact with focused contract assertions in `backend/tests/contract/test_presentations.py`, including the proved replace/delete findings, the upload inventory-only status, and the items that are explicitly **not** recommended yet.
- Proved that concurrent in-place replace is a real writer race: two `/api/v1/presentations/{id}/replace` requests can both clear the non-terminal active-session preflight, target version 2, and the loser can fall into the generic 500 fallback during page rebuild when page uniqueness collides.
- Proved that delete is not “just a theoretical multi-instance lock concern”: deleting a presentation that still has a live session reference currently returns 204 in the focused harness and the persisted `PracticeSession.presentation_id` becomes `None`.
- Kept the upload-new surface as discovery-only. Fresh ids + atomic file replace still isolate that path better than the stable-id replace path, so there is no proof-based reason to widen this slice into idempotency-key work or system-wide distributed locks.

## What This Slice Actually Established
1. **Replace is the only proved writer race today.** The current live risk is not “presentation mutations in general”; it is specifically in-place replace on a stable `presentation_id`, where two writers can share one version slot and collide during page rebuild.
2. **Delete is a policy/guard gap before it is a lock design problem.** The current delete route lacks a live-session preflight, so it can detach session authority even though replace already blocks live-session mutation.
3. **Upload-new is still lower priority.** Fresh `presentation_id` + storage-key isolation plus atomic writes mean the current slice has no evidence that upload-new needs locking or idempotency work yet.
4. **Discovery belongs next to the runtime seam.** The canonical source of truth for this risk family is now the code-adjacent discovery artifact plus its focused contract/integration proofs, not a separate audit markdown file.

## Patterns Established For Future Work
- Keep presentation mutation discovery conclusions code-adjacent in `backend/src/presentation_coach/api/presentations.py` and pin them with focused contract assertions.
- Separate **confirmed concurrent-writer races** from **route-guard/policy gaps** before introducing locks, retries, or distributed coordination.
- For truthful backend API race reproduction, use a per-request `get_db` override on a shared file-backed SQLite engine; do not rely on the shared `backend/tests/conftest.py::async_client` session to prove concurrency.
- Treat “retry-only mitigation” as insufficient when the losing writer has already touched shared page/thumbnail state; conflict needs serialization or an explicit CAS boundary first.

## Downstream Notes
- The next implementation slice should target replace serialization per `presentation_id` first (local compare-and-swap or lock), and only consider distributed locking if multiple app instances truly need to run the same mutation concurrently.
- Delete needs a product-policy decision before lock design: block while live sessions exist, retire/rehome sessions first, or make delete explicitly idempotent with clear ownership semantics.
- Do **not** widen work into upload-new idempotency keys or system-wide mutation locks unless a fresh focused proof shows cross-request contention on that path.

## Operational Readiness (Q8)
- **Health signal:** the code-adjacent discovery artifact still classifies replace as `confirmed_concurrent_writer_race`, delete as `confirmed_route_guard_gap`, upload as `inventory_only`, and the focused proof bundle (`test_presentations.py`, `test_presentation_flow.py`, `test_presentation_delete_permissions.py`) stays green.
- **Failure signal:** replace losers still surface only as generic 500 fallbacks, delete can still detach a live session from its `presentation_id`, or future changes erase the explicit discovery artifact and force agents back to audit-by-guessing.
- **Recovery procedure:** rerun the focused proof bundle first; if replace still reproduces, add serialization/CAS around in-place replace before touching broader lock scope. If delete still reproduces, decide and implement the route policy boundary before adding lock machinery. Re-run the same focused bundle after any mitigation.
- **Monitoring gaps:** there is no shipped production metric or admin surface that counts replace-conflict 500s or live-session delete detach events; today these risks are observable through focused tests and route-level logs, not through a dedicated runtime dashboard.

## Verification

## Fresh verification
- `rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py` → exit 0; the discovery constants, focused proof vocabulary, and replace/delete guard-gap coverage are present on the intended authority files.
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q` → exit 0; 11/11 tests passed.
- Fresh LSP diagnostics on `backend/src/presentation_coach/api/presentations.py`, `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_flow.py`, and `backend/tests/integration/test_presentation_delete_permissions.py` returned no diagnostics.

## Diagnostic surface confirmation
- Contract proof locks the discovery artifact itself: replace/delete findings, upload inventory-only status, and explicit “not recommended now” candidates.
- Integration proof reproduces the real concurrent replace failure mode with per-request DB sessions on a shared file-backed SQLite engine, avoiding the false shared-session race produced by the default async client fixture.
- Integration proof confirms delete currently has no route-level live-session blocker and can detach `PracticeSession.presentation_id`.
- Delete-permission proof still keeps owner/admin authorization boundaries separate from the newly confirmed live-session policy gap.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01 widened the original inventory-only writeback into one focused delete-path proof because the live route already showed no session-state preflight, and the slice goal required separating covered mutation surfaces from already-observable guard gaps.

## Known Limitations

- Concurrent in-place replace is still unmitigated in production: the losing writer still falls into a generic 500 fallback instead of a structured conflict response.
- Delete still has no live-session blocker and still does not remove stored PPT/thumbnail artifacts.
- Upload-new remains an inventory-only surface rather than a proved race.
- The focused concurrent replace proof still emits an `SAWarning` from stale page-row deletion, which is useful evidence that shared page rebuild work is still unsafely overlapping but is not yet surfaced through a dedicated runtime metric.

## Follow-ups

1. Add per-`presentation_id` serialization or compare-and-swap around in-place replace and convert the loser path from generic 500 into an explicit conflict contract.
2. Make an explicit delete policy decision for live-session references before broadening into lock design.
3. Leave upload-new alone until focused evidence shows cross-request contention on that path.

## Files Created/Modified

- `backend/src/presentation_coach/api/presentations.py` — Added the code-adjacent inventory, focus, and discovery conclusion artifact for presentation mutation risk.
- `backend/tests/contract/test_presentations.py` — Pinned the discovery artifact with contract assertions.
- `backend/tests/integration/test_presentation_flow.py` — Added focused replace-race and delete-guard-gap proofs.
- `backend/tests/integration/test_presentation_delete_permissions.py` — Preserved owner/admin delete authorization proof beside the newly confirmed live-session policy gap.
- `.gsd/DECISIONS.md` — Recorded D201/D202 for the discovery seam and truthful concurrency-proof harness choice.
- `.gsd/KNOWLEDGE.md` — Captured the async-client harness gotcha and the code-adjacent discovery-artifact pattern for future agents.

## Verification

Fresh slice-plan verification passed from the repository root. `rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py` exited 0 and showed the intended discovery constants plus focused replace/delete proof lines. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q` exited 0 with 11/11 tests passing. Fresh LSP diagnostics on the touched backend authority/test files returned no diagnostics. The pytest run still reports the already-understood stale-writer `SAWarning` from concurrent page deletion, which matches the slice discovery conclusion rather than invalidating it.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The slice stayed in discovery mode and did not implement locking, retries, or delete-policy changes. The only scope widening was adding one focused delete-path proof because the live route already exposed that guard gap and the slice goal required separating real gaps from imagined risk.

## Known Limitations

Concurrent replace is still unmitigated and delete still lacks live-session blocking plus storage cleanup. Upload-new remains unproved rather than disproved; future work should only widen there with fresh evidence.

## Follow-ups

Prioritize per-presentation replace serialization/CAS and explicit conflict responses, then make a product-policy decision on delete behavior for live-session references before considering broader lock rollout.

## Files Created/Modified

None.
