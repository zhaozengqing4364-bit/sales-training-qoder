# 008 — 强调全部训练完成

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: MEDIUM
- **Category**: Delight / Feedback
- **Estimated scope**: 3 files，约 50 行

## Problem

全部训练完成是学员路径中最稀有、最重要的里程碑，但目前和普通静态卡片一样瞬间出现：

```tsx
/* web/src/components/newcomer-training/journey-home.tsx:17-19 — current */
{mission
    ? <LearnerMissionCard mission={mission} actionHref={`/newcomer-training/activities/${encodeURIComponent(mission.activityId)}`} />
    : <section className="rounded-3xl border border-emerald-200 bg-white p-7 shadow-sm"><p className="text-xl font-semibold text-emerald-950">当前训练已全部完成</p><p className="mt-2 text-sm text-slate-600">你可以在训练记录中查看成绩和反馈。</p></section>}
```

缺少一次性完成反馈，会削弱闭环感；但此处也不适合使用彩纸、循环脉冲或大幅位移干扰阅读。

## Target

只给完成卡增加一次克制的 240ms 入场，普通当前任务卡保持静止：

```css
.motion-completion-reveal {
  opacity: 1;
  transform: scale(1);
  transition:
    opacity var(--duration-modal) var(--ease-out),
    transform var(--duration-modal) var(--ease-out);
}

@starting-style {
  .motion-completion-reveal {
    opacity: 0;
    transform: scale(0.97);
  }
}

@media (prefers-reduced-motion: reduce) {
  .motion-completion-reveal {
    transform: none;
    transition: opacity var(--duration-tooltip) var(--ease-out);
  }

  @starting-style {
    .motion-completion-reveal {
      opacity: 0;
      transform: none;
    }
  }
}
```

完成卡 section 使用 `motion-completion-reveal`、`data-motion-kind="spatial"` 和 `aria-live="polite"`。它从 `scale(0.97)` 淡入到 1，不移动位置、不循环；减弱动态只淡入 160ms。

## Repo conventions to follow

- 使用计划 001 的 `--duration-modal: 240ms`、`--duration-tooltip: 160ms` 与 `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`。
- 采用与计划 007 相同的 CSS `@starting-style` 模式，避免把服务端组件变成 client component。
- 学员端成功色和卡片结构保持现状。

## Steps

1. 在 `web/src/app/globals.css` motion utilities 区域加入 `.motion-completion-reveal`、对应 `@starting-style` 与 reduced-motion 规则。
2. 在 `web/src/components/newcomer-training/journey-home.tsx:19` 只给全部完成 section 添加 `motion-completion-reveal`、`data-motion-kind="spatial"`、`aria-live="polite"`；不要给 `LearnerMissionCard` 添加动效。
3. 扩展 `web/src/components/newcomer-training/journey-home.test.tsx`：断言有任务时没有完成动效类；全部完成时存在动效类、live region、完成文案和训练记录入口。

## Boundaries

- Do NOT 添加彩纸、粒子、音效、循环 pulse、自动跳转或额外成功弹窗。
- Do NOT 动画化 JourneyOutline 或普通当前任务卡。
- Do NOT 修改任务选择逻辑、完成判定或训练记录链接。
- Do NOT 使用大于 `scale(0.97)` 的初始缩小值，也不要 overshoot。
- If a step doesn't match the code you find (drift since the commit stamp), STOP and report instead of improvising.

## Verification

- **Mechanical**: 在 `web/` 运行 `npm test -- src/components/newcomer-training/journey-home.test.tsx src/app/globals.motion.test.ts`、`npx eslint src/components/newcomer-training/journey-home.tsx src/components/newcomer-training/journey-home.test.tsx`、`npx tsc --noEmit`、`npm run build`，全部退出码为 0；检查生产 CSS 包含 `.motion-completion-reveal`。
- **Feel check**: 用“仍有任务”和“全部完成”两组 journey 数据刷新页面；前者不应出现额外入场，后者只在完成卡首次挂载时有一次轻微淡入放大。Animations 面板调到 10%，确认无 overshoot、无布局变化、不会在重渲染时重复播放。
- **Reduced motion**: 开启 `prefers-reduced-motion` 后完成卡只原地淡入 160ms。
- **Done when**: 完成里程碑获得一次不打扰阅读的反馈，普通任务路径零新增动效，辅助技术能收到完成状态。
