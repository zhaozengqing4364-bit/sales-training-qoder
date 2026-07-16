# Implementation notes

## Completed

- 统一公司邮箱创建/登录契约，邮箱 trim + lowercase。
- 系统生成 72 小时一次性临时密码，明文仅创建/重置响应返回，数据库只存哈希。
- 临时凭证只能进入强制改密流程；改密、停用、删除、重置会使旧会话失效。
- `training_manager` 成为销售组长唯一规范角色；补齐登录限流、审计和管理端凭证交付。

## Data flow

Admin UI -> `POST /admin/users` -> normalized email and role validation -> generated temporary password -> password hash + credential state persisted -> plaintext returned once only.

Temporary login -> limited `password_change` token -> `POST /auth/change-temporary-password` -> new hash + credential version -> normal business session.

## Compatibility

- Existing accounts default to `active` credential state.
- Existing JWTs without credential-version claims remain valid until their normal expiry.
- Existing environment-password accounts retain the compatibility login path.
- Existing `support` and `admin` create/update values remain accepted; `training_manager` is added as the canonical sales-lead role.

## Deviations

- 企业邮箱域名白名单等待业务方提供域名后以配置接入，当前只校验标准邮箱格式。
- 企业微信、IAM、SSO 按定稿范围延期。
