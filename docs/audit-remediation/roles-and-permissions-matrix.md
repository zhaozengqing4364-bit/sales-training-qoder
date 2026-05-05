# Roles And Permissions Matrix

Generated: `2026-05-06`

## Scope

This matrix defines the minimum target permissions for five admin-facing roles:

- 系统管理员
- 教研/内容管理员
- 运营
- 支持
- 只读审计

Current persisted user roles are still constrained by `users.role IN ('user', 'admin', 'support')`. Therefore this document separates implemented compatibility from target-state roles. The existing `admin` role remains a compatibility superuser and retains every permission listed below.

## Permission Keys

| Permission key | Purpose | Current status | Evidence |
| --- | --- | --- | --- |
| `release_verification.manage` | Create release candidates, update checks, run verification, make decisions | Implemented for `admin` | `backend/src/admin/api/permissions.py`, `backend/src/admin/api/release_verification.py` |
| `business_rule.publish` | Publish, rollback, disable, or delete governed business-rule configs | Implemented for `admin` | `backend/src/admin/api/permissions.py`, `backend/src/admin/api/business_rules.py` |
| `admin_settings.manage` | Manage general/security/notification settings drafts, preview, publish, rollback, and audit | Implemented for `admin` | `backend/src/admin/api/settings.py` |
| `scoring_ruleset.manage` | Manage scoring rulesets, dry-run, publish, rollback, and audit | Implemented for `admin` | `backend/src/admin/api/permissions.py`, `backend/src/admin/api/scoring_rulesets.py` |
| `system_logs.read` | Read audit logs with redaction policy | Implemented for `admin`; support visibility remains route-specific | `backend/src/admin/api/system_logs.py`, `backend/src/admin/api/security_inventory.py` |
| `support_runtime.read` | Read support runtime diagnostics | Implemented for `admin` and `support` | `backend/src/router_registry.py` |

## Minimum Target Matrix

| Capability | 系统管理员 | 教研/内容管理员 | 运营 | 支持 | 只读审计 | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Release verification management | allow | deny | deny | deny | read-only target | Admin implemented; read-only auditor target not persisted |
| Business-rule publish/rollback | allow | allow | allow limited growth/recommendation target | deny | read-only target | Admin implemented; narrowed roles documented but not persisted |
| Scoring ruleset publish/rollback/dry-run | allow | allow | deny | deny | read-only target | Admin implemented; content role target not persisted |
| Admin settings general/security/notifications | allow | deny | deny | deny | read-only target | Admin implemented |
| Model config CRUD/test/default/delete | allow | deny | deny | deny | read-only target | Existing admin API implemented |
| User management and role changes | allow | deny | deny | deny | read-only target | Existing admin API implemented |
| System logs and audit evidence | allow | deny | deny | support redacted view target | allow read-only target | Admin implemented; support/read-only split partly pending |
| Support runtime diagnostics | allow | deny | deny | allow redacted | allow read-only target | Admin/support implemented for runtime diagnostics |
| Governance matrix read | allow | allow target | allow target | allow target | allow target | Admin implemented; non-admin target pending role migration |

## Implementation Notes

- `backend/src/admin/api/permissions.py` provides named permission checks without widening the persisted role constraint. This keeps current login and authorization behavior compatible.
- `admin` maps to all high-risk permissions.
- `content_admin`, `operations`, and `readonly_auditor` are target-state roles only until a database migration, admin user UI, tests, and rollout plan widen `users.role`.
- `support` exists today but should remain read-oriented and redacted unless an endpoint explicitly grants additional support access.

## Backlog

| Backlog item | Reason | Required artifacts |
| --- | --- | --- |
| Widen persisted role enum | Database currently accepts only `user`, `admin`, `support` | Alembic migration, admin user edit tests, rollback plan |
| Add read-only auditor APIs | Current admin APIs usually require full admin | Route-level read-only dependencies, contract tests |
| Scope business-rule publish by domain | Operations should not publish every rule family | Domain-aware permission helper, API tests |
| Expose permission matrix in user management | Admins need visibility before assigning future roles | UI update, integration tests |
| Add support-safe governance read surface | Support should view diagnostics without secrets or mutation authority | Redaction policy, positive/negative RBAC tests |
