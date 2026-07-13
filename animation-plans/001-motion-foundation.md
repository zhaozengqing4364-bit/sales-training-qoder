# 001 — 建立动效 token 与减弱动态契约

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: HIGH
- **Category**: Accessibility / Cohesion & tokens
- **Estimated scope**: 1–2 files，约 50 行

## Problem

全局样式只有颜色、阴影和圆角 token，没有动效 token，也没有减弱动态策略：

```css
/* web/src/app/globals.css:3 — current */
:root {
  /* Premium Palette - Warm & Airy */
  /* Backgrounds */
  --color-bg-main: #FAFAF9;
  --color-bg-card: #FFFFFF;
  /* ... */
  --glass-bg: rgba(255, 255, 255, 0.65);
  --glass-border: rgba(255, 255, 255, 0.6);
  --glass-shine: rgba(255, 255, 255, 0.4);
}
```

源码中不存在 `prefers-reduced-motion`、`motion-reduce` 或 `useReducedMotion`。后续组件如果各自写时长和缓动，会继续产生不一致。

## Target

在 `:root` 中增加且只保留以下共享值：

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
--duration-press: 140ms;
--duration-tooltip: 160ms;
--duration-popover: 200ms;
--duration-modal: 240ms;
--duration-drawer: 320ms;
```

增加统一的减弱动态契约：

```css
@media (prefers-reduced-motion: reduce) {
  [data-motion-kind="spatial"] {
    transform: var(--motion-reduced-transform, none) !important;
    transition-property: opacity, color, background-color, border-color, box-shadow !important;
  }

  [data-motion-kind="continuous"] {
    animation: none !important;
  }
}
```

减弱动态不是删除所有反馈：颜色、透明度和焦点反馈必须保留；只去除位移、缩放、旋转和持续脉冲。对于依赖 transform 完成基础定位的组件（例如居中 Modal），用局部 `--motion-reduced-transform` 保留非动效定位基线。

## Repo conventions to follow

- 全局设计变量已经位于 `web/src/app/globals.css:3` 的 `:root`，新 token 继续放在这里。
- Tailwind v4 通过 `web/src/app/globals.css:1` 的 `@import "tailwindcss"` 加载；不要创建第二套 Tailwind 配置。
- 后续组件通过 `duration-[var(--duration-press)]` 和 `ease-[var(--ease-out)]` 使用 token。

## Steps

1. 修改 `web/src/app/globals.css`，在现有 glass token 之后加入上述 8 个动效 token。
2. 在文件末尾加入上述 `prefers-reduced-motion` 媒体查询。
3. 增加一个样式契约测试，读取 `globals.css` 并断言三个缓动 token、五个持续时间 token和媒体查询存在；测试文件放在 `web/src/app/globals.motion.test.ts`。
4. 不给任何元素添加动画；本计划只建立基础契约。

## Boundaries

- Do NOT 修改任何业务组件。
- Do NOT 增加依赖或 Tailwind 动效插件。
- Do NOT 使用 `* { animation: none }` 之类的全局清除规则。
- 如果 `globals.css` 已出现同名 token，停止并报告，不得创建近似命名。

## Verification

- **Mechanical**: 在 `web/` 运行 `npx vitest run src/app/globals.motion.test.ts`、`npx tsc --noEmit`、`npx eslint src/app/globals.motion.test.ts`、`npm run build`，全部退出码为 0。
- **Feel check**: 本计划不改变当前视觉；在浏览器 DevTools Rendering 面板切换 `prefers-reduced-motion`，页面布局和颜色不得变化。
- **Done when**: token 只有一处权威定义，减弱动态选择器存在，且没有业务页面视觉回归。
