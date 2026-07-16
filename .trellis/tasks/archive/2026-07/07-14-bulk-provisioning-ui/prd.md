# 管理端批量开户体验

## Goal

在用户管理上下文内完成模板下载、导入校验、就地建组、确认执行、部分成功处理和一次性凭据保存。

## Scope

* 下载 UTF-8 CSV 模板和上传入口。
* 行/团队两级预览、错误定位、原地修正和主组长选择。
* 确认、执行进度、取消/中断、部分成功结果和失败团队重试。
* 客户端一次性凭据 CSV、离开警告和凭据丢失后的批量重置。
* loading、empty、no-result、permission、stale/conflict、failure/recovery 状态。
* 以根目录 `DESING.md` 为产品/交互规范，复用 `web/design-system/sales-trainer/DESIGN.md` 的视觉 tokens 和现有组件。

## Acceptance Criteria

* [x] 管理员无需离开导入流程即可创建未知团队并指定主组长。
* [x] 输入在可恢复失败、返回和重试后不会丢失。
* [x] 重要批次结果有持久结果页，不只显示 toast。
* [x] 凭据只在当前结果会话显示/导出一次，刷新后明确不可恢复。
* [x] 键盘、焦点、窄屏、长名称和 50+ 行数据验证通过。

## Dependencies

* Parent: `../07-14-account-team-lead/prd.md`
* Requires: `../07-14-bulk-provisioning-backend/prd.md`
