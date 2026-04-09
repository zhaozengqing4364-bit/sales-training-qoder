---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 输出 query/index discovery 结论

沉淀后续优化列表，显式区分“已证实的性能缺口”和“尚需真实 Postgres 证据的猜测项”。

## Inputs

- `backend/tests/contract/test_analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/unit/common/test_leaderboard_service.py`

## Expected Output

- `discovery artifact`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q

## Observability Impact

future performance backlog evidence
