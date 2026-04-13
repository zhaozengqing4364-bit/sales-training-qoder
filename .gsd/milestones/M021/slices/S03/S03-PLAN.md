# S03: Canonical evaluation kernel 收口

**Goal:** 统一评分维度、rollup 和 evidence kernel，避免多套分数事实继续漂移。
**Demo:** After this: realtime、report、history、admin、replay 至少共享一套 canonical sales/presentation evaluation kernel，旧读者通过 compatibility readers 过渡。

## Must-Haves

- realtime/report/history/admin/replay 至少共享一套 canonical dimension schema 与 rollup contract。
- 旧字段/旧维度通过 compatibility readers 暂时保留，而不是继续各算各的。
- focused backend/web tests 锁定 canonical vs compatibility 行为。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 结束后，realtime/report/history/admin/replay 至少共享一套 canonical evaluation kernel；S04 的质量事件可以直接挂在这条事实线。

## Verification

- score drift 可以从 canonical kernel 与 compatibility reader 的差异中被明确定位，而不是通过页面互相比对猜。

## Tasks

- [ ] **T01: 定义 canonical evaluation schema 与 compatibility reader map** `est:55m`
  - 盘点现有 sales/presentation 评分维度、rollup、report 字段、history/admin 聚合字段，写出 canonical schema 候选与 compatibility readers 列表。
- 明确哪些 surface 先切 canonical，哪些只能暂时镜像。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/effectiveness`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/analytics`, `web/src/lib/api/types.ts`
  - Verify: rg -n "logic_score|accuracy_score|completeness_score|overall_score|dimension_scores|effectiveness_snapshot|leaderboard|history" backend/src/common backend/src/agent web/src/lib/api/types.ts

- [ ] **T02: 实现 canonical evaluation kernel 与 compatibility readers** `est:3h`
  - 在 backend shared effectiveness/session-evidence/read-side services 中实现 canonical kernel，并让 realtime write path 与 report/history/admin/replay 统一读它。
- 保留旧字段通过 compatibility readers 输出，避免一次性打断当前前端 surfaces。
- 对 sales 与 presentation 的差异使用同一 kernel 下的 scenario-aware schema，而不是两套完全不同 contract。
  - Files: `backend/src/common/effectiveness`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/analytics`, `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/presentation_coach/services/presentation_report_service.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q

- [ ] **T03: 让前端读侧显式消费 canonical/compat contract** `est:45m`
  - 更新 web shared types / report/replay/history/admin focused tests，让页面明确区分 canonical 字段与 compat 字段。
- 文档化 canonical kernel 与 compat reader 的退役计划。
  - Files: `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`, `web/src/app/(dashboard)/history/page.tsx`, `web/src/app/admin`
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/effectiveness
- backend/src/common/conversation/session_evidence.py
- backend/src/common/analytics
- web/src/lib/api/types.ts
- backend/src/agent/capabilities/realtime_scoring.py
- backend/src/presentation_coach/services/presentation_report_service.py
- web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
- web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
- web/src/app/(dashboard)/history/page.tsx
- web/src/app/admin
