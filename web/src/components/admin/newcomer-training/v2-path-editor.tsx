"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    AlertTriangle,
    ArrowDown,
    ArrowLeft,
    ArrowUp,
    CheckCircle2,
    Copy,
    Eye,
    FileCheck2,
    GripVertical,
    Plus,
    Rocket,
    Save,
    Trash2,
} from "lucide-react";

import {
    ActivityResourceDrawer,
    type FoundationResourceField,
} from "@/components/admin/newcomer-training/activity-resource-drawer";
import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { generateClientId } from "@/lib/client-id";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import type {
    FoundationActivityDefinitionV2,
    FoundationActivityTypeV2,
    FoundationPathDraftV2,
    FoundationPathWorkspace,
    FoundationPathValidation,
    FoundationReleasePreview,
    FoundationStageDefinitionV2,
} from "@/lib/api/types/foundation-admin";

const ACTIVITY_LABELS: Record<FoundationActivityTypeV2, string> = {
    lesson: "内容学习",
    quiz: "知识测验",
    audio_assessment: "录音讲解",
    ai_coach: "训练教练",
    assignment: "异步客户场景",
};

type Selection = { stageId: string | null; activityId: string | null };
type BindingState = {
    activityType: FoundationActivityTypeV2;
    field: FoundationResourceField;
    currentRevisionId: string;
} | null;

export function FoundationV2PathEditor({ pathId }: { pathId: string }) {
    const workspace = useQuery({
        queryKey: ["foundation-admin", "path-workspace", pathId],
        queryFn: () => api.admin.newcomerTraining.getPathWorkspace(pathId),
    });
    if (workspace.isPending) {
        return <main className="px-4 py-6 md:px-6"><div aria-label="正在加载路径编辑器" className="mx-auto grid max-w-[1600px] gap-4 lg:grid-cols-[300px_minmax(420px,1fr)_360px]">{[0, 1, 2].map((item) => <div key={item} className="h-[620px] animate-pulse rounded-2xl bg-slate-100" />)}</div></main>;
    }
    if (workspace.error || !workspace.data) {
        return <main className="px-4 py-6 md:px-6"><div role="alert" className="mx-auto max-w-3xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-950"><h1 className="font-semibold">路径编辑器加载失败</h1><p className="mt-2 text-sm">{getApiErrorMessage(workspace.error)}</p><Button type="button" variant="outline" className="mt-4 bg-white" onClick={() => void workspace.refetch()}>重新加载</Button></div></main>;
    }
    const workspaceKey = `${workspace.data.path.version}:${workspace.data.working_revision?.revision_id ?? ""}:${workspace.data.published_revision?.revision_id ?? ""}`;
    return <FoundationV2PathEditorSession key={workspaceKey} pathId={pathId} initialWorkspace={workspace.data} />;
}

