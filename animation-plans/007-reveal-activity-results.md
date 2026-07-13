# 007 — 平稳呈现活动结果

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: MEDIUM
- **Category**: Feedback / Continuity
- **Estimated scope**: 3 files，约 45 行

## Problem

活动提交后的结果面板从不存在直接切换为完整卡片，没有帮助用户把“刚才的操作”与“新出现的结果”联系起来：

```tsx
/* web/src/components/newcomer-training/activity-result-panel.tsx:27-30 — current */
return <section aria-live="polite" className={`rounded-2xl border p-5 ${completed ? "border-emerald-200 bg-emerald-50" : failed ? "border-amber-200 bg-amber-50" : "border-blue-200 bg-blue-50"}`}>
    <div className="flex items-start gap-3"><Icon className="mt-0.5 h-5 w-5 shrink-0" /><div><h2 className="font-semibold text-slate-900">{title}</h2><p className="mt-1 text-sm text-slate-600">{description}</p>{typeof score === "number" ? <p className="mt-3 text-2xl font-semibold text-slate-900">{score} / {maxScore ?? 100}</p> : null}</div></div>
    <div className="mt-4 flex flex-wrap gap-2"><Link className="inline-flex h-10 items-center rounded-full bg-slate-900 px-4 text-sm font-medium text-white" href={`/newcomer-training/modules/${encodeURIComponent(moduleId)}`}>返回模块</Link>{failed ? <span className="inline-flex items-center gap-1 text-sm text-amber-800"><RotateCcw className="h-4 w-4" />可在下方重试</span> : null}</div>
</section>;
```

这是低频、重要的状态变化，适合一次短促的入场反馈；不需要持续动画或等待动画。

## Target

在 `web/src/app/globals.css` 增加挂载时生效的 CSS 入场类：

```css
.motion-result-reveal {
  opacity: 1;
  transform: scale(1);
  transition:
    opacity var(--duration-popover) var(--ease-out),
    transform var(--duration-popover) var(--ease-out);
}

@starting-style {
  .motion-result-reveal {
    opacity: 0;
    transform: scale(0.97);
  }
}

@media (prefers-reduced-motion: reduce) {
  .motion-result-reveal {
    transform: none;
    transition: opacity var(--duration-tooltip) var(--ease-out);
  }

  @starting-style {
    .motion-result-reveal {
      opacity: 0;
      transform: none;
    }
  }
}
```

结果面板添加 `motion-result-reveal` 和 `data-motion-kind="spatial"`。正常模式从 `scale(0.97)` + `opacity: 0` 在 200ms 内到稳定态；减弱动态只做 160ms 透明度变化。

## Repo conventions to follow

- 使用计划 001 的 `--duration-popover: 200ms`、`--duration-tooltip: 160ms` 与 `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`。
- 保留当前 `aria-live="polite"`，结果文案仍由既有状态决定。
- 沿用 globals.css 中 `.motion-*` 命名和 reduced-motion 合同，不引入客户端状态。

## Steps

1. 在 `web/src/app/globals.css` 的 motion utilities 区域加入上面的 `.motion-result-reveal`、`@starting-style` 和 reduced-motion 规则。
2. 在 `web/src/components/newcomer-training/activity-result-panel.tsx:27` 给 section 添加 `motion-result-reveal` 与 `data-motion-kind="spatial"`，不改变 DOM 层级和业务条件。
3. 扩展 `web/src/components/newcomer-training/activity-result-panel.test.tsx`：分别渲染完成、未通过、处理中三种结果，断言动效类、`data-motion-kind`、`aria-live`、分数和操作文案保持正确。

## Boundaries

- Do NOT 把组件改成 client component，也不要引入 Framer Motion。
- Do NOT 延迟结果展示、逐字播放分数、循环闪烁或自动滚动页面。
- Do NOT 修改评分状态、链接目标、结果文案或颜色语义。
- Do NOT 使用 `scale(0)`；初始值必须是 `0.97`。
- If a step doesn't match the code you find (drift since the commit stamp), STOP and report instead of improvising.

## Verification

- **Mechanical**: 在 `web/` 运行 `npm test -- src/components/newcomer-training/activity-result-panel.test.tsx src/app/globals.motion.test.ts`、`npx eslint src/components/newcomer-training/activity-result-panel.tsx src/components/newcomer-training/activity-result-panel.test.tsx`、`npx tsc --noEmit`、`npm run build`，全部退出码为 0；检查生产 CSS 中存在 `.motion-result-reveal`。
- **Feel check**: 提交一次通过和一次未通过的活动，结果卡只在首次出现时轻微放大并淡入，内容立即可读，不应二次弹跳。Animations 面板调至 10%，确认变换中心稳定、卡片不推挤周围布局。
- **Reduced motion**: 开启 `prefers-reduced-motion` 后，卡片原地淡入 160ms，没有缩放。
- **Done when**: 三种结果状态都保持原业务行为，并在挂载时获得一次 200ms 的克制入场反馈；减弱动态仅淡入。
