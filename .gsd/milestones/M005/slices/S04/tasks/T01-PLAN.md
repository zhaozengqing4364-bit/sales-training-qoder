---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Add cohort issue buckets and weekly operating summaries to current analytics APIs

Extend the current admin analytics aggregation so it can produce cohort- and department-level issue buckets, repeated blocker families, degradation/not-evaluable breakdowns, and improving/risk lists on the same evidence line as learner and supervisor views.

## Inputs

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/admin/api/analytics.py`
- `backend/tests/contract/test_analytics.py`

## Expected Output

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/admin/api/analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/contract/test_analytics.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/contract/test_analytics.py
