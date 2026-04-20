---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Define the claim-truth flags on the current evaluator/session-evidence line

Define canonical truth flags for sales claims on the existing backend authority line: unsupported_claim, weak_evidence, evidence_pending, and evidence_verified. Add focused tests around evaluator/session-evidence semantics so the flags map cleanly onto current issue/goal families without renaming public report keys.

## Inputs

- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/conversation/session_evidence.py`
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md`

## Expected Output

- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py`
- `backend/tests/unit/test_session_evidence_service.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py