function FoundationV2PathEditorSession({ pathId, initialWorkspace }: { pathId: string; initialWorkspace: FoundationPathWorkspace }) {
    const router = useRouter();
    const queryClient = useQueryClient();
    const [tokenStore] = useState(() => createIdempotencyTokenStore());
    const startingDraft = workspaceDraft(initialWorkspace);
    const [baseline, setBaseline] = useState(() => JSON.stringify(startingDraft));
    const [draft, setDraft] = useState<FoundationPathDraftV2 | null>(() => startingDraft);
    const [selection, setSelection] = useState<Selection>(() => ({ stageId: startingDraft.stages[0]?.stage_id ?? null, activityId: null }));
    const [binding, setBinding] = useState<BindingState>(null);
    const [resourceLabels, setResourceLabels] = useState<Record<string, string>>({});
    const [newActivityType, setNewActivityType] = useState<FoundationActivityTypeV2>("lesson");
    const [validation, setValidation] = useState<FoundationPathValidation | null>(null);
    const [resultMessage, setResultMessage] = useState<string | null>(null);
    const [operationError, setOperationError] = useState<string | null>(null);
    const [releaseOpen, setReleaseOpen] = useState(false);
    const [releaseReason, setReleaseReason] = useState("");
    const [releasePreview, setReleasePreview] = useState<FoundationReleasePreview | null>(null);
    const [publishedMessage, setPublishedMessage] = useState<string | null>(null);
    const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);

    const workspace = useQuery({
        queryKey: ["foundation-admin", "path-workspace", pathId],
        queryFn: () => api.admin.newcomerTraining.getPathWorkspace(pathId),
        initialData: initialWorkspace,
    });

    const serializedDraft = draft ? JSON.stringify(draft) : "";
    const dirty = Boolean(draft && serializedDraft !== baseline);

    useEffect(() => {
        const warn = (event: BeforeUnloadEvent) => {
            if (!dirty) return;
            event.preventDefault();
            event.returnValue = "";
        };
        window.addEventListener("beforeunload", warn);
        return () => window.removeEventListener("beforeunload", warn);
    }, [dirty]);

    const save = useMutation({
        mutationFn: async () => {
            if (!draft || !workspace.data) throw new Error("路径草稿尚未加载完成。");
            const inputKey = `save-path:${pathId}:${workspace.data.path.version}:${JSON.stringify(draft)}`;
            const result = await api.admin.newcomerTraining.savePathDraftV2(
                pathId,
                draft,
                workspace.data.path.version,
                tokenStore.tokenFor(inputKey),
            );
            tokenStore.complete(inputKey);
            return result;
        },
        onSuccess: async () => {
            setBaseline(serializedDraft);
            setResultMessage("路径草稿已保存。现在可以运行正式校验或创建发布计划。");
            setOperationError(null);
            setValidation(null);
            await workspace.refetch();
        },
        onError: (error) => {
            setOperationError(`${getApiErrorMessage(error)} 当前编辑内容仍保留在页面中，请核对后重试。`);
            setResultMessage(null);
        },
    });

    const validate = useMutation({
        mutationFn: () => api.admin.newcomerTraining.validatePathV2(pathId),
        onSuccess: (result) => {
            setValidation(result);
            setResultMessage(result.valid ? "路径已通过正式校验，可以创建发布计划。" : `校验发现 ${result.issues.length} 个阻塞项，草稿仍可继续编辑。`);
            setOperationError(null);
        },
        onError: (error) => {
            setOperationError(getApiErrorMessage(error));
            setResultMessage(null);
        },
    });

    const previewRelease = useMutation({
        mutationFn: async () => {
            const revisionId = workspace.data?.working_revision?.revision_id;
            if (!revisionId) throw new Error("请先保存一个工作修订。");
            if (!releaseReason.trim()) throw new Error("请填写本次发布依据。");
            const key = `release-preview:${revisionId}:${releaseReason.trim()}`;
            const result = await api.admin.newcomerTraining.previewRelease(
                revisionId,
                releaseReason.trim(),
                tokenStore.tokenFor(key),
            );
            tokenStore.complete(key);
            return result;
        },
        onSuccess: (result) => {
            setReleasePreview(result);
            setOperationError(null);
        },
        onError: (error) => setOperationError(getApiErrorMessage(error)),
    });

    const publishRelease = useMutation({
        mutationFn: async () => {
            if (!releasePreview) throw new Error("请先完成发布预览。");
            const key = `publish-release:${releasePreview.release_plan_id}:${releasePreview.version}`;
            const result = await api.admin.newcomerTraining.publishRelease(
                releasePreview,
                tokenStore.tokenFor(key),
            );
            tokenStore.complete(key);
            return result;
        },
        onSuccess: async () => {
            setPublishedMessage(`发布记录已保存，路径第 ${workspace.data?.working_revision?.revision_no ?? "当前"} 版现已生效。`);
            setResultMessage("发布成功。现有在训学员继续使用原冻结版本，新分配学员使用本次发布版本。");
            setOperationError(null);
            await Promise.all([
                workspace.refetch(),
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "release-plans"] }),
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "workspace"] }),
            ]);
        },
        onError: (error) => setOperationError(`${getApiErrorMessage(error)} 旧发布版本仍保持有效。`),
    });

    const selectedStage = draft?.stages.find((stage) => stage.stage_id === selection.stageId) ?? null;
    const selectedActivity = selectedStage?.activities.find((activity) => activity.activity_id === selection.activityId) ?? null;

    const updateDraft = (updater: (value: FoundationPathDraftV2) => void) => {
        setDraft((current) => {
            if (!current) return current;
            const next = cloneDraft(current);
            updater(next);
            return next;
        });
        setResultMessage(null);
        setValidation(null);
        setReleasePreview(null);
        setPublishedMessage(null);
    };

    const updateStage = (stageId: string, updater: (stage: FoundationStageDefinitionV2) => FoundationStageDefinitionV2) => {
        updateDraft((current) => {
            current.stages = current.stages.map((stage) => stage.stage_id === stageId ? updater(stage) : stage);
        });
    };

    const updateActivity = (stageId: string, activityId: string, updater: (activity: FoundationActivityDefinitionV2) => FoundationActivityDefinitionV2) => {
        updateStage(stageId, (stage) => ({
            ...stage,
            activities: stage.activities.map((activity) => activity.activity_id === activityId ? updater(activity) : activity),
        }));
    };

    const addStage = () => {
        const stage = defaultStage((draft?.stages.length ?? 0) + 1);
        updateDraft((current) => { current.stages.push(stage); });
        setSelection({ stageId: stage.stage_id, activityId: null });
    };

    const duplicateStage = (stage: FoundationStageDefinitionV2) => {
        const idMap = new Map(stage.activities.map((activity) => [activity.activity_id, `activity-${generateClientId()}`]));
        const copy: FoundationStageDefinitionV2 = {
            ...cloneStage(stage),
            stage_id: `stage-${generateClientId()}`,
            sequence: (draft?.stages.length ?? 0) + 1,
            title: `${stage.title}（副本）`,
            activities: stage.activities.map((activity) => ({
                ...cloneActivity(activity),
                activity_id: idMap.get(activity.activity_id) ?? `activity-${generateClientId()}`,
                prerequisite_activity_ids: activity.prerequisite_activity_ids.map((id) => idMap.get(id) ?? id),
            })),
        };
        updateDraft((current) => { current.stages.push(copy); normalizeStageSequences(current); });
        setSelection({ stageId: copy.stage_id, activityId: null });
    };

    const moveStage = (stageId: string, direction: -1 | 1) => {
        updateDraft((current) => {
            const index = current.stages.findIndex((stage) => stage.stage_id === stageId);
            const target = index + direction;
            if (index < 0 || target < 0 || target >= current.stages.length) return;
            [current.stages[index], current.stages[target]] = [current.stages[target], current.stages[index]];
            normalizeStageSequences(current);
        });
    };

    const archiveStage = (stageId: string) => {
        if (!draft || draft.stages.length <= 1) return;
        updateDraft((current) => { current.stages = current.stages.filter((stage) => stage.stage_id !== stageId); normalizeStageSequences(current); });
        const next = draft.stages.find((stage) => stage.stage_id !== stageId);
        setSelection({ stageId: next?.stage_id ?? null, activityId: null });
    };

    const addActivity = (stageId: string) => {
        const activity = defaultActivity(newActivityType);
        updateStage(stageId, (stage) => ({ ...stage, activities: [...stage.activities, activity] }));
        setSelection({ stageId, activityId: activity.activity_id });
    };

    const moveActivity = (stageId: string, activityId: string, direction: -1 | 1) => {
        updateStage(stageId, (stage) => {
            const activities = [...stage.activities];
            const index = activities.findIndex((activity) => activity.activity_id === activityId);
            const target = index + direction;
            if (index < 0 || target < 0 || target >= activities.length) return stage;
            [activities[index], activities[target]] = [activities[target], activities[index]];
            return { ...stage, activities };
        });
    };

    const duplicateActivity = (stageId: string, activity: FoundationActivityDefinitionV2) => {
        const copy = { ...cloneActivity(activity), activity_id: `activity-${generateClientId()}`, title: `${activity.title}（副本）`, prerequisite_activity_ids: [] } as FoundationActivityDefinitionV2;
        updateStage(stageId, (stage) => ({ ...stage, activities: [...stage.activities, copy] }));
        setSelection({ stageId, activityId: copy.activity_id });
    };

    const archiveActivity = (stageId: string, activityId: string) => {
        const stage = draft?.stages.find((item) => item.stage_id === stageId);
        if (!stage || stage.activities.length <= 1) return;
        updateStage(stageId, (current) => ({
            ...current,
            activities: current.activities
                .filter((activity) => activity.activity_id !== activityId)
                .map((activity) => ({
                    ...activity,
                    prerequisite_activity_ids: activity.prerequisite_activity_ids.filter((id) => id !== activityId),
                }) as FoundationActivityDefinitionV2),
        }));
        setSelection({ stageId, activityId: null });
    };

    const reorderActivity = (stageId: string, sourceId: string, targetId: string) => {
        if (sourceId === targetId) return;
        updateStage(stageId, (stage) => {
            const activities = [...stage.activities];
            const from = activities.findIndex((activity) => activity.activity_id === sourceId);
            const to = activities.findIndex((activity) => activity.activity_id === targetId);
            if (from < 0 || to < 0) return stage;
            const [moved] = activities.splice(from, 1);
            activities.splice(to, 0, moved);
            return { ...stage, activities };
        });
    };

    const structuralNodes = useMemo(() => draft?.stages.flatMap((stage) => [
        { stageId: stage.stage_id, activityId: null },
        ...stage.activities.map((activity) => ({ stageId: stage.stage_id, activityId: activity.activity_id })),
    ]) ?? [], [draft]);

    if (!draft) return null;

    return (
        <FoundationAdminCapabilityBoundary capability="edit_paths">
            <main className="px-4 py-5 md:px-6">
                <div className="mx-auto max-w-[1600px] space-y-4">
                    <header className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 xl:flex-row xl:items-center xl:justify-between">
                        <div className="min-w-0">
                            <Link
                                href="/admin/newcomer-training/paths"
                                prefetch={false}
                                onClick={(event) => {
                                    if (!dirty) return;
                                    event.preventDefault();
                                    setLeaveDialogOpen(true);
                                }}
                                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950"
                            ><ArrowLeft className="h-4 w-4" />返回路径列表</Link>
                            <div className="mt-3 flex flex-wrap items-center gap-3"><h1 className="truncate text-2xl font-bold text-slate-950">{workspace.data.path.title}</h1><Badge variant={dirty ? "orange" : "green"}>{dirty ? "有未保存修改" : "草稿已保存"}</Badge></div>
                            <p className="mt-1 text-sm text-slate-500">工作修订与正式发布分开；发布不会自动迁移任何活跃学员。</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button type="button" variant="outline" onClick={() => validate.mutate()} disabled={dirty || validate.isPending || !workspace.data.working_revision}><FileCheck2 className="mr-2 h-4 w-4" />{validate.isPending ? "正在校验…" : "正式校验"}</Button>
                            <Button type="button" variant="outline" onClick={() => { setReleaseOpen(true); setReleasePreview(null); setPublishedMessage(null); }} disabled={dirty || !workspace.data.working_revision}><Rocket className="mr-2 h-4 w-4" />发布预览</Button>
                            <Button type="button" onClick={() => save.mutate()} disabled={!dirty || save.isPending}><Save className="mr-2 h-4 w-4" />{save.isPending ? "正在保存…" : "保存草稿"}</Button>
                        </div>
                    </header>

                    {operationError ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{operationError}</div> : null}
                    {resultMessage ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{resultMessage}</div> : null}

                    <div className="grid min-h-[700px] gap-4 xl:grid-cols-[300px_minmax(440px,1fr)_360px]">
                        <StructurePane
                            draft={draft}
                            selection={selection}
                            nodes={structuralNodes}
                            newActivityType={newActivityType}
                            onNewActivityType={setNewActivityType}
                            onSelect={setSelection}
                            onAddStage={addStage}
                            onDuplicateStage={duplicateStage}
                            onMoveStage={moveStage}
                            onArchiveStage={archiveStage}
                            onAddActivity={addActivity}
                            onMoveActivity={moveActivity}
                            onDuplicateActivity={duplicateActivity}
                            onArchiveActivity={archiveActivity}
                            onReorderActivity={reorderActivity}
                        />
                        <section aria-labelledby="editor-form-title" className="rounded-2xl border border-slate-200 bg-white p-5">
                            <h2 id="editor-form-title" className="font-semibold text-slate-950">编辑内容</h2>
                            <p className="mt-1 text-sm text-slate-500">字段错误会在正式校验后定位到对应阶段或活动；保存草稿允许稍后补充关联资源。</p>
                            <div className="mt-5">
                                {!selectedStage ? (
                                    <PathForm draft={draft} onChange={(field, value) => updateDraft((current) => { current[field] = value; })} />
                                ) : selectedActivity ? (
                                    <ActivityForm
                                        activity={selectedActivity}
                                        resourceLabels={resourceLabels}
                                        onChange={(updater) => updateActivity(selectedStage.stage_id, selectedActivity.activity_id, updater)}
                                        onBind={(field) => setBinding({ activityType: selectedActivity.type, field, currentRevisionId: resourceRevision(selectedActivity, field) })}
                                    />
                                ) : (
                                    <StageForm stage={selectedStage} onChange={(updater) => updateStage(selectedStage.stage_id, updater)} />
                                )}
                            </div>
                        </section>
                        <PreviewPane draft={draft} validation={validation} dirty={dirty} selectedActivityId={selection.activityId} />
                    </div>
                </div>
            </main>

            {binding ? (
                <ActivityResourceDrawer
                    open
                    activityType={binding.activityType}
                    field={binding.field}
                    currentRevisionId={binding.currentRevisionId}
                    onClose={() => setBinding(null)}
                    onBind={(revisionId, label) => {
                        if (!selection.stageId || !selection.activityId) return;
                        updateActivity(selection.stageId, selection.activityId, (activity) => bindResource(activity, binding.field, revisionId));
                        setResourceLabels((current) => ({ ...current, [`${selection.activityId}:${binding.field}`]: label }));
                    }}
                />
            ) : null}

            <ConfirmDialog
                open={leaveDialogOpen}
                onOpenChange={setLeaveDialogOpen}
                title="离开路径编辑？"
                description="路径草稿还有未保存修改。离开后，本次修改不会保留。"
                confirmText="放弃未保存修改并离开"
                cancelText="继续编辑"
                variant="warning"
                onConfirm={() => {
                    setLeaveDialogOpen(false);
                    router.push("/admin/newcomer-training/paths");
                }}
            />

            <Dialog open={releaseOpen} onOpenChange={(open) => { if (!previewRelease.isPending && !publishRelease.isPending) setReleaseOpen(open); }}>
                <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>发布计划</DialogTitle>
                        <DialogDescription>系统会冻结精确修订、校验依赖和影响；任一步失败时旧发布继续有效。</DialogDescription>
                    </DialogHeader>
                    {publishedMessage ? (
                        <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-950"><CheckCircle2 className="h-6 w-6 text-emerald-600" /><h3 className="mt-2 font-semibold">发布成功</h3><p className="mt-1 text-sm">{publishedMessage}</p><p className="mt-2 text-xs">活跃学员仍冻结在其原路径版本。</p></div>
                    ) : (
                        <>
                            <Field label="发布依据" helper="说明本次发布的业务原因，发布记录和审计将保留此内容。"><textarea className={textareaClassName} value={releaseReason} onChange={(event) => { setReleaseReason(event.target.value); setReleasePreview(null); }} maxLength={2000} /></Field>
                            {releasePreview ? <ReleasePreviewPanel preview={releasePreview} /> : null}
                            {operationError ? <p role="alert" className="text-sm text-red-700">{operationError}</p> : null}
                        </>
                    )}
                    <DialogFooter>
                        <Button type="button" variant="ghost" onClick={() => setReleaseOpen(false)} disabled={previewRelease.isPending || publishRelease.isPending}>{publishedMessage ? "关闭" : "取消"}</Button>
                        {!publishedMessage && !releasePreview ? <Button type="button" onClick={() => { setOperationError(null); previewRelease.mutate(); }} disabled={previewRelease.isPending}>{previewRelease.isPending ? "正在检查…" : "创建发布预览"}</Button> : null}
                        {!publishedMessage && releasePreview ? <Button type="button" onClick={() => { setOperationError(null); publishRelease.mutate(); }} disabled={releasePreview.status !== "ready" || publishRelease.isPending}>{publishRelease.isPending ? "正在发布…" : releasePreview.status === "ready" ? "确认发布此计划" : "处理阻塞项后再发布"}</Button> : null}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </FoundationAdminCapabilityBoundary>
    );
}

