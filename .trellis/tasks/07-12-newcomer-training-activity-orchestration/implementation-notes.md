# Implementation Notes

## Assumptions

- 当前 `codex/newcomer-training-v0-9-closure` 是本 Goal 的功能分支。
- 当前普通 checkout 不是 linked worktree；由于 Goal 指定当前工作树为权威且存在必须保留的用户修改，选择原地执行，不创建第二工作树。
- 普通 CI 使用 Fake/local Provider；真实 StepAudio 仅走已有受控门禁。

## Protected Existing Changes

- `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`：用户既有修改，禁止纳入本任务提交。

## Deviations

- Task 2：默认 SQLite 开发库从空库执行完整 Alembic 历史链时，既有 `001` 迁移因
  `practice_sessions` 不存在而失败，尚未运行到本次 `092`。本次以 ORM 元数据真实建表、
  SQLite schema 反射、迁移脚本静态契约和专项测试验证 `092`；完整迁移链问题保留到
  Task 15 reset/seed 闭环，不静默忽略。

## Verification Evidence

- Baseline：旧路径配置专项 `22 passed`。
- Task 1 RED：新测试因 `sales_trainer.orchestration` 不存在而 collection error，符合功能缺失预期。
- Task 1 GREEN：`14 passed`。
- Task 1 Ruff：`All checks passed!`。
- Task 1 Mypy：`Success: no issues found in 4 source files`。
- CodeGraph 尚未索引新文件，`impact` 无法识别；新包当前只有新增测试调用，无既有共享调用者。
- Task 2 RED：repository 模块不存在，collection error，符合功能缺失预期。
- Task 2 GREEN：repository + schema 反射 `4 passed`。
- Task 2 Ruff：`All checks passed!`。
- Task 2 Mypy：`Success: no issues found in 1 source file`。
- Task 2 Alembic：默认空 SQLite 的既有历史链在 `001` 失败，未触达 `092`；错误为
  `no such table: practice_sessions`，已纳入最终 reset/seed 验证项。
