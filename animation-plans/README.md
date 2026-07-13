# 新人训练路径动效改进计划

审计基线提交：`19fb9e6e`

范围：学员端 `/newcomer-training`、模块与活动页，以及管理端新人训练路径编排、管理侧栏、确认弹窗、快速新建、Toast 和移动端抽屉。

| 编号 | 计划 | 严重度 | 状态 | 依赖 |
| --- | --- | --- | --- | --- |
| 001 | [建立动效 token 与减弱动态契约](./001-motion-foundation.md) | HIGH | DONE | 无 |
| 002 | [恢复弹窗、Tooltip 与 Toast 的真实动效](./002-restore-feedback-motion.md) | HIGH | DONE | 001 |
| 003 | [收紧管理端高频按钮与导航反馈](./003-sharpen-admin-controls.md) | HIGH | DONE | 001 |
| 004 | [移除侧栏折叠中的布局动画](./004-remove-sidebar-layout-motion.md) | HIGH | DONE | 003 |
| 005 | [优化移动端管理抽屉](./005-optimize-mobile-admin-sheet.md) | HIGH | DONE | 001 |
| 006 | [补全路径拖拽反馈](./006-add-path-drag-feedback.md) | HIGH | DONE | 001、003 |
| 007 | [平稳呈现活动结果](./007-reveal-activity-results.md) | MEDIUM | DONE | 001 |
| 008 | [强调全部训练完成](./008-celebrate-training-completion.md) | MEDIUM | DONE | 001、007 |
| 009 | [澄清草稿保存状态](./009-clarify-draft-save-status.md) | MEDIUM | DONE | 001、003 |
| 010 | [连贯展开训练阶段](./010-animate-journey-disclosure.md) | MEDIUM | DONE | 001 |

## 推荐执行顺序

1. 先执行 `001`，建立全项目唯一的缓动、持续时间和减弱动态契约。
2. 执行 `002`、`003`、`005`，解决当前最明显的失效动效、拖沓反馈和移动端掉帧风险。
3. 执行 `004`，它与 `003` 同时修改管理侧栏，必须在 `003` 之后完成以减少冲突。
4. 执行 `006` 和 `009`，补齐路径编排的直接操作反馈。
5. 最后执行 `007`、`008`、`010`，为学员端增加低频、有目的的反馈。

每项计划必须单独提交和验收。不得把未完成的多个计划混进同一提交。若基线代码与计划摘录不一致，停止执行该计划并先进行 `improve-animations reconcile`。

## 完成记录（2026-07-13）

- 10 项计划已实现；未新增依赖，减弱动态、键盘入口和既有业务状态保持兼容。
- 前端完整 Vitest：182 个测试文件通过，1131 个测试通过、6 个跳过；TypeScript、ESLint、生产构建均通过。
- 公网正式模式专项浏览器验收：桌面学员端、移动学员端、管理端和 `prefers-reduced-motion` 共 1 条闭环测试通过，运行时零 console/page error。
- 学员端生产路由资源 gzip 从 158805 B 增至 159674 B，增量 869 B，低于 15 KB 预算。
- 计划 002 的 Toast 最终使用 CSS keyframe 和 200ms 延迟移除，而未在根级 `ToastProvider` 引入 Framer Motion；退场行为不变，并避免所有路由承担额外客户端依赖。
- 原有三组新人训练 E2E 中 3/5 通过；其余两项失败分别来自“未选中测验活动却预期加载试卷目录”和当前种子修订缺少指定产品模块，均与本次动效链路无关，未以修改业务行为或测试断言掩盖。
