"use client";

import type { ActivityConfig, ModuleConfig, PhaseConfig, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import type { EditorSelection } from "@/lib/newcomer-training/editor-state";
import { ACTIVITY_PRESENTATIONS } from "@/lib/newcomer-training/activity-registry";
import { AiCoachEditor } from "./activity-editors/ai-coach-editor";
import { AssignmentEditor } from "./activity-editors/assignment-editor";
import { AudioAssessmentEditor } from "./activity-editors/audio-assessment-editor";
import { LessonEditor } from "./activity-editors/lesson-editor";
import { QuizEditor } from "./activity-editors/quiz-editor";
import { RealtimeRoleplayEditor } from "./activity-editors/realtime-roleplay-editor";
import type { ActivityEditorResources, QuickCreateKind } from "./activity-editors/types";
import { PathRuleEditor } from "./path-rule-editor";

interface PathInspectorProps {
    path: TrainingPathPayload;
    selection: EditorSelection;
    onPatch: (patch: Record<string, unknown>) => void;
    resources: ActivityEditorResources;
    onActivityChange: (activity: ActivityConfig) => void;
    onQuickCreate: (kind: QuickCreateKind) => void;
}

function Field({ label, value, onChange, multiline = false }: { label: string; value: string; onChange: (value: string) => void; multiline?: boolean }) {
    const className = "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";
    return <label className="block text-sm font-medium text-slate-700">{label}
        {multiline ? <textarea className={className} rows={4} value={value} onChange={(event) => onChange(event.target.value)} /> :
            <input className={className} value={value} onChange={(event) => onChange(event.target.value)} />}
    </label>;
}

function BaseForm({ name, title, description, required, estimatedMinutes, onPatch, children }: {
    name: string; title: string; description: string | null; required?: boolean; estimatedMinutes?: number | null;
    onPatch: (patch: Record<string, unknown>) => void; children?: React.ReactNode;
}) {
    return <form aria-label={name} onSubmit={(event) => event.preventDefault()} className="space-y-4">
        <Field label="名称" value={title} onChange={(value) => onPatch({ title: value })} />
        <Field label="说明" value={description ?? ""} multiline onChange={(value) => onPatch({ description: value || null })} />
        {required !== undefined && <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={required} onChange={(event) => onPatch({ required: event.target.checked })} />必修</label>}
        {estimatedMinutes !== undefined && <label className="block text-sm font-medium text-slate-700">预计用时（分钟）<input type="number" min={0} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" value={estimatedMinutes ?? ""} onChange={(event) => onPatch({ estimated_minutes: event.target.value ? Number(event.target.value) : null })} /></label>}
        {children}
    </form>;
}

function findSelected(path: TrainingPathPayload, selection: EditorSelection): TrainingPathPayload | PhaseConfig | ModuleConfig | ActivityConfig {
    if (selection.kind === "path") return path;
    for (const phase of path.phases) {
        if (selection.kind === "phase" && phase.phase_id === selection.phase_id) return phase;
        for (const moduleConfig of phase.modules) {
            if (selection.kind === "module" && moduleConfig.module_id === selection.module_id) return moduleConfig;
            if (selection.kind === "activity") {
                const activity = moduleConfig.activities.find((item) => item.activity_id === selection.activity_id);
                if (activity) return activity;
            }
        }
    }
    return path;
}

export function PathInspector({ path, selection, onPatch, resources, onActivityChange, onQuickCreate }: PathInspectorProps) {
    const selected = findSelected(path, selection);
    const activity = selection.kind === "activity" ? selected as ActivityConfig : null;
    const editor = activity?.type === "lesson" ? <LessonEditor value={activity} resources={resources} onChange={onActivityChange} onQuickCreate={onQuickCreate} /> :
        activity?.type === "quiz" ? <QuizEditor value={activity} resources={resources} onChange={onActivityChange} onQuickCreate={onQuickCreate} /> :
            activity?.type === "audio_assessment" ? <AudioAssessmentEditor value={activity} resources={resources} onChange={onActivityChange} onQuickCreate={onQuickCreate} /> :
                activity?.type === "realtime_roleplay" ? <RealtimeRoleplayEditor value={activity} resources={resources} onChange={onActivityChange} /> :
                    activity?.type === "ai_coach" ? <AiCoachEditor value={activity} resources={resources} onChange={onActivityChange} /> :
                        activity?.type === "assignment" ? <AssignmentEditor value={activity} resources={resources} onChange={onActivityChange} /> : null;
    return <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-5"><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">当前编辑</p><h2 className="mt-1 text-lg font-semibold text-slate-900">{selection.kind === "path" ? "路径设置" : selection.kind === "phase" ? "阶段设置" : selection.kind === "module" ? "模块设置" : "活动设置"}</h2></div>
        {selection.kind === "path" && <BaseForm name="路径设置" title={(selected as TrainingPathPayload).title} description={(selected as TrainingPathPayload).description} onPatch={onPatch} />}
        {selection.kind === "phase" && <BaseForm name="阶段设置" title={(selected as PhaseConfig).title} description={(selected as PhaseConfig).description} required={(selected as PhaseConfig).required} onPatch={onPatch} />}
        {selection.kind === "module" && <BaseForm name="模块设置" title={(selected as ModuleConfig).title} description={(selected as ModuleConfig).description} required={(selected as ModuleConfig).required} estimatedMinutes={(selected as ModuleConfig).estimated_minutes} onPatch={onPatch}><PathRuleEditor path={path} value={selected as ModuleConfig} onPatch={onPatch} /></BaseForm>}
        {selection.kind === "activity" && <BaseForm name="活动设置" title={(selected as ActivityConfig).title} description={(selected as ActivityConfig).description} required={(selected as ActivityConfig).required} estimatedMinutes={(selected as ActivityConfig).estimated_minutes} onPatch={onPatch}>
            <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600">活动类型：{ACTIVITY_PRESENTATIONS[(selected as ActivityConfig).type].label}</p>
            <PathRuleEditor path={path} value={selected as ActivityConfig} onPatch={onPatch} />
            {editor}
        </BaseForm>}
    </section>;
}
