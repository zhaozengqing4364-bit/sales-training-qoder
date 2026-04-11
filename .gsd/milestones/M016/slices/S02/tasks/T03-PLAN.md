---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 为统一错误 shape 补跨端 proof

Why: 如果没有 focused proof，错误 shape 很容易在某个 route family 的局部修补中再次漂移。

Do:
1. 补 focused contract/integration proof，覆盖统一错误 shape 的关键正负路径。
2. 确认 frontend client 不需要 page-local 猜测错误格式。
3. 保持测试聚焦在已收口的 route family，不引入大而全的新 suite。

Done when: contract tests 能稳定证明错误 outward shape 统一，且 frontend client 解析规则不再分叉。

## Inputs

- `backend/tests/contract/*.py`
- `web/src/lib/api/*.test.ts`

## Expected Output

- `backend/tests/contract/*.py`
- `web/src/lib/api/*.test.ts`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q

## Observability Impact

统一错误 shape 的回归可由 focused contract tests 直接拦截。
