# 为团队看板测试创建多角色 seed 账号

## Goal

团队学习看板（07-07-manager-team-learning-dashboard）代码已实现并提交，但数据库里没有 training_manager 账号，也没有同部门的 learner 账号，用户无法实测看板。本任务创建一套多角色测试账号（密码极简），让用户能登录不同角色验证看板行为。

## What I already know

- 密码登录：`/api/v1/auth/login`（http_routes.py:33），用 `verify_password`（api.py:227）校验 `User.hashed_password`
- 密码哈希：`pwd_context.hash(password)`（api.py:232，passlib pbkdf2_sha256/bcrypt）
- User 模型（common/db/models.py:109）：user_id/wechat_user_id(unique)/department/email(unique)/hashed_password/role/is_active
- admin create_user API 不设密码（无 hashed_password），创建的账号无法密码登录
- role 值域（roles.py）：admin/super_admin/support/training_lead/training_manager/content_admin/newcomer_content_admin/operations/ops/operator/sre/readonly_auditor/learner/user
- 看板权限：training_manager 可看本部门 learner；`_team_scope` 返回 training_manager 的 department
- dev 登录只创建 1 个 admin 账号（dev@example.com / department=Development），无 training_manager
- journey 数据：`_build_journey` 从 path active revision + outcomes 实时算，learner 账号存在即有 journey（未做题显示 not_started）
- seed 脚本模式：参考 `backend/scripts/seed_newcomer_training_path.py`（sys.path.insert + AsyncSessionLocal + pwd_context）

## Requirements

- R1 创建一个 seed 脚本 `backend/scripts/seed_team_dashboard_accounts.py`，幂等（重复执行不报错，已存在则更新）
- R2 创建以下账号（密码统一最简，如 `123456`）：
  - 1 个 training_manager（部门：销售一部）— 主测账号，登录看 `/team` 看板
  - 2-3 个 learner/user（部门：销售一部，同部门）— 看板能看到这些学员
  - 1 个 learner（部门：销售二部，不同部门）— 验证 training_manager 看不到跨部门学员（AC5）
  - 1 个 training_manager（无 department）— 验证空部门提示（AC8）
  - 1 个 admin（已有 dev 账号，无需新建，但可加一个密码登录的 admin 方便测）
- R3 账号 email 用"3 个单词"格式（用户要求简单），如 `manager.one@team.com`
- R4 脚本可独立运行：`cd backend && .venv/bin/python scripts/seed_team_dashboard_accounts.py`
- R5 不破坏现有 dev 账号（dev@example.com 保留 admin）
- R6 部分 learner 需有 journey 进度数据（至少 1 个有 module outcome），让看板不全是空——但这依赖 path 是否已 seed。若 path 已存在，learner 账号即有 journey（not_started）；若要更真实进度需手动做题，本任务不做（Out of Scope，账号能登录 + 看板有列表即可）

## Acceptance Criteria

- [ ] AC1 跑 seed 脚本后，能用 training_manager 账号 + 简单密码登录
- [ ] AC2 training_manager 登录后跳转 `/team`，看到本部门学员列表
- [ ] AC3 看板只显示同部门学员，不显示其他部门（AC5 验证）
- [ ] AC4 无 department 的 training_manager 登录看板显示空部门提示（AC8）
- [ ] AC5 learner 账号登录跳转 `/`（不进看板），sidebar 无「我的团队」入口
- [ ] AC6 脚本幂等：重复执行不报错、不产生重复账号

## Out of Scope

- 给 learner 制造真实 journey 进度（做题/录音）——需手动或额外脚本，账号本身能登录看板即可
- 生产环境账号（本脚本仅 dev/测试，依赖 development 环境的 DB）
- 修改密码登录 API 或权限模型

## Technical Approach

新建 `backend/scripts/seed_team_dashboard_accounts.py`：
1. 参考 `seed_newcomer_training_path.py` 的 DB 连接 + ORM 模式
2. 用 `pwd_context.hash("123456")` 生成 hashed_password
3. 定义账号清单（list of dict：email/name/department/role/wechat_user_id）
4. 幂等逻辑：按 email 查找，存在则更新 role/department/hashed_password，不存在则创建
5. wechat_user_id 用稳定的占位符（如 `seed_team_{email}`），保证 unique 且可重复执行
6. 打印创建结果（账号 + role + department + 登录密码）

## 账号清单（待确认）

倾向方案（密码统一 `123456`）：

| email | name | department | role | 用途 |
|-------|------|-----------|------|------|
| manager.one@team.com | 张经理 | 销售一部 | training_manager | 主测：看本部门学员 |
| learner.one@team.com | 学员甲 | 销售一部 | learner | 同部门学员 |
| learner.two@team.com | 学员乙 | 销售一部 | user | 同部门学员 |
| learner.three@team.com | 学员丙 | 销售二部 | learner | 跨部门（不应被看到） |
| manager.two@team.com | 李经理 | (空) | training_manager | 空部门提示 |

## Decision (ADR-lite)

**Context**：用户要"3 个单词账号 + 最简单密码"测看板，需多角色 + 跨部门 + 空部门场景。
**Decision**：建独立 seed 脚本，5 个账号覆盖主测/同部门/跨部门/空部门/learner 角色，密码统一 `123456`，幂等可重复执行。
**Consequences**：仅 dev 环境用；learner 无真实 journey 进度（看板显示 not_started 状态，足够验证功能）；要测真实进度需手动做题。
