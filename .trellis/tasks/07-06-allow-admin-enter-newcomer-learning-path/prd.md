# PRD：允许管理员进入新人训练学习路径

## 背景

当前权限模型 `SALES_TRAINER_LEARNER_ROLES = {user, learner}`，admin 角色不在学员集合里。开发者登录账号（dev@example.com，role=admin）进入 `/sales-trainer` 时被 `[NEWCOMER_LEARNER_ROLE_REQUIRED]` 挡住，看到「当前账号无权进入新人训练学习路径」。

用户诉求：Developer/Development 账号（admin）也要能查看学员端训练路径，便于开发调试和产品验收。

## 真实用户与任务

- **用户**：开发者 / 培训负责人 / 管理员
- **任务**：用 admin 账号登录后，既能进管理后台管理训练路径，也能进学员端查看训练内容（开发调试 + 产品验收）

## 成功标准

1. admin 角色访问 `/api/v1/sales-trainer/journey` 不再返回 403
2. admin 能看到与 learner 相同的训练模块列表
3. admin 在学员端的训练进度独立于 learner（按 user_id 隔离）
4. 现有 learner/user 角色行为不变
5. 现有 admin 管理后台权限不受影响
6. 不引入安全风险（admin 本就是最高权限，进入学员端不越权）

## 改动范围

### 后端

1. `backend/src/sales_trainer/permissions.py` `can_enter_sales_trainer_learning_path()`：
   - admin 角色放行进入学员端
   - 保持 `is_active` 校验
2. 回归测试：补充 admin 角色可进入学员端的测试

### 前端

3. 无代码改动（前端不校验学员角色，由后端控制）

## 风险等级

P2（普通权限调整）。admin 本就是最高权限角色，允许其进入学员端不构成越权。不改变 learner/user 的权限边界。

## 安全底线

- 仅放行 `PLATFORM_ADMIN_ROLES`（admin/super_admin），不放行 content_admin/ops 等其他管理角色
- admin 进入学员端仍按 user_id 隔离训练进度，不会看到其他学员数据
- 不影响管理后台权限校验

## 验证矩阵

| 场景 | 预期 |
|------|------|
| admin 访问 /sales-trainer/journey | 200，返回训练模块 |
| learner 访问 /sales-trainer/journey | 200，返回训练模块（行为不变） |
| 未登录访问 /sales-trainer/journey | 401 |
| admin 访问管理后台 | 正常（行为不变） |
| admin 训练进度 | 按 admin 的 user_id 独立计算 |

## 回滚

- 回退 `can_enter_sales_trainer_learning_path()` 改动

## 不做

- 不改前端 sidebar / 页面
- 不改 `SALES_TRAINER_LEARNER_ROLES` 集合本身（保持 {user, learner}）
- 不改其他管理角色（content_admin/ops）的学员端权限
- 不改 journey 内部的 viewer/learner 校验逻辑
