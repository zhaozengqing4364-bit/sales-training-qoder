---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 建立 admin 权限矩阵与敏感日志出口清单

建立 admin route permission matrix，按接口列出访问角色、拒绝路径和当前证据；同时扫描 logger/middleware/helper 中可能输出 token/password/cookie/email 的高风险点。

## Inputs

- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`
- `backend/src/common/auth/*`

## Expected Output

- `permission matrix`
- `redaction inventory`

## Verification

rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth

## Observability Impact

current permission / redaction risk inventory
