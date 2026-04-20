---
estimated_steps: 2
estimated_files: 3
skills_used: []
---

# T03: 把 redaction boundary 固化到 inventory 与扫描文档

- 更新 security inventory / architecture scan / support guidance，明确哪类错误详情留在 backend，哪类可安全展示给 admin/support。
- 把这套 policy 变成后续 M021 质量事件的前置约束。

## Inputs

- `T02 结果`
- `M021 planned quality events`

## Expected Output

- `backend/src/admin/api/security_inventory.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
