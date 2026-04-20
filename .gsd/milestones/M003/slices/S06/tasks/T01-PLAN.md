---
estimated_steps: 4
estimated_files: 7
skills_used: []
---

# T01: Close scoring and unlock same-session replay/highlights

1. Add focused unit/integration/contract regressions that lock the two-stage sales status boundary and same-session replay/highlights unlock path.
2. Implement a narrow sales-only finalization seam in `ReportGenerationTrigger` that promotes `scoring -> completed` only when `SessionEvidenceService` can already read canonical evidence for that same session.
3. Re-run the accepted M003 backend chain and one localhost same-session learner-route proof: `/practice/{sessionId}` -> lifecycle end -> background finalization -> `/practice/{sessionId}/report` -> `/practice/{sessionId}/replay` plus sibling replay/highlights APIs.
4. Record the slice artifacts and evaluate whether M003 can now enter milestone validation.

## Inputs

- `docs/plans/2026-03-27-m003-s06-scoring-replay-unlock.md`
- `.gsd/milestones/M003/M003-ROADMAP.md`
- `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md`
- `.gsd/milestones/M003/slices/S05/S05-UAT.md`
- `.gsd/REQUIREMENTS.md`

## Expected Output

- `backend sales finalization seam implemented`
- `fresh backend regression evidence`
- `fresh localhost same-session report/replay/highlights proof`
- `S06 summary and UAT artifacts`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_report_generation_trigger.py tests/integration/test_session_lifecycle_api.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py -v && cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/integration/test_replay_api.py tests/contract/test_practice_evidence_contract.py && live localhost proof on /practice/{sessionId}, /practice/{sessionId}/report, /practice/{sessionId}/replay, plus GET /api/v1/practice/sessions/{id}/knowledge-check, /report, /api/v1/sessions/{id}/replay, /highlights

## Observability Impact

Adds explicit finalization logging and same-session proof evidence on the accepted report/replay/highlights route family.
