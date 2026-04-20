---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: Group PPT learning issues at page and point level on the current report line

Extend the current presentation report builder so it can group issues at page/point level on the existing authority line: off-page, missing point, overlong explanation, forbidden wording, and weak Q&A handling. Lock the contract with focused backend tests rather than freeform UI expectations.

## Inputs

- `backend/src/presentation_coach/services/presentation_report_service.py`
- `backend/src/common/conversation/session_evidence.py`

## Expected Output

- `backend/src/presentation_coach/services/presentation_report_service.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/test_presentation_report_service.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_presentation_report_service.py
