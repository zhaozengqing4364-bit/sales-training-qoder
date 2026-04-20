---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T01: 划分 practice backend 的应用层责任面

- 沿 `backend/src/common/api/practice.py` 盘点当前真实 responsibility clusters：session create+policy freeze、lifecycle、report/read model、audio audit/signing、runtime descriptor。
- 在 `backend/src/common` 下设计最小 application/service module 边界，避免新造第二套 route family。
- 先补一组 focused tests 或 inventory assertions，锁住现有 outward contract。

## Inputs

- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/db/session_lifecycle.py`

## Expected Output

- `backend/src/common/api/practice.py`
- `backend/src/common/*service*.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_session_lifecycle_api.py -x -q
