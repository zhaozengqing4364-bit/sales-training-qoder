---
id: T02
parent: S02
milestone: M014
key_files:
  - backend/src/common/services/password_reset.py
  - backend/src/common/db/models.py
  - backend/src/common/auth/api.py
  - backend/src/common/rate_limit/api_limiter.py
  - backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py
  - backend/tests/integration/test_auth_login_api.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - 将 password reset lifecycle 明确拆分为 consumed（`used_at`）与 invalidated（`invalidated_at` + `invalidation_reason`），避免旧 token supersede 时继续伪装成“已消费”。
  - 保持 `ConsoleEmailService` 作为默认 delivery seam，但把发送结果持久化为 `delivery_status` / `delivery_attempted_at` / `delivery_error`，让 forgot-password 在投递失败时仍返回防枚举成功响应，同时保留可观测证据。
  - 把限流策略常量提升到 password reset seam，并修复全局 `rate_limit` 装饰器对 `JSONResponse` 不回填 `X-RateLimit-*` 头的问题，确保 focused auth tests 和运行时诊断看到一致表面。
duration: 
verification_result: passed
completed_at: 2026-04-11T14:34:02.597Z
blocker_discovered: false
---

# T02: Formalized password-reset lifecycle and delivery seams with explicit invalidation state, resilient delivery fallback, and auth-focused proof.

**Formalized password-reset lifecycle and delivery seams with explicit invalidation state, resilient delivery fallback, and auth-focused proof.**

## What Happened

我先把计划要求翻译成红测，直接在 `backend/tests/integration/test_auth_login_api.py` 增补了三类 auth-focused 证明：1）重复申请 reset 时旧 token 不能再被伪装成已消费；2）forgot-password 成功响应必须带 `X-RateLimit-*` 头；3）邮件投递失败时 forgot-password 仍要保持防枚举成功表面。红测先后暴露出两个事实：一是这组集成测试需要像现有 reset suite 一样预注册 `agent.models` 才能让 sqlite metadata 建表成功；二是现状确实存在正式 seam 缺口——旧 token 被写进 `used_at`、`JSONResponse` 丢失限流头、控制台邮件一旦抛错就把 forgot-password 打成 500。随后我在 `backend/src/common/services/password_reset.py` 正式化了 reset lifecycle 和 delivery seam：增加 `PASSWORD_RESET_RATE_LIMIT_*` 常量与 `build_password_reset_email_service()`；发起重置时把旧未消费 token 标记为 `invalidated_at + invalidation_reason='superseded'`，而不是继续复用 `used_at`；新增投递后续处理，在 email transport 成功时写入 `delivery_status='sent'`，失败时写入 `delivery_status='failed'`、`delivery_attempted_at`、`delivery_error` 并记录结构化日志，但 API 仍返回通用成功文案；reset 时若 token 已过期，会把该行持久化标记为 `invalidation_reason='expired'` 后再拒绝，保留可回查的生命周期痕迹。为让这些状态成为正式 schema contract，我在 `backend/src/common/db/models.py` 扩展了 `PasswordResetToken` 模型，并新增 Alembic migration `backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py`。同时我在 `backend/src/common/rate_limit/api_limiter.py` 修复了装饰器只给 dict 响应附加限流头的问题，让返回 `JSONResponse` 的 forgot-password 也能暴露 `X-RateLimit-*`。最后，我把新的 seam 证明补进 `backend/tests/integration/test_auth_login_api.py`，覆盖 supersede、投递失败降级、过期 token 拒绝与限流头表面，并把这个 gotcha 回写到 `.gsd/KNOWLEDGE.md`，另用 GSD 决策记录了 password-reset lifecycle/delivery 的正式表示方式（D176）。

## Verification

我先运行新增的 focused auth 红测子集，确认当前实现会因为三类 seam 缺口而失败：旧 token 被标记成 `used_at`、forgot-password 成功响应没有 `X-RateLimit-*` 头、控制台邮件 transport 抛错时 forgot-password 会直接变成 500。实现完成后，任务合同中的 backend auth focused 验证命令 `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` 全量通过，新增 proof 确认了 superseded/expired token 生命周期、delivery failure 持久化和 rate-limit 头表面；我又补跑了现有 `backend/tests/integration/test_password_reset_api.py -x -q`，确认原 forgot/reset suite 没有因 lifecycle 正式化而回归。最后用 `py_compile` 校验了改动过的 auth/service/model/rate-limit/migration/test 文件，确认未留下未执行路径上的语法问题。按照 slice 级验证要求，backend auth focused proof 已满足，profile 页面行为与语速偏好持久化的 slice 级证明留待 T03 完成。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q` | 0 | ✅ pass | 4588ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q` | 0 | ✅ pass | 4049ms |
| 3 | `backend/venv/bin/python -m py_compile backend/src/common/services/password_reset.py backend/src/common/db/models.py backend/src/common/auth/api.py backend/src/common/rate_limit/api_limiter.py backend/tests/integration/test_auth_login_api.py backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py` | 0 | ✅ pass | 74ms |

## Deviations

本地真实基线与计划快照有一处小偏差：`026_password_reset_tokens` migration 与独立的 `backend/tests/integration/test_password_reset_api.py` 已经存在，所以我没有重做 reset 核心持久化，而是在此基础上新增 `027_password_reset_lifecycle_delivery`，把 lifecycle/delivery 语义正式化，并把 auth-focused proof 补进了计划指定的 `test_auth_login_api.py`。

## Known Issues

默认邮件投递仍然是 `ConsoleEmailService`，只把 reset link 打到控制台；这次任务把它正式化成可替换且有持久化状态的 seam，但没有接入真实外部邮件平台。Slice 级的 profile 修改密码入口闭环与语速偏好持久化仍待 T03 完成。

## Files Created/Modified

- `backend/src/common/services/password_reset.py`
- `backend/src/common/db/models.py`
- `backend/src/common/auth/api.py`
- `backend/src/common/rate_limit/api_limiter.py`
- `backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py`
- `backend/tests/integration/test_auth_login_api.py`
- `.gsd/KNOWLEDGE.md`
