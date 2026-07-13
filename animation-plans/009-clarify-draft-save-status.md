# 009 — 澄清草稿保存状态

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: MEDIUM
- **Category**: Feedback / Accessibility
- **Estimated scope**: 2 files，约 45 行

## Problem

管理端草稿状态在“有未保存修改”和“草稿已保存”之间直接切换，没有过渡，也没有 live status 语义：

```tsx
/* web/src/components/admin/newcomer-training/path-editor.tsx:174 — current */
<div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-semibold text-slate-950">新人训练路径</h1><span className={`rounded-full px-3 py-1 text-xs font-medium ${dirty ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>{dirty ? "有未保存修改" : "草稿已保存"}</span></div><p className="mt-1 text-sm text-slate-500">配置学员要完成的阶段、模块和任务。当前 {draft.phases.length} 个阶段、{moduleCount} 个模块。</p></div>
```

颜色和文案跳变不够连贯，屏幕阅读器也不会可靠播报保存完成；但这是高频状态，不能用位移、弹跳或反复闪烁抢注意力。

## Target

把 badge 变为稳定的状态区域，只过渡背景色与文字颜色 140ms：

```tsx
<span
  role="status"
  data-save-state={dirty ? "dirty" : "saved"}
  className={cn(
    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
    "transition-[color,background-color] duration-[var(--duration-press)] ease-[var(--ease-out)]",
    dirty ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800",
  )}
>
  {!dirty ? <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" /> : null}
  {dirty ? "有未保存修改" : "草稿已保存"}
</span>
```

不增加移动和缩放。`role="status"` 提供 polite live region；只有保存成功态显示已有 `CheckCircle2` 图标，颜色不再是唯一信息来源。

## Repo conventions to follow

- 使用计划 001 的 `--duration-press: 140ms` 与 `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`。
- 使用项目现有 `cn` 工具以及已经从 `lucide-react` 导入的 `CheckCircle2`，不新增图标依赖。
- 保持 `dirty` 的来源和保存/发布成功后清零逻辑不变。

## Steps

1. 在 `web/src/components/admin/newcomer-training/path-editor.tsx` 把当前一行 span 展开为上面的结构；如文件尚未导入 `cn`，从既有 `@/lib/utils` 路径导入。
2. 添加 `role="status"`、`data-save-state` 和非装饰性文字；图标必须 `aria-hidden="true"`，避免重复播报。
3. 只给 color/background-color 添加 140ms transition，不加 transform、opacity、keyframes 或 `transition-all`。
4. 扩展 `web/src/components/admin/newcomer-training/path-editor.test.tsx`：初始态为 saved；任意字段变化后为 dirty；保存成功后恢复 saved；保存失败后保持 dirty；断言 `role=status`、data 属性、文字和图标状态。

## Boundaries

- Do NOT 修改 `dirty` 状态机、保存/发布 API、错误处理或按钮 loading 行为。
- Do NOT 用 toast 替代页内持久状态，也不要重复播报用户每次输入。
- Do NOT 添加位移、缩放、循环动画或 `transition-all`。
- Do NOT 仅依靠颜色表达保存状态。
- If a step doesn't match the code you find (drift since the commit stamp), STOP and report instead of improvising.

## Verification

- **Mechanical**: 在 `web/` 运行 `npm test -- src/components/admin/newcomer-training/path-editor.test.tsx`、`npx eslint src/components/admin/newcomer-training/path-editor.tsx src/components/admin/newcomer-training/path-editor.test.tsx`、`npx tsc --noEmit`、`npm run build`，全部退出码为 0。
- **Feel check**: 连续修改多个字段再保存；badge 应保持原位，只在 140ms 内平滑切换颜色，成功图标清晰出现，不发生弹跳。快速输入时状态不应重启动画或影响键盘焦点。
- **Reduced motion**: 此方案本身不含空间运动；开启 `prefers-reduced-motion` 后仍可保留短促颜色过渡，状态文字和图标完整。
- **Done when**: 保存状态可由文字、图标、语义三种方式识别，颜色切换克制，失败不会错误显示“草稿已保存”。
