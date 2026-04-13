---
id: T03
parent: S03
milestone: M020
key_files:
  - docs/api-contract/support-runtime.md
  - docs/backup-recovery-runbook.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
key_decisions:
  - Keep `/api/v1/support/runtime` documented as a release-health summary contract and point live websocket state inspection to `SessionManager.get_stats()` plus `SessionStateService.get_stats()` instead of inventing a new cluster-state API surface.
  - Document restart/drain semantics around the existing authority split: live connection visibility is instance-local and ephemeral, while Redis reconnect snapshots are the only shared restart-safe runtime authority.
duration: 
verification_result: passed
completed_at: 2026-04-13T23:43:17.365Z
blocker_discovered: false
---

# T03: Aligned support/runtime docs with the shipped websocket authority split and added restart/drain guidance for Redis snapshots versus process-local connections.

**Aligned support/runtime docs with the shipped websocket authority split and added restart/drain guidance for Redis snapshots versus process-local connections.**

## What Happened

I treated T03 as a doc-contract and runbook hardening pass, not a code-path redesign. First I reread the live support runtime API implementation plus the websocket authority surfaces added in T01/T02. That exposed a real drift in `docs/api-contract/support-runtime.md`: the file still described the old faults filter and log-style payload shape instead of the shipped `overview` / `faults` contract backed by `RuntimeStatusService`, and it did not explain that `/api/v1/support/runtime` is a release-health summary surface rather than a websocket cluster-state API. I rewrote that contract to match the current `severity` filter, the actual overview/fault payloads, and the two companion runtime inspection surfaces: `SessionManager.get_stats()` for process-local live connection visibility and `SessionStateService.get_stats()` for shared Redis reconnect snapshots, including request/connection epoch and last-error semantics.

I then updated `docs/backup-recovery-runbook.md` to make restart/drain behavior explicit instead of leaving it as an operator assumption. The runbook now says what a single-instance/systemd restart actually preserves, what it always drops, why a zeroed `SessionManager` registry after restart is expected, why Redis snapshots are the only restart-safe runtime authority, and why multi-instance drain still depends on external traffic steering because the repo does not ship a drain endpoint or cluster-wide live connection authority. Finally, I wrote the same rule into section 7.2.3 of `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` so downstream slices inherit one durable explanation instead of rediscovering it from websocket code and prior task summaries.

## Verification

Ran the exact task-plan verification command from repo root after the edits. The grep gate passed with exit code 0 and surfaced reconnect, epoch, snapshot, active connection, drain, and restart wording in all three required artifacts: `docs/api-contract/support-runtime.md`, `docs/backup-recovery-runbook.md`, and `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`. I also read back the edited sections to confirm the support-runtime contract now matches the shipped `severity`-based faults API and that the new restart/drain guidance is formatted cleanly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` | 0 | ✅ pass | 58ms |

## Deviations

The plan only said to add state-inspection and restart/drain guidance, but the live `docs/api-contract/support-runtime.md` was also materially stale relative to the shipped API. I corrected that local mismatch while doing the planned runtime-authority write-back so the durable support surface matches the real backend contract instead of preserving an outdated faults schema.

## Known Issues

The repository still does not ship a repo-native websocket drain endpoint, load-balancer/ingress traffic-drain script, or cluster-wide live connection authority. This task documents that gap clearly but does not implement the missing operational control plane.

## Files Created/Modified

- `docs/api-contract/support-runtime.md`
- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
