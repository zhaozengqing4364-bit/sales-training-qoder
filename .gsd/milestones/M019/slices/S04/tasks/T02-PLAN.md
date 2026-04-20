---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T02: 把 workflow 与观测出口对齐到真实 authority

- 新增或拆分 GitHub Actions，让 web/backend focused gates、依赖安装 authority、docs/spec drift check 与 release baseline 一致。
- 为 frontend error reporting 和 metrics surface 做明确收口：要么补对口 route/check，要么让缺失成为显式失败信号而非静默假接通。
- 保持所有验证命令都能从 repo root 直接运行。

## Inputs

- `T01 inventory`
- `web/package.json`
- `backend/requirements.txt`
- `backend/pyproject.toml`

## Expected Output

- `.github/workflows/*.yml`
- `backend/src/main.py or backend/src/common/api/*.py`
- `web/src/components/ErrorBoundary.tsx`

## Verification

rg -n "npm --prefix web|backend/venv/bin/python -m pytest|requirements.txt|package-lock|metrics|analytics/error" .github/workflows && npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" && backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
