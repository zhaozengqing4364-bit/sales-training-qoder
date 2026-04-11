# S03: 文件上传 / 资源竞争 / 分布式锁风险 discovery

**Goal:** 把文件上传并发、资源竞争、分布式锁缺失这类“风险项”先转成可证据化的 discovery 结论。
**Demo:** presentation upload / replace 等并发风险点被列成可证据化清单，并给出下一步建议。

## Must-Haves

- presentation upload/replace/delete 的共享资源访问点被盘清。
- focused proof 能区分真实竞争问题和想象风险。
- discovery 结论明确列出下一步建议与当前不建议做的项。

## Proof Level

- This slice proves: contract

## Integration Closure

S03 在现有 presentation upload/replace/delete 链路上沉淀资源竞争 discovery 结论，为未来是否新增幂等/锁策略提供事实基线。

## Verification

- future agents 可直接从 discovery 结论与 focused presentation proofs 判断哪些 race 已证实、哪些只是 audit 猜测。

## Tasks

- [ ] **T01: 定位 upload / resource race 风险点** `est:35m`
  Why: 先沿真实 upload/replace/delete 链路识别共享资源访问点，才能把 active-session blocker 已覆盖的和未覆盖的竞争面分开。

Do:
1. 梳理 presentation upload/replace/delete 路径的共享资源访问点。
2. 对照现有 active-session blocker，区分已覆盖与未覆盖竞争面。
3. 明确最值得先证明的 race surface。

Done when: 已形成 upload/resource race 风险点列表，后续 focused proof 有明确目标。
  - Files: `backend/src/presentation_coach/api/presentations.py`, `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_flow.py`
  - Verify: rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py

- [ ] **T02: 用 focused proof 区分真实并发问题与想象风险** `est:1h`
  Why: discovery 的价值在于把“真实问题”与“audit 猜测”分开，而不是先上锁再找理由。

Do:
1. 为最可疑路径补最小复现 proof 或 focused tests。
2. 证明哪些路径真的会发生竞争，哪些只是理论风险。
3. 对真实风险提出下一步建议（局部锁、幂等、状态约束等），但不抢跑到实现。 

Done when: focused presentation proof 通过，且已有一份区分真实问题/想象风险的结论。
  - Files: `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_flow.py`, `backend/tests/integration/test_presentation_delete_permissions.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q

- [ ] **T03: 输出 upload/resource race discovery 结论** `est:25m`
  Why: 没有沉淀出的 discovery artifact，后续 agent 还会重新从 audit 文本猜 upload/resource 风险。

Do:
1. 输出 discovery 结论，列出真实竞争点、共享资源冲突面和多实例锁需求候选。
2. 明确哪些项当前不建议实现，以及原因。
3. 保持结论基于 focused proof，而不是抽象架构讨论。

Done when: 后续是否新增锁/幂等策略有一份可直接引用的 discovery 结论。
  - Files: `backend/src/presentation_coach/api/presentations.py`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q

## Files Likely Touched

- backend/src/presentation_coach/api/presentations.py
- backend/tests/contract/test_presentations.py
- backend/tests/integration/test_presentation_flow.py
- backend/tests/integration/test_presentation_delete_permissions.py
