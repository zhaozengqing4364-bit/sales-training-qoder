# 002 — 恢复弹窗、Tooltip 与 Toast 的真实动效

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: HIGH
- **Category**: Cohesion / Interruptibility / Physicality
- **Estimated scope**: 5 files，约 160 行

## Problem

共享反馈组件声明了当前构建无法生成的类：

```tsx
/* web/src/components/ui/glass-modal.tsx:24 — current */
"fixed inset-0 ... data-[state=open]:animate-in data-[state=closed]:animate-out ..."

/* web/src/components/ui/glass-modal.tsx:98 — current */
"fixed left-[50%] top-[50%] ... duration-200 data-[state=open]:animate-in ... data-[state=open]:zoom-in-95 ..."

/* web/src/components/ui/glass-tooltip.tsx:21 — current */
"... animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out ..."

/* web/src/components/ui/toast.tsx:47 — current */
<div className={`... animate-in slide-in-from-right-4 ${styles[toast.type]}`}>
```

生产 CSS 中 `animate-in`、`animate-out`、`zoom-in-95`、`fade-in-0`、`slide-in-from-right-4` 的匹配数均为 0。Toast 还在 `toast.tsx:60-61` 直接从数组删除，没有退场阶段。

## Target

- Overlay：240ms opacity，`var(--ease-out)`。
- Modal：240ms opacity + `scale(0.97 → 1)`，居中原点；关闭使用同一时长，不从屏幕边缘滑入。
- Tooltip：160ms opacity + `scale(0.97 → 1)`，原点必须是 `var(--radix-tooltip-content-transform-origin)`。
- Toast：200ms opacity + `translateX(16px) scale(0.97) → translateX(0) scale(1)`；退出到 `translateX(16px) scale(0.97)`。
- 减弱动态：Overlay/Modal/Tooltip/Toast 只做 160ms opacity，不移动、不缩放。

Modal CSS 必须显式保留居中 transform：

```css
transform: translate(-50%, -50%) scale(1);
```

Toast 使用与共享组件一致的 CSS keyframe，并通过显式退出状态等待 200ms 后移除：

```css
.motion-toast[data-state="open"] { animation: motion-toast-in var(--duration-popover) var(--ease-out) both; }
.motion-toast[data-state="closed"] { animation: motion-toast-out var(--duration-popover) var(--ease-out) both; }
```

## Repo conventions to follow

- Token 权威来自 `web/src/app/globals.css`：`--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`、`--duration-tooltip: 160ms`、`--duration-modal: 240ms`。
- Radix Dialog 与 Tooltip 继续负责 portal、焦点和存在周期；不要重写无障碍逻辑。
- ToastProvider 位于根布局；不得仅为 Toast 让所有路由加载 Framer Motion。CSS keyframe 是该共享入口的首选实现。

## Steps

1. 在 `web/src/app/globals.css` 的组件层定义 `.motion-dialog-overlay`、`.motion-dialog-content`、`.motion-tooltip` 及对应 open/closed keyframes。Modal keyframe从 `translate(-50%,-50%) scale(0.97)` 到 `translate(-50%,-50%) scale(1)`；Tooltip 从 `scale(0.97)` 到 `scale(1)`。
2. 为 closed 状态定义独立退场 keyframe，确保 Radix Presence 等待退场完成；不要使用 `transition: all`。
3. 修改 `glass-modal.tsx`，删除所有无效 `animate-in/out`、fade、zoom、slide 类，分别添加 `.motion-dialog-overlay` 和 `.motion-dialog-content`，并添加 `data-motion-kind="spatial"`。
4. 修改 `glass-tooltip.tsx`，删除无效类，添加 `.motion-tooltip`、`data-motion-kind="spatial"` 和 Radix transform origin。
5. 修改 `toast.tsx`：为条目维护显式 `open/closed` 退出状态，关闭后等待 200ms 再从数组移除；保留 4 秒自动关闭行为，并清理定时器。
6. 新增或扩展共享组件测试：断言 Radix data-state 类已替换；Toast 删除时会进入退出生命周期；关闭按钮 accessible name 不变。

## Boundaries

- Do NOT 安装 `tailwindcss-animate` 或 `tw-animate-css`。
- Do NOT 修改弹窗结构、文案、焦点陷阱和业务回调。
- Do NOT 给 Modal 添加弹跳或 `scale(0)`。
- Do NOT 修改新人训练之外的业务页面；共享组件自然影响其调用者属于预期兼容范围。

## Verification

- **Mechanical**: 在 `web/` 运行相关 UI 测试、`npx tsc --noEmit`、目标文件 ESLint、`npm run build`；随后确认构建 CSS 中存在 `.motion-dialog-content` 和 `.motion-tooltip`，且源码不再包含对应无效类。
- **Feel check**: 打开训练路径预览、发布确认、删除确认、快速新建与侧栏 Tooltip；DevTools 动画速度设为 10%，确认 Modal 从中心缩放、Tooltip 从触发器方向缩放、Toast 完整退场。快速连续开关时不得从错误位置重启。
- **Reduced motion**: 切换减弱动态后，所有组件只淡入淡出，不发生位移或缩放。
- **Done when**: 五个管理端反馈入口都有真实、可见、可退场且可减弱的动效。
