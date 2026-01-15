# Design Document

## Overview

本设计实现前后端完整对接，包括：
1. 后端新增 6 个 API 端点
2. 后端添加 1 个路径别名
3. 前端创建数据转换层
4. 前端 API 客户端配置调整

设计原则：
- 后端遵循现有架构模式（FastAPI + SQLAlchemy 2.0 + Pydantic v2）
- 前端保持现有结构，新增 transforms 层
- 统一响应格式，减少前端适配工作

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                    │
├─────────────────────────────────────────────────────────────┤
│  UI Components                                               │
│       ↓                                                      │
│  Hooks (useApi, useAuth)                                     │
│       ↓                                                      │
│  API Client (client.ts)  ←→  Transforms (transforms.ts)     │
│       ↓                                                      │
│  HTTP Fetch                                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓ HTTP
┌─────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                        │
├─────────────────────────────────────────────────────────────┤
│  API Routes                                                  │
│  ├── /auth/login           (NEW)                            │
│  ├── /dashboard/stats      (NEW)                            │
│  ├── /dashboard/recommendation (NEW)                        │
│  ├── /sessions             (EXISTS - /practice/history)     │
│  ├── /agents               (EXISTS)                         │
│  ├── /admin/users          (NEW)                            │
│  ├── /admin/agents         (EXISTS)                         │
│  ├── /admin/personas       (EXISTS)                         │
│  ├── /admin/knowledge-bases (ALIAS → /admin/knowledge)      │
│  ├── /admin/training-records (NEW)                          │
│  └── /admin/system-logs    (NEW)                            │
├─────────────────────────────────────────────────────────────┤
│  Services Layer                                              │
│  ├── auth_service                                           │
│  ├── dashboard_service     (NEW)                            │
│  ├── user_service          (NEW)                            │
│  └── system_log_service    (NEW)                            │
├─────────────────────────────────────────────────────────────┤
│  Database (SQLite/PostgreSQL)                                │
│  ├── User (EXISTS)                                          │
│  ├── PracticeSession (EXISTS)                               │
│  └── SystemLog (NEW)                                        │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### Backend Components

#### 1. Dashboard API (`backend/src/common/api/dashboard.py`)

```python
# New file - Dashboard endpoints for frontend

router = APIRouter()

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns:
    {
        "success": true,
        "data": {
            "weekly_activity": {
                "total_duration_minutes": int,
                "session_count": int,
                "trend_percentage": float,
                "trend_direction": "up" | "down" | "flat"
            },
            "last_session": {
                "score": float,
                "percentile": int,
                "trend": "stable" | "up" | "down"
            }
        }
    }
    """

@router.get("/dashboard/recommendation")
async def get_recommendation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns:
    {
        "success": true,
        "data": {
            "title": str,
            "reason": str,
            "action_label": str,
            "target_path": str
        }
    }
    """
```

#### 2. Auth API Enhancement (`backend/src/common/auth/api.py`)

```python
# Add to existing auth module

@router.post("/auth/login")
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Request: { "email": str, "password": str }
    Returns:
    {
        "success": true,
        "data": {
            "token": str,
            "user": { "id": str, "name": str, "email": str, "role": str }
        }
    }
    """
```

#### 3. Admin Users API (`backend/src/admin/api/users.py`)

```python
# New file - User management for admin

router = APIRouter()

@router.get("/admin/users")
async def list_users(
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    status: str | None = None,
    role: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns paginated user list with filtering
    """

@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns: { "success": true }
    """
```

#### 4. Admin Training Records API (`backend/src/admin/api/training_records.py`)

```python
# New file - Training records management

router = APIRouter()

@router.get("/admin/training-records")
async def list_training_records(
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns all sessions (admin view, not filtered by user)
    """

@router.delete("/admin/training-records/{session_id}")
async def delete_training_record(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns: { "success": true }
    """
```

#### 5. System Logs API (`backend/src/admin/api/system_logs.py`)

```python
# New file - System logs for audit

router = APIRouter()

@router.get("/admin/system-logs")
async def list_system_logs(
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Returns:
    {
        "success": true,
        "data": [
            {
                "id": str,
                "action": str,
                "user_identifier": str,
                "ip_address": str,
                "status": "success" | "failed" | "warning",
                "created_at": str (ISO8601)
            }
        ]
    }
    """
```

