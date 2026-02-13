# 分析与排行榜 API 契约

> 状态: ✅ 已实现（2026-02-10 更新）
>
> 后端实现: `backend/src/common/api/analytics.py`

## 概览

- 基础路径: `/api/v1`
- 认证方式: `Authorization: Bearer <token>`
- 当前接口返回为**直接 JSON 对象**（非 `{ success, data }` 包裹）

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

