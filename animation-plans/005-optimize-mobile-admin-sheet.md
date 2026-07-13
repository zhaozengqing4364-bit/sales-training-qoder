# 005 — 优化移动端管理抽屉

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: HIGH
- **Category**: Performance / Accessibility / Interruptibility
- **Estimated scope**: 2 files，约 70 行

## Problem

移动端管理抽屉使用 Framer Motion 的 `x/y` 简写并叠加全屏 blur：

```tsx
/* web/src/components/ui/glass-sheet.tsx:66-77 — current */
const variants: Variants = {
    closed: {
        x: side === "left" ? "-100%" : side === "right" ? "100%" : 0,
        y: side === "bottom" ? "100%" : 0,
        opacity: 0,
    },
    open: {
        x: 0,
        y: 0,
        opacity: 1,
        transition: { type: "spring", damping: 30, stiffness: 300 },
    },
};

/* web/src/components/ui/glass-sheet.tsx:90 — current */
className="fixed inset-0 z-50 bg-slate-900/20 backdrop-blur-sm"
```

`x/y` 简写运行于主线程；全屏 blur 在移动设备上进一步增加合成压力，也没有 `useReducedMotion()` 分支。

## Target

使用完整 transform：

```tsx
const closedTransform = side === "left"
  ? "translate3d(-100%,0,0)"
  : side === "right"
    ? "translate3d(100%,0,0)"
    : "translate3d(0,100%,0)";

const variants: Variants = {
  closed: {
    opacity: 0,
    transform: reduceMotion ? "translate3d(0,0,0)" : closedTransform,
    transition: { duration: reduceMotion ? 0.16 : 0.2, ease: [0.23, 1, 0.32, 1] },
  },
  open: {
    opacity: 1,
    transform: "translate3d(0,0,0)",
    transition: reduceMotion
      ? { duration: 0.16, ease: [0.23, 1, 0.32, 1] }
      : { type: "spring", duration: 0.5, bounce: 0.2 },
  },
};
```

Backdrop 改为 `bg-slate-900/25`，删除动画期间的 `backdrop-blur-sm`。

## Repo conventions to follow

- 继续使用已有 AnimatePresence、portal、焦点恢复和 Escape 关闭逻辑。
- Spring 精确使用 `{ type: "spring", duration: 0.5, bounce: 0.2 }`。
- 减弱动态只淡入淡出 160ms。

## Steps

1. 从 `framer-motion` 增加 `useReducedMotion` 导入并在组件顶层读取。
2. 用上述完整 transform variants 替换 `x/y` variants；禁止保留 `x` 或 `y` 属性。
3. Backdrop 删除 `backdrop-blur-sm`，使用更明确的纯色透明遮罩。
4. 为 sheet 内容添加 `data-motion-kind="spatial"`。
5. 扩展 `glass-sheet.test.tsx`，覆盖左、右、下三个方向，断言 transform 字符串与关闭/焦点行为不变。

## Boundaries

- Do NOT 修改 drawer 尺寸、圆角、portal、焦点管理或关闭手势。
- Do NOT 增加拖拽关闭；当前需求只优化已有打开/关闭。
- Do NOT 使用 Framer `x/y/scale` 简写。
- Do NOT 保留全屏 filter blur。

## Verification

- **Mechanical**: 运行 GlassSheet 与 AdminShell 测试、类型检查、目标文件 ESLint、生产构建。
- **Feel check**: 使用 375×812 和低性能设备模拟，连续打开/关闭移动菜单；面板应携带速度自然进入，遮罩不闪白。Performance 面板确认动画只更新 transform/opacity，没有 Layout。
- **Reduced motion**: 面板原地淡入淡出，不从边缘移动。
- **Done when**: 三个方向均正确、可中断、无 x/y 简写、无全屏 blur。
