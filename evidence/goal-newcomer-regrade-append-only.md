# 新人训练路径历史重评 append-only 证据

时间：2026-06-04

## 本次交付范围

- 新增 `sales_trainer_regrade_runs` append-only 表和 ORM 模型。
- 新增历史考试重评 API：
  - `POST /api/v1/admin/sales-trainer/regrades/quiz-attempts/{attempt_id}/preview`
  - `POST /api/v1/admin/sales-trainer/regrades/quiz-attempts/{attempt_id}/run`
  - `POST /api/v1/admin/newcomer-training/regrades/quiz-attempts/{attempt_id}/preview`
  - `POST /api/v1/admin/newcomer-training/regrades/quiz-attempts/{attempt_id}/run`
- 新增权限 `can_regrade_sales_trainer_history`，仅 `admin/super_admin/ops/operator/operations/sre` 可执行。
- 新增操作日志 `historical_regrade.completed`，metadata 包含 `reason`、`impact_scope`、`before_snapshot`、`after_snapshot`、`trace_id`、`append_only=true`、`history_overwrite=false`。
- 前端历史考试详情页新增“重新评分历史记录”面板，支持预览影响、填写原因、确认重评。
- 更新 `docs/api-contract/sales-trainer.md` 的历史重评契约和错误码。

## 红测

命令：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_regrade_api.py::test_should_regrade_quiz_attempt_as_explicit_high_risk_append_only_action -q --no-cov
```

结果：

- 失败，`/api/v1/admin/newcomer-training/regrades/quiz-attempts/{attempt_id}/preview` 返回 404。
- 失败点正确：目标要求该端点存在并先做权限判断，content admin 应被 403 拦截。

## 后端验证

命令：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_regrade_api.py::test_should_regrade_quiz_attempt_as_explicit_high_risk_append_only_action -q --no-cov
```

结果：`1 passed, 1 warning`

命令：

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_regrade_api.py tests/integration/test_newcomer_training_path_paper_api.py tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_audit_logs.py -q --no-cov
```

结果：`17 passed, 1 warning`

命令：

```bash
cd backend && venv/bin/ruff check src/sales_trainer/regrade_models.py src/sales_trainer/regrade_schemas.py src/sales_trainer/regrade_api.py src/sales_trainer/services/regrade_service.py src/sales_trainer/services/regrade_calculator.py src/sales_trainer/router_registration.py src/sales_trainer/models.py src/sales_trainer/permissions.py tests/integration/test_newcomer_training_path_regrade_api.py
```

结果：`All checks passed!`

注意：一次串联命令误写成 `cd backend && ... && cd backend && venv/bin/ruff ...`，第二个 `cd backend` 导致 `zsh:1: no such file or directory: venv/bin/ruff`。该输出没有作为 ruff 通过证据，已单独重跑 ruff。

## 前端验证

命令：

```bash
cd web && npx vitest run 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx' src/lib/api/sales-trainer.test.ts --pool=threads --maxWorkers=1
```

结果：`2 passed / 16 tests passed`

命令：

```bash
cd web && npx tsc --noEmit
```

结果：通过。

## LOC 检查

```text
backend/src/sales_trainer/regrade_models.py: 60
backend/src/sales_trainer/regrade_schemas.py: 21
backend/src/sales_trainer/regrade_api.py: 124
backend/src/sales_trainer/services/regrade_service.py: 152
backend/src/sales_trainer/services/regrade_calculator.py: 178
backend/tests/integration/test_newcomer_training_path_regrade_api.py: 223
web/src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.tsx: 224
web/src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx: 183
web/src/components/admin/sales-trainer/quiz-attempt-regrade-panel.tsx: 166
```

## 已证明的行为

- 第一版考卷正确答案为 A，学员答 A 得 10 分并通过。
- 管理员发布同一题的新修订，正确答案变为 B。
- 重评预览显示原始成绩仍为 10，新重评结果为 0。
- content admin 调重评预览返回 403。
- 空原因执行重评返回 422。
- 执行重评后只新增 `sales_trainer_regrade_runs` 一条记录和 `historical_regrade.completed` 日志。
- 原始 `SalesTrainerQuizAttempt.total_score` 仍为 10，原始 answer snapshot 的正确答案仍为 A。

## 尚未完成

- 音频评分 / AI prompt 历史重评 UI 与 API 仍需接入同一 regrade run 模型。
- 浏览器验收还需要跑真实页面：预览影响、填写原因、确认重评、操作日志可见。
- 全目标仍未完成，不能据此标记 goal complete。