function StructurePane({
    draft,
    selection,
    nodes,
    newActivityType,
    onNewActivityType,
    onSelect,
    onAddStage,
    onDuplicateStage,
    onMoveStage,
    onArchiveStage,
    onAddActivity,
    onMoveActivity,
    onDuplicateActivity,
    onArchiveActivity,
    onReorderActivity,
}: {
    draft: FoundationPathDraftV2;
    selection: Selection;
    nodes: Selection[];
    newActivityType: FoundationActivityTypeV2;
    onNewActivityType: (value: FoundationActivityTypeV2) => void;
    onSelect: (value: Selection) => void;
    onAddStage: () => void;
    onDuplicateStage: (stage: FoundationStageDefinitionV2) => void;
    onMoveStage: (stageId: string, direction: -1 | 1) => void;
    onArchiveStage: (stageId: string) => void;
    onAddActivity: (stageId: string) => void;
    onMoveActivity: (stageId: string, activityId: string, direction: -1 | 1) => void;
    onDuplicateActivity: (stageId: string, activity: FoundationActivityDefinitionV2) => void;
    onArchiveActivity: (stageId: string, activityId: string) => void;
    onReorderActivity: (stageId: string, sourceId: string, targetId: string) => void;
}) {
    const [dragging, setDragging] = useState<{ stageId: string; activityId: string } | null>(null);
    const handleKeyboard = (event: React.KeyboardEvent) => {
        if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
        const index = nodes.findIndex((node) => node.stageId === selection.stageId && node.activityId === selection.activityId);
        if (index < 0) return;
        const target = event.key === "ArrowUp" ? index - 1 : index + 1;
        if (target < 0 || target >= nodes.length) return;
        event.preventDefault();
        onSelect(nodes[target]);
    };
    return (
        <aside aria-labelledby="path-structure-title" className="rounded-2xl border border-slate-200 bg-white p-4" onKeyDown={handleKeyboard}>
            <div className="flex items-center justify-between"><div><h2 id="path-structure-title" className="font-semibold text-slate-950">阶段与活动</h2><p className="mt-1 text-xs text-slate-500">方向键可切换选择</p></div><Button type="button" variant="ghost" size="sm" onClick={() => onSelect({ stageId: null, activityId: null })}>路径设置</Button></div>
            <div className="mt-4 space-y-3">
                {draft.stages.map((stage, stageIndex) => (
                    <div key={stage.stage_id} className="rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                        <div className="flex items-start gap-1">
                            <button type="button" onClick={() => onSelect({ stageId: stage.stage_id, activityId: null })} className={`min-w-0 flex-1 rounded-lg px-3 py-2 text-left text-sm font-semibold ${selection.stageId === stage.stage_id && !selection.activityId ? "bg-slate-900 text-white" : "text-slate-800 hover:bg-white"}`}><span className="block text-xs opacity-70">阶段 {stageIndex + 1}</span><span className="block truncate">{stage.title}</span></button>
                            <div className="flex shrink-0 flex-col">
                                <IconButton label="上移阶段" onClick={() => onMoveStage(stage.stage_id, -1)} disabled={stageIndex === 0}><ArrowUp /></IconButton>
                                <IconButton label="下移阶段" onClick={() => onMoveStage(stage.stage_id, 1)} disabled={stageIndex === draft.stages.length - 1}><ArrowDown /></IconButton>
                            </div>
                        </div>
                        <div className="mt-2 space-y-1">
                            {stage.activities.map((activity, activityIndex) => (
                                <div
                                    key={activity.activity_id}
                                    draggable
                                    onDragStart={() => setDragging({ stageId: stage.stage_id, activityId: activity.activity_id })}
                                    onDragEnd={() => setDragging(null)}
                                    onDragOver={(event) => event.preventDefault()}
                                    onDrop={() => {
                                        if (dragging?.stageId === stage.stage_id) onReorderActivity(stage.stage_id, dragging.activityId, activity.activity_id);
                                        setDragging(null);
                                    }}
                                    className="flex items-center gap-1"
                                >
                                    <GripVertical className="h-4 w-4 shrink-0 cursor-grab text-slate-400" aria-hidden />
                                    <button type="button" onClick={() => onSelect({ stageId: stage.stage_id, activityId: activity.activity_id })} className={`min-w-0 flex-1 rounded-lg px-2 py-2 text-left text-sm ${selection.activityId === activity.activity_id ? "bg-blue-100 text-blue-950" : "text-slate-600 hover:bg-white"}`}><span className="block truncate">{activityIndex + 1}. {activity.title}</span><span className="block text-[11px] opacity-70">{ACTIVITY_LABELS[activity.type]}</span></button>
                                    <div className="flex shrink-0">
                                        <IconButton label="上移活动" onClick={() => onMoveActivity(stage.stage_id, activity.activity_id, -1)} disabled={activityIndex === 0}><ArrowUp /></IconButton>
                                        <IconButton label="下移活动" onClick={() => onMoveActivity(stage.stage_id, activity.activity_id, 1)} disabled={activityIndex === stage.activities.length - 1}><ArrowDown /></IconButton>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="mt-3 flex gap-2">
                            <select aria-label={`新增到${stage.title}的活动类型`} className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs" value={newActivityType} onChange={(event) => onNewActivityType(event.target.value as FoundationActivityTypeV2)}>{Object.entries(ACTIVITY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
                            <Button type="button" size="sm" variant="outline" onClick={() => onAddActivity(stage.stage_id)}><Plus className="h-4 w-4" /><span className="sr-only">新增活动</span></Button>
                        </div>
                        {selection.stageId === stage.stage_id ? (
                            <div className="mt-2 flex flex-wrap gap-1 border-t border-slate-200 pt-2">
                                {selection.activityId ? (
                                    <>
                                        <Button type="button" size="sm" variant="ghost" onClick={() => { const activity = stage.activities.find((item) => item.activity_id === selection.activityId); if (activity) onDuplicateActivity(stage.stage_id, activity); }}><Copy className="mr-1 h-3.5 w-3.5" />复制活动</Button>
                                        <Button type="button" size="sm" variant="ghost" className="text-red-700" disabled={stage.activities.length <= 1} onClick={() => { if (selection.activityId) onArchiveActivity(stage.stage_id, selection.activityId); }}><Trash2 className="mr-1 h-3.5 w-3.5" />归档活动</Button>
                                    </>
                                ) : (
                                    <>
                                        <Button type="button" size="sm" variant="ghost" onClick={() => onDuplicateStage(stage)}><Copy className="mr-1 h-3.5 w-3.5" />复制阶段</Button>
                                        <Button type="button" size="sm" variant="ghost" className="text-red-700" disabled={draft.stages.length <= 1} onClick={() => onArchiveStage(stage.stage_id)}><Trash2 className="mr-1 h-3.5 w-3.5" />归档阶段</Button>
                                    </>
                                )}
                            </div>
                        ) : null}
                    </div>
                ))}
            </div>
            <Button type="button" variant="outline" className="mt-4 w-full" onClick={onAddStage}><Plus className="mr-2 h-4 w-4" />新增阶段</Button>
        </aside>
    );
}

function PathForm({ draft, onChange }: { draft: FoundationPathDraftV2; onChange: (field: "title" | "revision_label", value: string) => void }) {
    return <div className="space-y-4"><Field label="路径名称" helper="学员和管理员看到的业务名称。"><Input value={draft.title} onChange={(event) => onChange("title", event.target.value)} maxLength={200} /></Field><Field label="修订说明" helper="说明该工作修订相对上一版的业务变化。"><Input value={draft.revision_label} onChange={(event) => onChange("revision_label", event.target.value)} maxLength={120} /></Field></div>;
}

function StageForm({ stage, onChange }: { stage: FoundationStageDefinitionV2; onChange: (updater: (stage: FoundationStageDefinitionV2) => FoundationStageDefinitionV2) => void }) {
    return (
        <div className="space-y-4">
            <Field label="阶段名称"><Input value={stage.title} onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))} /></Field>
            <Field label="阶段目标"><textarea className={textareaClassName} value={stage.objective} onChange={(event) => onChange((current) => ({ ...current, objective: event.target.value }))} /></Field>
            <ListField label="进入条件" helper="每行一个条件；没有条件时可留空。" values={stage.entry_conditions} onChange={(values) => onChange((current) => ({ ...current, entry_conditions: values }))} />
            <div className="grid gap-4 sm:grid-cols-2">
                <Field label="完成规则"><select className={selectClassName} value={stage.completion_rule} onChange={(event) => onChange((current) => ({ ...current, completion_rule: event.target.value as FoundationStageDefinitionV2["completion_rule"] }))}><option value="all_required">完成全部必修活动</option><option value="all_activities">完成全部活动</option></select></Field>
                <Field label="学员可见性"><select className={selectClassName} value={stage.visibility} onChange={(event) => onChange((current) => ({ ...current, visibility: event.target.value as FoundationStageDefinitionV2["visibility"] }))}><option value="learner">学员可见</option><option value="assigned_only">分配后可见</option></select></Field>
            </div>
        </div>
    );
}

