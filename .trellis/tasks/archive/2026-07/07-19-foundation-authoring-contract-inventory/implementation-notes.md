# Implementation Notes

## Scope

本任务只落地内容生产权威合同、Legacy 映射、验收勘误和只读 inventory。未修改运行时 API、权限代码、页面、Schema 或业务数据，未提供 apply/migrate 开关。

## Decisions

- 2026-07-18 的首发证据继续作为运行时真值保留；2026-07-20 只重新打开管理员 Authoring 与真实 Legacy 内容迁移结论。
- Legacy `sales_trainer` 内容表没有可靠 `organization_id`，报告固定标记 `global_unscoped`，目标组织必须在后续 dry-run 前明确选择。
- Authoring 资源联合冻结为 `source_document | learning_unit | question | quiz | audio_material | scoring_scheme | coach_profile | scenario`；Prompt/模型/Provider/密钥继续由独立 AI 治理权限管理。
- 当前 `AudioActivityResourceRevision` 与 `CoachProfileRevision` 没有显式逻辑容器/pointer；inventory 只派生展示并标记 `derived_missing_logical_container`，不把它误报成已完整实现。
- Inventory 对 PostgreSQL 执行 `SET TRANSACTION READ ONLY`，只发出 SELECT，结束时 rollback；输出不含 storage key、Source URI、Prompt 正文、raw snapshot、转写或个人数据。

## Current Database Findings

生成报告：`research/current-inventory.json` 与 `research/current-inventory.md`。

- Legacy active path：1；活动：2；材料：4；材料版本：2；评分 Prompt 元数据：2。
- 明确定位 `石犀ppt讲解` 与 `demo讲解`。
- 四条同名 PPT 材料触发 `LEGACY_MATERIAL_SAME_NAME_INCOMPLETE_HASH`；另有同 hash 多逻辑对象冲突，不能自动合并。
- `石犀ppt讲解` 的 Legacy 材料/评分引用可进入 dry-run；`demo讲解` 缺 Legacy material 引用，需要补充 Demo/脚本来源。
- 当前 Foundation 组织 `default` 与 `slice2-seed-validation` 主要是标准包资源；两者都没有对应用户 PPT Source。

## Deviations

- 无范围偏离。
- 当前报告没有尝试验证受保护文件是否真实存在或解码成功，因为读取文件内容和迁移 apply 明确属于后续任务；该项保持为 dry-run/人工输入前置条件。

## Verification

- Ruff + format check：新增 inventory 与三个新增测试文件通过。
- Mypy：inventory 脚本通过，`Success: no issues found in 1 source file`。
- Pytest：inventory unit/integration 与 Authoring contract 共 `14 passed`；唯一 Passlib `crypt` 弃用警告为既存问题。
- 当前开发库：使用最终脚本重新生成 JSON/Markdown，包含无法验证 Prompt 与材料冲突项，`writes_performed=0`。