#### 6. SystemLog Model (`backend/src/common/db/models.py`)

```python
# Add to existing models

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    user_identifier = Column(String(255), nullable=False)  # email or "system"
    ip_address = Column(String(45), nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, warning
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Frontend Components

#### 1. Transforms Layer (`web/src/lib/api/transforms.ts`)

```typescript
// New file - Data transformation utilities

import { DashboardStats, SessionItem, Agent, AdminUser } from "./types";

/**
 * Transform backend dashboard response to frontend type
 */
export function transformDashboardStats(backendData: any): DashboardStats {
    return {
        weekly_activity: {
            total_duration_minutes: backendData.total_duration_minutes || 0,
            session_count: backendData.session_count || 0,
            trend_percentage: backendData.trend_percentage || 0,
            trend_direction: backendData.trend_direction || "flat"
        },
        last_session: {
            score: backendData.last_score || 0,
            percentile: backendData.percentile || 50,
            trend: backendData.score_trend || "stable"
        }
    };
}

/**
 * Transform backend session to frontend SessionItem
 */
export function transformSession(backendSession: any): SessionItem {
    const startTime = new Date(backendSession.start_time);
    const endTime = backendSession.end_time ? new Date(backendSession.end_time) : new Date();
    const durationSeconds = Math.floor((endTime.getTime() - startTime.getTime()) / 1000);
    
    return {
        id: backendSession.session_id,
        scenario_type: backendSession.scenario_type || "sales_bot",
        title: backendSession.title || generateSessionTitle(backendSession),
        start_time: backendSession.start_time,
        duration_seconds: durationSeconds,
        overall_score: calculateOverallScore(backendSession),
        feedback_summary: backendSession.feedback_summary
    };
}

/**
 * Calculate overall score from dimension scores
 */
export function calculateOverallScore(session: any): number {
    const logic = session.logic_score || 0;
    const accuracy = session.accuracy_score || 0;
    const completeness = session.completeness_score || 0;
    return Math.round(logic * 0.4 + accuracy * 0.3 + completeness * 0.3);
}

/**
 * Generate session title from metadata
 */
function generateSessionTitle(session: any): string {
    const type = session.scenario_type === "sales_bot" ? "销售对练" : "演讲练习";
    const persona = session.persona_name || "";
    return persona ? `${type} - ${persona}` : type;
}

/**
 * Ensure agent has ui_metadata with defaults
 */
export function transformAgent(backendAgent: any): Agent {
    return {
        ...backendAgent,
        ui_metadata: backendAgent.ui_metadata || {
            icon_key: "User",
            theme_color: "bg-slate-50 text-slate-600",
            tags: []
        }
    };
}

/**
 * Format duration for display
 */
