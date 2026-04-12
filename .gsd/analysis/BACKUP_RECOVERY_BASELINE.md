# Backup / Recovery Baseline Analysis

最后更新：2026-04-12

## 当前产物

- 可执行 runbook：`docs/backup-recovery-runbook.md`
- 事实盘点：`docs/setup/backup-recovery-current-state.md`

## 本次已复核的 repo-local 引用

- `scripts/dev-up.sh`
- `scripts/dev-stop.sh`
- `backend/src/main.py`
- `backend/scripts/repair_legacy_schema.py`
- `backend/scripts/bootstrap_auth_admin.py`
- `backend/src/common/db/session.py`
- `backend/src/common/config.py`
- `backend/src/common/storage/document.py`
- `backend/src/common/knowledge/vector_store.py`
- `backend/src/admin/api/admin.py`
- `docs/setup/auth-local.md`

## 当前基线结论

1. 当前仓库已经具备最小手工恢复链路：
   - 启停脚本：`scripts/dev-up.sh` / `scripts/dev-stop.sh`
   - 数据库 schema 对齐：`cd backend && alembic upgrade head`
   - 老库修复：`backend/scripts/repair_legacy_schema.py`
   - 管理员重建：`backend/scripts/bootstrap_auth_admin.py`
2. 当前仓库仍然没有 repo-native 的自动备份/恢复平台；runbook 只能基于标准工具（`pg_dump` / `pg_restore` / `redis-cli` / `tar`）和现有脚本写成手工操作基线。
3. 当前恢复顺序应保持为：
   - 停服务
   - 恢复 PostgreSQL
   - 对齐 Alembic / 必要时修老 schema
   - 恢复本地目录
   - 可选恢复 Redis 会话快照
   - 必要时重建管理员账号
   - 重启并执行 `/health` 验证
4. 以下仍是已知缺口，而不是已落地能力：
   - Redis 服务级恢复脚本
   - OSS 音频对象批量导出
   - 统一 RTO/RPO 与明确值班人
   - 固定季度演练记录机制

## Follow-up（不属于当前可执行基线）

- 灾难恢复演练建议已单列在 `docs/backup-recovery-runbook.md` 的 `8.1 灾难恢复演练建议（建议项，不代表已落地）`；执行时不要把该建议误写成“当前已实施流程”。
- 后续改进项已单列在 `docs/backup-recovery-runbook.md` 的 `8.2 后续改进（与当前可执行内容分开）`；未来如果真的落地脚本或流程，应先更新这些 follow-up，再把对应条目提升进当前基线。

## 后续阅读顺序

如果下一位执行者需要继续完善该主题，建议顺序为：

1. 先读 `docs/backup-recovery-runbook.md`
2. 再读 `docs/setup/backup-recovery-current-state.md`
3. 最后回到下列代码入口核对漂移：
   - `scripts/dev-up.sh`
   - `scripts/dev-stop.sh`
   - `backend/src/common/db/session.py`
   - `backend/src/common/config.py`
   - `backend/src/common/storage/document.py`
   - `backend/src/common/knowledge/vector_store.py`
   - `backend/src/common/websocket/session_state_service.py`
   - `backend/src/common/oss/signing.py`
