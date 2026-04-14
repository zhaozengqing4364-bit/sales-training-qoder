---
id: T02
parent: S01
milestone: M022
key_files:
  - backend/src/common/effectiveness/canonical.py
  - backend/src/common/effectiveness/methodology.py
  - backend/src/common/effectiveness/__init__.py
  - backend/src/agent/capabilities/realtime_scoring.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/services/practice_session_service.py
  - backend/src/common/api/practice.py
  - backend/tests/unit/test_sales_methodology_contract.py
  - backend/tests/unit/test_effectiveness_canonical_kernel.py
  - backend/tests/unit/test_realtime_scoring.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - Expose methodology semantics additively via `canonical_evaluation_kernel.methodology` and mirror the same payload through `compatibility_readers.sales_methodology_rubric_v1` instead of inventing new top-level report/realtime fields.
  - Derive sales methodology status only inside the shared canonical builder from dimension scores plus optional stage / main_issue / next_goal / claim_truth context so realtime and read-side consumers cannot drift.
duration: 
verification_result: passed
completed_at: 2026-04-14T05:31:35.115Z
blocker_discovered: false
---

# T02: Wired methodology-aware rubric summaries into sales canonical kernels and compatibility readers for realtime, report/replay, and history surfaces.

**Wired methodology-aware rubric summaries into sales canonical kernels and compatibility readers for realtime, report/replay, and history surfaces.**

## What Happened

I connected the T01 sales methodology contract into the shared effectiveness runtime/read-side path instead of letting each surface reinterpret rubric meaning on its own. `backend/src/common/effectiveness/canonical.py` now attaches sales-only methodology metadata to canonical dimension payloads, emits an additive `canonical_evaluation_kernel.methodology` summary, and mirrors that same summary through a new compatibility reader `sales_methodology_rubric_v1` on sales realtime/report/replay/history/admin surfaces. `backend/src/common/effectiveness/methodology.py` now owns the rubric-to-dimension map plus the cross-surface methodology summary builder, while `common.effectiveness.__init__` exports those helpers for shared use. `backend/src/agent/capabilities/realtime_scoring.py` now passes stage context into the shared builder so live scoring snapshots expose the methodology summary immediately. `backend/src/common/conversation/session_evidence.py` rebuilds the final report/read-side kernel after sales alignment so report/replay/history consumers read methodology status from the same aligned stage + main_issue + next_goal + claim_truth context instead of stale session rows. I also threaded the optional stage context through the two realtime snapshot-to-session compatibility paths in `backend/src/common/services/practice_session_service.py` and `backend/src/common/api/practice.py` so persisted realtime score snapshots stay on the same builder contract. Focused tests were extended at the contract, canonical-kernel, realtime, report/replay, and history layers so the same rubric summary is asserted across runtime and manager-facing read-side consumers.

## Verification

Ran the fresh focused methodology proof bundle after the implementation landed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_sales_methodology_contract.py backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_realtime_scoring.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/contract/test_practice_evidence_contract.py -k "methodology or canonical_kernel or attach_canonical_kernel or emits_canonical_kernel or same_kernel" -x -q`, which finished 8 selected tests green and proved the new shared methodology reader on contract, realtime, report/replay, and history surfaces. Then ran the exact task-plan verification command `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q`, which finished 24 selected tests green. Finally checked LSP diagnostics on the touched Python files in `common/effectiveness`, `agent/capabilities/realtime_scoring.py`, `common/conversation/session_evidence.py`, `common/services/practice_session_service.py`, and `common/api/practice.py`; all returned clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_sales_methodology_contract.py backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_realtime_scoring.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/contract/test_practice_evidence_contract.py -k "methodology or canonical_kernel or attach_canonical_kernel or emits_canonical_kernel or same_kernel" -x -q` | 0 | ✅ pass | 5320ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q` | 0 | ✅ pass | 7435ms |

## Deviations

None.

## Known Issues

Pre-existing pytest-cov 'module-not-imported / no-data-collected' warnings still appear on focused repo-root backend pytest commands, but the verification suites exited 0 and the task-specific assertions all passed.

## Files Created/Modified

- `backend/src/common/effectiveness/canonical.py`
- `backend/src/common/effectiveness/methodology.py`
- `backend/src/common/effectiveness/__init__.py`
- `backend/src/agent/capabilities/realtime_scoring.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/services/practice_session_service.py`
- `backend/src/common/api/practice.py`
- `backend/tests/unit/test_sales_methodology_contract.py`
- `backend/tests/unit/test_effectiveness_canonical_kernel.py`
- `backend/tests/unit/test_realtime_scoring.py`
- `backend/tests/unit/test_history_service_evidence_projection.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
