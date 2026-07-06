# 尾部类型债修复剩余 one-off full mypy 错误文件

## Goal

在不改变 DB schema、业务语义和现有用户改动的前提下，修复用户指定的剩余 one-off full mypy 错误文件，并完成最小必要验证。

## What I already know

* 用户已明确给出目标文件清单与每个文件的剩余错误数量上限。
* 任务范围限定为后端类型修复，允许直接相关 tests，不允许回滚用户改动。
* 仓库要求后端改动保持最小、遵循既有服务/API 模式，并执行 `mypy`、`ruff`、相关 `pytest --no-cov` 验证。
* 当前仓库存在大量未提交修改，因此本次只能在指定文件和直接相关测试内做手术式变更。

## Assumptions

* 本次错误主要是局部类型标注、可空值收窄、集合/字典泛型、序列化返回类型等 one-off 问题，可通过最小代码调整解决。
* 若个别目标文件路径与用户描述略有偏差，以仓库真实路径为准，但仍只改对应责任文件。

## Requirements

* 仅修复用户点名目标文件中的 mypy 错误。
* 保持现有行为与业务语义不变，不改 schema，不引入新依赖。
* 仅在必要时补充或调整直接相关 tests。
* 验证覆盖目标 mypy、ruff、相关 pytest `--no-cov`。

## Acceptance Criteria

* [ ] 目标文件上的 mypy 错误清零。
* [ ] 改动仅限责任文件与直接相关测试。
* [ ] `ruff check` 通过。
* [ ] 相关 pytest `--no-cov` 通过，或明确说明未通过/未执行原因。

## Definition of Done

* 类型修复保持最小改动。
* 无新增业务逻辑、schema 变更或密钥写入。
* 最终说明包含验证证据与剩余风险。

## Out of Scope

* 非目标文件的顺手重构。
* 业务规则调整、接口语义调整、数据迁移。
* 大范围清理当前工作树中的其他脏改动。

## Technical Approach

先用目标 mypy 命令收敛精确错误，再按文件分组修复。优先使用已有类型、局部变量收窄、显式转换和返回类型注解；仅在必要时调整相关测试以匹配静态类型约束。

## Technical Notes

* 相关规范：`backend/AGENTS.md`、`backend/src/common/AGENTS.md`、`backend/src/sales_trainer/AGENTS.md`、`backend/src/agent/AGENTS.md`、`backend/src/prompt_templates/AGENTS.md`
* 相关 Trellis spec：`.trellis/spec/backend/index.md`、`.trellis/spec/backend/quality-guidelines.md`、`.trellis/spec/backend/error-handling.md`、`.trellis/spec/backend/logging-guidelines.md`
* 需要先确认真实文件路径后再执行局部 mypy。
