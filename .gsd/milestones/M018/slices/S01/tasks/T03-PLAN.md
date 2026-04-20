---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T03: 输出 query/index discovery 结论

Why: 如果不把结论输出成可消费 backlog，后续 agent 仍会重新从零评估 query/index 风险。

Do:
1. 沉淀后续优化列表。
2. 显式区分“已证实的性能缺口”和“仍需真实 Postgres 证据的猜测项”。
3. 保持结论与 focused proof 对齐，不写空泛优化建议。

Done when: 后续是否起性能实现 slice 有一份明确、分层的 discovery 结论可复用。

## Inputs

- `backend/tests/contract/test_analytics.py`

## Expected Output

- `backend/tests/contract/test_analytics.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q

## Observability Impact

query/index baseline 成为可回查的 performance discovery artifact。
