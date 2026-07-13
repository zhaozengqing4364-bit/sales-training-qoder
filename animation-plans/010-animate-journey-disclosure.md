# 010 — 连贯展开训练阶段

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: MEDIUM
- **Category**: Continuity / Accessibility / Performance
- **Estimated scope**: 2 files，约 85 行

## Problem

学员端阶段折叠时只有箭头使用默认 transform transition，模块内容直接挂载或消失：

```tsx
/* web/src/components/newcomer-training/journey-outline.tsx:21-23 — current */
<span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{stateLabel}</span><ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
</button>
{open && <div className="border-t border-slate-100 px-4 py-3 sm:px-5"><ol className="space-y-2">{phase.modules.map((moduleConfig) => <li key={moduleConfig.module_id}><Link href={`/newcomer-training/modules/${encodeURIComponent(moduleConfig.module_id)}`} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"><span className="min-w-0"><span className="block text-sm font-medium text-slate-800">{moduleConfig.outcome || moduleConfig.title}</span><span className="mt-0.5 block text-xs text-slate-500">{moduleConfig.outcome ? `${moduleConfig.title} · ` : ""}{moduleConfig.locked ? moduleConfig.lock_reason : `${moduleConfig.completed_count}/${moduleConfig.total_required} 个必修活动`}</span></span><span className="shrink-0 text-xs text-slate-500">{moduleConfig.activities.find((item) => !item.completed)?.locked ? "等待解锁" : activityStatusLabel(moduleConfig.activities.find((item) => !item.completed) ?? moduleConfig.activities.at(-1)!)}</span></Link></li>)}</ol></div>}
```

箭头和内容的节奏不一致，内容突现；默认 transition 也没有明确时长、曲线或减弱动态分支。

## Target

使用项目已有 Framer Motion，为内容增加 200ms 的 opacity + 8px 位移，不动画 height：

```tsx
const reduceMotion = useReducedMotion();
const hiddenTransform = reduceMotion ? "translate3d(0,0,0)" : "translate3d(0,-8px,0)";

<AnimatePresence initial={false}>
  {open ? (
    <motion.div
      key="content"
      initial={{ opacity: 0, transform: hiddenTransform }}
      animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
      exit={{ opacity: 0, transform: hiddenTransform }}
      transition={{
        duration: reduceMotion ? 0.16 : 0.2,
        ease: [0.23, 1, 0.32, 1],
      }}
      data-motion-kind="spatial"
      className="border-t border-slate-100 px-4 py-3 sm:px-5"
    >
      {/* existing ordered list unchanged */}
    </motion.div>
  ) : null}
</AnimatePresence>
```

箭头明确使用 200ms `--ease-out`；减弱动态时禁用旋转并让内容只淡入淡出 160ms。内容关闭期间不得设 `height: 0`，避免 Layout 帧和文字挤压。

## Repo conventions to follow

- 继续使用已安装的 `framer-motion@12.25.0`；不新增依赖。
- Framer 禁止 `x`、`y`、`scale` 简写，必须使用完整 `transform` 字符串。
- 使用 `--duration-popover: 200ms`、`--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`；Framer 对应 `duration: 0.2` 与 `ease: [0.23, 1, 0.32, 1]`。
- 保留原生 button、`aria-expanded`、初始只展开当前阶段和所有 Link 行为。

## Steps

1. 在 `web/src/components/newcomer-training/journey-outline.tsx` 从 `framer-motion` 导入 `AnimatePresence`、`motion`、`useReducedMotion`，在组件顶层读取 reduced-motion 偏好。
2. 将条件渲染的内容容器包入 `AnimatePresence initial={false}`；使用上面的完整 transform、duration 和 easing，保留现有 `<ol>` 及链接结构。
3. 把 ChevronDown 的类改为 `transition-transform duration-[var(--duration-popover)] ease-[var(--ease-out)] motion-reduce:transform-none`；`open` 时仍旋转 180°，减弱动态下由 `aria-expanded` 和内容可见性表达状态。
4. 新增 `web/src/components/newcomer-training/journey-outline.test.tsx`：断言默认只展开当前阶段、点击后 `aria-expanded` 变化、内容挂载/退出、链接保持正确，并 mock `matchMedia` 覆盖 reduced-motion。
5. 生产构建前后记录 `/newcomer-training` 客户端 chunk 的 gzip 体积。若首次加载 gzip 增量超过 15KB，STOP 并报告；不要擅自换成 height 动画。可接受的后续决策是改用 CSS `@starting-style` 仅处理入场、关闭即时隐藏。

## Boundaries

- Do NOT 动画化 height、max-height、grid-template-rows、padding、margin 或 border-width。
- Do NOT 修改阶段解锁、当前阶段计算、模块排序、链接或状态文案。
- Do NOT 使用 Framer `x/y/scale` 简写。
- Do NOT 让页面首次渲染时当前阶段重播入场；`AnimatePresence` 必须 `initial={false}`。
- Do NOT 引入新的 motion 依赖。
- If a step doesn't match the code you find (drift since the commit stamp), STOP and report instead of improvising.

## Verification

- **Mechanical**: 在 `web/` 运行 `npm test -- src/components/newcomer-training/journey-outline.test.tsx src/components/newcomer-training/journey-home.test.tsx`、`npx eslint src/components/newcomer-training/journey-outline.tsx src/components/newcomer-training/journey-outline.test.tsx`、`npx tsc --noEmit`、`npm run build`，全部退出码为 0；记录并比较 `/newcomer-training` 客户端 chunk gzip 体积，增量不超过 15KB。
- **Feel check**: 连续展开/折叠不同阶段，内容应从上方 8px 内平滑接入，关闭可中断，不出现文字压扁、卡片跳高动画或残留内容。Animations 面板调至 10%，确认只更新 transform/opacity，没有 Layout。
- **Reduced motion**: 开启 `prefers-reduced-motion` 后，内容原地淡入淡出 160ms，箭头不旋转，按钮和 `aria-expanded` 仍准确。
- **Done when**: 箭头与内容反馈一致，展开/折叠可中断、无布局属性动画、初始页不重播，包体积在阈值内。
