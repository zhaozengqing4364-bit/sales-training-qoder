---
id: T03
parent: S03
milestone: M017
key_files:
  - backend/src/presentation_coach/api/presentations.py
  - backend/tests/contract/test_presentations.py
key_decisions:
  - Kept the upload/resource-race discovery conclusion code-adjacent in `backend/src/presentation_coach/api/presentations.py` and pinned the artifact with contract assertions instead of creating a separate audit-only document.
duration: 
verification_result: passed
completed_at: 2026-04-11T22:08:52.025Z
blocker_discovered: false
---

# T03: Added a code-adjacent presentation race discovery conclusion artifact and pinned it with a focused contract proof so future work can cite confirmed race surfaces directly.

**Added a code-adjacent presentation race discovery conclusion artifact and pinned it with a focused contract proof so future work can cite confirmed race surfaces directly.**

## What Happened

I extended `backend/src/presentation_coach/api/presentations.py` with `PRESENTATION_RESOURCE_RACE_DISCOVERY_CONCLUSIONS`, a canonical code-adjacent discovery artifact that turns the earlier audit/proof work into directly reusable facts. The new conclusion explicitly separates confirmed findings from inventory-only surfaces: concurrent in-place replace is the only proved writer race today, delete is a confirmed route-guard gap rather than a lock design problem, and new uploads remain lower priority because fresh presentation ids plus atomic writes currently isolate that path. I also encoded the shared conflict surfaces and the multi-instance lock candidate boundary so downstream agents can see where a per-`presentation_id` serialization seam makes sense and where lock work should still wait for a product-policy decision.

To keep that discovery artifact durable, I widened the existing contract proof in `backend/tests/contract/test_presentations.py` so the test now asserts the conclusion structure itself: the proved replace/delete findings, the upload inventory-only status, and the items that are explicitly not recommended yet. This task intentionally did not implement locking, retries, or delete-policy changes; it only converted the slice’s focused proof results into a code-adjacent conclusion future slices can quote without re-auditing the routes.

## Verification

The task-plan verification command passed end to end: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q` finished 11/11 green. That run exercises the strengthened contract assertion for the new discovery artifact plus the earlier focused replace/delete proofs, so the code-adjacent conclusion is now validated by the same backend proof line. Fresh LSP diagnostics on `backend/src/presentation_coach/api/presentations.py` and `backend/tests/contract/test_presentations.py` also reported no issues.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q` | 0 | ✅ pass | 4220ms |

## Deviations

The written task plan listed only `backend/src/presentation_coach/api/presentations.py`, but I also updated `backend/tests/contract/test_presentations.py` so the new discovery conclusion is enforced by a focused contract test instead of remaining an unpinned prose constant.

## Known Issues

Concurrent in-place replace is still unmitigated in production and the losing writer can still fall into the generic 500 fallback during page rebuild. The delete route still has no live-session blocker and still leaves stored PPT/thumbnail cleanup unresolved. Upload-new-presentation remains an inventory-only surface rather than a proved race.

## Files Created/Modified

- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
