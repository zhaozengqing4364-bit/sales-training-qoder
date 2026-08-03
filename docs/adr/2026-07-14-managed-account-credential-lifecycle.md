# ADR: Managed account credential lifecycle

- Status: accepted
- Date: 2026-07-14

## Context

Administrator-created users previously had an inconsistent `username/display_name/name` contract and the supplied password was validated but not persisted. Login also depended on environment-wide compatibility passwords. This cannot support per-person accounts, forced first-login password replacement, or reliable credential invalidation.

## Decision

1. Company email is the login identifier and is normalized with `trim + lowercase`; the database enforces uniqueness on `lower(email)` after a conflict preflight.
2. Administrator-created accounts receive a system-generated high-entropy temporary password. Only its hash is persisted, while the plaintext is returned in the create response exactly once.
3. Credential lifecycle is stored on `User` as `credential_status`, `temporary_password_expires_at`, `password_changed_at`, and monotonic `credential_version`.
4. Temporary login issues a JWT with `scope=password_change`. Normal business dependencies reject that scope. Successful first-login replacement increments `credential_version` and issues a `scope=business` session.
5. 密码登录只接受 `User.hashed_password`。`AUTH_SHARED_PASSWORD` 与 `AUTH_USER_PASSWORDS_JSON` 的已有配置值不由初始化流程删除，但不再具有登录权威。
6. `training_manager` is the canonical persisted role for the “销售组长” product role.

## Consequences

- Password reset and first-login replacement invalidate versioned sessions without storing plaintext credentials.
- The migration must fail safely when case-insensitive email conflicts exist; operations must resolve conflicts before retrying.
- The create response is sensitive and must not be cached, logged, or re-exported server-side.
- WeCom/IAM/SSO can later bind to the same user identity without becoming the team-authorization source.

## Rollback

首发 baseline 不提供回到共享密码或无 credential claims 会话的兼容回滚。若账号流程出现故障，关闭受影响的开户入口并通过受管管理员 bootstrap/重置流程恢复；不得重新启用环境共享密码。
