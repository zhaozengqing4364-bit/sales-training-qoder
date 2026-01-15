# Implementation Plan: Frontend-Backend Integration

## Overview

本计划实现前后端完整对接，采用"后端补齐 API + 前端转换层"策略。后端新增缺失的 API 端点，前端创建 transforms 层处理数据转换。

**技术栈**: Python 3.11 + FastAPI + SQLAlchemy 2.0 + Pydantic v2 (后端) / TypeScript + Next.js (前端)

## Tasks

- [x] 1. 后端用户相关 API
  - [x] 1.1 实现 `GET /users/me` 用户信息接口
    - 创建 `backend/src/common/api/users.py`
    - 返回当前用户的 `id`, `display_name`, `avatar_url`, `role`, `department`, `settings`
    - 使用 `get_current_user` 依赖获取当前用户
    - _Requirements: 1.1, 1.2_
  - [x] 1.2 实现 `POST /auth/login` 登录接口
    - 在 `backend/src/common/auth/api.py` 添加登录端点
    - 接收 `email`, `password`，返回 `token` 和 `user` 对象
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 1.3 实现 `POST /auth/logout` 登出接口
    - 清除服务端 token 状态（如有）
    - _Requirements: 1.2_

- [x] 2. 后端仪表盘 API
  - [x] 2.1 实现 `GET /dashboard/stats` 统计接口
    - 创建 `backend/src/common/api/dashboard.py`
    - 计算 `weekly_activity`: `total_duration_minutes`, `session_count`, `trend_percentage`, `trend_direction`
    - 计算 `last_session`: `score`, `percentile`, `trend`
    - 查询当前用户本周和上周的练习数据进行对比
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 2.2 实现 `GET /recommendations/latest` 推荐接口
    - 基于用户最近练习数据生成推荐
    - 返回 `title`, `reason`, `action_label`, `target_path`
    - _Requirements: 2.4, 2.5_

- [x] 3. 后端训练相关 API
  - [x] 3.1 实现 `GET /training-categories` 训练大类接口
    - 创建 `backend/src/common/api/training.py`
    - 返回训练分类列表：销售、演讲、客服
    - 包含 `id`, `title`, `description`, `icon_key`, `color_theme`, `agent_count`, `tags`, `status`
    - _Requirements: 3.1_
  - [x] 3.2 实现 `GET /sessions` 历史记录接口
    - 支持 `limit`, `page`, `page_size`, `sort` 参数
    - 返回 `{ total, items: [{ id, title, agent_type, start_time, duration_seconds, score }] }`
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. 后端管理 API
  - [x] 4.1 实现 `GET /admin/users` 用户列表接口
    - 创建 `backend/src/admin/api/users.py`
    - 支持 `page`, `page_size`, `search`, `status`, `role` 参数
    - 返回分页用户列表
    - _Requirements: 4.1, 4.2, 4.3_
  - [x] 4.2 实现 `DELETE /admin/users/{id}` 删除用户接口
    - 软删除或硬删除用户
    - _Requirements: 4.4_
  - [x] 4.3 添加 `/admin/knowledge-bases` 路径别名
    - 在 `backend/src/main.py` 添加路由别名指向现有 `/admin/knowledge`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x] 4.4 实现 `GET /admin/training-records` 训练记录接口
    - 创建 `backend/src/admin/api/training_records.py`
    - 返回所有用户的训练记录（管理员视图）
    - 支持分页和搜索
    - _Requirements: 6.1, 6.2_
  - [x] 4.5 实现 `DELETE /admin/training-records/{id}` 删除记录接口
    - _Requirements: 6.3_
  - [x] 4.6 实现 `GET /admin/system-logs` 系统日志接口
    - 创建 `backend/src/admin/api/system_logs.py`
    - 添加 SystemLog 模型到 `backend/src/common/db/models.py`
    - 返回 `id`, `action`, `user_identifier`, `ip_address`, `status`, `created_at`
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 5. 后端配置调整
  - [x] 5.1 更新 CORS 配置支持 localhost:3000
    - 修改 `backend/src/main.py` 的 CORS_ORIGINS
    - _Requirements: 8.1, 8.2_
  - [x] 5.2 注册新路由到 main.py
    - 导入并注册 users, dashboard, training, admin 路由
    - _Requirements: 2.1, 3.1, 4.1_

- [x] 6. Checkpoint - 后端 API 完成
  - 运行后端测试确保所有新 API 正常工作
  - 使用 curl 或 httpie 手动测试各端点

- [x] 7. 前端数据转换层
  - [x] 7.1 创建 `web/src/lib/api/transforms.ts`
    - 实现 `transformDashboardStats()` 转换仪表盘数据
    - 实现 `transformSession()` 转换会话数据，计算 `duration_seconds` 和 `overall_score`
    - 实现 `transformAgent()` 确保 `ui_metadata` 存在
    - 实现 `formatDuration()` 和 `formatDate()` 格式化函数
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  - [x] 7.2 编写 transforms 单元测试
    - 测试各转换函数处理正常数据
    - 测试 null/undefined 值的处理
    - **Property 7: Transform session preserves data**
    - **Property 8: Transform handles missing ui_metadata**
    - **Property 9: Transform handles null values**
    - **Validates: Requirements 10.2, 10.4, 10.6**

- [x] 8. 前端 API 客户端调整
  - [x] 8.1 更新 `web/src/lib/api/client.ts`
    - 确保 `API_MODE` 设置为 "real"
    - 导入并使用 transforms 函数
    - 更新各 API 方法使用转换层
    - _Requirements: 9.1, 9.2, 9.3_
  - [x] 8.2 更新 `web/.env.local` 配置
    - 确保 `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`
    - _Requirements: 9.2_

- [x] 9. Final Checkpoint - 集成测试
  - 启动后端服务 `cd backend && python -m uvicorn src.main:app --reload`
  - 启动前端服务 `cd web && npm run dev`
  - 测试登录流程
  - 测试仪表盘数据加载
  - 测试训练大厅页面
  - 测试历史记录页面

## Notes

- 所有任务均为必须完成
- 后端遵循现有架构模式：FastAPI + SQLAlchemy 2.0 + Pydantic v2
- 所有 API 响应使用统一格式 `{ success, data, trace_id }`
- 前端 transforms 层负责数据格式转换，保持 UI 组件简洁
