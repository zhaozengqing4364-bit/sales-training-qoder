"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BookOpen, Download, FileText, Plus, Search, Upload } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { generateClientId } from "@/lib/client-id";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import type { FoundationLearningResourceDetail } from "@/lib/api/types/foundation-admin";
import type { FoundationSourceContentKind } from "@/lib/api/types/foundation-admin";
import {
    toFoundationSourceRevisionViewModel,
    type FoundationSourceRevisionViewModel,
} from "@/lib/newcomer-training/view-models";

type ContentType = "source_document" | "learning_unit";

export function FoundationContentWorkspace() {
    const queryClient = useQueryClient();
    const [tokenStore] = useState(() => createIdempotencyTokenStore());
    const [contentType, setContentType] = useState<ContentType>("source_document");
    const [search, setSearch] = useState("");
    const [submittedSearch, setSubmittedSearch] = useState("");
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [showCreate, setShowCreate] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const resources = useQuery({
        queryKey: ["foundation-admin", "content-resources", contentType, submittedSearch],
        queryFn: () => api.admin.newcomerTraining.listResourcesV2({
            resource_type: contentType,
            search: submittedSearch || undefined,
            page_size: 100,
        }),
    });
    const detail = useQuery({
        queryKey: ["foundation-admin", "content-resource", contentType, selectedId],
        queryFn: () => api.admin.newcomerTraining.getResourceV2(contentType, selectedId ?? ""),
        enabled: Boolean(selectedId),
    });

    const refresh = async () => {
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: ["foundation-admin", "content-resources", contentType] }),
            queryClient.invalidateQueries({ queryKey: ["foundation-admin", "content-resource", contentType] }),
        ]);
    };

    return (
        <FoundationAdminCapabilityBoundary capability="edit_content">
            <main className="px-4 py-6 md:px-6">
                <div className="mx-auto max-w-[1500px] space-y-6">
                    <AdminPageHeader
                        title="内容工作区"
                        description="原始材料、来源位置和整理后的学习单元分别保留修订；训练路径只绑定精确版本。"
                        icon={<BookOpen className="h-7 w-7 text-blue-600" />}
                        primaryAction={<Button type="button" onClick={() => setShowCreate((value) => !value)}><Plus className="mr-2 h-4 w-4" />新建{contentType === "source_document" ? "原始材料" : "学习单元"}</Button>}
                    />

                    <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
                        <Button type="button" variant={contentType === "source_document" ? "primary" : "ghost"} onClick={() => { setContentType("source_document"); setSelectedId(null); setShowCreate(false); }}>原始材料与来源</Button>
                        <Button type="button" variant={contentType === "learning_unit" ? "primary" : "ghost"} onClick={() => { setContentType("learning_unit"); setSelectedId(null); setShowCreate(false); }}>整理后学习单元</Button>
                    </div>

                    {showCreate ? contentType === "source_document" ? (
                        <CreateSourceForm tokenStore={tokenStore} onCreated={async (resourceId, nextMessage) => { setSelectedId(resourceId); setShowCreate(false); setMessage(nextMessage); await refresh(); }} />
                    ) : (
                        <CreateUnitForm tokenStore={tokenStore} onCreated={async (resourceId) => { setSelectedId(resourceId); setShowCreate(false); setMessage("学习单元草稿已创建，可由路径发布计划统一校验和批准。"); await refresh(); }} />
                    ) : null}

                    {message ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div> : null}
                    {error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div> : null}

                    <div className="grid min-h-[620px] gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
                        <section aria-label="内容列表" className="rounded-2xl border border-slate-200 bg-white p-4">
                            <form role="search" className="flex gap-2" onSubmit={(event) => { event.preventDefault(); setSubmittedSearch(search.trim()); }}>
                                <label className="relative min-w-0 flex-1"><span className="sr-only">搜索内容</span><Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" /><Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="搜索名称或业务编码" /></label>
                                <Button type="submit" variant="outline" size="sm">搜索</Button>
                            </form>
                            <div className="mt-3 space-y-2">
                                {resources.isPending ? [0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100" />) : resources.error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{getApiErrorMessage(resources.error)}<button type="button" className="ml-2 font-semibold underline" onClick={() => void resources.refetch()}>重试</button></div> : resources.data?.items.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">{submittedSearch ? "没有匹配内容" : "还没有内容，可从当前工作区新建。"}</div> : resources.data?.items.map((item) => <button key={item.resource_id} type="button" onClick={() => setSelectedId(item.resource_id)} className={`w-full rounded-xl border p-4 text-left ${selectedId === item.resource_id ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}><div className="flex items-start justify-between gap-2"><span className="min-w-0 truncate font-medium text-slate-950">{item.title}</span><Badge variant={item.status === "active" ? "green" : item.status === "archived" ? "gray" : "orange"}>{item.status === "active" ? "已发布" : item.status === "archived" ? "已归档" : "草稿"}</Badge></div><p className="mt-2 truncate text-xs text-slate-500">{item.working_revision_id ? "有工作修订" : "无待发布修改"} · {new Date(item.updated_at).toLocaleDateString("zh-CN")}</p></button>) }
                            </div>
                        </section>

                        <section aria-label="内容详情" className="rounded-2xl border border-slate-200 bg-white p-5">
                            {!selectedId ? <div className="grid h-full min-h-80 place-items-center text-center text-sm text-slate-500"><div><FileText className="mx-auto h-8 w-8 text-slate-300" /><p className="mt-3">从左侧选择内容查看修订和来源。</p></div></div> : detail.isPending ? <div aria-label="正在加载内容详情" className="space-y-3">{[0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100" />)}</div> : detail.error || !detail.data ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-900"><h2 className="font-semibold">内容详情加载失败</h2><p className="mt-2 text-sm">{getApiErrorMessage(detail.error)}</p><Button type="button" variant="outline" className="mt-4 bg-white" onClick={() => void detail.refetch()}>重新加载</Button></div> : contentType === "source_document" ? <SourceDetail key={`${detail.data.resource.resource_id}:${detail.data.resource.version}`} detail={detail.data} tokenStore={tokenStore} onChanged={async (nextMessage) => { setMessage(nextMessage); setError(null); await refresh(); }} onError={(caught) => setError(getApiErrorMessage(caught))} /> : <UnitDetail key={`${detail.data.resource.resource_id}:${detail.data.resource.version}`} detail={detail.data} tokenStore={tokenStore} onChanged={async (nextMessage) => { setMessage(nextMessage); setError(null); await refresh(); }} onError={(caught) => setError(getApiErrorMessage(caught))} />}
                        </section>
                    </div>
                </div>
            </main>
        </FoundationAdminCapabilityBoundary>
    );
}

export function CreateSourceForm({ tokenStore, onCreated }: { tokenStore: ReturnType<typeof createIdempotencyTokenStore>; onCreated: (resourceId: string, message: string) => void }) {
    const [contentKind, setContentKind] = useState<FoundationSourceContentKind>("document");
    const [title, setTitle] = useState("");
    const [stableKey, setStableKey] = useState("");
    const [url, setUrl] = useState("");
    const [manualContent, setManualContent] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [revisionLabel, setRevisionLabel] = useState("初始草稿");
    const [error, setError] = useState<string | null>(null);
    const sourceMode = contentKind === "external_demo" ? "url" : contentKind === "script" ? "manual" : "file";
    const create = useMutation({
        mutationFn: async () => {
            if (!title.trim() || !stableKey.trim()) throw new Error("请填写材料名称和业务编码。");
            let key: string;
            let result: Record<string, unknown>;
            let message: string;
            if (sourceMode === "file") {
                if (!file) throw new Error("请选择要上传的材料文件。");
                const validationError = validateSourceUploadFile(file, contentKind);
                if (validationError) throw new Error(validationError);
                key = `upload-source:${stableKey.trim()}:${file.name}:${file.size}:${file.lastModified}`;
                const formData = new FormData();
                formData.set("stable_key", stableKey.trim());
                formData.set("title", title.trim());
                formData.set("revision_label", revisionLabel.trim() || "初始草稿");
                formData.set("content_kind", contentKind);
                formData.set("file", file);
                result = await api.admin.newcomerTraining.uploadSourceDocumentV2(
                    formData,
                    tokenStore.tokenFor(key),
                );
                message = "材料已安全保存并进入后台解析；解析完成前不能发布，可在评测任务中查看进度或恢复失败任务。";
            } else {
                const sourceValue = sourceMode === "url" ? url.trim() : manualContent.trim();
                if (sourceMode === "url" && !sourceValue.startsWith("https://")) throw new Error("外部 Demo 必须使用 HTTPS 地址。");
                if (sourceMode === "manual" && !sourceValue) throw new Error("请填写讲解稿正文。");
                key = `create-source:${contentKind}:${stableKey.trim()}:${sourceValue}`;
                result = await api.admin.newcomerTraining.createResourceV2("source_document", { resource_type: "source_document", stable_key: stableKey.trim(), title: title.trim(), working_revision: { revision_label: revisionLabel.trim() || "初始草稿", source_type: sourceMode, content_kind: contentKind, source_uri: sourceMode === "url" ? sourceValue : `manual://learning/source/${generateClientId()}`, file_hash: await sha256Hex(sourceValue), parser_version: "curated-source-v1", parse_status: "ready", processing_state: "ready", processing_stage: "curated", preview_version: "learning-preview-v1", ...(sourceMode === "manual" ? { manual_content: sourceValue } : {}) } }, tokenStore.tokenFor(key));
                const revisionId = text(record(result.working_revision).revision_id);
                if (!revisionId) throw new Error("材料已创建，但修订信息不完整，请刷新后重试。");
                await api.admin.newcomerTraining.createSourceAnchorV2(revisionId, { anchor_key: sourceMode === "url" ? "external-link" : "full-script", label: sourceMode === "url" ? "Demo 入口" : "完整讲解稿", locator: { type: "paragraph", paragraph_id: sourceMode === "url" ? "external-link" : "full-script", start_offset: 0, end_offset: Math.max(1, sourceValue.length) }, excerpt_hash: await sha256Hex(sourceValue) }, tokenStore.tokenFor(`${key}:anchor`));
                tokenStore.complete(`${key}:anchor`);
                message = sourceMode === "url" ? "受控 Demo 链接已创建；学员端只会在新窗口打开，不会执行嵌入脚本。" : "讲解稿已创建并保留来源定位，可继续编排学习单元。";
            }
            tokenStore.complete(key);
            const resourceId = text(record(result.resource).document_id);
            if (!resourceId) throw new Error("材料已创建，但返回信息不完整，请刷新列表。");
            return { resourceId, message };
        },
        onSuccess: ({ resourceId, message }) => onCreated(resourceId, message),
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });
    return (
        <section aria-labelledby="create-source-title" className="rounded-2xl border border-blue-200 bg-blue-50/50 p-5">
            <h2 id="create-source-title" className="font-semibold text-slate-950">新建原始材料草稿</h2>
            <p className="mt-1 text-sm text-slate-600">先选择业务材料类型；系统会使用对应的受控上传、链接或手工正文合同。</p>
            <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); setError(null); create.mutate(); }}>
                <Field label="材料类型"><select className={selectClassName} value={contentKind} onChange={(event) => { setContentKind(event.target.value as FoundationSourceContentKind); setFile(null); setError(null); }}>{SOURCE_KIND_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="材料名称"><Input value={title} onChange={(event) => setTitle(event.target.value)} /></Field>
                <Field label="业务编码"><Input value={stableKey} onChange={(event) => setStableKey(event.target.value)} /></Field>
                {sourceMode === "url" ? (
                    <Field label="来源地址"><Input type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://…" /></Field>
                ) : sourceMode === "manual" ? (
                    <label className="space-y-1 text-sm font-medium text-slate-700 md:col-span-2">讲解稿正文<textarea className={`${textareaClassName} min-h-40`} value={manualContent} onChange={(event) => setManualContent(event.target.value)} maxLength={100000} /></label>
                ) : (
                    <div className="space-y-1 text-sm text-slate-700">
                        <label htmlFor="source-upload-file" className="font-medium">材料文件</label>
                        <Input
                            id="source-upload-file"
                            type="file"
                            accept={sourceAccept(contentKind)}
                            aria-describedby="source-upload-help"
                            onChange={(event) => {
                                const selected = event.target.files?.[0] ?? null;
                                setFile(selected);
                                setError(selected ? validateSourceUploadFile(selected, contentKind) : null);
                            }}
                        />
                        <span id="source-upload-help" className="block text-xs text-slate-500">{sourceUploadHelp(contentKind)}。旧版 .ppt 请先另存为 .pptx；上传后可离开页面，真实处理结果会保留。</span>
                    </div>
                )}
                <Field label="修订说明"><Input value={revisionLabel} onChange={(event) => setRevisionLabel(event.target.value)} /></Field>
                {error ? <p role="alert" className="text-sm text-red-700 md:col-span-2">{error}</p> : null}
                <div className="md:col-span-2">
                    <Button type="submit" disabled={create.isPending || Boolean(error)}>
                        {create.isPending ? sourceMode === "file" ? "正在上传…" : "正在创建…" : sourceMode === "file" ? <><Upload className="mr-2 h-4 w-4" />上传并开始处理</> : "创建材料草稿"}
                    </Button>
                </div>
            </form>
        </section>
    );
}

