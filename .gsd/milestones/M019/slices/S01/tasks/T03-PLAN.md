---
estimated_steps: 3
estimated_files: 3
skills_used: []
---

# T03: 把 authority 结果写回文档与验证入口

- 更新 runbook / setup / architecture scan，让后续执行模型能直接分辨什么时候跑 Alembic、什么时候跑 bootstrap、什么时候不该让 startup 自动补洞。
- 为 M019 后续 slices 写下可复用的 repo-root 验证命令。
- 确认 `.github/workflows` 与此 authority line 不冲突。

## Inputs

- `T01/T02 结果`
- `.github/workflows/nfr-performance-check.yml`

## Expected Output

- `docs/backup-recovery-runbook.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.github/workflows/*`

## Verification

rg -n "alembic upgrade head|bootstrap|init_db|migration" docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .github/workflows
