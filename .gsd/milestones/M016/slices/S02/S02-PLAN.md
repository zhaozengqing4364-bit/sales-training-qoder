# S02: API 错误契约与异常分类收口

**Goal:** 统一后端 API 的错误响应格式，减少裸 HTTPException 与通用 except Exception 在业务层直接暴露
**Demo:** After this: audit 命中的高频 API surface 返回统一错误 shape，frontend client 不再 page-local 猜测

## Tasks
- [ ] **T01: 定位高频 API surface 的错误 shape 漂移点** — 盘点 prompt templates、presentations、auth 等高噪声 route family 的错误返回形状，标出裸 HTTPException / 通用 except Exception / page-local frontend 解析分叉。
  - Estimate: 35m
  - Files: backend/src/prompt_templates/api/routes.py, backend/src/presentation_coach/api/presentations.py, backend/src/common/auth/service.py, web/src/lib/api/client.ts
  - Verify: rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth
- [ ] **T02: 收口 backend error contract 并对齐 frontend client** — 实现统一错误 shape：把 domain / permission / not-found / validation error 收口到一致 outward contract，并确保 frontend apiFetch 能稳定解析。
  - Estimate: 1h
  - Files: backend/src/prompt_templates/api/routes.py, backend/src/presentation_coach/api/presentations.py, backend/src/common/auth/service.py, web/src/lib/api/client.ts
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
- [ ] **T03: 为统一错误 shape 补跨端 proof** — 补 focused contract/integration proof，确认 frontend 不需要 page-local 猜测错误格式。
  - Estimate: 40m
  - Files: backend/tests/contract/*.py, web/src/lib/api/*.test.ts
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
