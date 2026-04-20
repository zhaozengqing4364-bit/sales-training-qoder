---
estimated_steps: 4
estimated_files: 2
skills_used:
  - fastapi-python
---

# T03: Support runtime: classify audio anomalies in RuntimeStatusService

**Slice:** S03 — 音频审计降级与诊断
**Milestone:** M009

## Description

Add audio anomaly kinds (audio_upload_degraded, audio_missing) to `_build_fault_items()`. Derive audio anomaly state from `voice_policy_snapshot.runtime_metrics.audio_audit` bounded summary on `RuntimeSessionRecord`. Reuse existing typed anomaly pattern so `/support/runtime` renders them generically alongside stuck_scoring, knowledge_search_failed, etc.

## Steps

1. Add `audio_diagnostics: dict[str, Any]` field to `RuntimeSessionRecord` dataclass (with `field(default_factory=dict)`). In `_build_runtime_records()`, extract `audio_audit` from `voice_policy_snapshot.runtime_metrics` for each session and store it as `audio_diagnostics`. Only do this extraction if `voice_policy_snapshot` is a dict and has the nested structure.

2. In `_build_fault_items()`, after existing anomaly checks, inspect `record.audio_diagnostics` for audio audit data. Add audio anomaly detection:
   - If `audio_diagnostics` has `failed_segment_count > 0` and `learner_status == 'partial'`, emit `kind='audio_upload_degraded'` with `severity='warning'`.
   - If `learner_status == 'missing'` (segments exist but none uploaded), emit `kind='audio_missing'` with `severity='warning'`.
   - If `failed_segment_count > total_segment_count / 2` (majority failed), escalate to `severity='blocking'`.
   - Diagnostics dict should include `learner_status`, `failed_segment_count`, `total_segment_count`.

3. Add unit tests in `test_support_runtime_service.py` proving:
   - Session with `audio_diagnostics` having `learner_status='partial'` and `failed_segment_count > 0` → `audio_upload_degraded` warning item.
   - Session with `learner_status='missing'` and segment rows exist → `audio_missing` warning item.
   - Session with `failed_segment_count > total/2` → `audio_upload_degraded` blocking item.
   - Session with `learner_status='available'` → no audio anomaly items.

4. Ensure existing `test_support_runtime_service.py` tests continue to pass (the new `audio_diagnostics` field defaults to empty dict, so existing tests with no audio data are unaffected).

## Must-Haves

- [ ] RuntimeSessionRecord has audio_diagnostics field extracted from voice_policy_snapshot
- [ ] _build_fault_items emits audio_upload_degraded and audio_missing anomaly kinds
- [ ] Severity escalation when >50% of segments failed
- [ ] Unit tests prove all three anomaly scenarios plus no-anomaly baseline

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py -v -k audio`
- All audio-related tests pass; existing tests unaffected

## Observability Impact

- Signals added: support/runtime overview and faults endpoints now include audio anomaly items with kind, severity, summary, and diagnostics
- How a future agent inspects: GET /api/v1/support/runtime/faults with no severity filter; look for items with kind starting with `audio_`
- Failure state exposed: audio_upload_degraded (partial/missing uploads), audio_missing (all failed)

## Inputs

- `backend/src/support/services/runtime_status_service.py` — RuntimeSessionRecord dataclass + _build_runtime_records + _build_fault_items to extend
- `backend/tests/unit/test_support_runtime_service.py` — existing test file to extend with audio anomaly tests

## Expected Output

- `backend/src/support/services/runtime_status_service.py` — audio_diagnostics field + audio anomaly classification logic
- `backend/tests/unit/test_support_runtime_service.py` — new audio anomaly unit tests
