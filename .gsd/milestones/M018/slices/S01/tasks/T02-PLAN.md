---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 形成 evidence-backed DB performance baseline

用 focused tests、explain 或代码级查询审视形成第一轮 baseline，明确哪些只是猜测、哪些值得后续起 implementation slice。

## Inputs

- `backend/tests/contract/test_analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/unit/common/test_leaderboard_service.py`

## Expected Output

- `discovery artifact`
- `follow-up backlog`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q

## Observability Impact

query/index baseline
