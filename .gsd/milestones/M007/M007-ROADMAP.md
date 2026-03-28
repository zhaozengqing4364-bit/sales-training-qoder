# M007: 

## Vision
把现有 realtime coaching 能力在当前 learner/runtime/report/replay 路由族上做成可证明完成的正式闭环，并把旧 M002 remediation 事实线和工件线正式吸收到 M007，结束“产品看起来差不多完成，但 live proof 和 milestone authority 还没真正收口”的状态。

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 教练健康状态真相收口 | high | — | ✅ | After this: on the current `/practice/{sessionId}` learner route, coach degraded / resumed is explicitly visible without interrupting training, and reconnect no longer causes the UI/runtime surfaces to lie about recovery state. |
| S02 | 同 session 结论同源收口 | high | S01 | ⬜ | After this: one real localhost sales session can be followed from live coaching on `/practice/{sessionId}` through `/practice/{sessionId}/report` and `/practice/{sessionId}/replay`, and the issue/goal family stays coherent on that same session. |
| S03 | M002 remediation 归并与权威切换 | medium | S01, S02 | ⬜ | After this: the remaining M002 remediation facts are no longer hanging off an old temporary closeout narrative; M007 becomes the clear authority for the unfinished closure work and its evidence. |
| S04 | 最终集成验证与封板 | medium | S01, S02, S03 | ⬜ | After this: M007 can be validated and closed honestly because live proof and artifact reconciliation pass together, and realtime coaching can be marked complete without caveats. |
