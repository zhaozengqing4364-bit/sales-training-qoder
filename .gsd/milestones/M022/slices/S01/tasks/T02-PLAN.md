---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T02: 把 rubric contract 接入 realtime 与 read-side

- 在 shared effectiveness/realtime scoring/report readers 中接入方法论语义。
- 保持当前外部 contract 尽量稳定，通过 compatibility readers 过渡。
- focused tests 锁定 report/realtime/manager surfaces 对同一 rubric 的解释一致。

## Inputs

- `T01 rubric contract`
- `current tests`

## Expected Output

- `backend/src/common/effectiveness/*`
- `backend/src/agent/capabilities/realtime_scoring.py`
- `backend/tests/*sales*`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q