function CreateUnitForm({ tokenStore, onCreated }: { tokenStore: ReturnType<typeof createIdempotencyTokenStore>; onCreated: (resourceId: string) => void }) {
    const [blockType, setBlockType] = useState<"rich_text" | "source_excerpt" | "slide_deck" | "video" | "audio_example" | "attachment">("rich_text");
    const [sourceRevisionId, setSourceRevisionId] = useState("");
    const [anchorId, setAnchorId] = useState("");
    const [title, setTitle] = useState("");
    const [stableKey, setStableKey] = useState("");
    const [objective, setObjective] = useState("");
    const [content, setContent] = useState("");
    const [checkpoint, setCheckpoint] = useState("");
    const [error, setError] = useState<string | null>(null);
    const sources = useQuery({ queryKey: ["foundation-admin", "source-options"], queryFn: () => api.admin.newcomerTraining.listResourcesV2({ resource_type: "source_document", page_size: 100 }) });
    const anchors = useQuery({ queryKey: ["foundation-admin", "source-anchors", sourceRevisionId], queryFn: () => api.admin.newcomerTraining.listSourceAnchorsV2(sourceRevisionId), enabled: Boolean(sourceRevisionId) });
    const create = useMutation({
        mutationFn: async () => {
            if (!title.trim() || !stableKey.trim() || !objective.trim() || !checkpoint.trim()) throw new Error("请完整填写学习单元内容。");
            if (["rich_text", "source_excerpt"].includes(blockType) && !content.trim()) throw new Error("请填写正文或来源摘录。");
            if (!anchorId) throw new Error("请选择一个已核对的来源位置。");
            const key = `create-unit:${stableKey.trim()}:${anchorId}`;
            const sourceBlockId = `block-${generateClientId()}`;
            const sourceBlock = {
                type: blockType,
                block_id: sourceBlockId,
                title: title.trim(),
                description: objective.trim(),
                order: 1,
                accessibility_alt: `${title.trim()}的训练材料`,
                source_revision_id: sourceRevisionId,
                source_anchor_id: anchorId,
                ...(blockType === "rich_text" ? { markdown: content.trim() } : {}),
                ...(blockType === "source_excerpt" ? { excerpt: content.trim() } : {}),
                ...(blockType === "slide_deck" ? { start_page: 1, end_page: null } : {}),
                ...(["video", "audio_example"].includes(blockType) ? { start_ms: 0, end_ms: null } : {}),
                ...(blockType === "attachment" ? { download_label: `下载${title.trim()}` } : {}),
            };
            const result = await api.admin.newcomerTraining.createResourceV2("learning_unit", { resource_type: "learning_unit", stable_key: stableKey.trim(), title: title.trim(), working_revision: { revision_label: "初始草稿", title: title.trim(), objectives: [objective.trim()], key_concepts: [], examples: [], checkpoints: [], practice_hints: [], content_blocks: [sourceBlock, { type: "checkpoint", block_id: `checkpoint-${generateClientId()}`, title: "学习检查点", description: null, order: 2, accessibility_alt: "学习完成检查点", prompt: checkpoint.trim(), required: true }] } }, tokenStore.tokenFor(key));
            tokenStore.complete(key);
            const resourceId = text(record(result.resource).unit_id);
            if (!resourceId) throw new Error("学习单元已创建，但返回信息不完整，请刷新列表。");
            return resourceId;
        },
        onSuccess: onCreated,
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });
    const sourceItems = sources.data?.items.filter((item) => item.working_revision_id || item.published_revision_id) ?? [];
    return <section aria-labelledby="create-unit-title" className="rounded-2xl border border-blue-200 bg-blue-50/50 p-5"><h2 id="create-unit-title" className="font-semibold text-slate-950">新建学习单元草稿</h2><p className="mt-1 text-sm text-slate-600">学习内容块必须同时冻结材料修订和来源位置；材料与学习单元由同一发布计划校验。</p><form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); setError(null); create.mutate(); }}><Field label="学习单元名称"><Input value={title} onChange={(event) => setTitle(event.target.value)} /></Field><Field label="业务编码"><Input value={stableKey} onChange={(event) => setStableKey(event.target.value)} /></Field><Field label="内容块类型"><select className={selectClassName} value={blockType} onChange={(event) => setBlockType(event.target.value as typeof blockType)}><option value="rich_text">精编正文</option><option value="source_excerpt">来源摘录</option><option value="slide_deck">PPT 分页讲解</option><option value="video">Demo 视频 / 链接</option><option value="audio_example">示范音频</option><option value="attachment">附件</option></select></Field><Field label="已核对材料"><select className={selectClassName} value={sourceRevisionId} onChange={(event) => { setSourceRevisionId(event.target.value); setAnchorId(""); }}><option value="">请选择材料</option>{sourceItems.map((item) => { const revisionId = item.working_revision_id ?? item.published_revision_id ?? ""; return <option key={item.resource_id} value={revisionId}>{item.title}{item.working_revision_id ? " · 工作修订" : " · 已发布"}</option>; })}</select></Field><Field label="来源位置"><select className={selectClassName} value={anchorId} onChange={(event) => setAnchorId(event.target.value)}><option value="">请选择位置</option>{anchors.data?.items.map((item) => <option key={item.anchor_id} value={item.anchor_id}>{item.label}</option>)}</select></Field><Field label="学习目标"><Input value={objective} onChange={(event) => setObjective(event.target.value)} /></Field><Field label="必修检查点"><Input value={checkpoint} onChange={(event) => setCheckpoint(event.target.value)} /></Field>{["rich_text", "source_excerpt"].includes(blockType) ? <label className="space-y-1 text-sm font-medium text-slate-700 md:col-span-2">{blockType === "rich_text" ? "精编正文" : "来源摘录"}<textarea className={textareaClassName} value={content} onChange={(event) => setContent(event.target.value)} /></label> : null}{sourceRevisionId && anchors.data?.items.length === 0 ? <p className="text-sm text-amber-700 md:col-span-2">所选材料尚无来源位置，请先在“原始材料与来源”中核对处理结果。</p> : null}{error ? <p role="alert" className="text-sm text-red-700 md:col-span-2">{error}</p> : null}<div className="md:col-span-2"><Button type="submit" disabled={create.isPending}>{create.isPending ? "正在创建…" : "创建结构化学习单元"}</Button></div></form></section>;
}

