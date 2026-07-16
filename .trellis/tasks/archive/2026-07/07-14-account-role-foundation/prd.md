# 账号与角色基础

## Goal

修复单账号创建与登录契约，建立公司邮箱登录、一次性临时密码、首次强制改密和统一销售组长角色，为批量开户提供安全权威入口。

## Scope

* 统一 `name/email/role` DTO，移除 `username/display_name` 歧义。
* 邮箱 trim + lowercase 及大小写唯一约束 dry-run。
* 创建账号时正确保存密码哈希；实现 temporary/active/reset_required 密码状态和 72 小时可配置有效期。
* 临时密码只签发限权改密凭证，完成改密后才能进入业务页面。
* 统一 `training_manager` 为销售组长规范角色，修复创建、导航和权限映射。
* 登录限流、安全日志、停用和临时密码重置。

## Acceptance Criteria

* [x] 真实前后端创建契约通过，不再出现缺少 `username`。
* [x] 新账号可用临时密码认证但不能访问业务 API，改密后旧密码立即失效。
* [x] 邮箱大小写变体不能重复创建，登录和重置结果一致。
* [x] 明文密码不进入数据库、日志或审计。
* [x] `training_manager` 可被平台管理员创建并获得一致的只读组长入口。

## Dependency

Parent: `../07-14-account-team-lead/prd.md`
