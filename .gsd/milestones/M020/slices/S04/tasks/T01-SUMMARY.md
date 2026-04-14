---
id: T01
parent: S04
milestone: M020
key_files:
  - scripts/recovery_drill_baseline.py
  - backend/tests/unit/test_recovery_drill_baseline.py
  - docs/backup-recovery-runbook.md
  - docs/setup/backup-recovery-current-state.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D227 — represent the recovery drill baseline as a non-destructive repo-local authority inventory script first, and require later automation to reuse its checked commands and authority paths instead of inventing a parallel script set.
duration: 
verification_result: passed
completed_at: 2026-04-14T00:09:54.183Z
blocker_discovered: false
---

# T01: Added a repo-local recovery drill inventory script and focused proof so auth/db/redis/websocket/OSS recovery checks now share one authority surface.

**Added a repo-local recovery drill inventory script and focused proof so auth/db/redis/websocket/OSS recovery checks now share one authority surface.**

## What Happened

I converted the manual M018 recovery baseline into one executable repo-local authority inventory instead of leaving the drill surface split across markdown only. The new `scripts/recovery_drill_baseline.py` names the six most valuable checked recovery drills for this slice contract: `db_migration`, `auth_bootstrap`, `redis_session_state`, `websocket_reconnect`, `oss_signing_playback`, and `health_check`. Each drill now carries one checked command, its authority paths, and the evidence operators should capture.

I also made the still-manual boundaries explicit in the same script so downstream work does not overclaim current capability: `redis_service_restore`, `oss_bucket_export`, and `multi_instance_drain` remain outside repo-native automation. That preserves an honest boundary between what the repository can already prove and what still depends on environment-level procedures.

Finally, I wrote the same authority line back into `docs/backup-recovery-runbook.md` and `docs/setup/backup-recovery-current-state.md`, so the docs now point at the script instead of carrying a second, drift-prone command list. A focused unit test was added fail-first and now proves that the drill inventory exists, names the intended hardened recovery seams, and validates every referenced authority path in the repository.

## Verification

Fresh verification reran the focused recovery-drill gate and the task-plan grep gate. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_recovery_drill_baseline.py -q` passed 3/3 and proved the new inventory script exists, exposes the expected drill ids, marks the manual-only boundaries, and validates the referenced authority paths. `python3 scripts/recovery_drill_baseline.py check` exited 0 and printed the repo-local drill inventory plus a clean repository validation result. `rg -n "backup|restore|recovery|drill|auth|redis|oss|websocket" scripts docs/backup-recovery-runbook.md docs/setup/backup-recovery-current-state.md` stayed green and confirmed the new script and both docs are grep-discoverable on the required recovery/auth/redis/websocket/oss seams. Fresh LSP diagnostics on `scripts/recovery_drill_baseline.py` and `backend/tests/unit/test_recovery_drill_baseline.py` reported no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_recovery_drill_baseline.py -q` | 0 | ✅ pass | 1342ms |
| 2 | `python3 scripts/recovery_drill_baseline.py check` | 0 | ✅ pass | 50ms |
| 3 | `rg -n "backup|restore|recovery|drill|auth|redis|oss|websocket" scripts docs/backup-recovery-runbook.md docs/setup/backup-recovery-current-state.md` | 0 | ✅ pass | 29ms |

## Deviations

Used `python3` for the new repo-root drill inventory commands because this local harness has no bare `python` on PATH; the checked commands and docs were updated to reflect the runnable invocation. No plan-invalidating deviations.

## Known Issues

The focused pytest invocation emits pytest-cov `module-not-imported` / `no-data-collected` warnings because it validates a repo-root script via importlib instead of importing backend `src/` modules. The test verdict is green and the warnings were not introduced by this task's runtime behavior.

## Files Created/Modified

- `scripts/recovery_drill_baseline.py`
- `backend/tests/unit/test_recovery_drill_baseline.py`
- `docs/backup-recovery-runbook.md`
- `docs/setup/backup-recovery-current-state.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
