---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T02: 按 authority table 重收 runtime snapshot 与 connection visibility

- 按 T01 table 收口 state：把需要跨实例/重启可见的 state 写入 Redis/snapshot，把纯进程内状态限制在明确边界。
- 为 drain/restart/reconnect 增加必要的 epoch / status / last-error signals。
- 避免把所有状态都强塞进 Redis；只提升 authority 真正需要的部分。

## Inputs

- `T01 table`
- `current runtime tests`

## Expected Output

- `backend/src/common/websocket/session_manager.py`
- `backend/src/common/websocket/session_state_service.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -x -q
