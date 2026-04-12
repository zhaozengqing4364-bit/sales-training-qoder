---
id: M018
title: "Performance / dependency / recovery baselines"
status: complete
completed_at: 2026-04-12T04:55:10.187Z
key_decisions:
  - D203 — keep the DB performance baseline in code-adjacent inventories and separate proved gaps from unproved index ideas
  - D204 — keep `QUERY_INDEX_DISCOVERY_CONCLUSIONS` in `backend/tests/contract/test_analytics.py` as the canonical follow-up backlog
  - D205 — dependency-governance truth anchors on `web/package-lock.json` and `backend/requirements.txt`
  - D206 — repository-local docs plus `scripts/dependency-governance.sh` are the canonical dependency-governance entrypoint
  - D207 — requirements-truth backend audit proof remains authoritative even when the exact venv gate is green
  - D208 — backend JWT handling now standardizes on `PyJWT[crypto]` plus shared `JWTError` from `common.auth.service`
  - D209 — backup/recovery baseline docs must stay limited to revalidated repo-local commands and keep drills/improvements in Follow-up
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/admin/api/training_records.py
  - backend/tests/contract/test_analytics.py
  - backend/src/common/auth/service.py
  - scripts/dependency-governance.sh
  - docs/setup/dependency-governance-baseline.md
  - docs/setup/backup-recovery-current-state.md
  - docs/backup-recovery-runbook.md
  - .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
lessons_learned:
  - In this repository, milestone close-out must compare against `origin/001-ai-practice-system`, not `main`, or the code-change verification gate yields a false failure.
  - When the roadmap only exposes acceptance through the slice-overview `After this` column, close-out should verify those shipped outcomes directly and explicitly record the absence of separate Success Criteria / Horizontal Checklist blocks.
  - Operational baseline work becomes trustworthy only when the repository can rerun the proof from local authority seams — code-adjacent inventories for performance, repo-local scripts/docs for dependency governance, and runbook/current-state/analysis layering for recovery.
  - Backend pytest proof for milestone close-out should be run serially in this repo because repo-root pytest-cov still shares a top-level coverage database and can create spurious parallel failures.
---

# M018: Performance / dependency / recovery baselines

**Closed M018 by turning audit-era performance, dependency, and recovery suspicions into verified repository baselines with executable proof seams and truthful follow-up boundaries.**

## What Happened

M018 closed three different kinds of "looks-like-a-problem" audit debt without pretending they were already fixed. S01 converted database performance suspicion into a code-adjacent discovery baseline: the analytics/history/session-evidence/training-record seams now carry explicit DB hotspot inventories, `backend/tests/contract/test_analytics.py::QUERY_INDEX_DISCOVERY_CONCLUSIONS` is the canonical follow-up backlog, and a fresh close-out rerun of `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q` passed 23/23. S02 converted dependency governance from prose into a rerunnable repository capability: `docs/setup/dependency-governance-baseline.md` plus `scripts/dependency-governance.sh` now anchor the workflow, the backend JWT seam moved from `python-jose` to `PyJWT[crypto]`, and fresh milestone verification reran `npm audit --prefix web` (0 vulnerabilities), `backend/venv/bin/python -m pip_audit` (no known vulnerabilities), `backend/venv/bin/python -m piplicenses --from=mixed --format=json`, two focused backend pytest bundles (17/17 and 26/26), and `bash scripts/dependency-governance.sh status` successfully. S03 converted recovery ambiguity into a truthful operational baseline: `docs/setup/backup-recovery-current-state.md`, `docs/backup-recovery-runbook.md`, and `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md` now document the current manual cadence, restore order, and post-recovery verification seams without promoting future drill ideas into shipped capability.

## Decision Re-evaluation

| Decision | Re-evaluation | Verdict | Next milestone action |
| --- | --- | --- | --- |
| D203 — keep the first-round DB performance baseline in code-adjacent inventories and grade confirmed query-shape facts separately from unproved index ideas | Fresh S01 pytest proof plus the contract backlog still support this split; nothing in close-out justified promoting hypotheses into implementation work. | Still valid | Keep until real Postgres evidence exists. |
| D204 — keep `QUERY_INDEX_DISCOVERY_CONCLUSIONS` in `backend/tests/contract/test_analytics.py` as the canonical follow-up backlog | Fresh 23-test analytics bundle still passes and the contract file remains the clearest executable backlog seam. | Still valid | Revisit only if a stronger shared authority seam replaces the contract. |
| D205 — dependency-governance truth anchors on `web/package-lock.json` + `backend/requirements.txt` | Fresh web/backend audit reruns and `scripts/dependency-governance.sh status` still point at those files as the truthful install/audit inputs. | Still valid | Revisit only after backend packaging metadata becomes authoritative. |
| D206 — repository-local doc + wrapper script are the canonical dependency-governance entrypoint | Fresh `bash scripts/dependency-governance.sh status` confirmed the wrapper remains the right first stop for prerequisites and drift. | Still valid | Maintain the doc/script together. |
| D207 — OSV-backed / requirements-scoped pip-audit remains the truthful repo-level backend proof seam even if the exact gate is green | The exact gate is green today, but the repo-level governance story still depends on requirements truth rather than ambient venv contents. | Still valid | Keep both exact and requirements-scoped proof green. |
| D208 — backend JWT handling uses `PyJWT[crypto]` with shared `JWTError` from `common.auth.service` | Fresh auth/runtime pytest bundles passed, so the shared seam remains the correct hardening choice. | Still valid | Monitor only if downstream callers need broader JWT capabilities. |
| D209 — backup/recovery baseline docs must stay limited to revalidated repo-local commands/paths and isolate drill/improvement guidance in Follow-up | Fresh runbook/analysis grep proof still shows the baseline/follow-up separation working as intended. | Still valid | Preserve this documentation boundary in future recovery automation work. |

