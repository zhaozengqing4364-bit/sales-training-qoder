"use client";

import { ChevronDown, ChevronUp, Copy, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ActivityType, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import type { EditorSelection } from "@/lib/newcomer-training/editor-state";
import { ACTIVITY_PRESENTATIONS } from "@/lib/newcomer-training/activity-registry";

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
    return <span className="ml-auto flex shrink-0 gap-1">
        <Button type="button" size="icon" variant="ghost" className="h-7 w-7" disabled={first}
            aria-label={`上移 ${title}`} onClick={(event) => { event.stopPropagation(); onMove("up"); }}>
            <ChevronUp className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="icon" variant="ghost" className="h-7 w-7" disabled={last}
            aria-label={`下移 ${title}`} onClick={(event) => { event.stopPropagation(); onMove("down"); }}>
            <ChevronDown className="h-3.5 w-3.5" />
        </Button>
    </span>;
}

export function PathOutline(props: PathOutlineProps) {
    const selectedId = props.selection.kind === "path" ? "path" :
        props.selection.kind === "phase" ? props.selection.phase_id :
            props.selection.kind === "module" ? props.selection.module_id : props.selection.activity_id;
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

    return <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-2">
            <button type="button" onClick={() => props.onSelect({ kind: "path" })}
                className={`rounded-lg px-2 py-1 text-left text-sm font-semibold ${selectedId === "path" ? "bg-slate-900 text-white" : "text-slate-800"}`}>
                训练路径大纲
            </button>
            <Button type="button" size="icon" variant="ghost" className="h-8 w-8" aria-label="新增阶段" onClick={props.onAddPhase}>
                <Plus className="h-4 w-4" />
            </Button>
        </div>
        <div role="tree" aria-label="训练路径大纲" className="space-y-2">
            {props.path.phases.length === 0 && <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-500">还没有阶段，先新增一个阶段。</p>}
            {props.path.phases.map((phase, phaseIndex) => <div key={phase.phase_id} role="treeitem" aria-level={1}
                draggable onDragStart={(event) => dragStart(event, "phase", phase.phase_id)}
                onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, "phase", phase.phase_id)}
                className="rounded-xl border border-slate-200 bg-slate-50 p-2">
                <div className="flex items-center gap-1">
                    <button type="button" aria-label={`编辑阶段 ${phase.title}`} onClick={() => props.onSelect({ kind: "phase", phase_id: phase.phase_id })}
                        className={`min-w-0 flex-1 truncate rounded-lg px-2 py-1 text-left text-sm font-medium ${selectedId === phase.phase_id ? "bg-blue-100 text-blue-800" : "text-slate-800"}`}>
                        {phase.title}
                    </button>
                    <MoveButtons title={phase.title} first={phaseIndex === 0} last={phaseIndex === props.path.phases.length - 1}
                        onMove={(direction) => props.onMove("phase", phase.phase_id, direction)} />
                    <Button type="button" size="icon" variant="ghost" className="h-7 w-7" aria-label={`复制阶段 ${phase.title}`} onClick={() => props.onDuplicate("phase", phase.phase_id)}><Copy className="h-3.5 w-3.5" /></Button>
                    <Button type="button" size="icon" variant="ghost" className="h-7 w-7 text-red-600" aria-label={`删除阶段 ${phase.title}`} onClick={() => props.onDelete("phase", phase.phase_id, phase.title)}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
                <div role="group" className="mt-2 space-y-2 pl-3">
                    {phase.modules.map((module, moduleIndex) => <div key={module.module_id} role="treeitem" aria-level={2}
                        data-kind="module" data-title={module.title} draggable
                        onDragStart={(event) => dragStart(event, "module", module.module_id)}
                        onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, "module", module.module_id)}
                        className="rounded-lg border border-slate-200 bg-white p-1.5">
                        <div className="flex items-center gap-1">
                            <button type="button" aria-label={`编辑模块 ${module.title}`} onClick={() => props.onSelect({ kind: "module", module_id: module.module_id })}
                                className={`min-w-0 flex-1 truncate rounded-md px-2 py-1 text-left text-sm ${selectedId === module.module_id ? "bg-blue-100 text-blue-800" : "text-slate-700"}`}>{module.title}</button>
                            <MoveButtons title={module.title} first={moduleIndex === 0} last={moduleIndex === phase.modules.length - 1}
                                onMove={(direction) => props.onMove("module", module.module_id, direction)} />
                            <Button type="button" size="icon" variant="ghost" className="h-7 w-7" aria-label={`复制模块 ${module.title}`} onClick={() => props.onDuplicate("module", module.module_id)}><Copy className="h-3.5 w-3.5" /></Button>
                            <Button type="button" size="icon" variant="ghost" className="h-7 w-7 text-red-600" aria-label={`删除模块 ${module.title}`} onClick={() => props.onDelete("module", module.module_id, module.title)}><Trash2 className="h-3.5 w-3.5" /></Button>
                        </div>
                        <div role="group" className="mt-1 space-y-1 pl-3">
                            {module.activities.map((activity, activityIndex) => <div key={activity.activity_id} role="treeitem" aria-level={3}
                                draggable onDragStart={(event) => dragStart(event, "activity", activity.activity_id)}
                                onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, "activity", activity.activity_id)}
                                className="flex items-center gap-1 rounded-md px-1 hover:bg-slate-50">
                                <button type="button" aria-label={`编辑活动 ${activity.title}`} onClick={() => props.onSelect({ kind: "activity", activity_id: activity.activity_id })}
                                    className={`min-w-0 flex-1 truncate rounded-md px-2 py-1 text-left text-xs ${selectedId === activity.activity_id ? "bg-blue-100 text-blue-800" : "text-slate-600"}`}>
                                    {activity.title} · {ACTIVITY_PRESENTATIONS[activity.type].label}
                                </button>
                                <MoveButtons title={activity.title} first={activityIndex === 0} last={activityIndex === module.activities.length - 1}
                                    onMove={(direction) => props.onMove("activity", activity.activity_id, direction)} />
                                <Button type="button" size="icon" variant="ghost" className="h-7 w-7" aria-label={`复制活动 ${activity.title}`} onClick={() => props.onDuplicate("activity", activity.activity_id)}><Copy className="h-3.5 w-3.5" /></Button>
                                <Button type="button" size="icon" variant="ghost" className="h-7 w-7 text-red-600" aria-label={`删除活动 ${activity.title}`} onClick={() => props.onDelete("activity", activity.activity_id, activity.title)}><Trash2 className="h-3.5 w-3.5" /></Button>
                            </div>)}
                            <label className="flex items-center gap-1 px-1 text-xs text-slate-500"><Plus className="h-3.5 w-3.5" /><span className="sr-only">新增活动</span><select aria-label={`为 ${module.title} 新增活动`} defaultValue="" className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs" onChange={(event) => { if (event.target.value) props.onAddActivity(module.module_id, event.target.value as ActivityType); event.target.value = ""; }}><option value="" disabled>新增活动…</option>{Object.values(ACTIVITY_PRESENTATIONS).map((item) => <option key={item.type} value={item.type}>{item.label}</option>)}</select></label>
                        </div>
                    </div>)}
                    <label className="flex items-center gap-1 px-1 text-xs text-slate-500"><Plus className="h-3.5 w-3.5" /><span className="sr-only">新增模块</span><select aria-label={`为 ${phase.title} 新增模块`} defaultValue="" className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs" onChange={(event) => { if (event.target.value) props.onAddModule(phase.phase_id, event.target.value as ActivityType); event.target.value = ""; }}><option value="" disabled>从模块模板新增…</option>{Object.values(ACTIVITY_PRESENTATIONS).map((item) => <option key={item.type} value={item.type}>{item.label}模块</option>)}</select></label>
                </div>
            </div>)}
        </div>
    </section>;
}