function ActivityForm({ activity, resourceLabels, onChange, onBind }: { activity: FoundationActivityDefinitionV2; resourceLabels: Record<string, string>; onChange: (updater: (activity: FoundationActivityDefinitionV2) => FoundationActivityDefinitionV2) => void; onBind: (field: FoundationResourceField) => void }) {
    const common = (patch: Partial<FoundationActivityDefinitionV2>) => onChange((current) => ({ ...current, ...patch }) as FoundationActivityDefinitionV2);
    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3"><span className="text-sm font-medium text-slate-700">活动类型</span><Badge variant="blue">{ACTIVITY_LABELS[activity.type]}</Badge></div>
            <Field label="活动名称"><Input value={activity.title} onChange={(event) => common({ title: event.target.value })} /></Field>
            <Field label="训练目标"><textarea className={textareaClassName} value={activity.objective} onChange={(event) => common({ objective: event.target.value })} /></Field>
            <Field label="为什么重要"><textarea className={textareaClassName} value={activity.why_it_matters} onChange={(event) => common({ why_it_matters: event.target.value })} /></Field>
            <ListField label="完成步骤" helper="每行一个清晰动作。" values={activity.steps} onChange={(steps) => common({ steps })} />
            <ListField label="成功标准" helper="每行一个可验证结果。" values={activity.success_criteria} onChange={(success_criteria) => common({ success_criteria })} />
            <ListField label="能力映射" helper="每行一个已治理的能力编码；发布校验会核对映射。" values={activity.competency_keys} onChange={(competency_keys) => common({ competency_keys })} />
            <div className="grid gap-4 sm:grid-cols-2">
                <Field label="预计时长（分钟）"><Input type="number" min={1} max={1440} value={activity.estimated_minutes} onChange={(event) => common({ estimated_minutes: positiveNumber(event.target.value, 1) })} /></Field>
                <Field label="模型依赖"><select className={selectClassName} value={activity.ai_dependency} onChange={(event) => common({ ai_dependency: event.target.value as FoundationActivityDefinitionV2["ai_dependency"] })}><option value="none">不依赖模型</option><option value="optional">可降级运行</option><option value="required">必须使用模型</option></select></Field>
            </div>
            <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-sm text-slate-700"><input type="checkbox" checked={activity.required} onChange={(event) => common({ required: event.target.checked })} className="h-4 w-4" />该活动为必修</label>
            <div className="grid gap-4 sm:grid-cols-2">
                <Field label="最多尝试次数"><Input type="number" min={0} max={100} value={activity.retry_policy.max_attempts} onChange={(event) => common({ retry_policy: { ...activity.retry_policy, max_attempts: nonNegativeNumber(event.target.value) } })} /></Field>
                <Field label="重试间隔（秒）"><Input type="number" min={0} max={604800} value={activity.retry_policy.retry_interval_seconds} onChange={(event) => common({ retry_policy: { ...activity.retry_policy, retry_interval_seconds: nonNegativeNumber(event.target.value) } })} /></Field>
            </div>
            <div className="border-t border-slate-200 pt-5"><h3 className="font-semibold text-slate-950">类型配置</h3><p className="mt-1 text-sm text-slate-500">通过资源选择器关联精确修订，不直接编辑内部配置。</p><div className="mt-4 space-y-4"><ActivityConfigForm activity={activity} resourceLabels={resourceLabels} onChange={onChange} onBind={onBind} /></div></div>
        </div>
    );
}

