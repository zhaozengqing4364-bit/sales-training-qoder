# S02: API 错误契约与异常分类收口

**Goal:** 统一后端 API 的错误响应格式，减少裸 HTTPException 与通用 except Exception 在业务层直接暴露。
**Demo:** audit 命中的高频 API surface 返回统一错误 shape，frontend client 不再 page-local 猜测。

## Must-Haves

- audit 命中的高频 API surface 返回统一 outward 错误 shape。
- frontend `apiFetch` 不再需要 page-local 猜测错误结构。
- focused contract/integration proof 能覆盖至少一条 domain error、permission error、not-found 或 validation error 的统一行为。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 把 auth/presentation 等高频 API surface 的 outward 错误形状收口到统一 contract，为 S03 的 admin 安全面和 frontend client 复用提供稳定错误边界。

## Verification

- future agents 可通过统一错误 shape 与 contract tests 更快定位后端失败源，而不必沿着 page-local 错误猜测一路倒推。

## Tasks

- [x] **T01: 定位高频 API surface 的错误 shape 漂移点** `est:35m`
  Why: 只有先找到哪些 route family 正在 outward 暴露漂移的错误 shape，后续收口才不会扩成全 backend 扫荡。

Do:
1. 盘点 prompt templates、presentations、auth 等高噪声 route family 的错误返回形状。
2. 标出裸 `HTTPException`、通用 `except Exception` 和 frontend page-local 解析分叉。
3. 找出最小的一组 shared contract seam。

Done when: 已有一份高频 API surface 错误 shape 漂移清单，足够指导后续统一收口。
  - Files: `backend/src/prompt_templates/api/routes.py`, `backend/src/presentation_coach/api/presentations.py`, `backend/src/common/auth/service.py`, `web/src/lib/api/client.ts`
  - Verify: rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth

- [ ] **T02: 收口 backend error contract 并对齐 frontend client** `est:1h`
  Why: 统一 outward 错误 shape 是 frontend client 和 admin/learner 页面停止 page-local 猜测的前提。

Do:
1. 为 domain、permission、not-found、validation error 收口统一 outward contract。
2. 在高噪声 route family 上落这套 contract，而不是一次性扫完整个 backend。
3. 对齐 frontend `apiFetch`，确保稳定解析这套 shape。
4. 不重写 FastAPI 全局异常体系，只修当前 audit 命中的核心 surface。

Done when: focused contract/integration proof 通过，frontend client 不再依赖页面本地错误猜测。
  - Files: `backend/src/prompt_templates/api/routes.py`, `backend/src/presentation_coach/api/presentations.py`, `backend/src/common/auth/service.py`, `web/src/lib/api/client.ts`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q

- [ ] **T03: 为统一错误 shape 补跨端 proof** `est:40m`
  Why: 如果没有 focused proof，错误 shape 很容易在某个 route family 的局部修补中再次漂移。

Do:
1. 补 focused contract/integration proof，覆盖统一错误 shape 的关键正负路径。
2. 确认 frontend client 不需要 page-local 猜测错误格式。
3. 保持测试聚焦在已收口的 route family，不引入大而全的新 suite。

Done when: contract tests 能稳定证明错误 outward shape 统一，且 frontend client 解析规则不再分叉。
  - Files: `backend/tests/contract/*.py`, `web/src/lib/api/*.test.ts`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q

## Files Likely Touched

- backend/src/prompt_templates/api/routes.py
- backend/src/presentation_coach/api/presentations.py
- backend/src/common/auth/service.py
- web/src/lib/api/client.ts
- backend/tests/contract/*.py
- web/src/lib/api/*.test.ts
