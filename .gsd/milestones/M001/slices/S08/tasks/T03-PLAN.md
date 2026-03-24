---
estimated_steps: 4
estimated_files: 4
skills_used:
  - safe-grow
  - frontend-audit
  - agent-browser
  - assess
  - verification-before-completion
---

# T03: 复用既有 UAT 路径完成桌面端发布波次验收并落盘 S08 证据

**Slice:** S08 — 桌面端发布验收与可观测性收口
**Milestone:** M001

## Description

S08 不是“把 support/runtime 做漂亮”就结束的 slice，它是 M001 的 final-assembly gate。这个任务要把已经在 S01、S03/S05、S06、S07 分别证明过的能力重新按发布波次串起来，并要求 support/runtime 对这些真实 failure mode 给出一致的 blocking/warning 映射。执行者需要在真实本地 stack 上完成 fresh proof，而不是照搬旧 summary：sales runtime reconnect/end-failure、canonical sales report、主管 `/admin/users/{id}`、PPT report happy/degraded、support runtime release health 五波都要重跑，并把 preflight、evidence、问题与结论写进 `S08-UAT.md`。

## Steps

1. 先基于 `.gsd/milestones/M001/slices/S01/S01-UAT.md`、`.gsd/milestones/M001/slices/S06/S06-UAT.md`、`.gsd/milestones/M001/slices/S07/S07-UAT.md` 编写 `.gsd/milestones/M001/slices/S08/S08-UAT.md`，明确五波顺序、前置约束与每波预期：`alembic upgrade head`、frontend/backend `localhost` 对齐、sales websocket 若报 SOCKS 依赖就先补 `python-socks`、presentation 禁用 websocket `type:"text"` shortcut。
2. 跑 slice-close 自动化验证：backend support/runtime suites、knowledge-check regression、S01 runtime suites、S03/S05 canonical report suites、S06 admin progress suites、S07 presentation suites，以及 web 的 lifecycle/report/admin/support-runtime focused suites。
3. 在本地 stack 上按五波执行 live/browser proof：sales runtime reconnect/end-failure → canonical sales report（含 optional enhancement degraded 只算 warning）→ `/admin/users/{id}` → PPT report happy/degraded → `/support/runtime`；每波都记录 Expected/Actual、关键 session/user IDs、console/network/backend diagnostics。
4. 把 fresh 结果、blockers、warnings 与最终发布结论写入 `S08-UAT.md`，明确 support/runtime 上看到的 blocking/warning 是否与真实路径一致，以及如果不一致该先追哪条 inspection surface。

## Must-Haves

- [ ] `S08-UAT.md` 必须是 fresh 波次验收记录，不能只复制旧 slice summary 或旧 UAT 文本。
- [ ] 五波 live proof 必须全部覆盖：sales runtime、canonical sales report、supervisor trend、PPT report、support runtime。
- [ ] 文档必须显式记录 preflight gotchas：`alembic upgrade head`、`localhost` host alignment、`python-socks`、presentation 真实 audio/page_change 路径。
- [ ] 最终结论必须区分 blocking 与 warning，并指出 support/runtime 是否正确反映了这些结论；如果没有，必须把偏差写成 blocker，而不是默认通过。

## Verification

- `cd backend && venv/bin/alembic upgrade head`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_support_runtime_service.py tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_knowledge_flow.py -k knowledge_check_distinguishes_runtime_statuses`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'`
- `test -s .gsd/milestones/M001/slices/S08/S08-UAT.md && rg -n "alembic upgrade head|python-socks|support/runtime|admin/users|practice/.+/report|localhost" .gsd/milestones/M001/slices/S08/S08-UAT.md`

## Inputs

- `.gsd/milestones/M001/slices/S01/S01-UAT.md` — sales runtime reconnect/end-failure 的已证实 live recipe。
- `.gsd/milestones/M001/slices/S06/S06-UAT.md` — supervisor `/admin/users/{id}` 成功/空/错误态的已证实 recipe。
- `.gsd/milestones/M001/slices/S07/S07-UAT.md` — PPT happy/degraded report 与 localhost/audio/page_change 约束。
- `backend/src/support/api/runtime_status.py` — T01 输出的 support runtime anomaly contract，T03 要用它验证 blocking/warning 是否映射正确。
- `web/src/app/(dashboard)/support/runtime/page.tsx` — T02 输出的 support runtime 发布健康页，T03 要用它完成最终 browser wave。

## Expected Output

- `.gsd/milestones/M001/slices/S08/S08-UAT.md` — fresh 五波发布验收脚本、执行证据与最终 blocking/warning 结论。
