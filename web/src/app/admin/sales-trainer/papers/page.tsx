"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { History, Pencil, Plus } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { NewcomerExamPaper, NewcomerExamPaperRevision } from "@/lib/api/types";
import { PAPER_STATUS_LABELS } from "./paper-form-model";

type ConfirmState =
    | { type: "publish"; paper: NewcomerExamPaper }
    | { type: "archive"; paper: NewcomerExamPaper }
    | null;

export default function NewcomerPapersPage() {
    const pathname = usePathname();
    const toast = useToast();
    const [items, setItems] = useState<NewcomerExamPaper[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [confirmState, setConfirmState] = useState<ConfirmState>(null);
    const [historyPaper, setHistoryPaper] = useState<NewcomerExamPaper | null>(null);
    const [revisions, setRevisions] = useState<NewcomerExamPaperRevision[]>([]);
    const [isHistoryLoading, setIsHistoryLoading] = useState(false);
    const [rollbackReasonByRevision, setRollbackReasonByRevision] = useState<Record<string, string>>({});
    const [rollbackRevisionId, setRollbackRevisionId] = useState<string | null>(null);

    const loadPapers = useCallback(async () => {
        setIsLoading(true);
        try {
            const result = await api.admin.newcomerTraining.listPapers({
                include_archived: true,
                limit: 100,
            });
            setItems(result.items);
        } catch (error) {
            setItems([]);
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        void loadPapers();
    }, [loadPapers]);

    async function handleConfirm() {
        if (!confirmState) {
            return;
        }
        setIsSubmitting(true);
        try {
            if (confirmState.type === "publish") {
                await api.admin.newcomerTraining.publishPaper(confirmState.paper.paper_id);
                toast.success("考卷已发布并生效，后续学员将使用当前版本");
            } else {
                await api.admin.newcomerTraining.archivePaper(confirmState.paper.paper_id);
                toast.success("考卷已归档");
            }
            setConfirmState(null);
            await loadPapers();
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function openRevisionHistory(paper: NewcomerExamPaper) {
        setHistoryPaper(paper);
        setRevisions([]);
        setRollbackReasonByRevision({});
        setIsHistoryLoading(true);
        try {
            const result = await api.admin.newcomerTraining.listPaperRevisions(paper.paper_id);
            setRevisions(result.items);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsHistoryLoading(false);
        }
    }

    async function rollbackToRevision(revision: NewcomerExamPaperRevision) {
        if (!historyPaper) {
            return;
        }
        const reason = rollbackReasonByRevision[revision.revision_id]?.trim() ?? "";
        if (!reason) {
            toast.error("请填写回滚原因。");
            return;
        }
        setRollbackRevisionId(revision.revision_id);
        try {
            await api.admin.newcomerTraining.rollbackPaper(historyPaper.paper_id, {
                target_revision_id: revision.revision_id,
                reason,
            });
            toast.success(`已回滚到第 ${revision.revision_no} 版，后续学员将使用该版本`);
            await loadPapers();
            await openRevisionHistory(historyPaper);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setRollbackRevisionId(null);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="商务技巧考卷管理"
                    description="按考卷管理题目组合、分值和发布状态；题目内容来自正式题目库。"
                    primaryAction={(
                        <Button asChild>
                            <Link href="/admin/sales-trainer/papers/new">
                                <Plus className="mr-2 h-4 w-4" />
                                新建考卷
                            </Link>
                        </Button>
                    )}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <ConfirmDialog
                open={Boolean(confirmState)}
                onOpenChange={(open) => !open && setConfirmState(null)}
                title={confirmState?.type === "publish" ? "发布并生效" : "归档考卷"}
                description={confirmState?.paper.title || ""}
                confirmText={confirmState?.type === "publish" ? "确认发布并生效" : "确认归档"}
                onConfirm={() => void handleConfirm()}
                isLoading={isSubmitting}
            />
            <div className="space-y-4">
                <GlassCard className="overflow-hidden p-0">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 text-left text-slate-500">
                                <th className="px-6 py-4">考卷</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">题目数</th>
                                <th className="px-6 py-4">更新时间</th>
                                <th className="px-6 py-4">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan={5} className="px-6 py-10 text-center text-slate-500">正在加载考卷...</td>
                                </tr>
                            ) : items.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-6 py-10 text-center text-slate-500">暂无考卷</td>
                                </tr>
                            ) : items.map((item) => (
                                <tr key={item.paper_id} className="border-b border-slate-100 last:border-b-0">
                                    <td className="px-6 py-4">
                                        <p className="font-medium text-slate-900">{item.title}</p>
                                        <p className="mt-1 text-xs text-slate-500">商务技巧 · {item.questions.length} 题</p>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex flex-wrap gap-2">
                                            <Badge className="bg-slate-100 text-slate-700">{PAPER_STATUS_LABELS[item.status]}</Badge>
                                            {item.has_unpublished_revision ? (
                                                <Badge className="bg-amber-100 text-amber-800">待发布修订</Badge>
                                            ) : null}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">{item.questions.length}</td>
                                    <td className="px-6 py-4">{new Date(item.updated_at).toLocaleString()}</td>
                                    <td className="px-6 py-4">
                                        <div className="flex flex-wrap gap-2">
                                            {item.status !== "archived" ? (
                                                <Button asChild variant="outline" size="sm">
                                                    <Link href={`/admin/sales-trainer/papers/${item.paper_id}/edit`}>
                                                        <Pencil className="mr-1 h-4 w-4" />
                                                        {item.status === "draft" ? "编辑草稿" : "编辑"}
                                                    </Link>
                                                </Button>
                                            ) : null}
                                            {item.status !== "archived" ? (
                                                <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "publish", paper: item })}>
                                                    发布并生效
                                                </Button>
                                            ) : null}
                                            <Button variant="outline" size="sm" onClick={() => void openRevisionHistory(item)}>
                                                <History className="mr-1 h-4 w-4" />
                                                历史版本
                                            </Button>
                                            {item.status !== "archived" ? (
                                                <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "archive", paper: item })}>
                                                    归档
                                                </Button>
                                            ) : null}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </GlassCard>
                {historyPaper ? (
                    <GlassCard className="space-y-4 p-6">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-bold text-slate-900">历史版本：{historyPaper.title}</h2>
                                <p className="mt-1 text-sm text-slate-600">回滚只影响后续学员；已经提交的考试记录继续保留当时快照。</p>
                            </div>
                            <Button variant="outline" size="sm" onClick={() => setHistoryPaper(null)}>关闭</Button>
                        </div>
                        {isHistoryLoading ? (
                            <p className="text-sm text-slate-500">正在加载历史版本...</p>
                        ) : revisions.length === 0 ? (
                            <p className="text-sm text-slate-500">暂无历史版本。</p>
                        ) : (
                            <div className="space-y-3">
                                {revisions.map((revision) => {
                                    const canRollback = revision.status === "published" && !revision.is_active;
                                    const reason = rollbackReasonByRevision[revision.revision_id] ?? "";
                                    return (
                                        <div key={revision.revision_id} className="rounded-lg border border-slate-200 bg-white p-4">
                                            <div className="flex flex-wrap items-center justify-between gap-3">
                                                <div>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <p className="font-semibold text-slate-900">第 {revision.revision_no} 版</p>
                                                        {revision.is_active ? <Badge className="bg-emerald-100 text-emerald-800">当前生效</Badge> : null}
                                                        {revision.is_working ? <Badge className="bg-amber-100 text-amber-800">待发布修订</Badge> : null}
                                                        {revision.change_class === "scoring_high_risk" ? <Badge className="bg-rose-100 text-rose-800">评分相关变更</Badge> : null}
                                                    </div>
                                                    <p className="mt-1 text-sm text-slate-600">{revision.title ?? "未命名版本"} · {revision.question_count} 题</p>
                                                </div>
                                            </div>
                                            {canRollback ? (
                                                <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                                                    <label className="sr-only" htmlFor={`rollback-reason-${revision.revision_no}`}>回滚原因（第 {revision.revision_no} 版）</label>
                                                    <Input
                                                        id={`rollback-reason-${revision.revision_no}`}
                                                        placeholder={`回滚原因（第 ${revision.revision_no} 版）`}
                                                        value={reason}
                                                        onChange={(event) => setRollbackReasonByRevision((current) => ({
                                                            ...current,
                                                            [revision.revision_id]: event.target.value,
                                                        }))}
                                                        disabled={rollbackRevisionId === revision.revision_id}
                                                    />
                                                    <Button
                                                        variant="outline"
                                                        onClick={() => void rollbackToRevision(revision)}
                                                        disabled={rollbackRevisionId === revision.revision_id || !reason.trim()}
                                                    >
                                                        回滚到第 {revision.revision_no} 版
                                                    </Button>
                                                </div>
                                            ) : null}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </GlassCard>
                ) : null}
            </div>
        </AdminIndexShell>
    );
}
