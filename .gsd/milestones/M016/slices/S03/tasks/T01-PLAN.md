---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 建立 admin 权限矩阵与敏感日志出口清单

Why: 先建立权限矩阵和敏感日志出口清单，才能避免 S03 变成盲扫 backend 的长期审计工程。

Do:
1. 建立 admin route permission matrix，列出接口、角色、拒绝路径和当前证据。
2. 扫描 logger/middleware/helper 中可能输出 token/password/cookie/email 的高风险点。
3. 标记最先处理的一组高风险 surface。

Done when: 后续修复有明确高风险目标，不需要继续扩大扫描范围。

## Inputs

- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`
- `backend/src/common/auth/*`

## Expected Output

- `backend/src/admin/api/*`
- `backend/src/common/monitoring/*`
- `backend/src/common/auth/*`

## Verification

rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth

## Observability Impact

形成 admin 权限矩阵与敏感日志出口 inventory。
