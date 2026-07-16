"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, History, Info, Library, Monitor, PencilLine, Save, Send } from "lucide-react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/glass-modal";
import type { ActivityConfig, ActivityType, AssetRevisionSummary, ModuleConfig, PathIssue, PathValidationResponse, PhaseConfig, TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { generateClientId } from "@/lib/client-id";
import { ACTIVITY_PRESENTATIONS } from "@/lib/newcomer-training/activity-registry";
import { addActivity, addModule, addPhase, deleteActivity, deleteModule, deletePhase, duplicateActivity, duplicateModule, duplicatePhase, moveActivity, moveModule, movePhase, updateSelectedObject, type EditorSelection } from "@/lib/newcomer-training/editor-state";
import { cn } from "@/lib/utils";
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
    onResourcesNeeded?: (activityType: ActivityType) => void;
}

const EMPTY_RESOURCES: ActivityEditorResources = { learning_contents: [], exam_papers: [], scoring_rubrics: [], materials: [], practice_templates: [], runtime_profiles: [], coach_profiles: [] };

const nextId = generateClientId;

function defaultPhase(): PhaseConfig { return { phase_id: nextId(), title: "新阶段", description: null, outcome: null, order_index: 1, required: true, modules: [] }; }
function defaultModule(type: ActivityType): ModuleConfig {
    const activity = defaultActivity(type);
    return { module_id: nextId(), title: `${ACTIVITY_PRESENTATIONS[type].label}模块`, description: null, outcome: null, order_index: 1, required: true, estimated_minutes: null, audience_rule: { learner_levels: [], roles: [], departments: [] }, prerequisites: [], completion_policy: { mode: "all_required", activity_ids: [activity.activity_id], count: null }, activities: [activity] };
}
function defaultActivity(type: ActivityType = "lesson"): ActivityConfig {
    const base = { activity_id: nextId(), title: ACTIVITY_PRESENTATIONS[type].label, description: null, objective: null, why_it_matters: null, steps: [], success_criteria: [], primary_action_label: null, order_index: 1, required: true, estimated_minutes: null, prerequisites: [] };
    switch (type) {
        case "lesson": return { ...base, type, config: { learning_content_id: "", completion_mode: "all_chapters" } };
        case "quiz": return { ...base, type, config: { exam_paper_id: "", pass_score: 80, max_attempts: null } };
        case "audio_assessment": return { ...base, type, config: { scoring_rubric_id: "", material_id: null, pass_score: 80, max_attempts: null, example_transcript: null } };
        case "realtime_roleplay": return { ...base, type, config: { practice_template_id: "", runtime_profile_id: "", completion_mode: "session_completed" } };
        case "ai_coach": return { ...base, type, config: { coach_profile_id: "", completion_mode: "session_completed" } };
        case "assignment": return { ...base, type, config: { submission_type: "text_or_file", review_mode: "manual_review", max_file_size_bytes: 10_485_760 } };
    }
}

function normalizeLearnerCopy(path: TrainingPathPayload): TrainingPathPayload {
    const clean = (values: string[]) => values.map((value) => value.trim()).filter(Boolean);
    const normalizeActivity = (activity: ActivityConfig): ActivityConfig => {
        const learnerCopy = {
            steps: clean(activity.steps),
            success_criteria: clean(activity.success_criteria),
        };
        if (activity.type === "audio_assessment") {
            return {
                ...activity,
                ...learnerCopy,
                config: {
                    ...activity.config,
                    example_transcript: activity.config.example_transcript?.trim() || null,
                },
            };
        }
        return { ...activity, ...learnerCopy };
    };
    return {
        ...path,
        phases: path.phases.map((phase) => ({
            ...phase,
            modules: phase.modules.map((moduleConfig) => ({
                ...moduleConfig,
                activities: moduleConfig.activities.map(normalizeActivity),
            })),
        })),
    };
}