export function formatDuration(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format date for display
 */
export function formatDate(isoString: string): string {
    const date = new Date(isoString);
    return date.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}
```

#### 2. Updated API Client (`web/src/lib/api/client.ts`)

```typescript
// Key changes to existing client.ts

// 1. Change API_MODE to "real"
const API_MODE: "mock" | "real" = "real";

// 2. Import transforms
import { transformDashboardStats, transformSession, transformAgent } from "./transforms";

// 3. Update API methods to use transforms
export const api = {
    dashboard: {
        getStats: async () => {
            const data = await client<any>("/dashboard/stats");
            return transformDashboardStats(data);
        },
        getHistory: async () => {
            const data = await client<any>("/sessions?limit=2");
            return data.sessions?.map(transformSession) || [];
        },
        // ...
    },
    // ...
};
```

## Data Models

### Backend Response Formats

#### Standard Success Response
```json
{
    "success": true,
    "data": { ... },
    "trace_id": "abc123"
}
```

#### Standard Error Response
```json
{
    "success": false,
    "error": "ERROR_CODE",
    "message": "Human readable message",
    "trace_id": "abc123"
}
```

#### Paginated List Response
```json
{
    "success": true,
    "data": {
        "items": [...],
        "total": 100,
        "page": 1,
        "page_size": 10,
        "has_more": true
    },
    "trace_id": "abc123"
}
```

### Database Schema Addition

```sql
-- New table for system logs
CREATE TABLE system_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(user_id),
    user_identifier VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    status VARCHAR(20) NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_system_logs_created_at ON system_logs(created_at DESC);
CREATE INDEX idx_system_logs_user_id ON system_logs(user_id);
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Login response structure
*For any* successful login request, the response SHALL contain `token` (non-empty string) and `user` object with `id`, `name`, `email`, `role` fields.
**Validates: Requirements 1.1, 1.2**

### Property 2: Dashboard stats response structure
*For any* dashboard stats response, it SHALL contain `weekly_activity` with numeric fields and `last_session` with score fields.
**Validates: Requirements 2.2, 2.3**

### Property 3: Session item completeness
*For any* session item returned by `/sessions` or `/admin/training-records`, it SHALL contain `id`, `scenario_type`, `title`, `start_time`, `duration_seconds`, `overall_score`.
**Validates: Requirements 3.2, 6.1**

### Property 4: Pagination limit enforcement
*For any* list API call with `limit=N` parameter, the response SHALL contain at most N items.
**Validates: Requirements 3.3, 4.2, 6.2, 7.2**

### Property 5: User item completeness
*For any* user item returned by `/admin/users`, it SHALL contain `id`, `username`, `email`, `role`, `status`, `last_active_at`.
**Validates: Requirements 4.3**

### Property 6: System log item completeness
*For any* log entry returned by `/admin/system-logs`, it SHALL contain `id`, `action`, `user_identifier`, `ip_address`, `status`, `created_at`.
**Validates: Requirements 7.3**

### Property 7: Transform session preserves data
*For any* backend session object, `transformSession()` SHALL produce a valid `SessionItem` with calculated `duration_seconds` and `overall_score`.
**Validates: Requirements 10.2**

### Property 8: Transform handles missing ui_metadata
*For any* agent object (with or without `ui_metadata`), `transformAgent()` SHALL return an agent with valid `ui_metadata` containing `icon_key`, `theme_color`, `tags`.
**Validates: Requirements 10.4**

### Property 9: Transform handles null values
*For any* input object with null/undefined fields, transform functions SHALL not throw and SHALL provide sensible defaults.
**Validates: Requirements 10.6**

### Property 10: API response envelope consistency
*For any* backend API response, it SHALL follow the envelope format with `success` boolean and either `data` (on success) or `error`/`message` (on failure).
**Validates: Requirements 11.1, 11.2**

## Error Handling

### Backend Error Handling

1. **Authentication Errors**
   - Invalid credentials → 401 Unauthorized with `{ success: false, error: "INVALID_CREDENTIALS" }`
   - Missing token → 401 Unauthorized with `{ success: false, error: "TOKEN_REQUIRED" }`
   - Expired token → 401 Unauthorized with `{ success: false, error: "TOKEN_EXPIRED" }`

2. **Authorization Errors**
   - Non-admin accessing admin endpoints → 403 Forbidden with `{ success: false, error: "ADMIN_REQUIRED" }`

3. **Resource Errors**
   - User not found → 404 Not Found with `{ success: false, error: "USER_NOT_FOUND" }`
   - Session not found → 404 Not Found with `{ success: false, error: "SESSION_NOT_FOUND" }`

4. **Validation Errors**
   - Invalid parameters → 422 Unprocessable Entity with `{ success: false, error: "VALIDATION_ERROR", message: "..." }`

### Frontend Error Handling

1. **Network Errors**
   - Connection failed → Show toast "网络连接失败，请检查网络"
   - Timeout → Show toast "请求超时，请重试"

2. **API Errors**
   - 401 → Redirect to login page
   - 403 → Show toast "权限不足"
   - 404 → Show appropriate empty state
   - 500 → Show toast "服务器错误，请稍后重试"

## Testing Strategy

### Backend Testing

1. **Unit Tests** (pytest)
   - Test each API endpoint with valid inputs
   - Test error cases (invalid credentials, missing resources)
   - Test pagination logic
   - Test query parameter filtering

2. **Integration Tests**
   - Test full authentication flow
   - Test CORS configuration
   - Test database operations

### Frontend Testing

1. **Unit Tests** (vitest)
   - Test transform functions with various inputs
   - Test null/undefined handling
   - Test date formatting

2. **Property-Based Tests** (fast-check)
   - Test transform functions preserve required fields
   - Test transform functions handle edge cases

### Test Configuration
- Backend: pytest with minimum 100 iterations for property tests
- Frontend: vitest with fast-check for property tests
- Each property test tagged with: **Feature: frontend-backend-integration, Property N: description**