## Milestone-level verification notes

- Code-change verification: `git merge-base HEAD main` is invalid in this repository because the real integration branch is `origin/001-ai-practice-system`; using the repository-equivalent diff command `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` produced non-`.gsd` changes, so this milestone did not collapse into planning-only output.
- Roadmap structure note: the preloaded roadmap excerpt did not include a separate `Success Criteria` or `Horizontal Checklist` block. Close-out therefore verified the slice overview `After this` outcomes directly as the milestone acceptance criteria.

## Success Criteria Results

The preloaded M018 roadmap excerpt did **not** include a separate `Success Criteria` section, so close-out verified the three explicit slice-overview `After this` outcomes as the milestone acceptance criteria.

- [x] **Query/index baseline exists and future performance work starts from real evidence instead of audit guesswork.**
  - Evidence from shipped artifacts: `backend/src/common/analytics/admin_analytics_service.py`, `backend/src/common/analytics/history_service.py`, `backend/src/common/conversation/session_evidence.py`, and `backend/src/admin/api/training_records.py` all expose `*_DB_PERFORMANCE_BASELINE` inventories; `backend/tests/contract/test_analytics.py` contains `QUERY_INDEX_DISCOVERY_CONCLUSIONS`.
  - Fresh verification: `rg -n "QUERY_INDEX_DISCOVERY_CONCLUSIONS|DB_PERFORMANCE_BASELINE" ...` matched the expected inventory/backlog seams, and the focused analytics pytest gate passed **23/23**.

- [x] **The repository now has an executable dependency scan / upgrade strategy baseline.**
  - Evidence from shipped artifacts: `docs/setup/dependency-governance-baseline.md` documents the process and `scripts/dependency-governance.sh` is the canonical repository entrypoint.
  - Fresh verification: `npm audit --prefix web` returned `found 0 vulnerabilities`; `backend/venv/bin/python -m pip_audit` returned `No known vulnerabilities found`; `backend/venv/bin/python -m piplicenses --from=mixed --format=json` generated a license inventory; focused backend auth/runtime pytest bundles passed **17/17** and **26/26**; `bash scripts/dependency-governance.sh status` reported ready prerequisites and authority files.

- [x] **A truthful backup/recovery runbook exists for the current deployment reality.**
  - Evidence from shipped artifacts: `docs/setup/backup-recovery-current-state.md`, `docs/backup-recovery-runbook.md`, and `.gsd/analysis/BACKUP_RECOVERY_BASELINE.md` exist and encode the current-state inventory, operator runbook, and short downstream pointer.
  - Fresh verification: milestone close-out reran the plan-defined doc checks; the runbook/analysis files were present, and `grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md` confirmed manual backup cadence, restore order, post-recovery validation, and explicit follow-up separation.

- Horizontal Checklist: no separate `Horizontal Checklist` block was present in the preloaded roadmap excerpt, so there were no additional checklist rows to verify.

## Definition of Done Results

- [x] **All slices complete.** `gsd_milestone_status(milestoneId="M018")` reported S01, S02, and S03 all `complete`, with task counts 3/3 done for every slice.
- [x] **All slice summaries exist.** `find .gsd/milestones/M018 -maxdepth 4 -type f \( -name 'S*-SUMMARY.md' -o -name 'M018-SUMMARY.md' \) | sort` confirmed S01/S02/S03 summary files are present.
- [x] **All task summaries exist.** `find .gsd/milestones/M018/slices -maxdepth 3 -type f -name 'T*-SUMMARY.md' | sort` confirmed all nine task summary files exist.
- [x] **Cross-slice integration points remain coherent.**
  - S01’s performance-discovery authority seams (`*_DB_PERFORMANCE_BASELINE`, `QUERY_INDEX_DISCOVERY_CONCLUSIONS`) are present and verified by the fresh 23-test analytics bundle.
  - S02’s dependency-governance seam (`docs/setup/dependency-governance-baseline.md` + `scripts/dependency-governance.sh` + shared `PyJWT` auth seam) remained runnable under fresh milestone verification.
  - S03’s runbook/analysis artifacts remained present and internally consistent under fresh grep/existence verification.
  - No slice summary claimed a requirement status transition or contradicted another slice’s delivered baseline.
- [x] **Code-change gate passed.** The repository-equivalent non-`.gsd` diff check against `origin/001-ai-practice-system` showed real code/document changes outside `.gsd/`, so the milestone was not planning-only.

## Requirement Outcomes

No requirement status transitions occurred in M018. The preloaded slice summaries explicitly reported no requirement advances, validations, invalidations, or re-scopes for this milestone, and milestone close-out found no contrary evidence requiring `gsd_requirement_update`.

## Deviations

None.

## Follow-ups

- Use `QUERY_INDEX_DISCOVERY_CONCLUSIONS` plus real Postgres evidence (`EXPLAIN`, `pg_stat_statements`, runtime timing) to decide whether any M018/S01 candidate graduates into an implementation slice.
- Keep the dependency-governance baseline green by maintaining `backend/requirements.txt`, `web/package-lock.json`, and `scripts/dependency-governance.sh` together whenever dependencies move.
- Promote backup/recovery Follow-up items (automation, owner roster, Redis/OSS/export tooling, RTO/RPO, drill evidence) only after the repository actually ships those capabilities.
