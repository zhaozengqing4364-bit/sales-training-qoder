"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Copy, Plus, Search, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ActivityType, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import type { EditorSelection } from "@/lib/newcomer-training/editor-state";
import { ACTIVITY_PRESENTATIONS } from "@/lib/newcomer-training/activity-registry";
import { cn } from "@/lib/utils";

type OutlineKind = "phase" | "module" | "activity";
type DragItem = { kind: OutlineKind; id: string };

interface PathOutlineProps {
    path: TrainingPathPayload;
    selection: EditorSelection;
    onSelect: (selection: EditorSelection) => void;
    onMove: (kind: "phase" | "module" | "activity", id: string, direction: "up" | "down") => void;
    onDuplicate: (kind: "phase" | "module" | "activity", id: string) => void;
    onDelete: (kind: "phase" | "module" | "activity", id: string, title: string) => void;
    onAddPhase: () => void;
    onAddModule: (phaseId: string, template: ActivityType) => void;
    onAddActivity: (moduleId: string, type: ActivityType) => void;
    onDropItem: (kind: "phase" | "module" | "activity", sourceId: string, targetId: string) => void;
}

function MoveButtons({ title, first, last, onMove }: {
    title: string; first: boolean; last: boolean; onMove: (direction: "up" | "down") => void;
}) {
    return <span className="ml-auto flex shrink-0 gap-1 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100">
        <Button type="button" size="icon" variant="ghost" className="h-10 w-10" disabled={first}
            aria-label={`上移 ${title}`} onClick={(event) => { event.stopPropagation(); onMove("up"); }}>
            <ChevronUp className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="icon" variant="ghost" className="h-10 w-10" disabled={last}
            aria-label={`下移 ${title}`} onClick={(event) => { event.stopPropagation(); onMove("down"); }}>
            <ChevronDown className="h-3.5 w-3.5" />
        </Button>
    </span>;
}

