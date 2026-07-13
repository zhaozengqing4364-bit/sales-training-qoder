# 003 — 收紧管理端高频按钮与导航反馈

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: HIGH
- **Category**: Purpose & frequency / Performance
- **Estimated scope**: 3–4 files，约 80 行

## Problem

共享按钮和管理导航使用 `transition-all`，导航持续 300ms 并缩放图标：

```tsx
/* web/src/components/ui/button.tsx:24 — current */
"... transition-all duration-200 ... active:scale-[0.98]"

/* web/src/components/layout/admin-sidebar.tsx:561 — current */
"... transition-all duration-300 group relative"

/* web/src/components/layout/admin-sidebar.tsx:574-576 — current */
"transition-all duration-300 shrink-0",
isActive ? "text-slate-900 scale-110" : "text-slate-400 group-hover:text-slate-600 group-hover:scale-105"
```

这些交互每天发生几十次，300ms 缓动和持续缩放让导航显得黏滞；`transition-all` 还会动画化阴影、尺寸等非预期属性。

## Target

共享按钮：

```tsx
"... transition-[color,background-color,border-color,box-shadow,transform] duration-[var(--duration-press)] ease-[var(--ease-out)] active:scale-[0.97] motion-reduce:active:scale-100"
```

管理导航链接和分组按钮：

```tsx
"... transition-[color,background-color,box-shadow] duration-[var(--duration-press)] ease-[var(--ease-out)]"
```

图标只过渡颜色 140ms；删除 `scale-110`、`group-hover:scale-105`。当前项左侧指示条直接出现，不做路由切换动画。

## Repo conventions to follow

- 使用 `--duration-press: 140ms` 和 `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`。
- 保留 `active:scale-[0.97]` 作为明确按压反馈，减弱动态时取消缩放。
- 保留现有颜色、阴影、圆角和焦点样式。

## Steps

1. 修改 `web/src/components/ui/button.tsx:24`，以明确属性列表替换 `transition-all duration-200`，按压比例从 0.98 统一为 0.97。
2. 修改 `web/src/components/layout/admin-sidebar.tsx` 中 AdminNavLink、SectionTrigger、品牌区、折叠按钮的 `transition-all`；高频导航只保留颜色/背景/阴影过渡。
3. 删除 AdminNavLink 与 SectionTrigger 图标的 hover/active 缩放，只保留 140ms 颜色过渡。
4. 检查 `web/src/components/admin/sales-trainer/module-nav.tsx:127`；它已经使用 `transition-colors`，只补充 140ms token，不增加缩放。
5. 扩展 `admin-sidebar.test.tsx`，断言导航不含 `transition-all`、`scale-110`、`group-hover:scale-105`，并保留 active 状态和 accessible label。

## Boundaries

- Do NOT 修改导航信息架构、展开状态或权限过滤。
- Do NOT 动画路由页面本身。
- Do NOT 删除焦点环、disabled 状态或按压反馈。
- Do NOT 调整颜色和排版。

## Verification

- **Mechanical**: 运行 Button/Sidebar/ModuleNav 测试、`npx tsc --noEmit`、目标文件 ESLint、`npm run build`。
- **Feel check**: 连续点击新人训练下的路径、学员进度、达标审核和训练记录；状态反馈应在 140ms 内完成，图标不放大，键盘导航不等待动画。10% 慢放时只能看到颜色、背景、阴影与按压 transform。
- **Reduced motion**: 按钮仍有颜色反馈，但按压不缩放。
- **Done when**: 目标文件不存在高频 `transition-all`，导航不再有装饰性图标缩放。
