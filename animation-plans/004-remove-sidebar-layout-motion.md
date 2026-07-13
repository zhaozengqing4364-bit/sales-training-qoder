# 004 — 移除侧栏折叠中的布局动画

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: HIGH
- **Category**: Performance / Purpose & frequency
- **Estimated scope**: 3 files，约 45 行

## Problem

侧栏折叠同时动画固定侧栏宽度与主区域 margin：

```tsx
/* web/src/components/layout/admin-sidebar.tsx:75 — current */
"... transition-all duration-300 ease-in-out ...",
isCollapsed ? "w-20 px-3" : "w-72 px-5"

/* web/src/components/layout/admin-shell.tsx:138-139 — current */
"... transition-all duration-300 ease-in-out",
isCollapsed ? "md:ml-28" : "md:ml-80"
```

`width` 和 `margin-left` 会触发布局与绘制；两处 300ms 动画同时执行，复杂管理页容易卡顿。这个布局操作不需要被动画化。

## Target

- `w-20/w-72`、`px-3/px-5`、`md:ml-28/md:ml-80` 立即切换，不设置 transition。
- 折叠按钮继续使用计划 003 的 140ms 按压/颜色反馈。
- Chevron 或 PanelLeft 图标可以做 160ms opacity，但不得动画 width、margin、padding、left 或 right。
- 不制造“保留大空白”或“侧栏覆盖内容”的替代布局。

## Repo conventions to follow

- 使用现有 Zustand `useSidebarStore` 作为唯一状态权威。
- 保留两个离散布局规格：折叠 `w-20` + `md:ml-28`，展开 `w-72` + `md:ml-80`。
- 高频反馈使用 `--duration-press: 140ms`；布局不使用 duration token。

## Steps

1. 在 `admin-sidebar.tsx` 的 `<aside>` 删除 `transition-all duration-300 ease-in-out`。
2. 在 `admin-shell.tsx` 的主 `<main>` 删除 `transition-all duration-300 ease-in-out`；保留滚动和高度行为。
3. 检查品牌名称和底部用户卡；删除任何依赖 width 动画才能正确隐藏的样式，改用现有条件渲染或即时 `hidden`。
4. 扩展 `admin-shell.test.tsx` 与 `admin-sidebar.test.tsx`：切换 store 后断言布局类同步改变，且两个容器都不含 `transition-all`。

## Boundaries

- Do NOT 把 width/margin 动画改成 CSS grid 列动画。
- Do NOT 让展开侧栏覆盖主内容。
- Do NOT 修改移动端 GlassSheet；它由计划 005 处理。
- Do NOT 修改侧栏持久化键或默认折叠状态。

## Verification

- **Mechanical**: 运行 AdminShell/AdminSidebar 测试、类型检查、目标文件 ESLint、生产构建。
- **Feel check**: 在包含长路径编辑器的页面连续折叠/展开 20 次；内容位置应立即稳定，不出现 300ms 追赶、文字挤压或水平滚动。Performance 面板中不应出现持续 300ms 的 Layout 记录。
- **Reduced motion**: 与默认模式一致，布局即时切换。
- **Done when**: 折叠状态正确持久化，布局无 transition，主内容与侧栏始终不重叠。
