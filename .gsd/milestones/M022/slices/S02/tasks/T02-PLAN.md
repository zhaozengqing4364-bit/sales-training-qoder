---
estimated_steps: 2
estimated_files: 6
skills_used: []
---

# T02: 把 industry pack contract 接入现有 admin 与 runtime surfaces

- 在现有 admin/persona/scenario/knowledge surfaces 上落地组合 contract，不新增第二套内容平台。
- 让 runtime snapshot / report evidence 能明确指出本次训练使用了哪种行业包/压力模型。

## Inputs

- `T01 contract`
- `current admin pages`

## Expected Output

- `backend/src/agent/api/*`
- `backend/src/common/db/schemas.py`
- `web/src/app/admin/personas/*`
- `web/src/app/admin/agents/*`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q && npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"
