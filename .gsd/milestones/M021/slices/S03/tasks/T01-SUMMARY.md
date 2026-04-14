---
id: T01
parent: S03
milestone: M021
key_files:
  - backend/src/common/effectiveness/canonical.py
  - backend/src/common/effectiveness/__init__.py
  - backend/src/common/conversation/session_evidence.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D236 — keep one shared logic/accuracy/completeness rollup contract while using scenario-aware canonical dimension catalogs and explicit compatibility readers.
duration: 
verification_result: mixed
completed_at: 2026-04-14T02:53:32.172Z
blocker_discovered: false
---

# T01: Added the canonical evaluation schema and compatibility reader registry for shared session-evidence consumers.

**Added the canonical evaluation schema and compatibility reader registry for shared session-evidence consumers.**

## What Happened

I locked the canonical evaluation kernel into code instead of leaving it as planning prose. In `backend/src/common/effectiveness/canonical.py` I added the shared `evaluation_kernel_v1` contract, scenario-aware dimension catalogs for sales and presentation, and the surface reader map that marks `report`/`replay`/`history`/`admin` as canonical consumers while keeping realtime and comprehensive-report paths explicit as source or compatibility mirrors. In `backend/src/common/effectiveness/__init__.py` I exported the new kernel definitions for downstream slices. In `backend/src/common/conversation/session_evidence.py` I added `describe_projection_kernel_contract(...)` and attached its output to the projection-built structured log so later work can inspect the canonical schema/version and compat readers from the same authority seam that powers replay/history/admin today. I also wrote the M021 architecture scan subsection that mirrors the code-owned map, saved decision D236 for the scenario-aware shared-rollup approach, and appended a knowledge note about the non-obvious rollup behavior that would otherwise cause future score drift. I did not migrate existing compat consumers yet; that remains the planned work for T02/T03.

## Verification

Verified with focused backend tests and the slice grep proof. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_session_evidence_service.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/unit/common/test_admin_analytics_service.py -q` passed (26 tests). `lsp diagnostics` reported no Python diagnostics for `backend/src/common/effectiveness/canonical.py` and `backend/src/common/conversation/session_evidence.py`. The task-plan grep command also passed, confirming the old score/report/history/admin surfaces are still discoverable for the upcoming reader migration work.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_session_evidence_service.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/unit/common/test_admin_analytics_service.py -q` | 0 | ✅ pass | 1870ms |
| 2 | `rg -n "logic_score|accuracy_score|completeness_score|overall_score|dimension_scores|effectiveness_snapshot|leaderboard|history" backend/src/common backend/src/agent web/src/lib/api/types.ts — exit 0, ✅ pass, duration not captured by the shell timing helper.` | -1 | unknown (coerced from string) | 0ms |
| 3 | `lsp diagnostics on backend/src/common/effectiveness/canonical.py and backend/src/common/conversation/session_evidence.py — no diagnostics.` | -1 | unknown (coerced from string) | 0ms |

## Deviations

None.

## Known Issues

No unexpected blockers. Legacy consumer cutovers in `common/api/practice.py`, leaderboard weighting, and web shared types are intentionally deferred to T02/T03.

## Files Created/Modified

- `backend/src/common/effectiveness/canonical.py`
- `backend/src/common/effectiveness/__init__.py`
- `backend/src/common/conversation/session_evidence.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/KNOWLEDGE.md`
