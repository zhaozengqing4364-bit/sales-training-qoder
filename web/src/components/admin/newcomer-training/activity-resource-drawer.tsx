"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassSheet } from "@/components/ui/glass-sheet";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { generateClientId } from "@/lib/client-id";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import type {
    FoundationActivityTypeV2,
    FoundationBindingResourceOption,
    FoundationBindingResourceType,
} from "@/lib/api/types/foundation-admin";

export type FoundationResourceField =
    | "learning_unit_revision_id"
    | "quiz_revision_id"
    | "audio_material_revision_id"
    | "scoring_scheme_revision_id"
    | "coach_profile_revision_id"
    | "scenario_revision_id";

const RESOURCE_LABELS: Record<FoundationBindingResourceType, string> = {
    learning_unit: "学习单元",
    quiz: "测验",
    audio_material: "录音讲解材料",
    scoring_scheme: "评分规则",
    scenario: "异步客户场景",
    coach_profile: "训练教练配置",
};

function resolveBindingType(
    activityType: FoundationActivityTypeV2,
    field: FoundationResourceField,
): FoundationBindingResourceType {
    if (activityType === "lesson") return "learning_unit";
    if (activityType === "quiz") return "quiz";
    if (activityType === "ai_coach") return "coach_profile";
    if (field === "scoring_scheme_revision_id") return "scoring_scheme";
    return activityType === "assignment" ? "scenario" : "audio_material";
}