export function PathEditor({ initialModel, onSave, onValidate, onPublish, resources: initialResources = EMPTY_RESOURCES, onResourcesNeeded }: PathEditorProps) {
    const [draft, setDraft] = useState(initialModel.payload);
    const [selection, setSelection] = useState<EditorSelection>({ kind: "path" });
    const [validation, setValidation] = useState(initialModel.validation);
    const [reason, setReason] = useState("");
    const [dirty, setDirty] = useState(false);
    const [pending, setPending] = useState<"save" | "validate" | "publish" | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<{ kind: "phase" | "module" | "activity"; id: string; title: string } | null>(null);
    const [resources, setResources] = useState(initialResources);
    const previousInitialResources = useRef(initialResources);
    const [quickCreate, setQuickCreate] = useState<ResourcePickerKind | null>(null);
    const [revisionId, setRevisionId] = useState(initialModel.working_revision_id ?? initialModel.active_revision_id);
    const [publishConfirmOpen, setPublishConfirmOpen] = useState(false);
    const [workspaceMode, setWorkspaceMode] = useState<"edit" | "preview">("edit");
    const [recentlyAddedActivityId, setRecentlyAddedActivityId] = useState<string | null>(null);

    const selectedActivityType = useMemo(() => {
        if (selection.kind !== "activity") return null;
        return draft.phases
            .flatMap((phase) => phase.modules)
            .flatMap((moduleConfig) => moduleConfig.activities)
            .find((activity) => activity.activity_id === selection.activity_id)?.type ?? null;
    }, [draft, selection]);

    useEffect(() => {
        if (selectedActivityType) onResourcesNeeded?.(selectedActivityType);
    }, [onResourcesNeeded, selectedActivityType]);

    useEffect(() => {
        if (previousInitialResources.current === initialResources) return;
        previousInitialResources.current = initialResources;
        setResources((current) => {
            const merge = (key: keyof ActivityEditorResources) => {
                const byId = new Map(current[key].map((resource) => [resource.id, resource]));
                initialResources[key].forEach((resource) => byId.set(resource.id, resource));
                return [...byId.values()];
            };
            return {
                learning_contents: merge("learning_contents"),
                exam_papers: merge("exam_papers"),
                scoring_rubrics: merge("scoring_rubrics"),
                materials: merge("materials"),
                practice_templates: merge("practice_templates"),
                runtime_profiles: merge("runtime_profiles"),
                coach_profiles: merge("coach_profiles"),
            };
        });
    }, [initialResources]);

    useEffect(() => {
        const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
        window.addEventListener("beforeunload", beforeUnload);
        return () => window.removeEventListener("beforeunload", beforeUnload);
    }, [dirty]);

    const draftRef = useRef(draft);
    const dirtyRef = useRef(dirty);
    const revisionIdRef = useRef(revisionId);
    draftRef.current = draft;
    dirtyRef.current = dirty;
    revisionIdRef.current = revisionId;

    const mutate = (transform: (path: TrainingPathPayload) => TrainingPathPayload) => { setDraft((current) => transform(current)); setDirty(true); setValidation(null); setError(null); };
    const persistDraft = async (pathOverride?: TrainingPathPayload): Promise<boolean> => {
        const candidate = normalizeLearnerCopy(pathOverride ?? draftRef.current);
        setDraft(candidate);
        draftRef.current = candidate;
        setPending("save");
        setError(null);
        try {
            if (!onSave) return false;
            const saved = await onSave(candidate, "保存训练路径草稿", revisionIdRef.current);
            if (saved) {
                setRevisionId(saved.revision_id);
                revisionIdRef.current = saved.revision_id;
            }
            setDirty(false);
            dirtyRef.current = false;
            setRecentlyAddedActivityId(null);
            return true;
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试。");
            return false;
        } finally {
            setPending(null);
        }
    };
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
        if (action === "publish" && !reason.trim()) { setError("请填写发布说明。"); return; }
        if (action === "save") {
            await persistDraft();
            return;
        }
        const candidate = normalizeLearnerCopy(draft);
        setDraft(candidate);
        setPending(action); setError(null);
        try {
            if (action === "validate") { setValidation(await onValidate?.(candidate) ?? { can_publish: true, issues: [] }); }
            if (action === "publish") {
                const publishValidation = await onValidate?.(candidate);
                if (publishValidation) {
                    setValidation(publishValidation);
                    if (!publishValidation.can_publish) {
                        const firstIssue = publishValidation.issues[0];
                        setPublishConfirmOpen(false);
                        setWorkspaceMode("edit");
                        if (firstIssue) focusIssue(firstIssue);
                        setError(firstIssue
                            ? `发布前还有 ${publishValidation.issues.length} 项配置需要处理，已定位到第一项。`
                            : "发布前检查未通过，请先处理路径配置问题。");
                        return;
                    }
                }
                const published = await onPublish?.(candidate, reason.trim(), revisionId);
                if (published) setRevisionId(published.revision_id);
                setDirty(false);
                setPublishConfirmOpen(false);
                setReason("");
            }
        } catch (cause) { setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试。"); }
        finally { setPending(null); }
    };
    const moduleCount = useMemo(() => draft.phases.reduce((sum, phase) => sum + phase.modules.length, 0), [draft]);

    return <div className="space-y-3">
        <header className="sticky top-3 z-20 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:px-5">
            <div className="flex flex-col gap-3 sm:grid sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center xl:grid-cols-[minmax(230px,1fr)_auto_auto] xl:gap-5">
                <div className="min-w-0 sm:col-start-1 xl:pr-2">
                    <div className="flex flex-wrap items-center gap-2.5">
                        <h1 className="text-xl font-semibold leading-7 tracking-[-0.02em] text-slate-950">新人训练路径</h1>
                        <span role="status" data-save-state={dirty ? "dirty" : "saved"} className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-[color,background-color] duration-[var(--duration-press)] ease-[var(--ease-out)]", dirty ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700")}>{!dirty ? <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" /> : <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-amber-500" />}{dirty ? "有未保存修改" : "草稿已保存"}</span>
                    </div>
                    <p className="mt-0.5 text-xs leading-5 text-slate-500">{draft.phases.length} 个阶段 · {moduleCount} 个模块</p>
                </div>

                <div className="flex items-center gap-2 self-start sm:col-start-2 sm:row-start-1 sm:self-auto">
                    <Link href="/admin/newcomer-training/resources" prefetch={false} className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
                        <Library aria-hidden="true" className="h-4 w-4" />内容库
                    </Link>
                    <div role="group" aria-label="工作区视图" className="flex w-fit rounded-lg bg-slate-100 p-0.5">
                    <button type="button" aria-pressed={workspaceMode === "edit"} onClick={() => setWorkspaceMode("edit")} className={cn("inline-flex h-9 items-center gap-2 rounded-[7px] px-3 text-sm font-medium transition-colors duration-[var(--duration-press)] ease-[var(--ease-out)]", workspaceMode === "edit" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500 hover:text-slate-800")}><PencilLine className="h-4 w-4" />编排</button>
                    <button type="button" aria-pressed={workspaceMode === "preview"} onClick={() => setWorkspaceMode("preview")} className={cn("inline-flex h-9 items-center gap-2 rounded-[7px] px-3 text-sm font-medium transition-colors duration-[var(--duration-press)] ease-[var(--ease-out)]", workspaceMode === "preview" ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-800")}><Monitor className="h-4 w-4" />实时预览</button>
                    </div>
                </div>

                <div className="grid w-full grid-cols-3 items-center gap-1.5 sm:col-span-2 sm:col-start-1 sm:flex sm:justify-end xl:col-span-1 xl:col-start-3 xl:row-start-1 xl:w-auto">
                    <Button className="h-10 min-w-0 whitespace-nowrap rounded-lg px-2.5 shadow-none sm:px-3.5" variant="ghost" isLoading={pending === "save"} onClick={() => void run("save")}><Save className="mr-1.5 h-4 w-4" />保存草稿</Button>
                    <Button className="h-10 min-w-0 rounded-lg px-2.5 sm:px-3.5" variant="outline" isLoading={pending === "validate"} onClick={() => void run("validate")}><CheckCircle2 className="mr-1.5 h-4 w-4" />检查</Button>
                    <Button className="h-10 min-w-0 rounded-lg px-2.5 shadow-none sm:px-3.5" isLoading={pending === "publish"} onClick={() => { setError(null); setPublishConfirmOpen(true); }}><Send className="mr-1.5 h-4 w-4" />发布</Button>
                </div>
            </div>
        </header>
        {error && !publishConfirmOpen && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <section data-testid="path-editor-layout" data-layout="outline-workspace" className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <div className="grid items-start lg:grid-cols-[minmax(340px,42%)_minmax(0,1fr)]">
                <div className="border-b border-slate-200 bg-white lg:border-b-0 lg:border-r">
                    <PathOutline embedded path={draft} selection={selection} onSelect={(nextSelection) => { setSelection(nextSelection); setRecentlyAddedActivityId(null); setWorkspaceMode("edit"); }} onMove={move}
                        onDropItem={(kind, sourceId, targetId) => mutate((path) => kind === "phase" ? movePhase(path, sourceId, "before", targetId) : kind === "module" ? moveModule(path, sourceId, "before", targetId) : moveActivity(path, sourceId, "before", targetId))}
                        onDuplicate={(kind, id) => mutate((path) => kind === "phase" ? duplicatePhase(path, id, nextId) : kind === "module" ? duplicateModule(path, id, nextId) : duplicateActivity(path, id, nextId))}
                        onDelete={(kind, id, title) => setDeleteTarget({ kind, id, title })}
                        onAddPhase={() => { const phase = defaultPhase(); mutate((path) => addPhase(path, phase)); setSelection({ kind: "phase", phase_id: phase.phase_id }); }}
                        onAddModule={(phaseId, type) => { const moduleConfig = defaultModule(type); mutate((path) => addModule(path, phaseId, moduleConfig)); setSelection({ kind: "module", module_id: moduleConfig.module_id }); }}
                        onAddActivity={(moduleId, type) => { const activity = defaultActivity(type); mutate((path) => addActivity(path, moduleId, activity)); setSelection({ kind: "activity", activity_id: activity.activity_id }); setRecentlyAddedActivityId(activity.activity_id); setWorkspaceMode("edit"); }} />
                </div>
                <div className="min-w-0 bg-white">
                    {workspaceMode === "edit" ? <>
                        <PathInspector embedded path={draft} selection={selection} resources={resources} onQuickCreate={setQuickCreate} recentlyAddedActivityId={recentlyAddedActivityId} onPatch={(patch) => mutate((path) => updateSelectedObject(path, selection, patch))} onActivityChange={(activity) => mutate((path) => updateSelectedObject(path, selection, activity as unknown as Record<string, unknown>))} />
                        <div className="divide-y divide-slate-200 border-t border-slate-200">
                            <details className="group px-5 py-4" open={Boolean(validation?.issues.length)}><summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-slate-800"><CheckCircle2 className="h-4 w-4 text-slate-500" />检查结果</summary><div className="pb-2 pt-3"><PathValidationPanel validation={validation} onFocusIssue={focusIssue} /></div></details>
                            <details className="group px-5 py-4"><summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-slate-800"><History className="h-4 w-4 text-slate-500" />版本历史</summary><div className="pb-2 pt-3"><PathRevisionHistory currentRevisionId={revisionId} onRestored={(restored) => { setDraft(restored.payload); setRevisionId(restored.revision_id); setDirty(false); setValidation(null); setSelection({ kind: "path" }); }} /></div></details>
                        </div>
                    </> : <div className="bg-slate-50/55 p-4 sm:p-6"><PathPreview path={draft} /></div>}
                </div>
            </div>
            <footer className="flex items-start gap-2 border-t border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 sm:items-center sm:px-5">
                <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400 sm:mt-0" />
                <span>编辑内容会立即同步到实时预览；发布后所有在训学员同步更新</span>
            </footer>
        </section>
        <ConfirmDialog open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }} title={`删除${deleteTarget?.title ?? "对象"}`} description="删除后，其下级内容也会从当前草稿移除。保存前仍可刷新页面放弃修改。" confirmText="删除" variant="danger" onConfirm={() => { if (!deleteTarget) return; const target = deleteTarget; mutate((path) => target.kind === "phase" ? deletePhase(path, target.id) : target.kind === "module" ? deleteModule(path, target.id) : deleteActivity(path, target.id)); setSelection({ kind: "path" }); setDeleteTarget(null); }} />
        <Dialog open={publishConfirmOpen} onOpenChange={(open) => { if (pending === "publish") return; setPublishConfirmOpen(open); if (!open) setError(null); }}>
            <DialogContent className="max-w-md rounded-2xl border-slate-200 bg-white p-6 shadow-xl backdrop-blur-none">
                <DialogHeader className="space-y-2 pr-8 text-left">
                    <DialogTitle className="text-xl font-semibold tracking-[-0.02em]">发布训练路径</DialogTitle>
                    <DialogDescription className="font-normal leading-6 text-slate-500"><span className="block">发布后，全体在训学员立即切换到新版本。</span><span className="block">已完成记录、评分和提交证据仍保留原始快照。</span></DialogDescription>
                </DialogHeader>
                <label className="mt-2 block text-sm font-medium text-slate-800">
                    发布说明
                    <input autoFocus aria-label="发布说明" value={reason} onChange={(event) => { setReason(event.target.value); if (error) setError(null); }} placeholder="例如：更新产品讲解任务和通过标准" className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900 outline-none transition-[border-color,box-shadow] focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                </label>
                {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
                <DialogFooter className="mt-2 gap-2 sm:space-x-0">
                    <Button type="button" variant="ghost" className="h-10 rounded-lg px-4" disabled={pending === "publish"} onClick={() => { setPublishConfirmOpen(false); setError(null); }}>取消</Button>
                    <Button type="button" className="h-10 rounded-lg px-4 shadow-none" isLoading={pending === "publish"} onClick={() => void run("publish")}>确认发布</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
        {quickCreate && <ResourcePickerDrawer
            kind={quickCreate}
            open
            onOpenChange={(open) => { if (!open) setQuickCreate(null); }}
            onBeforeRefineNavigate={async () => {
                if (!dirtyRef.current) return true;
                return persistDraft();
            }}
            onCreated={async (resource: ResourceOption) => {
                const key = quickCreate === "learning_content" ? "learning_contents" : quickCreate === "exam_paper" ? "exam_papers" : quickCreate === "material" ? "materials" : "scoring_rubrics";
                setResources((current) => ({ ...current, [key]: [...current[key], resource] }));
                const field = quickCreate === "learning_content" ? "learning_content_id" : quickCreate === "exam_paper" ? "exam_paper_id" : quickCreate === "material" ? "material_id" : "scoring_rubric_id";
                let nextDraft = draftRef.current;
                if (selection.kind === "activity") {
                    const selectedActivity = nextDraft.phases.flatMap((phase) => phase.modules).flatMap((moduleConfig) => moduleConfig.activities).find((item) => item.activity_id === selection.activity_id);
                    if (selectedActivity) {
                        nextDraft = updateSelectedObject(nextDraft, selection, { config: { ...selectedActivity.config, [field]: resource.id } });
                        setDraft(nextDraft);
                        draftRef.current = nextDraft;
                        setDirty(true);
                        dirtyRef.current = true;
                        setValidation(null);
                        setError(null);
                    }
                }
                // scoring_rubric 抽屉会先展示「去完善提示词」，由抽屉自行关闭；绑定后立即持久化草稿
                if (quickCreate !== "scoring_rubric") {
                    setQuickCreate(null);
                    return;
                }
                const draftPersisted = await persistDraft(nextDraft);
                return { draftPersisted };
            }}
        />}
    </div>;
}
