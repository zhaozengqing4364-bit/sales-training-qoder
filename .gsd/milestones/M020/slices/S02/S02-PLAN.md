# S02: Sensitive log 与 admin observability redaction 收口

**Goal:** 把 backend logger、system log route、admin logs page 收口到一致的 redaction/exposure policy。
**Demo:** After this: support/admin 能看到对排障有用但不泄密的日志与错误上下文，敏感字段不会在 logger 或 admin logs page 原样外露。

## Must-Haves

- token/password/cookie/email 等敏感字段在 logger sink、system log route、admin logs page 三层都遵守同一 policy。
- admin/support 仍能定位 trace_id、错误分类、阶段状态，而不是因为过度脱敏失去排障能力。
- focused tests 锁定允许暴露与禁止暴露的字段。

## Proof Level

- This slice proves: integration

## Integration Closure

S02 结束后，M020/M021 的 observability work 都可建立在安全可见的日志 surface 上，而不是一边加事件一边担心 UI/route 反向泄密。

## Verification

- 日志可见性与脱敏边界有统一规则，future agents 不再从 UI 或 route 误读敏感详情。

## Tasks

- [ ] **T01: 建立日志暴露 allowlist/denylist** `est:40m`
  - 盘点 `StructuredLogger`、`system_logs` API、admin logs page 当前暴露字段和脱敏逻辑。
- 建一份 allowlist/denylist：哪些字段可给 support/admin 看，哪些只能保留在 backend 内部。
- 把已有 inventory 与当前 UI/API 真正连起来，避免只在 logger 层修一半。
  - Files: `backend/src/common/monitoring/logger.py`, `backend/src/admin/api/system_logs.py`, `web/src/app/admin/logs/page.tsx`, `backend/src/admin/api/security_inventory.py`, `backend/src/common/monitoring/log_safety_inventory.py`
  - Verify: rg -n "token|password|cookie|email|user_identifier|ip_address|details" backend/src/common/monitoring backend/src/admin/api web/src/app/admin/logs/page.tsx

- [ ] **T02: 在 logger、API、UI 三层统一 redaction policy** `est:1.5h`
  - 在 logger sink、system log serialization、admin logs UI 三层统一应用 redaction policy。
- 保留 trace_id、severity、error code、phase、session_id 等排障必要字段。
- 为 admin/support 视角补 focused tests，防止未来新增字段绕过 policy。
  - Files: `backend/src/common/monitoring/logger.py`, `backend/src/admin/api/system_logs.py`, `web/src/app/admin/logs/page.tsx`, `backend/tests`, `web/src/app/admin/logs`
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"

- [ ] **T03: 把 redaction boundary 固化到 inventory 与扫描文档** `est:30m`
  - 更新 security inventory / architecture scan / support guidance，明确哪类错误详情留在 backend，哪类可安全展示给 admin/support。
- 把这套 policy 变成后续 M021 质量事件的前置约束。
  - Files: `backend/src/admin/api/security_inventory.py`, `backend/src/common/monitoring/log_safety_inventory.py`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md

## Files Likely Touched

- backend/src/common/monitoring/logger.py
- backend/src/admin/api/system_logs.py
- web/src/app/admin/logs/page.tsx
- backend/src/admin/api/security_inventory.py
- backend/src/common/monitoring/log_safety_inventory.py
- backend/tests
- web/src/app/admin/logs
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
