# S03: S03: 文件上传 / 资源竞争 / 分布式锁风险 discovery — UAT

**Milestone:** M017
**Written:** 2026-04-11T22:13:35.258Z

# S03: 文件上传 / 资源竞争 / 分布式锁风险 discovery — UAT

**Milestone:** M017

# S03 UAT — presentation upload / replace / delete concurrency discovery

## Preconditions
- Repository dependencies are installed and the backend test environment can run pytest.
- Execute all commands from the repository root: `/Users/zhaozengqing/github/销售训练qoder`.
- No browser session is required; this slice is accepted through focused backend proof on the live presentation mutation routes.

## Test Case 1 — Discovery artifact exists on the runtime authority seam
1. Run:
   `rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py`
2. Confirm the output includes:
   - `PRESENTATION_RESOURCE_RACE_INVENTORY`
   - `PRESENTATION_RESOURCE_RACE_FOCUS`
   - `PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS`
   - the contract assertion `test_resource_race_inventory_marks_replace_as_first_confirmed_proof_target`
   - the integration proofs for concurrent replace and delete without a route-level live-session blocker.

**Expected outcome**
- Command exits 0.
- The discovery conclusion is stored next to the live presentations API, not only in external notes, and the proof files clearly reference the replace/delete discovery seam.

## Test Case 2 — Contract locks the discovery conclusion itself
1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py -x -q`
2. Verify the contract suite checks that:
   - `upload_new_presentation` remains `inventory_only`;
   - `replace_presentation_in_place` is `confirmed_concurrent_writer_race` and recommends serialization before broader rollout;
   - `delete_presentation` is `confirmed_route_guard_gap` / `confirmed_route_guard_gap_not_lock_gap`;
   - `not_recommended_now` includes the broad distributed-lock and retry-only candidates.

**Expected outcome**
- Suite exits 0.
- The canonical discovery artifact cannot drift silently without breaking contract coverage.

## Test Case 3 — Concurrent replace is a real writer race
1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_presentation_flow.py -k concurrent_replace_requests_share_one_version_slot_and_lose_an_update -x -q`
2. Review the proof behavior:
   - two replace requests share a stable `presentation_id`;
   - both pass the active-session preflight;
   - one response succeeds with version 2;
   - the other falls into the generic 500 fallback;
   - the persisted presentation detail remains version 2 with the winning writer’s content.

**Expected outcome**
- Suite exits 0.
- Exactly one writer wins the replace and the other loses with a 500 fallback, proving a real concurrent-writer conflict instead of an imagined risk.

## Test Case 4 — Delete is currently a live-session guard gap, not only a permission check
1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_presentation_flow.py -k delete_presentation_has_no_route_level_active_session_blocker -x -q`
2. Confirm the proof behavior:
   - a presentation session is created successfully against the uploaded presentation;
   - deleting the presentation still returns 204;
   - the presentation row is gone;
   - the persisted `PracticeSession.presentation_id` becomes `None`.

**Expected outcome**
- Suite exits 0.
- The current delete contract proves the missing live-session preflight explicitly.

## Test Case 5 — Permission boundary still holds while the policy gap remains visible
1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_presentation_delete_permissions.py -x -q`
2. Verify the suite proves:
   - a non-owner non-admin still receives `[PRESENTATION_DELETE_FORBIDDEN]` 403;
   - the uploader can delete their own presentation;
   - an admin can delete another user’s presentation.

**Expected outcome**
- Suite exits 0.
- Authorization still works independently of the newly confirmed live-session delete gap.

## End-to-end acceptance command
Run the exact slice-level gate:
`backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q`

**Expected outcome**
- Exit 0.
- All 11 focused tests pass.

## Edge Cases To Re-check If This Slice Regresses
1. **False race reproduction from shared test session:** if a new concurrency proof uses `backend/tests/conftest.py::async_client`, verify it is not just reproducing shared-session commit errors. Real route-level race proofs must use fresh request sessions on one shared database.
2. **Premature lock expansion:** if a future change starts adding upload-new idempotency or broad distributed locking, verify a new focused proof exists first. This slice does not prove that upload-new is a harmful concurrent path.
3. **Delete policy rewrite:** if delete starts blocking live sessions or rehoming sessions automatically, re-run both the delete guard-gap proof and the permission-boundary suite so policy and authorization remain separable.
4. **Replace conflict mitigation:** if replace changes from 500 fallback to structured 409/conflict behavior, preserve the same concurrent-writer proof shape and only update the expected loser response once serialization/CAS is actually in place.
