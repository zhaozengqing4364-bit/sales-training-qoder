---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T02: 抽出 session create/lifecycle/report 应用服务

- 先抽 `create session + voice_policy_snapshot/runtime descriptor` 与 `lifecycle/report/read model` 两组 service，保持现有 response schema 和权限边界不变。
- 对 `audio_audit` / OSS signing / retry focus 等高耦合 helper 采用窄 service/assembler seam，而不是继续堆回 route。
- 保证 route 层只负责 auth、request parsing、response shape、HTTP code。

## Inputs

- `T01 的 seam 设计`
- `现有 practice/report/audio routes`

## Expected Output

- `backend/src/common/services/practice_session_service.py`
- `backend/src/common/services/practice_report_service.py`
- `backend/src/common/api/practice.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q
