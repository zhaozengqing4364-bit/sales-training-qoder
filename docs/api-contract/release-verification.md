# 发布验收契约（`release-verification`）

> 状态：✅ 已实现  
> 前缀：`/api/v1/admin/release-verification`

## 1) 核心实体

### ReleaseCandidate（汇总）

```ts
interface ReleaseCandidateSummary {
  release_candidate_id: string;
  release_version: string;
  status: 'pending' | 'passed' | 'failed';
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  pending_checks: number;
  decision?: 'go' | 'no_go' | 'conditional' | null;
  decision_reason?: string | null;
  created_at: string;
  updated_at: string;
}
```

### VerificationRecord（明细）

```ts
interface VerificationRecord {
  id: string;
  release_candidate_id: string;
  check_type: 'migration' | 'contract' | 'performance' | 'manual';
  check_name: string;
  status: 'pending' | 'passed' | 'failed' | 'skipped';
  passed: boolean;
  details?: Record<string, unknown> | null;
  error_message?: string | null;
  duration_ms?: number | null;
  checked_at?: string | null;
}
```

## 2) 接口

- `POST /candidates`：创建候选发布（可携带自定义 checks）
- `GET /candidates`：列表查询
  - query: `status?`, `limit`, `offset`
- `GET /candidates/latest`：最新候选发布
- `GET /candidates/{release_candidate_id}/report`：完整报告（汇总 + 明细）
- `PUT /checks/{record_id}`：更新单条校验结果
- `POST /candidates/{release_candidate_id}/decision`：人工 Go/No-Go
- `POST /candidates/{release_candidate_id}/run-verification`：触发自动校验
- `GET /candidates/{release_candidate_id}/quality-gate`：质量门结论
- `POST /candidates/{release_candidate_id}/auto-decision`：自动决策

## 3) 响应规范

统一响应包装：

```json
{
  "success": true,
  "data": {},
  "trace_id": "..."
}
```

错误示例：

```json
{
  "success": false,
  "error": "[REPORT_FAILED]",
  "message": "Failed to get verification report",
  "trace_id": "..."
}
```