export function PathOutline(props: PathOutlineProps) {
    const pathPhases = props.path.phases;
    const [query, setQuery] = useState("");
    const [expanded, setExpanded] = useState<Record<string, boolean>>(() => Object.fromEntries(pathPhases.map((phase, index) => [phase.phase_id, index === 0])));
    const [draggedItem, setDraggedItem] = useState<DragItem | null>(null);
    const [dropTarget, setDropTarget] = useState<DragItem | null>(null);
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const visiblePhases = useMemo(() => pathPhases.map((phase) => {
        if (!normalizedQuery || `${phase.title} ${phase.outcome ?? ""}`.toLocaleLowerCase().includes(normalizedQuery)) return phase;
        const modules = phase.modules.map((moduleConfig) => {
            if (`${moduleConfig.title} ${moduleConfig.outcome ?? ""}`.toLocaleLowerCase().includes(normalizedQuery)) return moduleConfig;
            const activities = moduleConfig.activities.filter((activity) => `${activity.title} ${ACTIVITY_PRESENTATIONS[activity.type].label}`.toLocaleLowerCase().includes(normalizedQuery));
            return activities.length ? { ...moduleConfig, activities } : null;
        }).filter((item): item is typeof phase.modules[number] => item !== null);
        return modules.length ? { ...phase, modules } : null;
    }).filter((item): item is typeof pathPhases[number] => item !== null), [normalizedQuery, pathPhases]);
    const selectedId = props.selection.kind === "path" ? "path" :
        props.selection.kind === "phase" ? props.selection.phase_id :
            props.selection.kind === "module" ? props.selection.module_id : props.selection.activity_id;
    const resetDragState = () => {
        setDraggedItem(null);
        setDropTarget(null);
    };
    const dragStart = (event: React.DragEvent, kind: OutlineKind, id: string) => {
        event.stopPropagation();
        event.dataTransfer.setData("application/x-training-outline", JSON.stringify({ kind, id }));
        event.dataTransfer.effectAllowed = "move";
        setDraggedItem({ kind, id });
        setDropTarget(null);
    };
    const dragOver = (event: React.DragEvent, kind: OutlineKind, targetId: string) => {
        event.stopPropagation();
        const validTarget = draggedItem?.kind === kind && draggedItem.id !== targetId;
        if (!validTarget) {
            event.dataTransfer.dropEffect = "none";
            setDropTarget(null);
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        setDropTarget((current) => current?.kind === kind && current.id === targetId
            ? current
            : { kind, id: targetId });
    };
    const dragLeave = (event: React.DragEvent, kind: OutlineKind, targetId: string) => {
        event.stopPropagation();
        if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return;
        setDropTarget((current) => current?.kind === kind && current.id === targetId ? null : current);
    };
    const drop = (event: React.DragEvent, kind: OutlineKind, targetId: string) => {
        event.stopPropagation();
        try {
            const source = JSON.parse(event.dataTransfer.getData("application/x-training-outline")) as { kind: string; id: string };
            if (source.kind === kind && source.id !== targetId) {
                event.preventDefault();
                props.onDropItem(kind, source.id, targetId);
            }
        } catch { /* malformed browser drag payload is ignored */ }
        finally { resetDragState(); }
    };
    const dragStateProps = (kind: OutlineKind, id: string) => {
        const isDragging = draggedItem?.kind === kind && draggedItem.id === id;
        const isDropTarget = dropTarget?.kind === kind && dropTarget.id === id;
        return {
            isDragging,
            isDropTarget,
            className: cn(
                "transition-[opacity,transform,box-shadow] duration-[var(--duration-press)] ease-[var(--ease-out)] motion-reduce:transform-none",
                isDragging && "opacity-50 scale-[0.97]",
                isDropTarget && "ring-2 ring-blue-400 ring-offset-1",
            ),
        };
    };

    return <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-2">
            <button type="button" onClick={() => props.onSelect({ kind: "path" })}
                className={`rounded-lg px-2 py-1 text-left text-sm font-semibold ${selectedId === "path" ? "bg-slate-900 text-white" : "text-slate-800"}`}>
                训练路径大纲
            </button>
            <Button type="button" size="icon" variant="ghost" className="h-10 w-10" aria-label="新增阶段" onClick={props.onAddPhase}>
                <Plus className="h-4 w-4" />
            </Button>
        </div>
        <label className="relative mb-3 block"><span className="sr-only">搜索路径大纲</span><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" /><input type="search" aria-label="搜索路径大纲" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索阶段、模块或活动" className="h-10 w-full rounded-xl border border-slate-200 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100" /></label>
        <div role="tree" aria-label="训练路径大纲" className="space-y-2">
            {props.path.phases.length === 0 && <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-500">还没有阶段，先新增一个阶段。</p>}
            {props.path.phases.length > 0 && visiblePhases.length === 0 ? <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-500">没有匹配的阶段、模块或活动。</p> : null}
            {visiblePhases.map((phase) => { const phaseIndex = pathPhases.findIndex((item) => item.phase_id === phase.phase_id); const isExpanded = Boolean(expanded[phase.phase_id]) || Boolean(normalizedQuery); const dragState = dragStateProps("phase", phase.phase_id); return <div key={phase.phase_id} role="treeitem" aria-level={1} aria-selected={selectedId === phase.phase_id}
                draggable aria-grabbed={dragState.isDragging} data-dragging={dragState.isDragging || undefined} data-drop-target={dragState.isDropTarget || undefined}
                onDragStart={(event) => dragStart(event, "phase", phase.phase_id)} onDragEnd={(event) => { event.stopPropagation(); resetDragState(); }}
                onDragOver={(event) => dragOver(event, "phase", phase.phase_id)} onDragLeave={(event) => dragLeave(event, "phase", phase.phase_id)} onDrop={(event) => drop(event, "phase", phase.phase_id)}
                className={cn("rounded-xl border border-slate-200 bg-slate-50 p-2", dragState.className)}>
                <div className="group/row flex items-center gap-1">
                    <Button type="button" size="icon" variant="ghost" className="h-10 w-10" aria-label={`${isExpanded ? "折叠" : "展开"}阶段 ${phase.title}`} onClick={() => setExpanded((current) => ({ ...current, [phase.phase_id]: !isExpanded }))}>{isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</Button>
                    <button type="button" aria-label={`编辑阶段 ${phase.title}`} onClick={() => props.onSelect({ kind: "phase", phase_id: phase.phase_id })}
                        className={`min-h-10 min-w-0 flex-1 truncate rounded-lg px-2 py-1 text-left text-sm font-medium ${selectedId === phase.phase_id ? "bg-blue-100 text-blue-800" : "text-slate-800"}`}>
                        {phase.title}
                    </button>
                    <MoveButtons title={phase.title} first={phaseIndex === 0} last={phaseIndex === props.path.phases.length - 1}
                        onMove={(direction) => props.onMove("phase", phase.phase_id, direction)} />
                    <Button type="button" size="icon" variant="ghost" className="h-10 w-10 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100" aria-label={`复制阶段 ${phase.title}`} onClick={() => props.onDuplicate("phase", phase.phase_id)}><Copy className="h-3.5 w-3.5" /></Button>
                    <Button type="button" size="icon" variant="ghost" className="h-10 w-10 text-red-600 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100" aria-label={`删除阶段 ${phase.title}`} onClick={() => props.onDelete("phase", phase.phase_id, phase.title)}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
                {isExpanded ? <div role="group" className="mt-2 space-y-2 pl-3">
                    {phase.modules.map((module) => { const originalPhase = pathPhases.find((item) => item.phase_id === phase.phase_id)!; const moduleIndex = originalPhase.modules.findIndex((item) => item.module_id === module.module_id); const dragState = dragStateProps("module", module.module_id); return <div key={module.module_id} role="treeitem" aria-level={2} aria-selected={selectedId === module.module_id}
                        data-kind="module" data-title={module.title} draggable aria-grabbed={dragState.isDragging} data-dragging={dragState.isDragging || undefined} data-drop-target={dragState.isDropTarget || undefined}
                        onDragStart={(event) => dragStart(event, "module", module.module_id)} onDragEnd={(event) => { event.stopPropagation(); resetDragState(); }}
                        onDragOver={(event) => dragOver(event, "module", module.module_id)} onDragLeave={(event) => dragLeave(event, "module", module.module_id)} onDrop={(event) => drop(event, "module", module.module_id)}
                        className={cn("rounded-lg border border-slate-200 bg-white p-1.5", dragState.className)}>
                        <div className="group/row flex items-center gap-1">
                            <button type="button" aria-label={`编辑模块 ${module.title}`} onClick={() => props.onSelect({ kind: "module", module_id: module.module_id })}
                                className={`min-h-10 min-w-0 flex-1 truncate rounded-md px-2 py-1 text-left text-sm ${selectedId === module.module_id ? "bg-blue-100 text-blue-800" : "text-slate-700"}`}>{module.title}</button>
                            <MoveButtons title={module.title} first={moduleIndex === 0} last={moduleIndex === phase.modules.length - 1}
                                onMove={(direction) => props.onMove("module", module.module_id, direction)} />
                            <Button type="button" size="icon" variant="ghost" className="h-10 w-10 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100" aria-label={`复制模块 ${module.title}`} onClick={() => props.onDuplicate("module", module.module_id)}><Copy className="h-3.5 w-3.5" /></Button>
                            <Button type="button" size="icon" variant="ghost" className="h-10 w-10 text-red-600 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100" aria-label={`删除模块 ${module.title}`} onClick={() => props.onDelete("module", module.module_id, module.title)}><Trash2 className="h-3.5 w-3.5" /></Button>
                        </div>
                        <div role="group" className="mt-1 space-y-1 pl-3">
                            {module.activities.map((activity, activityIndex) => { const dragState = dragStateProps("activity", activity.activity_id); return <div key={activity.activity_id} role="treeitem" aria-level={3} aria-selected={selectedId === activity.activity_id}
                                draggable aria-grabbed={dragState.isDragging} data-dragging={dragState.isDragging || undefined} data-drop-target={dragState.isDropTarget || undefined}
                                onDragStart={(event) => dragStart(event, "activity", activity.activity_id)} onDragEnd={(event) => { event.stopPropagation(); resetDragState(); }}
                                onDragOver={(event) => dragOver(event, "activity", activity.activity_id)} onDragLeave={(event) => dragLeave(event, "activity", activity.activity_id)} onDrop={(event) => drop(event, "activity", activity.activity_id)}
                                className={cn("group/row flex items-center gap-1 rounded-md px-1 hover:bg-slate-50", dragState.className)}>
                                <button type="button" aria-label={`编辑活动 ${activity.title}`} onClick={() => props.onSelect({ kind: "activity", activity_id: activity.activity_id })}
                                    className={`min-h-10 min-w-0 flex-1 truncate rounded-md px-2 py-1 text-left text-xs ${selectedId === activity.activity_id ? "bg-blue-100 text-blue-800" : "text-slate-600"}`}>
                                    {activity.title} · {ACTIVITY_PRESENTATIONS[activity.type].label}
                                </button>
                                <MoveButtons title={activity.title} first={activityIndex === 0} last={activityIndex === module.activities.length - 1}
                                    onMove={(direction) => props.onMove("activity", activity.activity_id, direction)} />
                                <Button type="button" size="icon" variant="ghost" className="h-10 w-10 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100" aria-label={`复制活动 ${activity.title}`} onClick={() => props.onDuplicate("activity", activity.activity_id)}><Copy className="h-3.5 w-3.5" /></Button>
                                <Button type="button" size="icon" variant="ghost" className="h-10 w-10 text-red-600 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100" aria-label={`删除活动 ${activity.title}`} onClick={() => props.onDelete("activity", activity.activity_id, activity.title)}><Trash2 className="h-3.5 w-3.5" /></Button>
                            </div>})}
                            <label className="flex items-center gap-1 px-1 text-xs text-slate-500"><Plus className="h-3.5 w-3.5" /><span className="sr-only">新增活动</span><select aria-label={`为 ${module.title} 新增活动`} defaultValue="" className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs" onChange={(event) => { if (event.target.value) props.onAddActivity(module.module_id, event.target.value as ActivityType); event.target.value = ""; }}><option value="" disabled>新增活动…</option>{Object.values(ACTIVITY_PRESENTATIONS).map((item) => <option key={item.type} value={item.type}>{item.label}</option>)}</select></label>
                        </div>
                    </div>})}
                    <label className="flex items-center gap-1 px-1 text-xs text-slate-500"><Plus className="h-3.5 w-3.5" /><span className="sr-only">新增模块</span><select aria-label={`为 ${phase.title} 新增模块`} defaultValue="" className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs" onChange={(event) => { if (event.target.value) props.onAddModule(phase.phase_id, event.target.value as ActivityType); event.target.value = ""; }}><option value="" disabled>从模块模板新增…</option>{Object.values(ACTIVITY_PRESENTATIONS).map((item) => <option key={item.type} value={item.type}>{item.label}模块</option>)}</select></label>
                </div> : null}
            </div>})}
        </div>
    </section>;
}
