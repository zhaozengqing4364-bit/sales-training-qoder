# S02: Practice backend application seam 抽离

**Goal:** 从 `backend/src/common/api/practice.py` 中抽出可单测、可复用的 application services，同时保持当前 route contract 不变。
**Demo:** After this: `practice.py` 不再独自承载会话创建、生命周期、报告、音频审计、runtime descriptor 编排，后续任务可以沿应用层 seam 精准改动。

## Must-Haves

- practice backend 的 create/lifecycle/report/audio/runtime-descriptor 编排从 route 文件中下沉到命名清晰的 service/application seam。
- focused backend contract/integration tests 仍沿现有 API surface 通过。
- route 文件保留输入校验和 response composition，而不是继续累积业务逻辑。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 结束后，practice backend 的创建/生命周期/报告/音频/runtime descriptor 会有明确应用层 seam；S03 前端域拆分和 M021 evidence kernel 统一可以直接复用这些 seams。

## Verification

- practice 失败可以先定位 route、application service、read model、storage/signing 中哪一层出了问题，而不是只剩一个 mega route 文件。

## Tasks

- [ ] **T01: 划分 practice backend 的应用层责任面** `est:50m`
  - 沿 `backend/src/common/api/practice.py` 盘点当前真实 responsibility clusters：session create+policy freeze、lifecycle、report/read model、audio audit/signing、runtime descriptor。
- 在 `backend/src/common` 下设计最小 application/service module 边界，避免新造第二套 route family。
- 先补一组 focused tests 或 inventory assertions，锁住现有 outward contract。
  - Files: `backend/src/common/api/practice.py`, `backend/src/common`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_session_lifecycle_api.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_session_lifecycle_api.py -x -q

- [ ] **T02: 抽出 session create/lifecycle/report 应用服务** `est:2h`
  - 先抽 `create session + voice_policy_snapshot/runtime descriptor` 与 `lifecycle/report/read model` 两组 service，保持现有 response schema 和权限边界不变。
- 对 `audio_audit` / OSS signing / retry focus 等高耦合 helper 采用窄 service/assembler seam，而不是继续堆回 route。
- 保证 route 层只负责 auth、request parsing、response shape、HTTP code。
  - Files: `backend/src/common/api/practice.py`, `backend/src/common/services`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/oss/signing.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q

- [ ] **T03: 固定 extracted seam 的 proof 与下游消费规则** `est:40m`
  - 把 route-level focused tests、architecture scan 和 milestone context 更新到新的 service seams。
- 确认 admin/history/replay 仍通过 SessionEvidenceService 和现有 route family 消费，而不是被抽层后绕开 canonical read model。
- 写清 downstream consumption：S03/M021 应该接哪个 service，而不是再回 `practice.py` 拼装。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_practice_evidence_flow.py`
  - Verify: rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py

## Files Likely Touched

- backend/src/common/api/practice.py
- backend/src/common
- backend/tests/contract/test_practice_evidence_contract.py
- backend/tests/integration/test_session_lifecycle_api.py
- backend/src/common/services
- backend/src/common/conversation/session_evidence.py
- backend/src/common/oss/signing.py
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/tests/integration/test_practice_evidence_flow.py
