# S03: Multi-instance session state 与 reconnect authority 收口

**Goal:** 把 SessionManager/SessionStateService 从‘单进程看起来能用’提升为多实例/重启可解释的 state authority。
**Demo:** After this: runtime connection visibility、session snapshot、reconnect/drain 语义对单实例和多实例都清晰，后续扩容不再完全依赖进程内假设。

## Must-Haves

- 进程内连接态与 Redis/session snapshot 的职责边界明确，重连 epoch 与 active connection visibility 有 authority。
- runtime restart/drain/reconnect 至少有一组 focused proof 覆盖。
- 不再默认把单机 systemd happy path 当作扩容语义。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 结束后，runtime state、snapshot、connection visibility、reconnect epoch 都有明确 authority；S04 drill 和 M021 realtime quality events 可以直接消费。

## Verification

- 连接数、session snapshot、reconnect state、last error/epoch 可以从明确 surface 检查，而不是读进程内偶然状态。

## Tasks

- [x] **T01: 建立 runtime state authority table** `est:50m`
  - 盘点 `common.websocket.session_manager`、`session_state_service`、sales/presentation handlers 当前各自持有什么 state。
- 画出单实例、多实例、进程重启三种场景下的 authority table：哪些 state 可以只在进程内，哪些必须进 Redis/persistent snapshot。
- 先补/锁一组 focused reconnect tests，防止后续 hardening 回归 current epoch semantics。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/websocket/session_manager.py`, `backend/src/common/websocket/session_state_service.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/presentation_coach/websocket`
  - Verify: rg -n "SessionManager|SessionStateService|snapshot|reconnect|active_connections|runtime_state" backend/src/common/websocket backend/src/sales_bot/websocket backend/src/presentation_coach/websocket

- [ ] **T02: 按 authority table 重收 runtime snapshot 与 connection visibility** `est:2h`
  - 按 T01 table 收口 state：把需要跨实例/重启可见的 state 写入 Redis/snapshot，把纯进程内状态限制在明确边界。
- 为 drain/restart/reconnect 增加必要的 epoch / status / last-error signals。
- 避免把所有状态都强塞进 Redis；只提升 authority 真正需要的部分。
  - Files: `backend/src/common/websocket/session_manager.py`, `backend/src/common/websocket/session_state_service.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -x -q

- [ ] **T03: 把 runtime state authority 写回 support/runbook surfaces** `est:35m`
  - 为 support/runtime、architecture scan、runbook 补充新的 state inspection surfaces 和 restart/drain guidance。
- 把单机/systemd 与未来多实例边界说清，不让 downstream milestones 再假设 ‘只要重启服务就行’。
  - Files: `docs/api-contract/support-runtime.md`, `docs/backup-recovery-runbook.md`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/websocket/session_manager.py
- backend/src/common/websocket/session_state_service.py
- backend/src/sales_bot/websocket/stepfun_realtime_handler.py
- backend/src/presentation_coach/websocket
- backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py
- docs/api-contract/support-runtime.md
- docs/backup-recovery-runbook.md
