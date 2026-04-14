---
id: T02
parent: S01
milestone: M021
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - docs/api-contract/sessions.md
  - docs/api-contract/prompt-templates.md
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - backend/tests/unit/common/test_knowledge_answer_feature_flag.py
  - backend/tests/unit/test_report_generation_trigger.py
key_decisions:
  - Use `docs/api-contract/sessions.md` and `docs/api-contract/prompt-templates.md` as the durable consumer-facing contract surfaces for the M021 live-vs-compat authority split, while `docs/api-contract/support-runtime.md` remains the read-side authority explainer for support/runtime health consumers.
duration: 
verification_result: mixed
completed_at: 2026-04-14T01:46:23.106Z
blocker_discovered: false
---

# T02: Wired the M021 AI authority inventory into focused proof files and API-contract docs.

**Wired the M021 AI authority inventory into focused proof files and API-contract docs.**

## What Happened

I turned the T01 live/compat/shadow inventory into durable proof and documentation instead of leaving it only in the architecture scan. On the proof side, I updated the focused session-snapshot, knowledge-rollout, and report-trigger test files so they explicitly say which authority path they lock: the live StepFun/session-snapshot runtime line, the compat-owned knowledge-answer rollout seam with shadow dual-run behavior, and the compatibility/enhancement report sidecar that must not be confused with canonical session evidence. On the docs side, I added authority-boundary sections to `docs/api-contract/sessions.md` and `docs/api-contract/prompt-templates.md`, then synced `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with a proof/doc consumer map that points downstream work at `sessions`, `prompt-templates`, and `support-runtime` for the live-vs-compat consumer split.

During verification, one syntax-only regression slipped into `backend/tests/unit/common/test_knowledge_answer_feature_flag.py` while inserting the new proof wording. I stopped, read the broken tail, removed the stray fragment, and reran the same pytest bundle until it passed cleanly. No plan-invalidating blocker was discovered.

## Verification

Ran a focused backend pytest bundle covering the live session-snapshot proof, the knowledge-answer rollout seam, and the report-generation sidecar proof: `backend/tests/integration/test_voice_runtime_session_snapshot.py::test_start_session_persists_voice_policy_snapshot`, `backend/tests/integration/test_voice_runtime_session_snapshot.py::test_snapshot_baseline_is_immutable_and_report_replay_refer_same_baseline`, `backend/tests/unit/common/test_knowledge_answer_feature_flag.py`, and `backend/tests/unit/test_report_generation_trigger.py`. The rerun finished 15/15 passing after the syntax-only fix. Ran the exact task-plan grep gate `rg -n "live|compat|shadow|retire|authority" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md docs/api-contract backend/tests`, which returned the expected authority wording across analysis, docs, and proof files. Also ran LSP diagnostics on the three touched Python test files, and all came back with no diagnostics.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py::test_start_session_persists_voice_policy_snapshot backend/tests/integration/test_voice_runtime_session_snapshot.py::test_snapshot_baseline_is_immutable_and_report_replay_refer_same_baseline backend/tests/unit/common/test_knowledge_answer_feature_flag.py backend/tests/unit/test_report_generation_trigger.py -q` | 0 | ✅ pass | 7624ms |
| 2 | `rg -n "live|compat|shadow|retire|authority" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md docs/api-contract backend/tests` | 0 | ✅ pass | 77ms |
| 3 | `lsp diagnostics backend/tests/integration/test_voice_runtime_session_snapshot.py — no diagnostics` | -1 | unknown (coerced from string) | 0ms |
| 4 | `lsp diagnostics backend/tests/unit/common/test_knowledge_answer_feature_flag.py — no diagnostics` | -1 | unknown (coerced from string) | 0ms |
| 5 | `lsp diagnostics backend/tests/unit/test_report_generation_trigger.py — no diagnostics` | -1 | unknown (coerced from string) | 0ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `docs/api-contract/sessions.md`
- `docs/api-contract/prompt-templates.md`
- `backend/tests/integration/test_voice_runtime_session_snapshot.py`
- `backend/tests/unit/common/test_knowledge_answer_feature_flag.py`
- `backend/tests/unit/test_report_generation_trigger.py`
