# 新人训练路径录音历史重评浏览器验收

时间：2026-06-04 12:07 CST

## 验收目标

补齐“高风险重评”真实浏览器证据：

- 管理员在录音详情页能看到“重新评分历史记录”。
- 重评必须先预览影响范围。
- 重评必须填写原因。
- 重评执行后只追加 regrade run 和操作日志，不覆盖原始评分。
- 操作日志能展开看到 `historical_regrade.completed`、`reason`、`trace_id`、`append_only`、`history_overwrite`、`before_snapshot`、`after_snapshot`。

## QA 数据

- 录音提交：`49ec020b-b761-4580-86b8-28e5afac69c7`
- 原始评分：`88`
- 原始 prompt hash：`source-prompt-hash`
- 目标评分标准修订：`441ad3a6-d879-4ffd-a3f2-b2c2ae2b8c25`
- 重评 trace_id：`6c00ed25edded09fd0a2d174ed99b946`

## 浏览器证据

- `evidence/goal-audio-regrade-detail-before-preview.png`
- `evidence/goal-audio-regrade-after-run.png`
- `evidence/goal-audio-regrade-operation-log-expanded.png`

可见结果：

- 录音详情页显示原始评分 `88`。
- 预览后显示 `1 条历史记录`、`只追加结果，不覆盖原始评分`。
- 执行后显示 `已生成录音重评记录，追踪号 6c00ed25edded09fd0a2d174ed99b946`。
- 操作日志第一行可展开原始数据，包含 `historical_regrade.completed`、`append_only: true`、`history_overwrite: false`、`before_snapshot.total_score: 88`、`after_snapshot.target_revision_no: 2`。

## 数据库证据

`evidence/goal-audio-regrade-browser-db-proof.txt` 证明：

- `sales_trainer_audio_score_results` 仍只有原始评分记录，`total_score=88.00`，`prompt_hash=source-prompt-hash`。
- `sales_trainer_regrade_runs` 追加一条 `target_type=audio_submission`、`status=completed` 的记录。
- `sales_trainer_operation_logs` 追加一条 `historical_regrade.completed`，`append_only=true`，`history_overwrite=false`。

## 注意

本地 3444 后端旧进程未加载新增 regrade 路由，第一次浏览器请求返回 404。已重启后端到当前工作树后复验通过。