export function ActivityResourceDrawer({
    open,
    activityType,
    field,
    currentRevisionId,
    onClose,
    onBind,
}: {
    open: boolean;
    activityType: FoundationActivityTypeV2;
    field: FoundationResourceField;
    currentRevisionId: string;
    onClose: () => void;
    onBind: (revisionId: string, label: string) => void;
}) {
    const queryClient = useQueryClient();
    const [tokenStore] = useState(() => createIdempotencyTokenStore());
    const resourceType = resolveBindingType(activityType, field);
    const [search, setSearch] = useState("");
    const [submittedSearch, setSubmittedSearch] = useState("");
    const [showQuickCreate, setShowQuickCreate] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const options = useQuery({
        queryKey: ["foundation-admin", "binding-resources", resourceType, submittedSearch],
        queryFn: () => api.admin.newcomerTraining.listBindingResources({
            resource_type: resourceType,
            search: submittedSearch || undefined,
            limit: 100,
        }),
        enabled: open,
    });

    const closeDrawer = () => {
        setSearch("");
        setSubmittedSearch("");
        setShowQuickCreate(false);
        setError(null);
        onClose();
    };

    const current = options.data?.items.find((item) => item.revision_id === currentRevisionId);
    const supportsQuickCreate = resourceType === "learning_unit" || resourceType === "quiz";

    return (
        <GlassSheet isOpen={open} onClose={closeDrawer} side="right" className="max-w-2xl overflow-y-auto rounded-l-3xl bg-white p-0">
            <div className="min-h-full px-5 pb-8 pt-6 sm:px-7">
                <div className="pr-12">
                    <p className="text-sm font-semibold text-blue-700">当前编辑流</p>
                    <h2 className="mt-1 text-xl font-semibold text-slate-950">选择{RESOURCE_LABELS[resourceType]}</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">选择精确修订后会自动关联到当前活动。工作修订可随发布计划一起审批；其他类型必须先完成本领域审批。</p>
                </div>

                {current ? (
                    <div className="mt-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
                        当前已选择：<span className="font-semibold">{current.title}</span> · 第 {current.revision_no} 版
                    </div>
                ) : currentRevisionId ? (
                    <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">当前引用未在可访问列表中，请重新选择或保留草稿后由有权限人员补充。</div>
                ) : null}

                <form
                    role="search"
                    className="mt-5 flex gap-2"
                    onSubmit={(event) => {
                        event.preventDefault();
                        setSubmittedSearch(search.trim());
                    }}
                >
                    <label className="relative flex-1">
                        <span className="sr-only">搜索资源</span>
                        <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-400" />
                        <Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-10" placeholder={`搜索${RESOURCE_LABELS[resourceType]}名称`} />
                    </label>
                    <Button type="submit" variant="outline">搜索</Button>
                </form>

                {supportsQuickCreate ? (
                    <div className="mt-4 flex justify-end">
                        <Button type="button" variant="ghost" size="sm" onClick={() => setShowQuickCreate((value) => !value)}>
                            <Plus className="mr-2 h-4 w-4" />{showQuickCreate ? "返回选择" : `快速新建${RESOURCE_LABELS[resourceType]}`}
                        </Button>
                    </div>
                ) : (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                        此资源包含评分或模型治理配置，不能用默认值代替审批。当前活动可先保留未绑定草稿，再由具备相应权限的负责人在本编辑流中选择已发布修订。
                    </div>
                )}

                {showQuickCreate && resourceType === "learning_unit" ? (
                    <QuickLearningUnitForm
                        tokenStore={tokenStore}
                        onCreated={(revisionId, label) => {
                            void queryClient.invalidateQueries({ queryKey: ["foundation-admin", "binding-resources", resourceType] });
                            onBind(revisionId, label);
                            closeDrawer();
                        }}
                    />
                ) : showQuickCreate && resourceType === "quiz" ? (
                    <QuickQuizForm
                        tokenStore={tokenStore}
                        onCreated={(revisionId, label) => {
                            void queryClient.invalidateQueries({ queryKey: ["foundation-admin", "binding-resources", resourceType] });
                            onBind(revisionId, label);
                            closeDrawer();
                        }}
                    />
                ) : (
                    <div className="mt-4 space-y-2">
                        {options.isPending ? (
                            <div aria-label="正在加载资源" className="space-y-2">{[0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100" />)}</div>
                        ) : options.error ? (
                            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                                资源加载失败：{getApiErrorMessage(options.error)}
                                <button type="button" className="ml-2 font-semibold underline" onClick={() => void options.refetch()}>重试</button>
                            </div>
                        ) : options.data?.items.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">没有可选择的{RESOURCE_LABELS[resourceType]}。{supportsQuickCreate ? "可在此处快速新建最小草稿。" : "可先保存当前路径草稿，稍后补充。"}</div>
                        ) : options.data ? options.data.items.map((item) => (
                            <ResourceOption
                                key={item.revision_id}
                                item={item}
                                selected={item.revision_id === currentRevisionId}
                                onSelect={() => {
                                    if (!item.bindable) return;
                                    setError(null);
                                    onBind(item.revision_id, `${item.title} · 第 ${item.revision_no} 版`);
                                    closeDrawer();
                                }}
                            />
                        )) : null}
                    </div>
                )}
                {error ? <p role="alert" className="mt-4 text-sm text-red-700">{error}</p> : null}
            </div>
        </GlassSheet>
    );
}

function ResourceOption({ item, selected, onSelect }: { item: FoundationBindingResourceOption; selected: boolean; onSelect: () => void }) {
    return (
        <button
            type="button"
            disabled={!item.bindable}
            onClick={onSelect}
            className="flex w-full items-start justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 text-left hover:border-blue-300 hover:bg-blue-50/40 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-70"
        >
            <span className="min-w-0">
                <span className="block truncate font-medium text-slate-950">{item.title}</span>
                <span className="mt-1 block text-xs text-slate-500">第 {item.revision_no} 版 · {item.stable_key}</span>
                {!item.bindable ? <span className="mt-2 block text-xs text-amber-700">完成审批发布后才能关联</span> : item.needs_approval ? <span className="mt-2 block text-xs text-blue-700">将由发布计划统一审批</span> : null}
            </span>
            <span className="flex shrink-0 items-center gap-2">
                <Badge variant={item.status === "published" ? "green" : "gray"}>{item.status === "published" ? "已发布" : item.status === "working" ? "工作修订" : "不可用"}</Badge>
                {selected ? <Check className="h-4 w-4 text-blue-600" aria-label="当前选择" /> : null}
            </span>
        </button>
    );
}

function QuickLearningUnitForm({ tokenStore, onCreated }: { tokenStore: ReturnType<typeof createIdempotencyTokenStore>; onCreated: (revisionId: string, label: string) => void }) {
    const queryClient = useQueryClient();
    const [title, setTitle] = useState("");
    const [stableKey, setStableKey] = useState("");
    const [objective, setObjective] = useState("");
    const [concept, setConcept] = useState("");
    const [checkpoint, setCheckpoint] = useState("");
    const [sourceRevisionId, setSourceRevisionId] = useState("");
    const [anchorId, setAnchorId] = useState("");
    const [anchorLabel, setAnchorLabel] = useState("");
    const [excerpt, setExcerpt] = useState("");
    const [page, setPage] = useState("1");
    const [sourceTitle, setSourceTitle] = useState("");
    const [sourceUrl, setSourceUrl] = useState("");
    const [error, setError] = useState<string | null>(null);

    const sources = useQuery({
        queryKey: ["foundation-admin", "resources", "source_document"],
        queryFn: () => api.admin.newcomerTraining.listResourcesV2({ resource_type: "source_document", page_size: 100 }),
    });
    const anchors = useQuery({
        queryKey: ["foundation-admin", "source-anchors", sourceRevisionId],
        queryFn: () => api.admin.newcomerTraining.listSourceAnchorsV2(sourceRevisionId),
        enabled: Boolean(sourceRevisionId),
    });

    const createSource = useMutation({
        mutationFn: async () => {
            if (!sourceTitle.trim() || !sourceUrl.trim()) throw new Error("请填写来源名称和可访问地址。");
            const key = `quick-source:${sourceTitle.trim()}:${sourceUrl.trim()}`;
            const created = await api.admin.newcomerTraining.createResourceV2(
                "source_document",
                {
                    resource_type: "source_document",
                    stable_key: stableKeyValue(sourceTitle, "source"),
                    title: sourceTitle.trim(),
                    working_revision: {
                        revision_label: "初始修订",
                        source_type: "url",
                        source_uri: sourceUrl.trim(),
                        file_hash: await sha256Hex(sourceUrl.trim()),
                        parser_version: "manual-review-v1",
                        parse_status: "ready",
                    },
                },
                tokenStore.tokenFor(key),
            );
            const resource = record(created.resource);
            const revisionId = stringValue(record(created.working_revision).revision_id);
            if (!stringValue(resource.document_id) || !revisionId) throw new Error("来源已创建，但返回修订信息不完整，请刷新后重试。");
            tokenStore.complete(key);
            return revisionId;
        },
        onSuccess: async (revisionId) => {
            await queryClient.invalidateQueries({ queryKey: ["foundation-admin", "resources", "source_document"] });
            setSourceRevisionId(revisionId);
            setAnchorId("");
            setSourceTitle("");
            setSourceUrl("");
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    const createAnchor = useMutation({
        mutationFn: async () => {
            if (!sourceRevisionId) throw new Error("请先选择已核对来源。");
            if (!anchorLabel.trim() || !excerpt.trim()) throw new Error("请填写来源位置名称和对应摘录。");
            const parsedPage = Number(page);
            if (!Number.isInteger(parsedPage) || parsedPage < 1) throw new Error("来源页码必须是大于 0 的整数。");
            const key = `quick-anchor:${sourceRevisionId}:${anchorLabel.trim()}:${excerpt.trim()}:${parsedPage}`;
            const result = await api.admin.newcomerTraining.createSourceAnchorV2(
                sourceRevisionId,
                {
                    anchor_key: `anchor-${generateClientId()}`,
                    label: anchorLabel.trim(),
                    locator: { type: "page", page: parsedPage, start_offset: 0, end_offset: Math.max(1, excerpt.trim().length) },
                    excerpt_hash: await sha256Hex(excerpt.trim()),
                },
                tokenStore.tokenFor(key),
            );
            tokenStore.complete(key);
            return result;
        },
        onSuccess: async (result) => {
            setAnchorId(result.anchor_id);
            await queryClient.invalidateQueries({ queryKey: ["foundation-admin", "source-anchors", sourceRevisionId] });
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    const createUnit = useMutation({
        mutationFn: async () => {
            if (!title.trim() || !stableKey.trim() || !objective.trim() || !concept.trim() || !checkpoint.trim()) throw new Error("请完成学习单元的名称、编码、目标、核心内容和检查点。");
            if (!anchorId) throw new Error("请选择或新建来源位置。");
            const key = `quick-unit:${stableKey.trim()}:${title.trim()}:${anchorId}`;
            const result = await api.admin.newcomerTraining.createResourceV2(
                "learning_unit",
                {
                    resource_type: "learning_unit",
                    stable_key: stableKey.trim(),
                    title: title.trim(),
                    working_revision: {
                        revision_label: "初始草稿",
                        title: title.trim(),
                        objectives: [objective.trim()],
                        key_concepts: [{
                            concept_id: `concept-${generateClientId()}`,
                            title: title.trim(),
                            content: concept.trim(),
                            source_anchor_ids: [anchorId],
                        }],
                        examples: [],
                        checkpoints: [{ checkpoint_id: `checkpoint-${generateClientId()}`, prompt: checkpoint.trim(), required: true }],
                        practice_hints: [],
                    },
                },
                tokenStore.tokenFor(key),
            );
            tokenStore.complete(key);
            const revisionId = stringValue(record(result.working_revision).revision_id);
            if (!revisionId) throw new Error("学习单元已创建，但修订信息不完整，请刷新资源列表后选择。");
            return revisionId;
        },
        onSuccess: (revisionId) => onCreated(revisionId, `${title.trim()} · 工作修订`),
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    const sourceItems = sources.data?.items.filter((item) => item.working_revision_id || item.published_revision_id) ?? [];
    const anchorItems = anchors.data?.items ?? [];
    return (
        <div className="mt-4 space-y-5 rounded-2xl border border-blue-200 bg-blue-50/40 p-5">
            <div>
                <h3 className="font-semibold text-slate-950">快速新建学习单元草稿</h3>
                <p className="mt-1 text-sm text-slate-600">来源必须先被明确核对；材料与学习单元由发布计划统一校验和批准。</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
                <Field label="学习单元名称"><Input value={title} onChange={(event) => setTitle(event.target.value)} /></Field>
                <Field label="业务编码"><Input value={stableKey} onChange={(event) => setStableKey(event.target.value)} placeholder="例如：product-value" /></Field>
            </div>
            <Field label="学习目标"><Input value={objective} onChange={(event) => setObjective(event.target.value)} /></Field>
            <TextField label="核心内容" value={concept} onChange={setConcept} />
            <Field label="必修检查点"><Input value={checkpoint} onChange={(event) => setCheckpoint(event.target.value)} placeholder="例如：能用自己的话说明核心价值" /></Field>

            <div className="border-t border-blue-100 pt-4">
                <Field label="已核对原始材料">
                    <select className={selectClassName} value={sourceRevisionId} onChange={(event) => { setSourceRevisionId(event.target.value); setAnchorId(""); }}>
                        <option value="">请选择来源</option>
                        {sourceItems.map((item) => { const revisionId = item.working_revision_id ?? item.published_revision_id ?? ""; return <option key={item.resource_id} value={revisionId}>{item.title}{item.working_revision_id ? " · 工作修订" : " · 已发布"}</option>; })}
                    </select>
                </Field>
                {sources.isPending ? <p className="mt-2 text-xs text-slate-500">正在加载来源…</p> : null}
                {sourceItems.length === 0 && !sources.isPending ? (
                    <div className="mt-3 space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                        <p className="text-sm font-medium text-slate-800">当前没有可用来源，可在这里录入并核对一个网址来源。</p>
                        <Field label="来源名称"><Input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} /></Field>
                        <Field label="来源地址"><Input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://…" /></Field>
                        <Button type="button" variant="outline" size="sm" onClick={() => { setError(null); createSource.mutate(); }} disabled={createSource.isPending}>{createSource.isPending ? "正在创建…" : "创建并选择来源"}</Button>
                    </div>
                ) : null}
            </div>

            {sourceRevisionId ? (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                    <Field label="来源位置">
                        <select className={selectClassName} value={anchorId} onChange={(event) => setAnchorId(event.target.value)}>
                            <option value="">请选择已有位置</option>
                            {anchorItems.map((item) => <option key={item.anchor_id} value={item.anchor_id}>{item.label}</option>)}
                        </select>
                    </Field>
                    <p className="text-xs text-slate-500">没有合适位置时，可在当前流程新建。</p>
                    <div className="grid gap-3 sm:grid-cols-[1fr_100px]">
                        <Field label="位置名称"><Input value={anchorLabel} onChange={(event) => setAnchorLabel(event.target.value)} placeholder="例如：第 3 页产品价值" /></Field>
                        <Field label="页码"><Input inputMode="numeric" value={page} onChange={(event) => setPage(event.target.value)} /></Field>
                    </div>
                    <TextField label="对应摘录" value={excerpt} onChange={setExcerpt} />
                    <Button type="button" size="sm" variant="outline" onClick={() => { setError(null); createAnchor.mutate(); }} disabled={createAnchor.isPending}>{createAnchor.isPending ? "正在保存…" : "新建并选择来源位置"}</Button>
                </div>
            ) : null}

            {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
            <Button type="button" onClick={() => { setError(null); createUnit.mutate(); }} disabled={createUnit.isPending}>{createUnit.isPending ? "正在创建…" : "创建并关联学习单元"}</Button>
        </div>
    );
}

function QuickQuizForm({ tokenStore, onCreated }: { tokenStore: ReturnType<typeof createIdempotencyTokenStore>; onCreated: (revisionId: string, label: string) => void }) {
    const [title, setTitle] = useState("");
    const [stableKey, setStableKey] = useState("");
    const [selected, setSelected] = useState<string[]>([]);
    const [error, setError] = useState<string | null>(null);
    const questions = useQuery({
        queryKey: ["foundation-admin", "resources", "question", "approved"],
        queryFn: () => api.admin.newcomerTraining.listResourcesV2({ resource_type: "question", page_size: 100 }),
    });
    const createQuiz = useMutation({
        mutationFn: async () => {
            if (!title.trim() || !stableKey.trim()) throw new Error("请填写测验名称和业务编码。");
            if (selected.length === 0) throw new Error("至少选择一道已批准题目。");
            const key = `quick-quiz:${stableKey.trim()}:${title.trim()}:${selected.join(",")}`;
            const result = await api.admin.newcomerTraining.createResourceV2(
                "quiz",
                {
                    resource_type: "quiz",
                    stable_key: stableKey.trim(),
                    title: title.trim(),
                    working_revision: {
                        revision_label: "初始草稿",
                        title: title.trim(),
                        questions: selected.map((revisionId) => ({ question_revision_id: revisionId, points: 1 })),
                        pass_threshold: 80,
                        max_attempts: 3,
                        retry_interval_seconds: 300,
                        feedback_policy: "after_submit",
                        time_limit_minutes: null,
                        shuffle_questions: false,
                        shuffle_options: false,
                        short_answer_scoring: null,
                    },
                },
                tokenStore.tokenFor(key),
            );
            tokenStore.complete(key);
            const revisionId = stringValue(record(result.working_revision).revision_id);
            if (!revisionId) throw new Error("测验已创建，但修订信息不完整，请刷新资源列表后选择。");
            return revisionId;
        },
        onSuccess: (revisionId) => onCreated(revisionId, `${title.trim()} · 工作修订`),
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });
    const items = useMemo(() => questions.data?.items.filter((item) =>
        ["approved", "published"].includes(item.status)
        && Boolean(item.working_revision_id || item.published_revision_id)
    ) ?? [], [questions.data]);
    return (
        <div className="mt-4 space-y-4 rounded-2xl border border-blue-200 bg-blue-50/40 p-5">
            <div><h3 className="font-semibold text-slate-950">快速新建测验草稿</h3><p className="mt-1 text-sm text-slate-600">只允许选择已经人工批准的题目修订；测验将在发布计划中再次校验。</p></div>
            <div className="grid gap-3 sm:grid-cols-2">
                <Field label="测验名称"><Input value={title} onChange={(event) => setTitle(event.target.value)} /></Field>
                <Field label="业务编码"><Input value={stableKey} onChange={(event) => setStableKey(event.target.value)} /></Field>
            </div>
            <fieldset className="space-y-2">
                <legend className="text-sm font-medium text-slate-700">已批准题目</legend>
                {questions.isPending ? <p className="text-sm text-slate-500">正在加载题目…</p> : items.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">暂无已批准题目。可先保存当前路径草稿，由题目审核人员完成审批后再回来选择。</p> : items.map((item) => {
                    const revisionId = item.working_revision_id ?? item.published_revision_id ?? "";
                    return <label key={item.resource_id} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700"><input type="checkbox" className="mt-1 h-4 w-4" checked={selected.includes(revisionId)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, revisionId] : current.filter((value) => value !== revisionId))} /><span><span className="block font-medium text-slate-950">{item.title}</span><span className="mt-1 block text-xs text-slate-500">{item.status === "approved" ? "已人工批准，将由发布计划生效" : "已发布正式题目"}</span></span></label>;
                })}
            </fieldset>
            {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
            <Button type="button" onClick={() => { setError(null); createQuiz.mutate(); }} disabled={createQuiz.isPending}>{createQuiz.isPending ? "正在创建…" : "创建并关联测验"}</Button>
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return <label className="block space-y-1 text-sm font-medium text-slate-700"><span>{label}</span>{children}</label>;
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return <label className="block space-y-1 text-sm font-medium text-slate-700"><span>{label}</span><textarea className="min-h-24 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

const selectClassName = "h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";

function record(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function stringValue(value: unknown): string {
    return typeof value === "string" ? value : "";
}

function stableKeyValue(value: string, prefix: string): string {
    const normalized = value.trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-").replace(/^-|-$/g, "");
    return `${prefix}-${normalized || generateClientId().slice(0, 8)}`.slice(0, 160);
}

async function sha256Hex(value: string): Promise<string> {
    const bytes = new TextEncoder().encode(value);
    if (globalThis.crypto?.subtle) {
        const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
        return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    }
    // The app is normally served in a secure context.  This fallback remains
    // deterministic for local HTTP demos; server validation still governs the
    // source lifecycle and never treats this as a security credential.
    let hash = 2_166_136_261;
    for (const byte of bytes) {
        hash ^= byte;
        hash = Math.imul(hash, 16_777_619);
    }
    return Array.from({ length: 8 }, (_, index) => (hash + index * 2_654_435_761) >>> 0)
        .map((part) => part.toString(16).padStart(8, "0"))
        .join("")
        .slice(0, 64);
}
