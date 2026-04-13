---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T01: 建立 runtime state authority table

- 盘点 `common.websocket.session_manager`、`session_state_service`、sales/presentation handlers 当前各自持有什么 state。
- 画出单实例、多实例、进程重启三种场景下的 authority table：哪些 state 可以只在进程内，哪些必须进 Redis/persistent snapshot。
- 先补/锁一组 focused reconnect tests，防止后续 hardening 回归 current epoch semantics。

## Inputs

- `session_manager`
- `session_state_service`
- `realtime handlers`
- `existing reconnect tests`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/common/websocket/session_manager.py`
- `backend/src/common/websocket/session_state_service.py`

## Verification

rg -n "SessionManager|SessionStateService|snapshot|reconnect|active_connections|runtime_state" backend/src/common/websocket backend/src/sales_bot/websocket backend/src/presentation_coach/websocket
