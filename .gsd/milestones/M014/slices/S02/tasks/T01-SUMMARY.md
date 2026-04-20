---
id: T01
parent: S02
milestone: M014
key_files:
  - .gsd/KNOWLEDGE.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - 将 M014/S02 后续工作基线固定为“保留现有 PasswordResetService + PasswordResetToken 后端 authority seam，不重做 reset 核心持久化；把改动聚焦到邮件投递 seam、profile 密码体验闭环和语速偏好真实持久化边界”。
duration: 
verification_result: passed
completed_at: 2026-04-11T14:19:44.738Z
blocker_discovered: false
---

# T01: 盘清了 auth/profile 真实现状，并把 forgot/reset 已正式化与 profile/语速偏好剩余缺口固化进知识库

**盘清了 auth/profile 真实现状，并把 forgot/reset 已正式化与 profile/语速偏好剩余缺口固化进知识库**

## What Happened

我按任务计划逐一核对了 `web/src/app/(auth)/*`、`web/src/app/(dashboard)/profile/page.tsx`、`backend/src/common/auth/api.py`、`backend/src/common/auth/service.py`，并补读了支撑 seam：`web/src/hooks/use-voice-speed-preference.ts`、`web/src/lib/api/client.ts`、`backend/src/common/services/password_reset.py`、`backend/src/common/db/models.py` 以及现有 focused tests。结论是：1）learner 侧 forgot/reset 前端页面已经存在且直接调用正式 `/auth/forgot-password` 与 `/auth/reset-password` API，reset 页面同时支持 query token 与手工粘贴 token；2）backend forgot/reset 不是过渡 stub，而是已经围绕 `PasswordResetService` + `PasswordResetToken` 落了真实持久化：token 以 SHA-256 hash 入库、30 分钟过期、申请新 token 时会失效旧未消费 token、消费后写入 `user.hashed_password` 并标记 `used_at`，登录也会优先校验这个重置后的哈希密码；3）真正仍属过渡/开发态的部分是邮件投递，默认 `ConsoleEmailService` 只把 `/reset-password?token=...` 打到控制台，本地恢复路径仍依赖这个 mock delivery seam；4）profile 页的“修改密码”并不是已登录 change-password flow，而是一个诚实的 `/forgot-password` Link handoff；5）语速偏好完全走 `useVoiceSpeedPreference()` 的 `localStorage` seam，profile 改 select 只会写 `voice_speed_preference` 本地键，不会 `PATCH /users/me`，刷新恢复也只靠这个 frontend-local storage；6）在本任务关注范围内没有继续使用 `window.location` 的 auth/profile 路径，但我记录了仍存在的静默容错点：profile `handleCancelEdit()` refetch 失败会静默保留草稿、`handleLogout()` 会忽略 logout API 失败后直接做前端退出、`useVoiceSpeedPreference()` 的 storage 读写失败会静默回退默认/内存值、forgot-password API 在 `SQLAlchemyError` 时仍返回通用成功文案以保持防枚举语义。为避免后续任务重复摸底，我把这些真实边界追加进了 `.gsd/KNOWLEDGE.md`，并同步更新了 `.codex/loop/state.json` 与 `.codex/loop/log.md`。

## Verification

我先运行任务计划中的 repo-root 检索命令，确认 auth 路由、profile 密码入口、语速偏好和 backend auth/reset 入口都能被直接定位；随后又对 `backend/tests` 做 focused 检索并补读 `backend/tests/integration/test_password_reset_api.py`，确认 forgot/reset 已经有独立的 integration proof，不只是 login suite。结合源码通读，已明确区分出正式能力（PasswordResetService/PasswordResetToken/token lifecycle）与仍是开发态/前端本地态的边界（ConsoleEmailService、profile Link handoff、localStorage-only voice speed）。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "forgot|reset|password|speech|rate|window.location" web/src/app/\(auth\) web/src/app/\(dashboard\)/profile backend/src/common/auth` | 0 | ✅ pass | 23ms |
| 2 | `rg -n "forgot|reset|PasswordReset|AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS|hashed_password" backend/tests -g "!**/__pycache__/**"` | 0 | ✅ pass | 12ms |

## Deviations

发现一个局部事实偏差：后续 T02 计划里更容易被拿来当 auth proof 的是 `backend/tests/integration/test_auth_login_api.py`，但本地真实 forgot/reset focused proof 已存在于 `backend/tests/integration/test_password_reset_api.py`。我没有改计划结构，只把这条差异写入 `.gsd/KNOWLEDGE.md` 和 loop 状态，供后续执行直接采用。

## Known Issues

未修复的真实缺口包括：1）password reset 邮件投递默认仍是 `ConsoleEmailService` 控制台打印，本地/开发态可恢复但不是真实邮件平台；2）profile “修改密码” 仍不是 authenticated in-profile change-password flow，而是诚实地跳去 forgot-password 流程；3）语速偏好仍只在前端 `localStorage` 持久化，没有用户级后端存储；4）若 forgot/reset 底层数据库异常，forgot-password API 仍会按防枚举设计返回通用成功文案，这对用户表面是正确的，但会让运维排查更依赖日志。

## Files Created/Modified

- `.gsd/KNOWLEDGE.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
