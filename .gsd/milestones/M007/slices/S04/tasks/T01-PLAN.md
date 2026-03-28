---
estimated_steps: 3
estimated_files: 4
skills_used:
  - safe-grow
  - fastapi-python
  - verification-before-completion
---

# T01: Persist fire-and-forget sales finalization on the trigger's own DB session

**Slice:** S04 — 最终集成验证与封板
**Milestone:** M007

## Description

Fix the persistence bug on the real fire-and-forget path, not just the injected-session happy path. The executor should load `safe-grow`, `fastapi-python`, and `verification-before-completion` before changing code. Work from the explicit-commit DB policy already used in this repo: the background trigger owns its own async session, so it must durably commit `report_status`, `report_error`, and the final sales `session.status` transition itself.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `AsyncSessionLocal` own-session trigger path | fail the focused regression and keep replay gating untouched until the persistence bug is fixed | treat as incomplete finalization and expose the persisted `scoring` wedge instead of masking it | stop and inspect the stored `PracticeSession.status/report_status/report_error` values before changing behavior |
| `SessionEvidenceService.get_projection(...)` | leave the session in `scoring` with explicit deferred/failure diagnostics rather than forcing `completed` | keep the session in `scoring` and surface the blocker in the regression output | fail soft and keep the session gated until canonical evidence is readable |
| optional enhanced report generation | persist `report_status="failed"` plus the truthful final sales status once canonical evidence is readable | keep failure visible via `report_error` without swallowing the terminal state | preserve the failure path and do not infer success from partial report payloads |

## Load Profile

- **Shared resources**: async DB sessions, transaction boundaries, and the background projection read.
- **Per-operation cost**: one session lookup, one projection pass, and the existing report-generation call.
- **10x breakpoint**: transaction / connection contention if the fix introduces duplicate commits, extra polling, or repeated projection passes.

## Negative Tests

- **Malformed inputs**: unknown `session_id`, missing session row, or malformed report result objects should fail cleanly without writing a false `completed` state.
- **Error paths**: optional enhanced-report failure must still persist `report_status="failed"` and a truthful terminal sales status on the own-session path.
- **Boundary conditions**: sessions already outside `scoring`, projection reads that are not yet complete, and `db=None` fire-and-forget execution must all preserve the current replay gate semantics.

## Steps

1. Inspect `backend/src/evaluation/services/report_generation_trigger.py`, the explicit-commit DB policy, and current retry/finalization branches so the background own-session flow commits status changes durably after success or failure finalization.
2. Add focused regressions that fail on `db=None` / own-session execution, including a real async-session test that proves a sales session moves from `scoring` to `completed` (or `failed` + `completed` when optional enhanced report generation fails) after the background trigger returns.
3. Re-run the focused unit/integration pack and stop if any existing injected-session tests still mask the own-session behavior instead of proving it.

## Must-Haves

- [ ] `ReplayService._check_session_completed()` and route-family gating stay untouched.
- [ ] Both success and failure branches persist through the trigger's own DB session.
- [ ] The new regression proves the live fire-and-forget path rather than caller-owned commit semantics.

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_report_generation_trigger.py backend/tests/integration/test_report_generation_trigger_fire_and_forget.py`

## Observability Impact

- Signals added/changed: durable `report_generation_completed`, `report_generation_failed`, and `sales_session_finalized` state transitions from the trigger's own DB session.
- How a future agent inspects this: rerun `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py` and inspect persisted `PracticeSession.status`, `report_status`, and `report_error` after the background trigger returns.
- Failure state exposed: whether the fire-and-forget path still leaves sessions stuck in `scoring` even though canonical report evidence is already readable.

## Inputs

- `backend/src/evaluation/services/report_generation_trigger.py` — current fire-and-forget finalization logic
- `backend/src/common/db/session.py` — explicit-commit DB policy
- `backend/src/common/db/session_lifecycle.py` — caller that launches the background trigger
- `backend/tests/unit/test_report_generation_trigger.py` — current unit coverage on the injected-session path
- `backend/tests/integration/test_session_lifecycle_api.py` — existing integration proof around `scoring` → background finalization

## Expected Output

- `backend/src/evaluation/services/report_generation_trigger.py` — own-session persistence fix
- `backend/tests/unit/test_report_generation_trigger.py` — updated unit coverage for success/failure persistence semantics
- `backend/tests/integration/test_report_generation_trigger_fire_and_forget.py` — new regression covering `db=None` / own-session execution
- `backend/tests/integration/test_session_lifecycle_api.py` — lifecycle proof aligned with the persisted finalization behavior
