# S01: Methodology-aware sales rubric 收口

**Goal:** 把销售训练从‘通用训练框架 + 销售规则’推进到方法论 aware 的 rubric contract。
**Demo:** After this: 销售训练会有一套可配置方法论/rubric contract，可以明确映射到 realtime、report、manager coaching，而不是只剩关键词阶段和散分。

## Must-Haves

- 至少一套销售方法论/rubric contract（例如 discovery/qualification/value/objection/next-step 维度）接入 canonical evaluation kernel。
- realtime/report/manager coaching 能读同一方法论语义，而不是各自解释。
- 不要求首轮就覆盖所有方法论，但必须明确配置入口与证据映射。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 结束后，S02 persona/industry pack 和 S03 manager calibration 都可以直接复用同一方法论 contract，而不是各自解释什么叫‘好销售对话’。

## Verification

- 方法论/rubric 命中、缺口、校准结果可以在 canonical evidence 上被定位，而不是只剩一个总分。

## Tasks

- [x] **T01: 定义首轮方法论-aware rubric contract** `est:1h`
  - 结合当前 sales_stage/realtime_scoring/effectiveness_snapshot 与 report surfaces，选定首轮方法论维度映射。
- 写出 rubric contract：方法论概念、可观察证据、评分/建议映射、兼容当前 score schema 的方式。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/common/effectiveness`, `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/agent/capabilities/sales_stage.py`, `docs/api-contract`
  - Verify: rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract

- [ ] **T02: 把 rubric contract 接入 realtime 与 read-side** `est:2.5h`
  - 在 shared effectiveness/realtime scoring/report readers 中接入方法论语义。
- 保持当前外部 contract 尽量稳定，通过 compatibility readers 过渡。
- focused tests 锁定 report/realtime/manager surfaces 对同一 rubric 的解释一致。
  - Files: `backend/src/common/effectiveness`, `backend/src/agent/capabilities/realtime_scoring.py`, `backend/src/common/conversation/session_evidence.py`, `backend/tests`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q

- [ ] **T03: 把 rubric 语义写回用户/管理面说明** `est:40m`
  - 更新 learner-facing 和 manager-facing 文档/文案，让方法论语义对用户可解释。
- 写明首轮不覆盖的方法论边界，防止产品话术超过真实能力。
  - Files: `docs/api-contract`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - Verify: rg -n "qualification|discovery|value|objection|next-step|rubric" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/app/(user)/practice/[sessionId]/report/page.tsx

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/common/effectiveness
- backend/src/agent/capabilities/realtime_scoring.py
- backend/src/agent/capabilities/sales_stage.py
- docs/api-contract
- backend/src/common/conversation/session_evidence.py
- backend/tests
- web/src/app/(user)/practice/[sessionId]/report/page.tsx
