# Requirements Document

## Introduction

本功能实现前后端完整对接，采用"后端补齐 API + 前端微调"的策略。后端新增缺失的 API 端点，前端调整少量路径映射，一次性完成全部对接工作。

## Glossary

- **API_Client**: 前端 `web/src/lib/api/client.ts` 中的 HTTP 请求封装模块
- **Backend_API**: 后端 FastAPI 提供的 RESTful 接口，基础路径为 `/api/v1`
- **Response_Envelope**: 后端统一响应格式 `{ success, data, trace_id, error?, message? }`
- **DashboardStats**: 前端仪表盘统计数据类型
- **SessionItem**: 训练历史记录数据类型
- **AdminUser**: 管理后台用户数据类型
- **SystemLog**: 系统日志数据类型

## Requirements

### Requirement 1: 认证 API

**User Story:** As a user, I want to login to the system, so that I can access protected features.

#### Acceptance Criteria

1. WHEN a user sends POST to `/auth/login` with email and password, THE Backend_API SHALL validate credentials and return JWT token
2. WHEN login is successful, THE Backend_API SHALL return `{ token, user: { id, name, email, role } }` in data field
3. IF credentials are invalid, THEN THE Backend_API SHALL return error with status 401

### Requirement 2: 用户仪表盘 API

**User Story:** As a user, I want to see my training statistics on the dashboard, so that I can track my progress.

#### Acceptance Criteria

1. WHEN a user sends GET to `/dashboard/stats`, THE Backend_API SHALL return weekly activity statistics
2. THE response SHALL include `weekly_activity` with `total_duration_minutes`, `session_count`, `trend_percentage`, `trend_direction`
3. THE response SHALL include `last_session` with `score`, `percentile`, `trend`
4. WHEN a user sends GET to `/dashboard/recommendation`, THE Backend_API SHALL return a training recommendation
5. THE recommendation SHALL include `title`, `reason`, `action_label`, `target_path`

### Requirement 3: 训练历史 API

**User Story:** As a user, I want to view my training history, so that I can review past sessions.

#### Acceptance Criteria

1. WHEN a user sends GET to `/sessions`, THE Backend_API SHALL return list of session items
2. EACH session item SHALL include `id`, `scenario_type`, `title`, `start_time`, `duration_seconds`, `overall_score`
3. THE Backend_API SHALL support `limit` query parameter for pagination

### Requirement 4: 管理后台用户 API

**User Story:** As an admin, I want to manage users, so that I can control system access.

#### Acceptance Criteria

1. WHEN admin sends GET to `/admin/users`, THE Backend_API SHALL return paginated user list
2. THE Backend_API SHALL support `page`, `page_size`, `search`, `status`, `role` query parameters
3. EACH user SHALL include `id`, `username`, `email`, `role`, `status`, `last_active_at`
4. WHEN admin sends DELETE to `/admin/users/{id}`, THE Backend_API SHALL delete the user and return success

### Requirement 5: 管理后台知识库 API 路径对齐

**User Story:** As an admin, I want to manage knowledge bases with consistent API paths, so that the frontend can access them correctly.

#### Acceptance Criteria

1. WHEN admin sends GET to `/admin/knowledge-bases`, THE Backend_API SHALL return knowledge base list (alias to existing `/admin/knowledge`)
2. WHEN admin sends DELETE to `/admin/knowledge-bases/{id}`, THE Backend_API SHALL delete the knowledge base
3. WHEN admin sends GET to `/admin/knowledge-bases/{id}/documents`, THE Backend_API SHALL return document list
4. WHEN admin sends POST to `/admin/knowledge-bases/{id}/upload`, THE Backend_API SHALL handle file upload

### Requirement 6: 管理后台训练记录 API

**User Story:** As an admin, I want to view and manage all training records, so that I can monitor system usage.

#### Acceptance Criteria

1. WHEN admin sends GET to `/admin/training-records`, THE Backend_API SHALL return all sessions (not just current user's)
2. THE Backend_API SHALL support `page`, `page_size`, `search` query parameters
3. WHEN admin sends DELETE to `/admin/training-records/{id}`, THE Backend_API SHALL delete the session record

### Requirement 7: 系统日志 API

**User Story:** As an admin, I want to view system logs, so that I can audit system activities.

#### Acceptance Criteria

1. WHEN admin sends GET to `/admin/system-logs`, THE Backend_API SHALL return system log entries
2. THE Backend_API SHALL support `page`, `page_size`, `search` query parameters
3. EACH log entry SHALL include `id`, `action`, `user_identifier`, `ip_address`, `status`, `created_at`

### Requirement 8: CORS 配置

**User Story:** As a developer, I want the backend to accept requests from the frontend, so that cross-origin requests work.

#### Acceptance Criteria

1. WHEN frontend runs on `localhost:3000`, THE Backend_API SHALL accept requests with proper CORS headers
2. THE Backend_API SHALL allow `Authorization` header in CORS configuration

### Requirement 9: 前端 API 客户端调整

**User Story:** As a developer, I want the frontend to use correct API paths, so that it communicates with the backend correctly.

#### Acceptance Criteria

1. THE API_Client SHALL set `API_MODE` to "real" by default
2. THE API_Client SHALL read `NEXT_PUBLIC_API_URL` from environment (default: `http://localhost:8000/api/v1`)
3. WHEN calling `/auth/login`, THE API_Client SHALL use `/auth/login` path (backend will implement this)


### Requirement 10: 前端数据转换层

**User Story:** As a developer, I want a dedicated transform layer to handle data conversion, so that API and UI logic are cleanly separated.

#### Acceptance Criteria

1. THE Frontend SHALL have a `transforms.ts` module in `web/src/lib/api/` directory
2. WHEN backend returns session data, THE Transform_Layer SHALL convert `session_id` to `id`, calculate `duration_seconds` from timestamps, compute `overall_score` from dimension scores
3. WHEN backend returns dashboard stats, THE Transform_Layer SHALL map backend fields to `DashboardStats` type structure
4. WHEN backend returns agent data, THE Transform_Layer SHALL ensure `ui_metadata` exists with default values if missing
5. THE Transform_Layer SHALL handle date/time format conversion from ISO8601 to display format
6. THE Transform_Layer SHALL handle null/undefined values gracefully with sensible defaults

### Requirement 11: 后端响应格式标准化

**User Story:** As a developer, I want consistent response formats from all backend APIs, so that the frontend can process them uniformly.

#### Acceptance Criteria

1. ALL backend APIs SHALL return `{ success: true, data: T, trace_id: string }` for successful responses
2. ALL backend APIs SHALL return `{ success: false, error: string, message: string, trace_id: string }` for error responses
3. ALL list APIs SHALL support pagination with `page`, `page_size` parameters and return `{ items: T[], total: number, page: number, page_size: number, has_more: boolean }`
4. ALL timestamp fields SHALL use ISO8601 format (e.g., "2026-01-11T10:30:00Z")
5. ALL ID fields SHALL use UUID string format
