"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Save, Send } from "lucide-react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import type { ActivityConfig, ActivityType, AssetRevisionSummary, ModuleConfig, PathIssue, PathValidationResponse, PhaseConfig, TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { ACTIVITY_PRESENTATIONS } from "@/lib/newcomer-training/activity-registry";
import { addActivity, addModule, addPhase, deleteActivity, deleteModule, deletePhase, duplicateActivity, duplicateModule, duplicatePhase, moveActivity, moveModule, movePhase, updateSelectedObject, type EditorSelection } from "@/lib/newcomer-training/editor-state";
import { PathInspector } from "./path-inspector";
import { PathOutline } from "./path-outline";
import { PathPreview } from "./path-preview";
import { PathValidationPanel } from "./path-validation-panel";
import { ResourcePickerDrawer, type ResourcePickerKind } from "./resource-picker-drawer";
import type { ActivityEditorResources, ResourceOption } from "./activity-editors/types";
import { PathRevisionHistory } from "./path-revision-history";

type Mutation = (path: TrainingPathPayload, reason: string, expectedRevisionId: string | null) => Promise<AssetRevisionSummary | void> | AssetRevisionSummary | void;

export interface PathEditorProps {
    initialModel: TrainingPathConfigResponse;
    onSave?: Mutation;
    onValidate?: (path: TrainingPathPayload) => Promise<PathValidationResponse> | PathValidationResponse;
    onPublish?: Mutation;
    resources?: ActivityEditorResources;
}

const EMPTY_RESOURCES: ActivityEditorResources = { learning_contents: [], exam_papers: [], scoring_rubrics: [], materials: [], practice_templates: [], runtime_profiles: [], coach_profiles: [] };

const nextId = () => crypto.randomUUID();

function defaultPhase(): PhaseConfig { return { phase_id: nextId(), title: "新阶段", description: null, order_index: 1, required: true, modules: [] }; }
function defaultModule(type: ActivityType): ModuleConfig {
    const activity = defaultActivity(type);
    return { module_id: nextId(), title: `${ACTIVITY_PRESENTATIONS[type].label}模块`, description: null, order_index: 1, required: true, estimated_minutes: null, audience_rule: { learner_levels: [], roles: [], departments: [] }, prerequisites: [], completion_policy: { mode: "all_required", activity_ids: [activity.activity_id], count: null }, activities: [activity] };
}
function defaultActivity(type: ActivityType = "lesson"): ActivityConfig {
    const base = { activity_id: nextId(), title: ACTIVITY_PRESENTATIONS[type].label, description: null, order_index: 1, required: true, estimated_minutes: null, prerequisites: [] };
    switch (type) {
        case "lesson": return { ...base, type, config: { learning_content_id: "", completion_mode: "all_chapters" } };
        case "quiz": return { ...base, type, config: { exam_paper_id: "", pass_score: 80, max_attempts: null } };
        case "audio_assessment": return { ...base, type, config: { scoring_rubric_id: "", material_id: null, pass_score: 80, max_attempts: null } };
        case "realtime_roleplay": return { ...base, type, config: { practice_template_id: "", runtime_profile_id: "", completion_mode: "session_completed" } };
        case "ai_coach": return { ...base, type, config: { coach_profile_id: "", completion_mode: "session_completed" } };
        case "assignment": return { ...base, type, config: { submission_type: "text_or_file", review_mode: "manual_review", max_file_size_bytes: 10_485_760 } };
    }
}

export function PathEditor({ initialModel, onSave, onValidate, onPublish, resources: initialResources = EMPTY_RESOURCES }: PathEditorProps) {
    const [draft, setDraft] = useState(initialModel.payload);
    const [selection, setSelection] = useState<EditorSelection>({ kind: "path" });
    const [validation, setValidation] = useState(initialModel.validation);
    const [reason, setReason] = useState("");
    const [dirty, setDirty] = useState(false);
    const [pending, setPending] = useState<"save" | "validate" | "publish" | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<{ kind: "phase" | "module" | "activity"; id: string; title: string } | null>(null);
    const [resources, setResources] = useState(initialResources);
    const [quickCreate, setQuickCreate] = useState<ResourcePickerKind | null>(null);
    const [revisionId, setRevisionId] = useState(initialModel.working_revision_id ?? initialModel.active_revision_id);
    const [publishConfirmOpen, setPublishConfirmOpen] = useState(false);

    useEffect(() => {
        const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
        window.addEventListener("beforeunload", beforeUnload);
        return () => window.removeEventListener("beforeunload", beforeUnload);
    }, [dirty]);

    const mutate = (transform: (path: TrainingPathPayload) => TrainingPathPayload) => { setDraft((current) => transform(current)); setDirty(true); setValidation(null); };
    const findSibling = (kind: "phase" | "module" | "activity", id: string, direction: "up" | "down") => {
        const list = kind === "phase" ? draft.phases : kind === "module" ? draft.phases.flatMap((phase) => phase.modules).find((item) => item.module_id === id) && draft.phases.find((phase) => phase.modules.some((item) => item.module_id === id))?.modules : draft.phases.flatMap((phase) => phase.modules).find((module) => module.activities.some((item) => item.activity_id === id))?.activities;
        if (!list) return null;
        const key = kind === "phase" ? "phase_id" : kind === "module" ? "module_id" : "activity_id";
        const index = list.findIndex((item) => (item as unknown as Record<string, string>)[key] === id);
        const target = list[index + (direction === "up" ? -1 : 1)];
        return target ? (target as unknown as Record<string, string>)[key] : null;
    };
    const move = (kind: "phase" | "module" | "activity", id: string, direction: "up" | "down") => {
        const target = findSibling(kind, id, direction); if (!target) return;
        const position = direction === "up" ? "before" : "after";
        mutate((path) => kind === "phase" ? movePhase(path, id, position, target) : kind === "module" ? moveModule(path, id, position, target) : moveActivity(path, id, position, target));
    };
    const focusIssue = (issue: PathIssue) => {
        if (draft.phases.some((item) => item.phase_id === issue.object_id)) setSelection({ kind: "phase", phase_id: issue.object_id });
        else if (draft.phases.some((phase) => phase.modules.some((item) => item.module_id === issue.object_id))) setSelection({ kind: "module", module_id: issue.object_id });
        else if (draft.phases.some((phase) => phase.modules.some((module) => module.activities.some((item) => item.activity_id === issue.object_id)))) setSelection({ kind: "activity", activity_id: issue.object_id });
        else setSelection({ kind: "path" });
    };
    const run = async (action: "save" | "validate" | "publish") => {
        if ((action === "save" || action === "publish") && !reason.trim()) { setError("请填写本次修改说明。"); return; }
        setPending(action); setError(null);
        try {
            if (action === "save") { const saved = await onSave?.(draft, reason.trim(), revisionId); if (saved) setRevisionId(saved.revision_id); setDirty(false); }
            if (action === "validate") { setValidation(await onValidate?.(draft) ?? { can_publish: true, issues: [] }); }
            if (action === "publish") { const published = await onPublish?.(draft, reason.trim(), revisionId); if (published) setRevisionId(published.revision_id); setDirty(false); setPublishConfirmOpen(false); }
        } catch (cause) { setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试。"); }
        finally { setPending(null); }
    };
    const moduleCount = useMemo(() => draft.phases.reduce((sum, phase) => sum + phase.modules.length, 0), [draft]);

    return <div className="space-y-4 pb-24">
        <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold text-slate-900">新人训练路径</h1><p className="mt-1 text-sm text-slate-500">按阶段、模块和活动组织训练内容。当前 {draft.phases.length} 个阶段、{moduleCount} 个模块。</p></div><span className={`rounded-full px-3 py-1 text-xs font-medium ${dirty ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>{dirty ? "有未保存修改" : "草稿已保存"}</span></header>
        {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <div className="grid gap-4 xl:grid-cols-[minmax(300px,0.9fr)_minmax(380px,1.15fr)_minmax(300px,0.9fr)]">
            <PathOutline path={draft} selection={selection} onSelect={setSelection} onMove={move}
                onDropItem={(kind, sourceId, targetId) => mutate((path) => kind === "phase" ? movePhase(path, sourceId, "before", targetId) : kind === "module" ? moveModule(path, sourceId, "before", targetId) : moveActivity(path, sourceId, "before", targetId))}
                onDuplicate={(kind, id) => mutate((path) => kind === "phase" ? duplicatePhase(path, id, nextId) : kind === "module" ? duplicateModule(path, id, nextId) : duplicateActivity(path, id, nextId))}
                onDelete={(kind, id, title) => setDeleteTarget({ kind, id, title })}
                onAddPhase={() => { const phase = defaultPhase(); mutate((path) => addPhase(path, phase)); setSelection({ kind: "phase", phase_id: phase.phase_id }); }}
                onAddModule={(phaseId, type) => { const moduleConfig = defaultModule(type); mutate((path) => addModule(path, phaseId, moduleConfig)); setSelection({ kind: "module", module_id: moduleConfig.module_id }); }}
                onAddActivity={(moduleId, type) => { const activity = defaultActivity(type); mutate((path) => addActivity(path, moduleId, activity)); setSelection({ kind: "activity", activity_id: activity.activity_id }); }} />
            <PathInspector path={draft} selection={selection} resources={resources} onQuickCreate={setQuickCreate} onPatch={(patch) => mutate((path) => updateSelectedObject(path, selection, patch))} onActivityChange={(activity) => mutate((path) => updateSelectedObject(path, selection, activity as unknown as Record<string, unknown>))} />
            <div className="space-y-4"><PathPreview path={draft} /><PathValidationPanel validation={validation} onFocusIssue={focusIssue} /><PathRevisionHistory currentRevisionId={revisionId} onRestored={(restored) => { setDraft(restored.payload); setRevisionId(restored.revision_id); setDirty(false); setValidation(null); setSelection({ kind: "path" }); }} /></div>
        </div>
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-6 py-3 backdrop-blur"><div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-end gap-3"><label className="mr-auto min-w-[260px] text-xs font-medium text-slate-600">修改说明<input aria-label="修改说明" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="例如：增加产品 A 训练模块" className="ml-2 w-72 rounded-full border border-slate-200 px-3 py-2 text-sm" /></label><Button variant="secondary" isLoading={pending === "save"} onClick={() => void run("save")}><Save className="mr-2 h-4 w-4" />保存草稿</Button><Button variant="outline" isLoading={pending === "validate"} onClick={() => void run("validate")}><CheckCircle2 className="mr-2 h-4 w-4" />检查并预览</Button><Button isLoading={pending === "publish"} onClick={() => { if (!reason.trim()) { setError("请填写本次修改说明。"); return; } setPublishConfirmOpen(true); }}><Send className="mr-2 h-4 w-4" />发布</Button></div></div>
        <ConfirmDialog open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }} title={`删除${deleteTarget?.title ?? "对象"}`} description="删除后，其下级内容也会从当前草稿移除。保存前仍可刷新页面放弃修改。" confirmText="删除" variant="danger" onConfirm={() => { if (!deleteTarget) return; const target = deleteTarget; mutate((path) => target.kind === "phase" ? deletePhase(path, target.id) : target.kind === "module" ? deleteModule(path, target.id) : deleteActivity(path, target.id)); setSelection({ kind: "path" }); setDeleteTarget(null); }} />
        <ConfirmDialog open={publishConfirmOpen} onOpenChange={setPublishConfirmOpen} title="确认发布训练路径" description="发布后只影响新进入训练的学员" confirmText="确认发布" isLoading={pending === "publish"} onConfirm={() => void run("publish")} />
        {quickCreate && <ResourcePickerDrawer kind={quickCreate} open onOpenChange={(open) => { if (!open) setQuickCreate(null); }} onCreated={(resource: ResourceOption) => {
            const key = quickCreate === "learning_content" ? "learning_contents" : quickCreate === "exam_paper" ? "exam_papers" : quickCreate === "material" ? "materials" : "scoring_rubrics";
            setResources((current) => ({ ...current, [key]: [...current[key], resource] }));
            const field = quickCreate === "learning_content" ? "learning_content_id" : quickCreate === "exam_paper" ? "exam_paper_id" : quickCreate === "material" ? "material_id" : "scoring_rubric_id";
            if (selection.kind === "activity") {
                const selectedActivity = draft.phases.flatMap((phase) => phase.modules).flatMap((moduleConfig) => moduleConfig.activities).find((item) => item.activity_id === selection.activity_id);
                if (selectedActivity) mutate((path) => updateSelectedObject(path, selection, { config: { ...selectedActivity.config, [field]: resource.id } }));
            }
            setQuickCreate(null);
        }} />}
    </div>;
}
