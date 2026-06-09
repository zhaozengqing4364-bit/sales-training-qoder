# Curriculum ExaminerAgent Revision Semantics

Timestamp: 2026-06-04T00:54:56Z

Scope:
- `curriculum_practice` ExaminerAgent publish/edit/republish lifecycle.
- Keep `ExaminerAgentService` under the 250 pure-LOC ceiling by splitting payload/hash, publish gate, duplicate, metadata, and revision workflow responsibilities.

Behavior delivered:
- Initial publish creates a `curriculum_examiner_agent` published revision and active pointer.
- Editing a published ExaminerAgent no longer returns `[EXAMINER_AGENT_NOT_EDITABLE]`.
- Published edit saves a future-only working revision and leaves the active row/read payload unchanged.
- Republish validates the working revision, applies its frozen payload to the active row, increments `version`, and moves the active revision pointer.
- Prompt, question-source, scoring-policy, timeout, and safety config changes are classified as `scoring_high_risk`.

Verification:
- `cd backend && venv/bin/python -m pytest tests/integration/test_examiner_agent_api.py::test_should_stage_future_revision_when_published_examiner_agent_is_edited -q --no-cov`
  - Red before implementation: no `curriculum_examiner_agent` published revision existed after initial publish.
  - Green after implementation: `1 passed, 1 warning`.
- `cd backend && venv/bin/python -m pytest tests/integration/test_examiner_agent_api.py -q --no-cov`
  - `5 passed, 1 warning`.
- `cd backend && venv/bin/python -m pytest tests/integration/test_examiner_agent_api.py tests/integration/test_practice_template_api.py -q --no-cov`
  - `17 passed, 1 warning`.
- `cd backend && venv/bin/ruff check src/curriculum_practice/services/examiner_agents.py src/curriculum_practice/services/examiner_agent_duplicates.py src/curriculum_practice/services/examiner_agent_payloads.py src/curriculum_practice/services/examiner_agent_publish_gates.py src/curriculum_practice/services/examiner_agent_revision_metadata.py src/curriculum_practice/services/examiner_agent_revision_service.py tests/integration/test_examiner_agent_api.py`
  - `All checks passed!`

Pure LOC:
- `backend/src/curriculum_practice/services/examiner_agents.py=247`
- `backend/src/curriculum_practice/services/examiner_agent_duplicates.py=26`
- `backend/src/curriculum_practice/services/examiner_agent_payloads.py=149`
- `backend/src/curriculum_practice/services/examiner_agent_publish_gates.py=148`
- `backend/src/curriculum_practice/services/examiner_agent_revision_metadata.py=82`
- `backend/src/curriculum_practice/services/examiner_agent_revision_service.py=175`

Residual scope:
- Full unified publish governance goal remains active.
- Browser acceptance, full RBAC/regrade flows, broader operation diagnostics, and final quality gate are not claimed by this slice.
