"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Copy, Plus, Upload } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import {
    api,
    getApiErrorMessage,
    getContentAssetErrorDetails,
} from "@/lib/api/client";
import type { TemplateReferenceItem } from "@/lib/api/types";
import { debug } from "@/lib/debug";

import {
    assetCardClassName,
    ContentAssetStatusGuide,
} from "./content-asset-status-guide";
import {
    CONTENT_ASSET_META,
    recordId,
    recordStatus,
    recordSubtitle,
    recordTitle,
    statusVariant,
    type AssetRecord,
    type ContentAssetType,
} from "./content-asset-utils";

export interface ContentAssetIndexProps {
    assetType: ContentAssetType;
}

type ConfirmTarget =
    | { type: "publish" | "archive"; item: AssetRecord }
    | { type: "unpublish"; item: AssetRecord; references: TemplateReferenceItem[] };

export function ContentAssetIndex({ assetType }: ContentAssetIndexProps) {
    const router = useRouter();
    const toast = useToast();
    const meta = CONTENT_ASSET_META[assetType];
    const isCase = assetType === "case-item";
    const [items, setItems] = useState<AssetRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [query, setQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [confirmTarget, setConfirmTarget] = useState<ConfirmTarget | null>(null);

    const loadItems = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const filters = { status: statusFilter, query };
            const response = isCase
                ? await api.admin.listCaseItems(filters)
                : await api.admin.listRoleProfiles(filters);
            setItems(response.items);
        } catch (err) {
            setError(`${meta.title} 加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[ContentAssetIndex] failed to load content assets", { assetType, error: err });
        } finally {
            setLoading(false);
        }
    }, [assetType, isCase, meta.title, query, statusFilter]);

    useEffect(() => {
        void Promise.resolve().then(loadItems);
    }, [loadItems]);

    const filteredItems = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        return items.filter((item) => {
            if (!normalizedQuery) return true;
            return [recordTitle(item), recordSubtitle(item), recordId(item)]
                .join(" ")
                .toLowerCase()
                .includes(normalizedQuery);
        });
    }, [items, query]);

    const replaceItem = (next: AssetRecord) => {
        setItems((current) => current.map((item) => (recordId(item) === recordId(next) ? next : item)));
    };

    const prependItem = (next: AssetRecord) => {
        setItems((current) => [next, ...current.filter((item) => recordId(item) !== recordId(next))]);
    };

    const duplicateItem = async (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const duplicated = isCase
                ? await api.admin.duplicateCaseItem((item as import("@/lib/api/types").CaseItemRecord).case_item_id)
                : await api.admin.duplicateRoleProfile((item as import("@/lib/api/types").RoleProfileRecord).role_profile_id);
            prependItem(duplicated);
            const references = isCase
                ? await api.admin.getCaseItemTemplateReferences((item as import("@/lib/api/types").CaseItemRecord).case_item_id)
                : await api.admin.getRoleProfileTemplateReferences((item as import("@/lib/api/types").RoleProfileRecord).role_profile_id);
            const baseMessage = `已复制为新草稿：${recordTitle(duplicated)}`;
            if (references.items.length > 0) {
                toast.success(`${baseMessage}。以下已发布模板仍绑定旧版本，请在模板草稿中换绑并重发：${references.items.map((ref) => ref.name).join("、")}`);
            } else {
                toast.success(baseMessage);
            }
            router.push(`${meta.basePath}/${recordId(duplicated)}/edit`);
        } catch (err) {
            setActionError(`复制失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const requestUnpublish = async (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const references = isCase
                ? await api.admin.getCaseItemTemplateReferences((item as import("@/lib/api/types").CaseItemRecord).case_item_id)
                : await api.admin.getRoleProfileTemplateReferences((item as import("@/lib/api/types").RoleProfileRecord).role_profile_id);
            setConfirmTarget({ type: "unpublish", item, references: references.items });
        } catch (err) {
            setActionError(`读取模板引用失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const handleUnpublish = async (item: AssetRecord, acknowledge: boolean) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const unpublished = isCase
                ? await api.admin.unpublishCaseItem((item as import("@/lib/api/types").CaseItemRecord).case_item_id, acknowledge)
                : await api.admin.unpublishRoleProfile((item as import("@/lib/api/types").RoleProfileRecord).role_profile_id, acknowledge);
            replaceItem(unpublished);
            setNotice(`已退回草稿：${recordTitle(unpublished)}`);
        } catch (err) {
            const details = getContentAssetErrorDetails(err);
            if (details?.referencing_templates?.length) {
                setConfirmTarget({
                    type: "unpublish",
                    item,
                    references: details.referencing_templates,
                });
            }
            setActionError(`退回草稿失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const handlePublish = async (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const published = isCase
                ? await api.admin.publishCaseItem((item as import("@/lib/api/types").CaseItemRecord).case_item_id)
                : await api.admin.publishRoleProfile((item as import("@/lib/api/types").RoleProfileRecord).role_profile_id);
            replaceItem(published);
            setNotice(`发布完成：${recordTitle(published)}`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const handleArchive = async (item: AssetRecord) => {
        setActionError(null);
        setNotice(null);
        setBusyId(recordId(item));
        try {
            const archived = isCase
                ? await api.admin.archiveCaseItem((item as import("@/lib/api/types").CaseItemRecord).case_item_id)
                : await api.admin.archiveRoleProfile((item as import("@/lib/api/types").RoleProfileRecord).role_profile_id);
            replaceItem(archived);
            setNotice(`归档完成：${recordTitle(archived)}`);
        } catch (err) {
            setActionError(`归档失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyId(null);
        }
    };

    const confirmDescription = confirmTarget
        ? confirmTarget.type === "archive"
            ? `将「${recordTitle(confirmTarget.item)}」归档，归档后不会再作为可绑定资产使用。`
            : confirmTarget.type === "unpublish"
                ? confirmTarget.references.length > 0
                    ? `将「${recordTitle(confirmTarget.item)}」退回草稿。以下已发布模板仍引用此资产，学员新开练可能在快照阶段失败：${confirmTarget.references.map((ref) => ref.name).join("、")}`
                    : `将「${recordTitle(confirmTarget.item)}」退回草稿。当前没有已发布模板引用此资产。`
                : `将「${recordTitle(confirmTarget.item)}」发布，发布后可被 PracticeTemplate 绑定引用。`
        : "确认执行该内容资产操作。";

    if (loading) {
        return <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">正在加载{meta.title}...</div>;
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">{meta.title}</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadItems}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title={meta.title}
                    description={meta.description}
                    primaryAction={(
                        <Button className="rounded-full" onClick={() => router.push(`${meta.basePath}/new`)}>
                            <Plus className="mr-2 h-4 w-4" />
                            新建资产
                        </Button>
                    )}
                    secondaryActions={(
                        <>
                            <Button variant="outline" className="rounded-full" onClick={() => router.push(`${meta.basePath}/import`)}>
                                <Upload className="mr-2 h-4 w-4" />
                                批量导入
                            </Button>
                            <Button variant="outline" onClick={loadItems}>刷新</Button>
                        </>
                    )}
                />
            )}
        >
            <ConfirmDialog
                open={!!confirmTarget}
                onOpenChange={(open) => {
                    if (!open) setConfirmTarget(null);
                }}
                title={
                    confirmTarget?.type === "archive"
                        ? "确认归档内容资产"
                        : confirmTarget?.type === "unpublish"
                            ? "确认退回草稿（慎用）"
                            : "确认发布内容资产"
                }
                description={confirmDescription}
                confirmText={
                    confirmTarget?.type === "archive"
                        ? "确认归档"
                        : confirmTarget?.type === "unpublish"
                            ? "确认退回草稿"
                            : "确认发布"
                }
                variant={confirmTarget?.type === "publish" ? "danger" : "warning"}
                onConfirm={() => {
                    const target = confirmTarget;
                    setConfirmTarget(null);
                    if (!target) return;
                    if (target.type === "archive") {
                        void handleArchive(target.item);
                        return;
                    }
                    if (target.type === "unpublish") {
                        void handleUnpublish(target.item, true);
                        return;
                    }
                    void handlePublish(target.item);
                }}
                isLoading={busyId !== null}
            />

            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}

            <GlassCard className="space-y-4 p-6">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h2 className="text-xl font-black text-slate-900">资产列表</h2>
                        <p className="text-xs text-slate-500">发布后可在 PracticeTemplate 编辑器中绑定；已发布内容请复制为新草稿后再修改。</p>
                    </div>
                    <Badge variant="gray">{filteredItems.length} / {items.length}</Badge>
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_180px]">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>搜索</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>状态</span>
                        <select
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={statusFilter}
                            onChange={(event) => setStatusFilter(event.target.value)}
                        >
                            <option value="all">全部</option>
                            <option value="draft">草稿</option>
                            <option value="published">已发布</option>
                            <option value="archived">已归档</option>
                        </select>
                    </label>
                </div>
                <div className="grid gap-3">
                    {filteredItems.map((item) => (
                        <div key={recordId(item)} className={assetCardClassName(item.status)}>
                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div className="space-y-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{recordTitle(item)}</h3>
                                        <Badge variant={statusVariant(item.status)}>{recordStatus(item)}</Badge>
                                    </div>
                                    <ContentAssetStatusGuide status={item.status} compact />
                                    <p className="text-sm text-slate-600">{recordSubtitle(item)}</p>
                                    <p className="text-xs text-slate-500">hash: {item.content_hash}</p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {item.status === "draft" ? (
                                        <Button variant="outline" asChild>
                                            <Link href={`${meta.basePath}/${recordId(item)}/edit`} prefetch={false}>编辑资产</Link>
                                        </Button>
                                    ) : item.status === "published" ? (
                                        <Button
                                            onClick={() => { void duplicateItem(item); }}
                                            disabled={busyId !== null}
                                        >
                                            <Copy className="mr-2 h-4 w-4" />
                                            {busyId === recordId(item) ? "复制中..." : "复制为新草稿"}
                                        </Button>
                                    ) : null}
                                    {item.status === "published" ? (
                                        <Button
                                            variant="outline"
                                            onClick={() => { void requestUnpublish(item); }}
                                            disabled={busyId !== null}
                                        >
                                            退回草稿（慎用）
                                        </Button>
                                    ) : null}
                                    <Button
                                        onClick={() => { setConfirmTarget({ type: "publish", item }); }}
                                        disabled={item.status === "published" || busyId !== null}
                                    >
                                        {busyId === recordId(item) ? "发布中..." : "发布资产"}
                                    </Button>
                                    {item.status !== "archived" && (
                                        <Button
                                            variant="outline"
                                            onClick={() => { setConfirmTarget({ type: "archive", item }); }}
                                            disabled={busyId !== null}
                                        >
                                            {busyId === recordId(item) ? "归档中..." : "归档资产"}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    {filteredItems.length === 0 && (
                        <EmptyState title="暂无资产" description="调整搜索或新建一个内容资产。" />
                    )}
                </div>
            </GlassCard>
        </AdminIndexShell>
    );
}
