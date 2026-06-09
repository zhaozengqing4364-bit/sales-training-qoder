# 新人训练路径录音历史重评 append-only 证据

时间：2026-06-04T03:32:11Z

## 目标切片

补齐历史录音评分结果的显式高风险重评能力：

- 预览历史录音重评影响范围。
- 执行重评必须填写原因。
- 仅管理员 / 运维类角色可操作，内容管理员被拒绝。
- 使用目标 `sales_trainer_audio_score_prompt` published revision 重新评分。
- 只追加 `sales_trainer_regrade_runs` 和 `historical_regrade.completed` 操作日志。
- 不覆盖原始 `SalesTrainerAudioScoreResult`、`prompt_hash`、`transcript_snapshot` 和旧分数。

## 红测

命令：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_audio_regrade_api.py::test_should_regrade_audio_submission_as_explicit_append_only_action -q --no-cov
```

首次结果：失败，`/api/v1/admin/newcomer-training/regrades/audio-submissions/{submission_id}/preview` 返回 404。

## 实现

新增 / 修改：

- `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py`
- `backend/src/sales_trainer/services/audio_regrade_calculator.py`
- `backend/src/sales_trainer/services/audio_regrade_service.py`
- `backend/src/sales_trainer/regrade_api.py`
- `backend/src/sales_trainer/regrade_schemas.py`
- `docs/api-contract/sales-trainer.md`

实现语义：

- `preview` 返回 `before_snapshot` 和 `after_snapshot`。
- `run` 创建 `SalesTrainerRegradeRun(target_type="audio_submission")`。
- 操作日志 metadata 包含 `regrade_run_id`、`target_revision_id`、`reason`、`impact_scope`、`before_snapshot`、`after_snapshot`、`trace_id`、`append_only=true`、`history_overwrite=false`。
- 原始 `SalesTrainerAudioScoreResult` 保持旧分数和旧 `prompt_hash`。

## 绿测与回归

音频重评单测：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_audio_regrade_api.py::test_should_regrade_audio_submission_as_explicit_append_only_action -q --no-cov
```

结果：1 passed, 1 warning。

聚焦回归：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_score_prompt_api.py tests/unit/test_newcomer_training_path_score_prompts.py tests/unit/test_newcomer_training_path_audio_lineage.py -q --no-cov
```

结果：6 passed, 1 warning。

Ruff：

```bash
cd backend && venv/bin/ruff check src/sales_trainer/services/audio_regrade_calculator.py src/sales_trainer/services/audio_regrade_service.py src/sales_trainer/regrade_api.py src/sales_trainer/regrade_schemas.py tests/integration/test_newcomer_training_path_audio_regrade_api.py
```

结果：All checks passed。

新人训练路径后端回归：

```bash
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_*.py tests/integration/test_newcomer_training_path_*.py -q --no-cov
```

结果：69 passed, 1 warning。

收窄 fake scoring service 合同后的最终复跑：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/integration/test_newcomer_training_path_regrade_api.py -q --no-cov
cd backend && venv/bin/ruff check src/sales_trainer/services/audio_regrade_calculator.py src/sales_trainer/services/audio_regrade_service.py src/sales_trainer/regrade_api.py src/sales_trainer/regrade_schemas.py tests/integration/test_newcomer_training_path_audio_regrade_api.py
```

结果：2 passed, 1 warning；Ruff All checks passed。

## LOC 约束

纯 LOC：

- `backend/src/sales_trainer/services/audio_regrade_calculator.py`: 148
- `backend/src/sales_trainer/services/audio_regrade_service.py`: 184
- `backend/src/sales_trainer/regrade_api.py`: 183
- `backend/tests/integration/test_newcomer_training_path_audio_regrade_api.py`: 212

## 剩余范围

本切片只证明录音重评后端 append-only 语义。前端重评入口、浏览器验收、旧/新学员全链路录音 prompt 变更浏览器证据仍属于后续目标范围。
