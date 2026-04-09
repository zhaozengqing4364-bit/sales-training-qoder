---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 定位热点查询与索引候选路径

梳理 analytics/history/admin/leaderboard/projection 的热点读路径，标出最可能的 N+1 / 索引缺口 / slow query 候选。

## Inputs

- `backend/src/common/analytics/*`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/admin/api/*`

## Expected Output

- `query baseline inventory`

## Verification

rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api

## Observability Impact

query hotspot inventory
