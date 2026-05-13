# 分析与排行榜 API 契约

> 状态: ✅ 已实现（2026-02-22 更新）
>
> 后端实现: `backend/src/common/api/analytics.py`

## 概览

- 基础路径: `/api/v1`
- 认证方式: `Authorization: Bearer <token>` 或 `HttpOnly` session cookie
- `/analytics/*` 接口返回为**直接 JSON 对象**（非 `{ success, data }` 包裹）
- `/admin/interventions/*` 接口返回为 `{ success, data, trace_id }` 包裹

---

## 参数归一化规则

### `scenario_type`

- `sales_bot` → `sales`
- 其他值按原样透传

### `time_period`

- `day` / `daily` → `daily`
- `week` / `weekly` → `weekly`
- `month` / `monthly` → `monthly`
- `all` / `all_time` → `all_time`
- 未识别值默认 `all_time`

---

## 排行榜接口

### 获取排行榜

```http
GET /api/v1/analytics/leaderboard
```

#### Query 参数

- `scenario_type` (可选): `sales` / `sales_bot` / `presentation`
- `time_period` (可选，默认 `all_time`)
- `include_me` (可选，默认 `false`): 是否在结果中附带当前用户排名 `my_rank`
- `limit` (可选，默认 `100`，范围 `1~1000`)

#### 响应结构

```json
{
  "scenario_type": "sales",
  "time_period": "weekly",
  "total_users": 18,
  "entries": [
    {
      "rank": 1,
      "user_id": "u_001",
      "username": "Alice",
      "total_sessions": 12,
      "average_score": 91.6,
      "best_score": 97.0
    }
  ],
  "my_rank": {
    "user_id": "u_123",
    "rank": 8,
    "total_sessions": 6,
    "average_score": 84.5,
    "total_users": 18,
    "percentile": 55.56,
    "time_period": "weekly",
    "scenario_type": "sales"
  }
}
```

> `my_rank` 仅在 `include_me=true` 且查询成功时出现。

---

### 获取当前用户排名

```http
GET /api/v1/analytics/leaderboard/my-rank
```

#### Query 参数

- `scenario_type` (可选)
- `time_period` (可选，默认 `all_time`)

#### 响应结构

```json
{
  "user_id": "u_123",
  "rank": 8,
  "total_sessions": 6,
  "average_score": 84.5,
  "total_users": 18,
  "percentile": 55.56,
  "time_period": "weekly",
  "scenario_type": "sales"
}
```

当用户在筛选范围内暂无数据时，`rank` 可能为 `null`，并可能包含 `message`。

---

## 错误响应

- 认证失败: `401 Unauthorized`
- 服务异常: `500`，`detail` 为 `"Failed to fetch leaderboard"` 或 `"Failed to fetch rank"`

---

## 仪表盘统计（沟通闭环）

### 获取训练仪表盘

```http
GET /api/v1/analytics/dashboard?scenario_type=sales&days=30
```

#### 关键字段（新增）

```json
{
  "effectiveness": {
    "pass_rate_3min_flow": 62.5,
    "pass_rate_5turn_defense": 55.0,
    "pass_rate_4step_structure": 58.75,
    "next_day_retry_rate": 31.25
  }
}
```

说明：
- 以上四项为 80/20 主看板核心指标（基于 `practice_sessions.effectiveness_snapshot` 真实计算）。
- 仅统计 `completed` 且 `evaluable=true` 的会话。

---

## 主管最小干预接口（Manager Lite）

> 后端实现: `backend/src/admin/api/interventions.py`
>
> 路径前缀: `/api/v1/admin/interventions`
>
> 认证: 需管理员权限（`admin`）

### 获取三类名单

```http
GET /api/v1/admin/interventions/lists?time_range=30d&limit=20&inactive_days=7
```

#### Query 参数

- `time_range` (可选): `7d | 30d | 90d | all_time`，默认 `30d`
- `limit` (可选): 每类名单返回条数，默认 `20`，范围 `1~100`
- `inactive_days` (可选): 连续未练阈值天数，默认 `7`，范围 `1~90`

#### 响应结构（该接口使用 `{ success, data }` 包裹）

