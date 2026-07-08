# Implementation Notes

## Plan

1. 收敛新人训练后台导航：顶层按“录音管理 / 学习专题 / 路径与达标 / 系统治理”组织，隐藏资源表型入口。
2. 新增 `/admin/sales-trainer/audio` 与 `/admin/sales-trainer/learning-topics` 路由族，复用现有 API 与页面能力。
3. 旧入口保持兼容：优先重定向到新模块入口，复杂新建/编辑页继续可访问但从新模块内进入。
4. 调整页面文案和模块内导航，避免管理员看到“场景治理”等内部术语。
5. 更新路由测试、页面测试与文档，运行 focused tests、typecheck/lint 可行命令。

## Deviations

暂无。

## Verification

- `npx vitest run` focused 27 个新人训练后台相关测试文件：99 tests passed。
- `npx tsc --noEmit`：passed。
- `npx eslint` 针对本次变更的 `web/src` TS/TSX 文件：0 errors。
- `npx next build`：passed，新增 `/admin/sales-trainer/audio/*` 与 `/admin/sales-trainer/learning-topics/*` 路由成功进入构建产物。
