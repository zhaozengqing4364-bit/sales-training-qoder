---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 定位热点查询与索引候选路径

Why: 先定位最可能的热点查询和索引候选路径，后续基线才能围绕真实风险而不是全文猜测。

Do:
1. 梳理 analytics/history/admin/leaderboard/projection 的热点读路径。
2. 标出最可能的 N+1、索引缺口和 slow query 候选。
3. 记录哪些只是 ORM 结构猜测，哪些已经接近真实热点。

Done when: 已形成热点查询与索引候选清单，可直接指导后续 evidence gathering。

## Inputs

- `backend/src/common/analytics/*`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/admin/api/*`

## Expected Output

- `backend/src/common/analytics/*`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/admin/api/*`

## Verification

rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api

## Observability Impact

形成热点查询与索引候选 inventory。