function ActivityConfigForm({ activity, resourceLabels, onChange, onBind }: { activity: FoundationActivityDefinitionV2; resourceLabels: Record<string, string>; onChange: (updater: (activity: FoundationActivityDefinitionV2) => FoundationActivityDefinitionV2) => void; onBind: (field: FoundationResourceField) => void }) {
    const resource = (field: FoundationResourceField, label: string) => <ResourceField label={label} bound={Boolean(resourceRevision(activity, field))} valueLabel={resourceLabels[`${activity.activity_id}:${field}`]} onOpen={() => onBind(field)} />;
    if (activity.type === "lesson") return <>{resource("learning_unit_revision_id", "学习单元修订")}<ListField label="必修检查点" helper="每行一个学习单元检查点编码。" values={activity.config.required_checkpoint_ids} onChange={(values) => onChange((current) => current.type === "lesson" ? { ...current, config: { ...current.config, required_checkpoint_ids: values } } : current)} /></>;
    if (activity.type === "quiz") return resource("quiz_revision_id", "测验修订");
    if (activity.type === "ai_coach") return resource("coach_profile_revision_id", "训练教练配置修订");
    if (activity.type === "audio_assessment") return <>{resource("audio_material_revision_id", "录音讲解材料修订")}{resource("scoring_scheme_revision_id", "评分规则修订")}<RecordingPolicyFields activity={activity} onChange={onChange} /></>;
    return <>{resource("scenario_revision_id", "客户场景修订")}{resource("scoring_scheme_revision_id", "评分规则修订")}<RecordingPolicyFields activity={activity} onChange={onChange} /><div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">首发客户场景固定为需求发现、异议处理、推进承诺三个异步录音片段。</div></>;
}

