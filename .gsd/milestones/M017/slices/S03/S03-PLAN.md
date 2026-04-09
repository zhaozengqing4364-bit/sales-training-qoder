# S03: 文件上传 / 资源竞争 / 分布式锁风险 discovery

**Goal:** 把文件上传并发、资源竞争、分布式锁缺失这类“风险项”先转成可证据化的 discovery 结论
**Demo:** After this: presentation upload / replace 等并发风险点被列成可证据化清单，并给出下一步建议

## Tasks
- [ ] **T01: 定位 upload / resource race 风险点** — 梳理 presentation upload / replace / delete 等路径的共享资源访问点，并和现有 active-session blocker 一起看，区分已覆盖与未覆盖的竞争面。
  - Estimate: 35m
  - Files: backend/src/presentation_coach/api/presentations.py, backend/tests/contract/test_presentations.py, backend/tests/integration/test_presentation_flow.py
  - Verify: rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py
- [ ] **T02: 用 focused proof 区分真实并发问题与想象风险** — 补最小复现 proof 或测试，确认哪些路径真的会发生竞争、哪些只是 audit 猜测；输出下一步建议（如局部锁、幂等、状态约束）。
  - Estimate: 1h
  - Files: backend/tests/contract/test_presentations.py, backend/tests/integration/test_presentation_flow.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q
- [ ] **T03: 输出 upload/resource race discovery 结论** — 沉淀 discovery artifact：列出真实竞争点、共享资源冲突面、多实例锁需求候选和不建议现在做的项。
  - Estimate: 25m
  - Files: backend/src/presentation_coach/api/presentations.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q
