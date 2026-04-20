---
estimated_steps: 2
estimated_files: 6
skills_used: []
---

# T01: 建立 org/team target-state matrix

- 盘点当前 user/session/agent/persona/knowledge/report/admin ownership 模型，找出所有隐含的‘单组织/单租户’假设。
- 建一张 org/team/member/role/access scope target-state matrix，对齐 authz、analytics、asset ownership。

## Inputs

- `current ownership/authz model`
- `M020 hardened auth boundary`
- `M022 S03 truth surfaces`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`

## Verification

rg -n "user_id|role|owner|agent_id|persona_id|knowledge_base|organization|tenant|team" backend/src/common backend/src/admin web/src/app/admin .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
