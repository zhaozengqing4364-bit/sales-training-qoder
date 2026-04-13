---
estimated_steps: 2
estimated_files: 5
skills_used: []
---

# T01: 定义 canonical evaluation schema 与 compatibility reader map

- 盘点现有 sales/presentation 评分维度、rollup、report 字段、history/admin 聚合字段，写出 canonical schema 候选与 compatibility readers 列表。
- 明确哪些 surface 先切 canonical，哪些只能暂时镜像。

## Inputs

- `S01/S02 outputs`
- `current score/report/history/admin surfaces`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/src/common/effectiveness/*`
- `backend/src/common/conversation/session_evidence.py`

## Verification

rg -n "logic_score|accuracy_score|completeness_score|overall_score|dimension_scores|effectiveness_snapshot|leaderboard|history" backend/src/common backend/src/agent web/src/lib/api/types.ts
