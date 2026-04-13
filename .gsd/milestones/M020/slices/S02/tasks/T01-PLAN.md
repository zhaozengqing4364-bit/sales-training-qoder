---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T01: 建立日志暴露 allowlist/denylist

- 盘点 `StructuredLogger`、`system_logs` API、admin logs page 当前暴露字段和脱敏逻辑。
- 建一份 allowlist/denylist：哪些字段可给 support/admin 看，哪些只能保留在 backend 内部。
- 把已有 inventory 与当前 UI/API 真正连起来，避免只在 logger 层修一半。

## Inputs

- `current logger/system log code`
- `M016 inventories`

## Expected Output

- `backend/src/common/monitoring/logger.py`
- `backend/src/admin/api/system_logs.py`
- `web/src/app/admin/logs/page.tsx`

## Verification

rg -n "token|password|cookie|email|user_identifier|ip_address|details" backend/src/common/monitoring backend/src/admin/api web/src/app/admin/logs/page.tsx
