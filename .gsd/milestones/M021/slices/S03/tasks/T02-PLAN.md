---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T02: 实现 canonical evaluation kernel 与 compatibility readers

- 在 backend shared effectiveness/session-evidence/read-side services 中实现 canonical kernel，并让 realtime write path 与 report/history/admin/replay 统一读它。
- 保留旧字段通过 compatibility readers 输出，避免一次性打断当前前端 surfaces。
- 对 sales 与 presentation 的差异使用同一 kernel 下的 scenario-aware schema，而不是两套完全不同 contract。

## Inputs

- `T01 schema`
- `S02 compiled prompt contract`

## Expected Output

- `backend/src/common/effectiveness/*`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/analytics/*`
- `backend/src/agent/capabilities/realtime_scoring.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q
