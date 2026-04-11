---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T02: 形成 evidence-backed DB performance baseline

Why: baseline 的关键是把“已证实”和“猜测”分开，而不是直接把所有性能建议都推成待实现项。

Do:
1. 结合 focused tests、explain 或代码级查询审视形成第一轮 baseline。
2. 标明哪些问题已有足够证据，哪些仍需要真实 Postgres/runtime 证据。
3. 不抢跑加索引或改查询，只产出 evidence-backed 基线。

Done when: focused analytics proof 通过，且 baseline 已能支撑后续优化优先级。

## Inputs

- `backend/tests/contract/test_analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/unit/common/test_leaderboard_service.py`

## Expected Output

- `backend/tests/contract/test_analytics.py`
- `backend/tests/unit/common/test_admin_analytics_service.py`
- `backend/tests/unit/common/test_leaderboard_service.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q

## Observability Impact

性能风险从 audit 建议变成 evidence-backed baseline。