```json
{
  "success": true,
  "data": {
    "not_passed": [
      {
        "user_id": "u_1",
        "user_name": "张三",
        "department": "销售一部",
        "overall_result": "fail",
        "session_id": "s_1",
        "session_start_time": "2026-02-21T09:00:00+00:00"
      }
    ],
    "inactive_streak": [
      {
        "user_id": "u_2",
        "user_name": "李四",
        "department": "销售二部",
        "last_session_at": "2026-02-10T11:00:00+00:00",
        "inactive_days": 11
      }
    ],
    "improving": [
      {
        "user_id": "u_3",
        "user_name": "王五",
        "department": "销售三部",
        "pass_gain": 18.5,
        "baseline_pass_rate": 40,
        "current_pass_rate": 58.5
      }
    ]
  },
  "trace_id": "trace-xxx"
}
```

### 一键提醒

```http
POST /api/v1/admin/interventions/remind
Content-Type: application/json
```

```json
{
  "user_id": "u_1",
  "note": "请按本周目标完成一次再练"
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "sent": true,
    "reminder_id": "reminder-uuid",
    "user_id": "u_1"
  },
  "trace_id": "trace-xxx"
}
```

---

## 管理端课程分析仪表盘

> 后端实现: `backend/src/admin/api/analytics_curriculum.py`
>
> 路径前缀: `/api/v1/admin/analytics`
>
> 认证: 当前实现为管理员权限（`admin`）。计划中的 supervisor/team action-level scope 依赖后续团队授权域模型，不在本接口中伪造。

### 获取课程分析仪表盘

```http
GET /api/v1/admin/analytics/curriculum?time_range=30d
```

#### Query 参数

- `time_range` (可选): `7d | 30d | 90d | all_time`，默认 `30d`

#### 响应结构（该接口使用 `{ success, data }` 包裹）

```json
{
  "success": true,
  "data": {
    "summary": {
      "assigned_count": 25,
      "completed_count": 23,
      "completion_rate": 0.92,
      "top_weak_dimension": "异议处理",
      "average_score_delta": 2.6
    },
    "heatmap": [
      {
        "template_id": "template-uuid",
        "template_name": "新人异议处理训练",
        "dimension": "异议处理",
        "average_score": 62.4,
        "sample_count": 8
      }
    ],
    "score_trend": [
      {
        "date": "2026-05-13",
        "average_score": 78.5,
        "sample_count": 3
      }
    ],
    "review_outcomes": {
      "approved": 12,
      "rejected": 2,
      "calibrated": 4,
      "retraining_required": 5
    },
    "retraining_conversion": {
      "created": 5,
      "started": 3,
      "completed": 2
    },
    "cache": {
      "enabled": false,
      "hit": false,
      "ttl_seconds": null
    }
  },
  "trace_id": "trace-xxx"
}
```

#### 指标口径

- `assigned_count`: 指定 `time_range` 内创建、且关联 `practice_template_id` 的课程训练任务数。
- `completed_count`: 指定 `time_range` 内开始、状态为 `completed`、且关联 `practice_template_id` 的课程会话数。
- `completion_rate`: `completed_count / assigned_count`；没有分配任务时为 `0`。
- `top_weak_dimension` / `heatmap`: 优先使用 `TrainingReportSnapshot.report_payload.dimension_scores`；缺失时使用冻结 `TrainingReportSnapshot.report_payload.lineage.stage_snapshots[*].dimension_scores`，不读取 latest `PracticeTemplate` 内容。
- `template_name`: 来自 `PracticeSession.curriculum_snapshot.practice_template.name`，用于保持历史课程名称不可变。
- `review_outcomes.calibrated`: 以 `SupervisorScoreCalibration` 记录作为主管校准权威来源，不依赖 review metadata。
- `cache`: 当前不新增缓存基础设施，返回 `enabled=false`；服务端用 `time_range` 与查询上限保护首版聚合。

#### 错误响应

- 非管理员: `401 Unauthorized` 或 `403 Forbidden`
- 服务异常: `{ "success": false, "error": "[CURRICULUM_ANALYTICS_FAILED]", "message": "Failed to load curriculum analytics dashboard" }`
