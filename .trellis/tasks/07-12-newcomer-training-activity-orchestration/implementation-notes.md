# Implementation Notes

## Assumptions

- 当前 `codex/newcomer-training-v0-9-closure` 是本 Goal 的功能分支。
- 当前普通 checkout 不是 linked worktree；由于 Goal 指定当前工作树为权威且存在必须保留的用户修改，选择原地执行，不创建第二工作树。
- 普通 CI 使用 Fake/local Provider；真实 StepAudio 仅走已有受控门禁。

## Protected Existing Changes

- `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`：用户既有修改，禁止纳入本任务提交。

## Deviations

- 暂无架构偏差。

## Verification Evidence

- Baseline：旧路径配置专项 `22 passed`。
- Task 1 RED：新测试因 `sales_trainer.orchestration` 不存在而 collection error，符合功能缺失预期。
- Task 1 GREEN：`14 passed`。
- Task 1 Ruff：`All checks passed!`。
- Task 1 Mypy：`Success: no issues found in 4 source files`。
- CodeGraph 尚未索引新文件，`impact` 无法识别；新包当前只有新增测试调用，无既有共享调用者。
