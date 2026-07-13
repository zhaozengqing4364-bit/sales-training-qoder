# 006 — 补全路径拖拽反馈

- **Status**: DONE
- **Commit**: 19fb9e6e
- **Severity**: HIGH
- **Category**: Physicality / Feedback / Accessibility
- **Estimated scope**: 2 files，约 95 行

## Problem

路径大纲允许拖拽阶段、模块和活动，但开始拖拽、经过可放置目标和完成放置时没有任何视觉状态：

```tsx
/* web/src/components/admin/newcomer-training/path-outline.tsx:56-66 — current */
const dragStart = (event: React.DragEvent, kind: string, id: string) => {
    event.dataTransfer.setData("application/x-training-outline", JSON.stringify({ kind, id }));
    event.dataTransfer.effectAllowed = "move";
};
const drop = (event: React.DragEvent, kind: "phase" | "module" | "activity", targetId: string) => {
    event.preventDefault();
    try {
        const source = JSON.parse(event.dataTransfer.getData("application/x-training-outline")) as { kind: string; id: string };
        if (source.kind === kind) props.onDropItem(kind, source.id, targetId);
    } catch { /* malformed browser drag payload is ignored */ }
};
```

可拖拽节点本身也没有拖动态或目标态：

```tsx
/* web/src/components/admin/newcomer-training/path-outline.tsx:82-85 — current */
return <div key={phase.phase_id} role="treeitem" aria-level={1} aria-selected={selectedId === phase.phase_id}
    draggable onDragStart={(event) => dragStart(event, "phase", phase.phase_id)}
    onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, "phase", phase.phase_id)}
    className="rounded-xl border border-slate-200 bg-slate-50 p-2">
```

用户无法确认“正在移动谁”“当前位置能否放置”，容易误放；后台高频编辑因此显得生硬且不可靠。

## Target

在组件内维护唯一拖拽状态，禁止为反馈做布局动画：

```tsx
type OutlineKind = "phase" | "module" | "activity";
type DragItem = { kind: OutlineKind; id: string };

const [draggedItem, setDraggedItem] = useState<DragItem | null>(null);
const [dropTarget, setDropTarget] = useState<DragItem | null>(null);
```

三类节点统一应用以下状态：

```tsx
const isDragging = draggedItem?.kind === kind && draggedItem.id === id;
const isDropTarget = dropTarget?.kind === kind && dropTarget.id === id;

className={cn(
  "transition-[opacity,transform,box-shadow] duration-[var(--duration-press)] ease-[var(--ease-out)]",
  isDragging && "opacity-50 scale-[0.97]",
  isDropTarget && "ring-2 ring-blue-400 ring-offset-1",
  "motion-reduce:transform-none"
)}
```

拖拽源只缩到 `0.97` 并降低透明度；可放置目标只显示静态 ring。结束、取消、格式错误或成功 drop 后，两个状态都必须清空。不同层级和拖到自身时不得显示目标态，也不得触发 `onDropItem`。

## Repo conventions to follow

- 使用 `web/src/app/globals.css` 中计划 001 定义的 `--duration-press: 140ms` 与 `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`。
- 继续保留现有上移/下移按钮作为键盘可用的排序方式；拖拽不是唯一入口。
- 复用项目已有 `cn` 工具，不手写重复字符串拼接。

## Steps

1. 在 `web/src/components/admin/newcomer-training/path-outline.tsx` 定义 `OutlineKind`、`DragItem`、`draggedItem` 和 `dropTarget`。
2. 收窄 `dragStart` 的 `kind` 类型；写入 payload 后设置拖拽源状态，并在 `onDragEnd` 无条件清空两个状态。
3. 增加 `dragOver(event, kind, id)`：只有当前拖拽项同类且不是自身时才 `preventDefault()`、设置 `dropEffect = "move"` 和目标态；不合法时设置 `dropEffect = "none"` 并清空目标态。
4. 修改 `drop`：校验同类且不是自身后才调用 `onDropItem`；使用 `finally` 无条件清空两个状态。
5. 把阶段、模块、活动三类节点都接到统一的 start/over/drop/end 处理器；添加 `aria-grabbed={isDragging}` 与 `data-dragging`、`data-drop-target` 供测试和调试观察。
6. 新增 `web/src/components/admin/newcomer-training/path-outline.test.tsx`，用 `fireEvent.dragStart/dragOver/drop/dragEnd` 覆盖合法同类放置、跨层级拒绝、自身拒绝、取消后复位，并确认上移/下移按钮仍可用。

## Boundaries

- Do NOT 改变 `onDropItem` 契约、排序算法、树结构或保存流程。
- Do NOT 动画化高度、位置重排、边框宽度或其他会触发布局的属性。
- Do NOT 引入拖拽依赖；继续使用原生 HTML Drag and Drop。
- Do NOT 删除键盘上移/下移能力。
- If a step doesn't match the code you find (drift since the commit stamp), STOP and report instead of improvising.

## Verification

- **Mechanical**: 在 `web/` 运行 `npm test -- src/components/admin/newcomer-training/path-outline.test.tsx src/components/admin/newcomer-training/path-editor.test.tsx`、`npx eslint src/components/admin/newcomer-training/path-outline.tsx src/components/admin/newcomer-training/path-outline.test.tsx`、`npx tsc --noEmit`、`npm run build`，全部退出码为 0。
- **Feel check**: 在管理端分别拖动阶段、模块、活动；源节点应轻微缩小且半透明，只有同层其他节点出现清晰 ring。快速来回经过多个目标时 ring 不应残留或闪烁；放置后顺序正确且状态立即清除。DevTools Animations 调到 10%，确认只有 opacity/transform/box-shadow，无 Layout。
- **Reduced motion**: 开启 `prefers-reduced-motion` 后，源节点只改变透明度、不缩放；静态目标 ring 保留。
- **Done when**: 三类拖拽均有明确源态和合法目标态，非法/取消/完成路径都不残留状态，键盘排序和保存行为无回归。
