"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Plus, RefreshCcw } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { LearningContentIndexTable } from "@/components/admin/learning-contents/learning-content-index-table";
import { api } from "@/lib/api/client";
import type { LearningContent } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { debug } from "@/lib/debug";

export default function AdminLearningContentsPage() {
    const router = useRouter();
    const [items, setItems] = useState<LearningContent[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<LearningContent | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.learningContents.list();
            setItems(result.items || []);
        } catch (err) {
            debug.error("Failed to load learning contents:", err);
            setError(err instanceof Error ? err.message : "加载失败");
            setItems([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadData();
    }, []);

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setNotice(null);
        setActionError(null);
        setIsDeleting(true);
        try {
            await api.learningContents.delete(deleteTarget.learning_content_id);
            setItems((current) => current.filter((currentItem) => currentItem.learning_content_id !== deleteTarget.learning_content_id));
            setNotice(`删除完成：${deleteTarget.title}`);
            setDeleteTarget(null);
        } catch (err) {
            debug.error("Failed to delete learning content:", err);
            setActionError(err instanceof Error ? err.message : "删除失败");
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="学习内容管理"
                    description="管理课程学习内容"
                    primaryAction={(
                        <Button className="rounded-full" onClick={() => router.push("/admin/learning-contents/new")}>
                            <Plus className="mr-2 h-4 w-4" />
                            新建内容
                        </Button>
                    )}
                    secondaryActions={(
                        <Button variant="outline" className="rounded-full" onClick={() => void loadData()} disabled={isLoading}>
                            <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                            刷新
                        </Button>
                    )}
                />
            )}
        >
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => {
                    if (!open) setDeleteTarget(null);
                }}
                title="删除学习内容草稿"
                description={deleteTarget ? `确定要删除「${deleteTarget.title}」吗？删除后该草稿无法恢复。` : "确定要删除该学习内容草稿吗？"}
                confirmText="确认删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {notice ? (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>
            ) : null}
            {actionError ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>
            ) : null}

            {error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-500">
                        <BookOpen className="h-8 w-8" />
                    </div>
                    <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                    <p className="mb-4 text-sm text-slate-500">{error}</p>
                    <Button onClick={() => void loadData()} className="rounded-full">
                        <RefreshCcw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                </GlassCard>
            ) : null}

            {isLoading && !error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-slate-500">加载中...</p>
                </GlassCard>
            ) : null}

            {!isLoading && !error ? (
                <LearningContentIndexTable items={items} onDelete={setDeleteTarget} />
            ) : null}
        </AdminIndexShell>
    );
}
