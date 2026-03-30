# S01: 后端结论证据合同与跨路由一致性 — UAT

**Milestone:** M010
**Written:** 2026-03-30T02:04:49.521Z

# S01 UAT: 后端结论证据合同与跨路由一致性

## Preconditions
- Backend running on `localhost:3444` with a test database.
- A completed sales session with retrieval ledger entries, transcript turns, and audio segments exists (created via test fixtures).

## Test Cases

### TC-01: Report route includes conclusion evidence
**Steps:**
1. `GET /api/v1/practice/sessions/{completed_session_id}/report`
2. Inspect response JSON for `conclusion_evidence` field.

**Expected:**
- `conclusion_evidence` is present and non-null.
- Contains `main_issue`, `next_goal`, `claim_truth` keys.
- Each key has `evidence_sources` with `retrieval_source`, `transcript_source`, `audio_source` entries.
- Source entries include availability flags and reference counts matching the session's retrieval/transcript/audio data.

### TC-02: Replay route includes conclusion evidence
**Steps:**
1. `GET /api/v1/sessions/{completed_session_id}/replay`
2. Inspect response JSON for `conclusion_evidence` field.

**Expected:**
- `conclusion_evidence` is structurally identical to the report route's value (same source availability, same hit counts, same turn references).

### TC-03: Knowledge-check route includes conclusion evidence
**Steps:**
1. `GET /api/v1/practice/sessions/{completed_session_id}/knowledge-check`
2. Inspect diagnostics response for `conclusion_evidence` field.

**Expected:**
- `conclusion_evidence` is structurally identical to report and replay values.

### TC-04: Presentation sessions return null conclusion evidence
**Steps:**
1. `GET /api/v1/practice/sessions/{completed_presentation_session_id}/report`
2. Inspect response for `conclusion_evidence`.

**Expected:**
- `conclusion_evidence` is `null`.

### TC-05: Degraded session (no retrieval, no audio) still produces consistent evidence
**Steps:**
1. Create a completed sales session with no retrieval hits and no audio segments.
2. Hit report, replay, and knowledge-check for that session.
3. Compare `conclusion_evidence` across all three.

**Expected:**
- All three routes return `conclusion_evidence` with `retrieval_source.available = false` and `audio_source.available = false`.
- `transcript_source.available = true` (transcript still present).
- All three routes return identical values.

### TC-06: Backward compatibility — existing report fields unaffected
**Steps:**
1. Hit report for a completed session created before M010.
2. Verify `score_snapshot`, `pass_flags`, `main_issue`, `next_goal`, `claim_truth` are unchanged.

**Expected:**
- All pre-existing report fields present and structurally identical to pre-M010 behavior.

## Automated Verification
All above cases are covered by the automated contract tests:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml \
  tests/contract/test_conclusion_evidence_parity.py \
  tests/contract/test_practice_evidence_contract.py \
  -x -q
```
Expected: 29 tests pass.

Full backward-compatibility sweep:
```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract -x -q
```
Expected: 83 tests pass.