function RecordingPolicyFields({ activity, onChange }: { activity: Extract<FoundationActivityDefinitionV2, { type: "audio_assessment" | "assignment" }>; onChange: (updater: (activity: FoundationActivityDefinitionV2) => FoundationActivityDefinitionV2) => void }) {
    const patchConfig = (patch: Partial<typeof activity.config>) => onChange((current) => current.type === activity.type ? { ...current, config: { ...current.config, ...patch } } as FoundationActivityDefinitionV2 : current);
    return <div className="grid gap-4 sm:grid-cols-2"><Field label="最长录音（秒）"><Input type="number" min={1} max={1800} value={activity.config.max_duration_seconds} onChange={(event) => patchConfig({ max_duration_seconds: positiveNumber(event.target.value, 1) })} /></Field><Field label="语言"><Input value={activity.config.language} onChange={(event) => patchConfig({ language: event.target.value })} /></Field><fieldset className="sm:col-span-2"><legend className="text-sm font-medium text-slate-700">允许录音方式</legend><div className="mt-2 flex gap-4">{(["browser", "file"] as const).map((mode) => <label key={mode} className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={activity.config.allowed_recording_modes.includes(mode)} onChange={(event) => patchConfig({ allowed_recording_modes: event.target.checked ? [...activity.config.allowed_recording_modes, mode] : activity.config.allowed_recording_modes.filter((item) => item !== mode) })} />{mode === "browser" ? "浏览器录音" : "上传录音文件"}</label>)}</div></fieldset>{activity.type === "audio_assessment" ? <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2"><input type="checkbox" checked={activity.config.baseline_only} onChange={(event) => patchConfig({ baseline_only: event.target.checked })} />仅作为基线评测，不计入正式达标</label> : null}</div>;
}

function ResourceField({ label, bound, valueLabel, onOpen }: { label: string; bound: boolean; valueLabel?: string; onOpen: () => void }) {
    return <div className={`rounded-xl border p-4 ${bound ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50/50"}`}><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-medium text-slate-900">{label}</p><p className="mt-1 text-xs text-slate-600">{bound ? valueLabel ?? "已关联精确修订" : "尚未关联，可保存草稿后稍后补充"}</p></div><Button type="button" size="sm" variant="outline" className="bg-white" onClick={onOpen}>{bound ? "更换资源" : "选择或快速新建"}</Button></div></div>;
}

function PreviewPane({ draft, validation, dirty, selectedActivityId }: { draft: FoundationPathDraftV2; validation: FoundationPathValidation | null; dirty: boolean; selectedActivityId: string | null }) {
    const issues = validation?.issues ?? [];
    const selectedIssues = selectedActivityId ? issues.filter((issue) => issue.activity_id === selectedActivityId || issue.field.includes(selectedActivityId)) : issues;
    return <aside className="space-y-4"><section aria-labelledby="learner-preview-title" className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center gap-2"><Eye className="h-5 w-5 text-blue-600" /><h2 id="learner-preview-title" className="font-semibold text-slate-950">学员路径预览</h2></div><p className="mt-2 text-sm text-slate-600">{draft.title}</p><div className="mt-4 space-y-4">{draft.stages.map((stage, index) => <div key={stage.stage_id}><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">阶段 {index + 1}</p><h3 className="mt-1 font-medium text-slate-900">{stage.title}</h3><div className="mt-2 space-y-2">{stage.activities.map((activity) => <div key={activity.activity_id} className={`rounded-lg border px-3 py-2 ${activity.activity_id === selectedActivityId ? "border-blue-300 bg-blue-50" : "border-slate-100 bg-slate-50"}`}><div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium text-slate-800">{activity.title}</span><span className="shrink-0 text-xs text-slate-500">{activity.estimated_minutes} 分钟</span></div><p className="mt-1 text-xs text-slate-500">{ACTIVITY_LABELS[activity.type]} · {activity.required ? "必修" : "选修"}</p></div>)}</div></div>)}</div></section><section aria-labelledby="validation-title" className="rounded-2xl border border-slate-200 bg-white p-5"><h2 id="validation-title" className="font-semibold text-slate-950">校验与引用影响</h2>{dirty ? <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">先保存草稿，再运行与学员运行时一致的正式校验。</p> : !validation ? <p className="mt-3 text-sm text-slate-500">尚未运行正式校验。发布预览还会检查所有资源、能力映射、模型策略与在训影响。</p> : validation.valid ? <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />当前工作修订通过路径校验。</div> : <div className="mt-3 space-y-2"><p className="text-sm font-medium text-red-700">发现 {issues.length} 个阻塞项</p>{selectedIssues.map((issue, index) => <div key={`${issue.code}-${index}`} className="rounded-xl border border-red-100 bg-red-50 p-3 text-sm text-red-900"><p className="font-medium">{issue.message}</p><p className="mt-1 text-xs text-red-700">请在对应活动字段中处理。</p></div>)}</div>}<div className="mt-4 border-t border-slate-100 pt-4 text-xs leading-5 text-slate-500">发布新版只影响后续新分配；活跃 Enrollment 保持冻结修订，迁移必须单独预览并确认。</div></section></aside>;
}

function ReleasePreviewPanel({ preview }: { preview: FoundationReleasePreview }) {
    const issues = preview.validation_report.issues ?? [];
    const impact = preview.impact_preview;
    return <div className="space-y-4"><div className={`rounded-xl border p-4 ${preview.status === "ready" ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}><div className="flex items-center gap-2">{preview.status === "ready" ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <AlertTriangle className="h-5 w-5 text-red-600" />}<h3 className="font-semibold text-slate-950">{preview.status === "ready" ? "发布计划可以执行" : "发布计划存在阻塞"}</h3></div><p className="mt-2 text-sm text-slate-700">已冻结 {preview.target_revisions.length} 个精确修订，依赖图{preview.dependency_graph.acyclic === false ? "存在循环" : "无循环"}。</p></div>{issues.length > 0 ? <div className="space-y-2">{issues.map((issue, index) => <div key={`${issue.code}-${index}`} className="rounded-xl border border-red-100 bg-white p-3 text-sm"><p className="font-medium text-red-800">{issue.message}</p><p className="mt-1 text-xs text-slate-500">请返回路径中对应活动处理后重新创建预览。</p></div>)}</div> : null}<div className="rounded-xl border border-slate-200 bg-white p-4"><h3 className="font-medium text-slate-950">学员影响</h3><dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><Impact label="当前版本活跃学员" value={impactNumber(impact.active_enrollments_on_current_revision)} /><Impact label="正在进行的训练" value={impactNumber(impact.active_attempts)} /><Impact label="自动迁移活跃学员" value={impact.automatic_migration === false ? "不会" : "需要确认"} /><Impact label="新分配学员" value={impact.future_enrollments_use_target === true ? "使用新版本" : "待确认"} /></dl></div></div>;
}

function Field({ label, helper, children }: { label: string; helper?: string; children: React.ReactNode }) {
    return <label className="block space-y-1 text-sm font-medium text-slate-700"><span>{label}</span>{children}{helper ? <span className="block text-xs font-normal leading-5 text-slate-500">{helper}</span> : null}</label>;
}

function ListField({ label, helper, values, onChange }: { label: string; helper?: string; values: string[]; onChange: (values: string[]) => void }) {
    return <Field label={label} helper={helper}><textarea className={textareaClassName} value={values.join("\n")} onChange={(event) => onChange(lines(event.target.value))} /></Field>;
}

function IconButton({ label, children, onClick, disabled }: { label: string; children: React.ReactElement<{ className?: string }>; onClick: () => void; disabled?: boolean }) {
    return <button type="button" aria-label={label} disabled={disabled} onClick={onClick} className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-700 disabled:opacity-30">{children}</button>;
}

function Impact({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-slate-500">{label}</dt><dd className="mt-1 font-medium text-slate-900">{value}</dd></div>;
}

const textareaClassName = "min-h-24 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
const selectClassName = "h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";

function workspaceDraft(workspace: FoundationPathWorkspace): FoundationPathDraftV2 {
    const draft = cloneDraft(
        workspace.working_revision?.snapshot
        ?? workspace.published_revision?.snapshot
        ?? defaultDraft(workspace.path.title),
    );
    if (!workspace.working_revision && workspace.published_revision) {
        draft.revision_label = `${workspace.published_revision.revision_label} 后续修订`;
    }
    return draft;
}

function defaultDraft(title: string): FoundationPathDraftV2 {
    return { contract_version: "newcomer_training_path_v2", title, revision_label: "初始草稿", stages: [defaultStage(1)] };
}

function defaultStage(sequence: number): FoundationStageDefinitionV2 {
    return { stage_id: `stage-${generateClientId()}`, sequence, title: `阶段 ${sequence}`, objective: "说明本阶段希望新人达到的结果", entry_conditions: [], completion_rule: "all_required", visibility: "learner", activities: [defaultActivity("lesson")] };
}

function defaultActivity(type: FoundationActivityTypeV2): FoundationActivityDefinitionV2 {
    const common = { activity_id: `activity-${generateClientId()}`, type, title: ACTIVITY_LABELS[type], objective: "说明学员完成后能够做到什么", why_it_matters: "说明这项能力对新人销售工作的价值", steps: ["按要求完成训练"], success_criteria: ["达到本活动的完成标准"], competency_keys: [], estimated_minutes: 20, required: true, prerequisite_activity_ids: [], ai_dependency: type === "ai_coach" ? "required" as const : "none" as const, retry_policy: { max_attempts: 0, retry_interval_seconds: 0 } };
    if (type === "lesson") return { ...common, type, config: { learning_unit_revision_id: "", required_checkpoint_ids: [] } };
    if (type === "quiz") return { ...common, type, config: { quiz_revision_id: "" } };
    if (type === "ai_coach") return { ...common, type, config: { coach_profile_revision_id: "" } };
    const recording = { allowed_recording_modes: ["browser", "file"] as Array<"browser" | "file">, max_duration_seconds: 1800, max_size_bytes: 100 * 1024 * 1024, language: "zh-CN" };
    if (type === "audio_assessment") return { ...common, type, config: { audio_material_revision_id: "", scoring_scheme_revision_id: "", ...recording, baseline_only: false } };
    return { ...common, type, config: { scenario_revision_id: "", scoring_scheme_revision_id: "", ...recording, segment_ids: ["discovery", "objection", "commitment"] } };
}

function bindResource(activity: FoundationActivityDefinitionV2, field: FoundationResourceField, revisionId: string): FoundationActivityDefinitionV2 {
    if (activity.type === "lesson" && field === "learning_unit_revision_id") return { ...activity, config: { ...activity.config, learning_unit_revision_id: revisionId } };
    if (activity.type === "quiz" && field === "quiz_revision_id") return { ...activity, config: { ...activity.config, quiz_revision_id: revisionId } };
    if (activity.type === "ai_coach" && field === "coach_profile_revision_id") return { ...activity, config: { ...activity.config, coach_profile_revision_id: revisionId } };
    if (activity.type === "audio_assessment") {
        if (field === "audio_material_revision_id") return { ...activity, config: { ...activity.config, audio_material_revision_id: revisionId } };
        if (field === "scoring_scheme_revision_id") return { ...activity, config: { ...activity.config, scoring_scheme_revision_id: revisionId } };
    }
    if (activity.type === "assignment") {
        if (field === "scenario_revision_id") return { ...activity, config: { ...activity.config, scenario_revision_id: revisionId } };
        if (field === "scoring_scheme_revision_id") return { ...activity, config: { ...activity.config, scoring_scheme_revision_id: revisionId } };
    }
    return activity;
}

function resourceRevision(activity: FoundationActivityDefinitionV2, field: FoundationResourceField): string {
    const config = activity.config as unknown as Record<string, unknown>;
    return typeof config[field] === "string" ? config[field] : "";
}

function cloneDraft(value: FoundationPathDraftV2): FoundationPathDraftV2 {
    return JSON.parse(JSON.stringify(value)) as FoundationPathDraftV2;
}

function cloneStage(value: FoundationStageDefinitionV2): FoundationStageDefinitionV2 {
    return JSON.parse(JSON.stringify(value)) as FoundationStageDefinitionV2;
}

function cloneActivity(value: FoundationActivityDefinitionV2): FoundationActivityDefinitionV2 {
    return JSON.parse(JSON.stringify(value)) as FoundationActivityDefinitionV2;
}

function normalizeStageSequences(draft: FoundationPathDraftV2) {
    draft.stages = draft.stages.map((stage, index) => ({ ...stage, sequence: index + 1 }));
}

function lines(value: string): string[] {
    return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function positiveNumber(value: string, fallback: number): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 1 ? parsed : fallback;
}

function nonNegativeNumber(value: string): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function impactNumber(value: unknown): string {
    return typeof value === "number" ? `${value} 人/项` : "待确认";
}
