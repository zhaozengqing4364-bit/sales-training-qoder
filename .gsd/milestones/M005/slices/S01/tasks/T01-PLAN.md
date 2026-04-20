---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T01: Replace legacy admin analytics math with projection-backed business summaries

Write focused failing tests around `backend/src/common/analytics/admin_analytics_service.py` and current admin analytics/user APIs, then replace legacy weighted-score calculations with projection-backed summaries sourced from `HistoryService` / `SessionEvidenceService`. Keep the current admin routes authoritative; do not create a second analytics pipeline.

## Inputs

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/admin/api/analytics.py`
- `backend/src/admin/api/users.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/contract/test_analytics.py`

## Expected Output

- `backend/src/common/analytics/admin_analytics_service.py`
- `backend/src/common/analytics/history_service.py`
- `backend/src/admin/api/analytics.py`
- `backend/src/admin/api/users.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/integration/test_admin_users_api.py`
- `backend/tests/contract/test_analytics.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/common/test_admin_analytics_service.py tests/integration/test_admin_users_api.py tests/contract/test_analytics.py