function SourceDetail({ detail, tokenStore, onChanged, onError }: { detail: FoundationLearningResourceDetail; tokenStore: ReturnType<typeof createIdempotencyTokenStore>; onChanged: (message: string) => void; onError: (error: unknown) => void }) {
    const [anchorLabel, setAnchorLabel] = useState("");
    const [excerpt, setExcerpt] = useState("");
    const [page, setPage] = useState("1");
    const selectedRevision = detail.working_revision ?? detail.published_revision;
    const source = toFoundationSourceRevisionViewModel(selectedRevision);
    const processingState = source?.processingState ?? "pending";
    const revisionId = processingState === "ready" && detail.resource.working_revision_id
        ? detail.resource.working_revision_id
        : detail.resource.published_revision_id ?? "";
    const anchors = useQuery({ queryKey: ["foundation-admin", "source-anchors", revisionId], queryFn: () => api.admin.newcomerTraining.listSourceAnchorsV2(revisionId), enabled: Boolean(revisionId) });
    const validate = useMutation({ mutationFn: () => api.admin.newcomerTraining.validateResourceV2("source_document", detail.resource.resource_id), onSuccess: (result) => onChanged(record(result).valid === true ? "材料通过校验。" : "材料仍有校验问题，请核对解析状态。"), onError });
    const retry = useMutation({ mutationFn: async () => { if (!source || !detail.resource.working_revision_id) throw new Error("当前没有可重试的工作修订。"); const key = `retry-source:${source.revisionId}:${source.processingState}:${source.failureMessage ?? ""}`; const result = await api.admin.newcomerTraining.retrySourceProcessingV2(source.revisionId, tokenStore.tokenFor(key)); tokenStore.complete(key); return result; }, onSuccess: () => onChanged("已重新提交处理；可离开页面，稍后刷新查看真实结果。"), onError });
    const createAnchor = useMutation({ mutationFn: async () => { if (!revisionId) throw new Error("材料解析完成并核对后才能新建来源位置。"); if (!anchorLabel.trim() || !excerpt.trim()) throw new Error("请填写来源位置名称和对应摘录。"); const parsedPage = Number(page); if (!Number.isInteger(parsedPage) || parsedPage < 1) throw new Error("页码必须大于 0。"); const key = `create-anchor:${revisionId}:${anchorLabel.trim()}:${excerpt.trim()}:${page}`; const result = await api.admin.newcomerTraining.createSourceAnchorV2(revisionId, { anchor_key: `anchor-${generateClientId()}`, label: anchorLabel.trim(), locator: { type: "page", page: parsedPage, start_offset: 0, end_offset: Math.max(1, excerpt.trim().length) }, excerpt_hash: await sha256Hex(excerpt.trim()) }, tokenStore.tokenFor(key)); tokenStore.complete(key); return result; }, onSuccess: async () => { setAnchorLabel(""); setExcerpt(""); await anchors.refetch(); onChanged("来源位置已保存；材料与引用内容会在发布计划中统一批准生效。"); }, onError });
    return (
        <div className="space-y-6">
            <DetailHeader detail={detail} />
            <RevisionComparison detail={detail} />
            {source?.isProcessing ? (
                <section role="status" className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
                    <h3 className="font-semibold">{source.processingLabel}</h3>
                    <p className="mt-1">可以离开当前页面；刷新只读取服务端状态，不会把等待误报为完成。</p>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                        <Link href="/admin/newcomer-training/assessments" prefetch={false} className="font-semibold underline">查看评测任务</Link>
                        <Button type="button" size="sm" variant="outline" className="bg-white" onClick={() => onChanged("已刷新材料解析状态。")}>刷新状态</Button>
                    </div>
                </section>
            ) : source?.canRetry ? (
                <section role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-950">
                    <h3 className="font-semibold">{source.processingLabel}</h3>
                    <p className="mt-1">{source.failureMessage ?? "已保留材料标题、原文件和成功结果，可从失败阶段重试。"}</p>
                    {source.missingPages.length > 0 ? <p className="mt-2">缺失页：{source.missingPages.join("、")}</p> : null}
                    <Button type="button" size="sm" variant="outline" className="mt-3 bg-white" onClick={() => retry.mutate()} disabled={retry.isPending}>{retry.isPending ? "正在提交…" : "重新处理"}</Button>
                </section>
            ) : null}
            {source ? <SourcePreview source={source} /> : <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">材料详情合同不完整，请刷新；系统不会把未知状态当作可发布。</div>}
            <div className="flex flex-wrap items-center gap-3">
                <Button type="button" variant="outline" onClick={() => validate.mutate()} disabled={!detail.resource.working_revision_id || validate.isPending}>{validate.isPending ? "正在校验…" : "校验材料"}</Button>
                {detail.resource.working_revision_id && processingState === "ready" ? <p className="text-sm text-blue-800">材料可建立来源位置；正式生效由路径发布计划统一完成。</p> : null}
            </div>
            {revisionId ? (
                <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <h3 className="font-semibold text-slate-950">来源位置</h3>
                    <p className="mt-1 text-sm text-slate-600">位置保留页码和摘录校验值，工作修订可先引用，发布计划会再次校验完整依赖。</p>
                    <div className="mt-3 space-y-2">
                        {anchors.isPending ? <p className="text-sm text-slate-500">正在加载来源位置…</p> : anchors.data?.items.length ? anchors.data.items.map((item) => <div key={item.anchor_id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm"><span className="font-medium text-slate-900">{item.label}</span><span className="ml-2 text-xs text-slate-500">{item.locator_type === "page" ? `第 ${String(item.locator.page ?? "-")} 页` : "已定位"}</span></div>) : <p className="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">还没有来源位置。</p>}
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_90px]">
                        <Field label="位置名称"><Input value={anchorLabel} onChange={(event) => setAnchorLabel(event.target.value)} /></Field>
                        <Field label="页码"><Input inputMode="numeric" value={page} onChange={(event) => setPage(event.target.value)} /></Field>
                        <label className="space-y-1 text-sm font-medium text-slate-700 sm:col-span-2">对应摘录<textarea className={textareaClassName} value={excerpt} onChange={(event) => setExcerpt(event.target.value)} /></label>
                        <div className="sm:col-span-2"><Button type="button" size="sm" variant="outline" onClick={() => createAnchor.mutate()} disabled={createAnchor.isPending}>{createAnchor.isPending ? "正在保存…" : "新建来源位置"}</Button></div>
                    </div>
                </section>
            ) : null}
        </div>
    );
}

function SourcePreview({ source }: { source: FoundationSourceRevisionViewModel }) {
    const readyPages = source.pages.filter((item) => item.status === "ready");
    const [page, setPage] = useState(readyPages[0]?.page ?? 1);
    const pageItem = source.pages.find((item) => item.page === page);
    const pageUrl = source.previewPageTemplate?.replace("{page}", String(page));
    return <section aria-labelledby="source-preview-title" className="rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 id="source-preview-title" className="font-semibold text-slate-950">编辑预览</h3><p className="mt-1 text-sm text-slate-600">{source.contentKindLabel} · {source.processingLabel}{source.originalFilename ? ` · ${source.originalFilename}` : ""}</p></div>{source.originalUrl ? <a href={source.originalUrl} className="inline-flex min-h-10 items-center text-sm font-semibold text-blue-700 underline"><Download className="mr-2 h-4 w-4" />查看原文件</a> : null}</div>
        {source.contentKind === "slide_deck" ? <div className="mt-4 space-y-3">{pageUrl && pageItem?.status === "ready" ? <img src={pageUrl} alt={`PPT 受控预览第 ${page} 页`} className="max-h-[65vh] w-full rounded-xl border border-slate-200 object-contain" /> : <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">该页预览暂不可用，原文件和成功页仍保留。</p>}<div className="flex flex-wrap gap-2" aria-label="选择预览页">{source.pages.map((item) => <button type="button" key={item.page} disabled={item.status !== "ready"} onClick={() => setPage(item.page)} className={`min-h-10 rounded-lg border px-3 text-sm ${page === item.page ? "border-blue-400 bg-blue-50 text-blue-900" : "border-slate-200"} disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400`}>第 {item.page} 页{item.status === "failed" ? "（失败）" : ""}</button>)}</div>{pageItem?.text ? <details className="rounded-lg bg-slate-50 p-3 text-sm"><summary className="cursor-pointer font-medium text-slate-800">查看本页提取文本</summary><p className="mt-2 whitespace-pre-wrap break-words leading-6 text-slate-700">{pageItem.text}</p></details> : null}</div> : null}
        {source.contentKind === "demo_video" && source.playbackUrl ? <video className="mt-4 max-h-[65vh] w-full rounded-xl bg-black" controls preload="metadata"><source src={source.playbackUrl} /></video> : null}
        {source.contentKind === "example_audio" && source.playbackUrl ? <audio className="mt-4 w-full" controls preload="metadata"><source src={source.playbackUrl} /></audio> : null}
        {source.contentKind === "external_demo" && source.externalUrl ? <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm"><p className="text-slate-700">外部页面不会嵌入管理端，也不会执行对方脚本。</p><a href={source.externalUrl} target="_blank" rel="noreferrer" className="mt-2 inline-flex min-h-10 items-center font-semibold text-blue-700 underline">在新窗口检查链接</a></div> : null}
        {source.contentKind === "script" && source.manualContent ? <div className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-4 text-sm leading-7 text-slate-700">{source.manualContent}</div> : null}
        {source.sections.length > 0 ? <div className="mt-4 max-h-[32rem] space-y-3 overflow-auto pr-1">{source.sections.map((item) => <article key={item.index} className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-medium text-slate-500">段落 {item.index}</p><p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{item.text}</p></article>)}</div> : null}
        {!source.canPreview && !source.externalUrl && !source.manualContent ? <p role="status" className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">处理完成后将在这里显示真实分页、正文或播放器；等待期间不会显示占位成功图。</p> : null}
    </section>;
}

function UnitDetail({ detail, tokenStore, onChanged, onError }: { detail: FoundationLearningResourceDetail; tokenStore: ReturnType<typeof createIdempotencyTokenStore>; onChanged: (message: string) => void; onError: (error: unknown) => void }) {
    const revision = record(detail.working_revision);
    const snapshot = record(revision.working_revision);
    const [title, setTitle] = useState(text(snapshot.title) || detail.resource.title);
    const [objectives, setObjectives] = useState(list(snapshot.objectives).join("\n"));
    const [hints, setHints] = useState(list(snapshot.practice_hints).join("\n"));
    const [blocks, setBlocks] = useState<Record<string, unknown>[]>(Array.isArray(snapshot.content_blocks) ? snapshot.content_blocks.map(record) : []);
    const save = useMutation({ mutationFn: async () => { if (!detail.resource.working_revision_id) throw new Error("已发布内容需要先创建新的工作修订。"); const payload = { ...snapshot, revision_label: text(snapshot.revision_label) || text(revision.revision_label) || "内容修订", title: title.trim(), objectives: lines(objectives), practice_hints: lines(hints), content_blocks: blocks }; const key = `save-unit:${detail.resource.resource_id}:${detail.resource.version}:${JSON.stringify(payload)}`; const result = await api.admin.newcomerTraining.saveResourceV2("learning_unit", detail.resource.resource_id, { resource_type: "learning_unit", working_revision: payload }, detail.resource.version, tokenStore.tokenFor(key)); tokenStore.complete(key); return result; }, onSuccess: () => onChanged("学习单元工作修订已保存；发布计划会再次校验 exact 来源和内容块。"), onError });
    const validate = useMutation({ mutationFn: () => api.admin.newcomerTraining.validateResourceV2("learning_unit", detail.resource.resource_id), onSuccess: (result) => onChanged(record(result).valid === true ? "学习单元通过校验。" : "学习单元仍有阻塞项，请核对来源和结构。"), onError });
    const updateBlock = (index: number, field: string, value: string) => setBlocks((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item));
    return <div className="space-y-6"><DetailHeader detail={detail} /><RevisionComparison detail={detail} />{detail.resource.working_revision_id ? <section className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4"><h3 className="font-semibold text-slate-950">Editor–Preview</h3><p className="text-sm text-slate-600">左侧编辑结构化内容块，右侧按学员阅读顺序预览；来源修订和定位保持冻结。</p><Field label="学习单元名称"><Input value={title} onChange={(event) => setTitle(event.target.value)} /></Field><label className="space-y-1 text-sm font-medium text-slate-700">学习目标（每行一个）<textarea className={textareaClassName} value={objectives} onChange={(event) => setObjectives(event.target.value)} /></label><div className="grid gap-4 xl:grid-cols-2"><div className="space-y-3" aria-label="内容块编辑器">{blocks.length ? blocks.map((block, index) => <div key={text(block.block_id) || index} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs font-semibold text-slate-500">{contentBlockLabel(text(block.type))} · 顺序 {String(block.order ?? index + 1)}</p><div className="mt-3 space-y-3"><Field label="标题"><Input value={text(block.title)} onChange={(event) => updateBlock(index, "title", event.target.value)} /></Field><label className="space-y-1 text-sm font-medium text-slate-700">说明<textarea className={textareaClassName} value={text(block.description)} onChange={(event) => updateBlock(index, "description", event.target.value)} /></label>{block.type === "rich_text" ? <label className="space-y-1 text-sm font-medium text-slate-700">精编正文<textarea className={textareaClassName} value={text(block.markdown)} onChange={(event) => updateBlock(index, "markdown", event.target.value)} /></label> : block.type === "source_excerpt" ? <label className="space-y-1 text-sm font-medium text-slate-700">来源摘录<textarea className={textareaClassName} value={text(block.excerpt)} onChange={(event) => updateBlock(index, "excerpt", event.target.value)} /></label> : block.type === "checkpoint" ? <label className="space-y-1 text-sm font-medium text-slate-700">检查点要求<textarea className={textareaClassName} value={text(block.prompt)} onChange={(event) => updateBlock(index, "prompt", event.target.value)} /></label> : <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">媒体范围与 exact 来源已冻结；如需更换材料，请新建工作修订并重新选择。</p>}</div></div>) : <p className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">这是兼容的旧文字学习单元；保存仍保留原结构，不会强制迁移。</p>}</div><div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4" aria-label="学员视角预览"><h4 className="font-semibold text-slate-950">{title || "未命名学习单元"}</h4>{lines(objectives).map((item) => <p key={item} className="text-sm text-slate-600">目标：{item}</p>)}{blocks.map((block, index) => <article key={`preview-${text(block.block_id) || index}`} className="rounded-lg border border-slate-100 p-3"><p className="text-xs text-slate-500">{contentBlockLabel(text(block.type))}</p><h5 className="mt-1 font-medium text-slate-900">{text(block.title)}</h5><p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{text(block.markdown) || text(block.excerpt) || text(block.prompt) || text(block.description) || "该媒体会在学员端使用受控预览或播放器呈现。"}</p></article>)}</div></div><label className="space-y-1 text-sm font-medium text-slate-700">练习提示（每行一个）<textarea className={textareaClassName} value={hints} onChange={(event) => setHints(event.target.value)} /></label><div className="flex flex-wrap gap-2"><Button type="button" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "正在保存…" : "保存工作修订"}</Button><Button type="button" variant="outline" onClick={() => validate.mutate()} disabled={validate.isPending}>{validate.isPending ? "正在校验…" : "校验学习单元"}</Button></div></section> : <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">当前没有待编辑修订。已发布内容不可原地修改；后续修订应从新的工作版本开始。</div>}<div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">引用影响会在路径发布预览中列出；归档已引用内容前必须先处理相应路径或题目引用。</div></div>;
}

function DetailHeader({ detail }: { detail: FoundationLearningResourceDetail }) {
    const queryClient = useQueryClient();
    const tokens = useRef(createIdempotencyTokenStore());
    const [showArchive, setShowArchive] = useState(false);
    const [reason, setReason] = useState("");
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const resourceType = detail.resource.resource_type;
    const references = useQuery({
        queryKey: ["foundation-admin", "content-references", resourceType, detail.resource.resource_id],
        queryFn: () => api.admin.newcomerTraining.getResourceReferencesV2(
            resourceType,
            detail.resource.resource_id,
        ),
    });
    const archive = useMutation({
        mutationFn: async () => {
            if (!reason.trim()) throw new Error("请填写归档原因。");
            const key = `archive-content:${resourceType}:${detail.resource.resource_id}:${detail.resource.version}:${reason.trim()}`;
            const result = await api.admin.newcomerTraining.archiveResourceV2(
                resourceType,
                detail.resource.resource_id,
                detail.resource.version,
                reason.trim(),
                tokens.current.tokenFor(key),
            );
            tokens.current.complete(key);
            return result;
        },
        onSuccess: async () => {
            setShowArchive(false);
            setReason("");
            setMessage("内容已归档；历史修订和已有引用保持可追溯，不会物理删除。后续发布不能再新增此引用。");
            setError(null);
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "content-resources"] }),
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "content-resource", resourceType, detail.resource.resource_id] }),
            ]);
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    return <div className="space-y-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="text-xl font-semibold text-slate-950">{detail.resource.title}</h2><p className="mt-1 text-sm text-slate-500">业务编码：{detail.resource.stable_key}</p></div><div className="flex items-center gap-2"><Badge variant={detail.resource.status === "active" ? "green" : detail.resource.status === "archived" ? "gray" : "orange"}>{detail.resource.status === "active" ? "已发布" : detail.resource.status === "archived" ? "已归档" : "草稿"}</Badge>{detail.resource.status !== "archived" ? <Button type="button" size="sm" variant="ghost" onClick={() => { setShowArchive((value) => !value); setError(null); }}><Archive className="mr-2 h-4 w-4" />预览归档</Button> : null}</div></div>{message ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{message}</div> : null}<section className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-950">当前引用影响</h3><p className="mt-1 text-sm text-slate-600">展示路径、学习单元、题目或测验对该对象全部修订的引用。</p></div>{references.data ? <Badge variant={references.data.total ? "orange" : "gray"}>{references.data.total} 项引用</Badge> : null}</div>{references.isPending ? <p className="mt-3 text-sm text-slate-500">正在检查引用…</p> : references.error ? <p role="alert" className="mt-3 text-sm text-red-700">{getApiErrorMessage(references.error)} <button type="button" className="font-semibold underline" onClick={() => void references.refetch()}>重试</button></p> : references.data?.items.length ? <div className="mt-3 space-y-2">{references.data.items.map((item, index) => <Link key={`${item.reference_type}-${item.title}-${index}`} href={item.href} prefetch={false} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm"><span><span className="font-medium text-slate-900">{item.title}</span><span className="mt-1 block text-xs text-slate-500">{referenceTypeLabel(item.reference_type)} · {item.revision_label}</span></span><Badge variant={item.status === "published" ? "green" : "gray"}>{item.status === "published" ? "已发布" : item.status === "working" ? "工作修订" : "历史修订"}</Badge></Link>)}</div> : <p className="mt-3 text-sm text-slate-500">当前没有被其他训练对象引用。</p>}{references.data?.is_partial ? <p className="mt-3 text-sm text-amber-800">引用数量较大，本次只完成部分扫描。归档前请缩小范围或稍后重试，不能把部分结果当作完整影响。</p> : null}</section>{showArchive ? <section className="rounded-xl border border-amber-200 bg-amber-50 p-4"><h3 className="font-semibold text-amber-950">确认归档影响</h3><p className="mt-1 text-sm text-amber-900">归档不会删除历史修订，也不会改变已冻结训练；它会阻止后续把此对象作为新的可选内容。</p><label className="mt-3 block space-y-1 text-sm font-medium text-amber-950">归档原因<Input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={2000} /></label>{error ? <p role="alert" className="mt-2 text-sm text-red-700">{error}</p> : null}<div className="mt-3 flex justify-end gap-2"><Button type="button" size="sm" variant="ghost" onClick={() => setShowArchive(false)} disabled={archive.isPending}>取消</Button><Button type="button" size="sm" variant="destructive" onClick={() => archive.mutate()} disabled={archive.isPending || references.data?.is_partial}>{archive.isPending ? "正在归档…" : references.data?.is_partial ? "影响未完整，暂不能归档" : "确认归档内容"}</Button></div></section> : null}</div>;
}

function RevisionComparison({ detail }: { detail: FoundationLearningResourceDetail }) {
    const working = record(detail.working_revision);
    const published = record(detail.published_revision);
    return <section aria-labelledby="revision-compare-title"><h3 id="revision-compare-title" className="font-semibold text-slate-950">修订对比</h3><div className="mt-3 grid gap-3 sm:grid-cols-2"><RevisionCard label="当前工作修订" revision={working} empty="没有待发布修改" /><RevisionCard label="当前已发布修订" revision={published} empty="尚未发布" /></div>{working.content_hash && published.content_hash ? <p className="mt-3 text-xs text-slate-500">{working.content_hash === published.content_hash ? "工作修订与已发布内容一致。" : "工作修订包含尚未发布的变更。"}</p> : null}</section>;
}

function RevisionCard({ label, revision, empty }: { label: string; revision: Record<string, unknown>; empty: string }) {
    const parseStatus = text(record(revision.working_revision).parse_status);
    return <div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>{revision.revision_id ? <><p className="mt-2 font-medium text-slate-900">第 {String(revision.revision_no ?? "-")} 版</p><p className="mt-1 text-sm text-slate-500">{revision.status === "published" ? "已发布" : revision.status === "working" ? "工作修订" : "已归档"}</p>{parseStatus ? <p className={`mt-2 text-sm font-medium ${parseStatus === "ready" ? "text-emerald-700" : parseStatus === "failed" ? "text-red-700" : "text-blue-700"}`}>{parseStatus === "ready" ? "材料解析完成" : parseStatus === "failed" ? "材料解析失败" : "材料等待解析"}</p> : null}</> : <p className="mt-2 text-sm text-slate-500">{empty}</p>}</div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="space-y-1 text-sm font-medium text-slate-700"><span>{label}</span>{children}</label>; }
const textareaClassName = "min-h-24 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
const selectClassName = "h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function text(value: unknown): string { return typeof value === "string" ? value : ""; }
function list(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []; }
function lines(value: string): string[] { return value.split("\n").map((item) => item.trim()).filter(Boolean); }
function referenceTypeLabel(value: string): string { return { path: "训练路径", learning_unit: "学习单元", question: "正式题目", quiz: "测验" }[value] ?? "训练对象"; }
function contentBlockLabel(value: string): string { return { rich_text: "精编正文", source_excerpt: "来源摘录", slide_deck: "PPT 分页", video: "Demo 视频", audio_example: "示范音频", attachment: "附件", checkpoint: "检查点" }[value] ?? "内容块"; }
async function sha256Hex(value: string): Promise<string> { const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)); return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join(""); }
const SOURCE_KIND_OPTIONS: Array<{ value: FoundationSourceContentKind; label: string }> = [
    { value: "document", label: "文档 / 表格" },
    { value: "slide_deck", label: "PPT 讲解材料" },
    { value: "demo_video", label: "Demo 视频" },
    { value: "external_demo", label: "受控 Demo 链接" },
    { value: "script", label: "手工讲解稿" },
    { value: "example_audio", label: "示范音频" },
    { value: "attachment", label: "训练附件" },
];
const SOURCE_EXTENSIONS: Record<FoundationSourceContentKind, Set<string>> = {
    document: new Set(["pdf", "docx", "txt", "md", "xlsx", "xls"]),
    slide_deck: new Set(["pptx"]),
    demo_video: new Set(["mp4", "webm"]),
    external_demo: new Set(),
    script: new Set(),
    example_audio: new Set(["mp3", "wav", "m4a"]),
    attachment: new Set(["pdf", "docx", "txt", "md", "xlsx", "xls", "pptx", "mp4", "webm", "mp3", "wav", "m4a"]),
};
export function validateSourceUploadFile(file: File, contentKind: FoundationSourceContentKind = "document"): string | null {
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (extension === "ppt") return "当前不能可信转换旧版 .ppt，请先另存为 .pptx。";
    if (!extension || !SOURCE_EXTENSIONS[contentKind].has(extension)) return `所选文件与“${SOURCE_KIND_OPTIONS.find((item) => item.value === contentKind)?.label ?? "材料"}”类型不匹配。${sourceUploadHelp(contentKind)}。`;
    if (file.size === 0) return "材料文件不能为空。";
    return null;
}
function sourceAccept(contentKind: FoundationSourceContentKind): string { return [...SOURCE_EXTENSIONS[contentKind]].map((item) => `.${item}`).join(","); }
function sourceUploadHelp(contentKind: FoundationSourceContentKind): string { const extensions = [...SOURCE_EXTENSIONS[contentKind]].map((item) => item.toUpperCase()).join("、"); return extensions ? `支持 ${extensions}` : "该类型不需要上传文件"; }
