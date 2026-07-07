# PRD：修复开发者登录管理员角色并发布新人训练路径

## 背景

当前开发者登录后是普通用户角色，无法进入管理后台；同时新人训练路径没有发布 active revision，学员端 `/sales-trainer` 看不到任何资料。这两个问题串联：普通用户进不了 `/admin/sales-trainer/paths` 发布路径，导致学员端永远空状态。

PPT 演练和商务礼仪代码均完整保留，未丢失。商务礼仪被收编到新人训练路径体系下，依赖 active revision 发布；PPT 演练走独立路径不受影响。

## 真实用户与任务

- **用户**：开发者（本地 dev 环境）/ 培训负责人
- **任务**：开发者登录后能进入管理后台发布训练路径，学员端能看到训练资料并开始学习

## 成功标准

1. 开发者登录（`/api/v1/auth/dev-login`）返回的 user.role 为 `admin`
2. 已存在的 dev 用户（`dev@example.com`）再次登录时 role 被补齐为 `admin`
3. 管理后台 `/admin/sales-trainer/paths` 能发布新人训练路径 active revision
4. 学员端 `/sales-trainer` 能看到已发布的训练模块
5. PPT 演练 `/training/presentation` 不受影响
6. 商务礼仪子模块在路径发布后可见

## 改动范围

### 后端

1. `backend/src/common/auth/service.py` `get_dev_user()`：
   - 新建 dev 用户时设置 `role="admin"`
   - 已存在 dev 用户若 role 为空或为 `user`，补齐为 `admin`（仅 dev 环境）
2. 回归测试：`backend/tests/unit/` 新增或补充 `get_dev_user` 角色断言

### 数据/运营

3. 通过管理后台或直接 SQL 将现有 `dev@example.com` 的 role 升为 admin（如代码改动后重新登录仍不生效，需手动修一次旧数据）

### 前端

4. 无代码改动（前端逻辑正确，role 来自后端）

## 风险等级

P1（涉及权限与角色）。但仅影响 dev 环境的 dev fallback 账号，生产环境 `is_dev_login_enabled()` 返回 false，不会被触发。

## 安全底线

- `get_dev_user()` 仅在 `_current_environment() == "development"` 时被调用，生产环境不可达
- 不修改 `is_dev_login_enabled()` 的环境判断逻辑
- 不影响企业微信 SSO 登录链路

## 验证矩阵

| 场景 | 预期 |
|------|------|
| dev 环境首次开发者登录 | role=admin |
| dev 环境已存在 dev 用户登录 | role 被补齐为 admin |
| 生产环境调用 dev-login | 403 DEV_LOGIN_DISABLED |
| 学员端访问 /sales-trainer（路径已发布） | 显示训练模块 |
| 学员端访问 /sales-trainer（路径未发布） | 显示「当前训练路径还没有发布完成」 |
| PPT 演练 /training/presentation | 正常可用 |

## 回滚

- 回退 `get_dev_user()` 的 role 赋值改动
- 数据库 `UPDATE users SET role='user' WHERE email='dev@example.com'`

## 不做

- 不改企业微信 SSO
- 不改前端 sidebar / login 页面
- 不改 admin/users API
- 不重构新人训练路径发布流程
