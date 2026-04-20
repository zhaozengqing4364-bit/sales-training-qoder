---
id: T03
parent: S03
milestone: M018
key_files:
  - docs/backup-recovery-runbook.md
  - .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Made the runbook’s repo-local authority seams explicit by listing the revalidated files instead of relying on implied code references.
  - Kept disaster-recovery drill advice and future improvements in a dedicated non-baseline Follow-up section so the runbook does not mix shipped recovery steps with recommendations.
duration: 
verification_result: passed
completed_at: 2026-04-12T00:10:18.785Z
blocker_discovered: false
---

# T03: Revalidated the backup/recovery runbook against live repo paths and moved drill/improvement guidance into explicit non-baseline follow-up sections.

**Revalidated the backup/recovery runbook against live repo paths and moved drill/improvement guidance into explicit non-baseline follow-up sections.**

## What Happened

I manually rechecked the runbook’s cited repo-local seams against the live repository and tightened both `docs/backup-recovery-runbook.md` and `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md` so they now point only at files and commands that are actually present today. The runbook introduction now names the specific repo-local references that were revalidated (`scripts/dev-up.sh`, `scripts/dev-stop.sh`, `backend/src/main.py`, `backend/scripts/repair_legacy_schema.py`, `backend/scripts/bootstrap_auth_admin.py`, the database/config/storage/vector-store seams, the legacy admin upload seam, and `docs/setup/auth-local.md`), and the `/health` verification step now explicitly anchors to the shipped backend route in `backend/src/main.py` instead of generic wording. I also restructured the tail of the runbook so quarterly disaster-recovery drill advice and future improvement items are grouped under a single `Follow-up（非当前可执行基线）` section, which keeps executable backup/recovery reality separate from unshipped recommendations. The baseline analysis file now mirrors that split and records the revalidated repo-local reference set so future agents can start from one factual pointer instead of re-auditing command/path drift from scattered code.

## Verification

Fresh verification was run after the final edits. A repo-local reference existence check confirmed every runbook-anchored file path used in this task is present in the current repository. A JSON parse check confirmed `.codex/loop/state.json` remained valid after the continuity update. The task-plan verification command `grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md` passed and showed the final runbook/baseline still expose the backup, recovery, and drill/follow-up surfaces future agents are expected to grep directly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 - <<'INNER' ... Path(...).exists() ... INNER` | 0 | ✅ pass | 24ms |
| 2 | `python3 - <<'INNER' import json, pathlib; json.loads(pathlib.Path('.codex/loop/state.json').read_text()); print('state.json ok') INNER` | 0 | ✅ pass | 21ms |
| 3 | `grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md` | 0 | ✅ pass | 3ms |

## Deviations

None.

## Known Issues

The repository still does not ship automated PostgreSQL backup scheduling, Redis restore automation, OSS bulk-export tooling, a single authoritative Chroma persistence path, or named RTO/RPO/on-call ownership; this task kept those items explicitly outside the executable baseline and inside Follow-up guidance rather than inventing capabilities.

## Files Created/Modified

- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
