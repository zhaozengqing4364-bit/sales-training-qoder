---
estimated_steps: 3
estimated_files: 3
skills_used: []
---

# T03: 固定 extracted seam 的 proof 与下游消费规则

- 把 route-level focused tests、architecture scan 和 milestone context 更新到新的 service seams。
- 确认 admin/history/replay 仍通过 SessionEvidenceService 和现有 route family 消费，而不是被抽层后绕开 canonical read model。
- 写清 downstream consumption：S03/M021 应该接哪个 service，而不是再回 `practice.py` 拼装。

## Inputs

- `T01/T02 结果`
- `current report/replay/history authority docs`

## Expected Output

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`

## Verification

rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py
