# S02: Persona / scenario / industry pack 运营化

**Goal:** 提升 persona/customer-pressure/scenario 深度，并形成可维护的行业包/场景包运营规则。
**Demo:** After this: persona/customer-pressure/scenario/industry pack 会通过现有 admin entrypoints 运作，角色扮演与场景深度不再只靠单条 prompt。

## Must-Haves

- persona/customer_pressure/scenario/knowledge 的组合方式有统一 contract，能表达行业差异和压力模型。
- 继续复用现有 admin agents/personas/knowledge entrypoints，而不是新造平台。
- focused tests 或 inventory 证明这些资产真正影响 runtime/evidence。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 结束后，S03 manager calibration 与 future enterprise rollout 能直接复用现有 admin entrypoints 管理内容资产，而不是再造内容平台。

## Verification

- future agents 可以从 admin/persona/knowledge surfaces 检查某个行业包/压力模型实际影响了哪些运行时行为。

## Tasks

- [x] **T01: 定义 industry pack / customer-pressure 资产合同** `est:50m`
  - 盘点现有 admin agents/personas/knowledge/scenarios surfaces 与 runtime snapshot 之间的映射。
- 定义首轮 industry pack contract：哪些字段属于 persona、哪些属于 scenario、哪些属于 knowledge bundle/customer pressure。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/agent/api`, `backend/src/agent/models.py`, `backend/src/sales_bot/api/scenarios.py`, `backend/src/common/knowledge`
  - Verify: rg -n "persona_policy|customer_pressure|scenario|knowledge_base|agent|industry" backend/src/agent backend/src/sales_bot backend/src/common/knowledge

- [ ] **T02: 把 industry pack contract 接入现有 admin 与 runtime surfaces** `est:2h`
  - 在现有 admin/persona/scenario/knowledge surfaces 上落地组合 contract，不新增第二套内容平台。
- 让 runtime snapshot / report evidence 能明确指出本次训练使用了哪种行业包/压力模型。
  - Files: `backend/src/agent/api`, `backend/src/common/db/schemas.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `web/src/app/admin/personas`, `web/src/app/admin/agents`, `web/src/app/admin/knowledge`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q && npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"

- [ ] **T03: 把资产运营规则写回计划与扫描文档** `est:35m`
  - 文档化行业包/压力模型如何影响 runtime、report、manager calibration，明确哪些仍是手工内容运营项。
- 把资产运营规则写入 architecture scan 和 product plan。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
  - Verify: rg -n "industry pack|customer pressure|scenario package|knowledge bundle" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/agent/api
- backend/src/agent/models.py
- backend/src/sales_bot/api/scenarios.py
- backend/src/common/knowledge
- backend/src/common/db/schemas.py
- backend/src/sales_bot/services/voice_runtime_policy.py
- web/src/app/admin/personas
- web/src/app/admin/agents
- web/src/app/admin/knowledge
- .gsd/plans/GSD_PLAN_post-M018-next-wave.md
