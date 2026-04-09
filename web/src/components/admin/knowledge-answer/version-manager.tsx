"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AdminKnowledgeConfigVersionResponse } from "@/lib/api/types";
import { GlassModal } from "@/components/ui/glass-modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface VersionManagerProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onVersionChange: () => void;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
    active: { label: "活跃", className: "bg-green-50 text-green-700 border-green-200" },
    draft: { label: "草稿", className: "bg-amber-50 text-amber-700 border-amber-200" },
    archived: { label: "已归档", className: "bg-slate-100 text-slate-700 border-slate-200" },
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function VersionManager({ open, onOpenChange, onVersionChange }: VersionManagerProps) {
    const toast = useToast();

    const [versions, setVersions] = useState<AdminKnowledgeConfigVersionResponse[]>([]);
    const [loading, setLoading] = useState(false);

    // Create form state
    const [newName, setNewName] = useState("");
    const [newNotes, setNewNotes] = useState("");
    const [creating, setCreating] = useState(false);

    // Delete confirm state
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeConfigVersionResponse | null>(null);
    const [deleting, setDeleting] = useState(false);

    // Activate loading
    const [activatingId, setActivatingId] = useState<string | null>(null);

    /* ── Load versions ── */
    const loadVersions = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.admin.getKnowledgeConfigVersions({ page: 1, page_size: 50 });
            setVersions(data.items);
        } catch {
            toast.error("加载版本列表失败");
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        if (open) {
            loadVersions();
        }
    }, [open, loadVersions]);

    /* ── Create version ── */
    const handleCreate = async () => {
        const trimmedName = newName.trim();
        if (!trimmedName) {
            toast.error("请输入版本名称");
            return;
        }

        setCreating(true);
        try {
            await api.admin.createKnowledgeConfigVersion({
                version_name: trimmedName,
                notes: newNotes.trim() || undefined,
            });
            toast.success("版本已创建");
            setNewName("");
            setNewNotes("");
            await loadVersions();
            onVersionChange();
        } catch (e) {
            toast.error(`创建失败：${getApiErrorMessage(e)}`);
        } finally {
            setCreating(false);
        }
    };

    /* ── Activate version ── */
    const handleActivate = async (v: AdminKnowledgeConfigVersionResponse) => {
        if (v.status === "active") return;

        setActivatingId(v.id);
        try {
            await api.admin.updateKnowledgeConfigVersion(v.id, { status: "active" });
            toast.success(`版本「${v.version_name}」已激活`);
            await loadVersions();
            onVersionChange();
        } catch (e) {
            toast.error(`激活失败：${getApiErrorMessage(e)}`);
        } finally {
            setActivatingId(null);
        }
    };

    /* ── Delete version ── */
    const handleDelete = async () => {
        if (!deleteTarget) return;

        setDeleting(true);
        try {
            await api.admin.deleteKnowledgeConfigVersion(deleteTarget.id);
            toast.success(`版本「${deleteTarget.version_name}」已删除`);
            await loadVersions();
            onVersionChange();
        } catch (e) {
            toast.error(`删除失败：${getApiErrorMessage(e)}`);
        } finally {
            setDeleting(false);
            setDeleteTarget(null);
        }
    };

    /* ── Helpers ── */
    const formatTime = (iso: string) => {
        try {
            return new Date(iso).toLocaleString("zh-CN", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return iso;
        }
    };

    const statusBadge = (status: string) => {
        const cfg = STATUS_BADGE[status] ?? { label: status, className: "bg-slate-100 text-slate-700 border-slate-200" };
        return (
            <Badge variant="outline" className={cfg.className}>
                {cfg.label}
            </Badge>
        );
    };

    /* ── Render ── */
    return (
        <>
            <GlassModal
                isOpen={open}
                onClose={() => onOpenChange(false)}
                title="版本管理"
                description="创建、激活或删除知识回答配置版本"
                size="xl"
            >
                <div className="space-y-5">
                    {/* ── New version form ── */}
                    <div className="rounded-xl border bg-slate-50 p-4 space-y-3">
                        <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                            <Plus className="h-4 w-4" />
                            新建版本
                        </h4>
                        <div className="grid gap-3 sm:grid-cols-2">
                            <Input
                                placeholder="版本名称"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                            />
                            <div className="flex gap-2">
                                <textarea
                                    className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-slate-300"
                                    rows={1}
                                    placeholder="备注（可选）"
                                    value={newNotes}
                                    onChange={(e) => setNewNotes(e.target.value)}
                                />
                            </div>
                        </div>
                        <Button
                            size="sm"
                            className="rounded-full"
                            disabled={creating || !newName.trim()}
                            onClick={handleCreate}
                        >
                            {creating && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            创建
                        </Button>
                    </div>

                    {/* ── Version list ── */}
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                        </div>
                    ) : versions.length === 0 ? (
                        <p className="py-8 text-center text-sm text-slate-400">暂无版本</p>
                    ) : (
                        <div className="divide-y divide-slate-100">
                            {versions.map((v) => {
                                const isActive = v.status === "active";
                                return (
                                    <div
                                        key={v.id}
                                        className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                                    >
                                        <div className="min-w-0 flex-1 space-y-1">
                                            <div className="flex items-center gap-2">
                                                <span className="truncate text-sm font-semibold text-slate-900">
                                                    {v.version_name}
                                                </span>
                                                {statusBadge(v.status)}
                                            </div>
                                            {v.notes && (
                                                <p className="truncate text-xs text-slate-500">{v.notes}</p>
                                            )}
                                            <p className="text-[10px] text-slate-400">
                                                更新于 {formatTime(v.updated_at)}
                                            </p>
                                        </div>

                                        <div className="flex shrink-0 items-center gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="rounded-full"
                                                disabled={isActive || activatingId === v.id}
                                                onClick={() => handleActivate(v)}
                                            >
                                                {activatingId === v.id && (
                                                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                                                )}
                                                激活
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="rounded-full text-red-600 hover:text-red-700 hover:bg-red-50"
                                                disabled={isActive}
                                                onClick={() => setDeleteTarget(v)}
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                            </Button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </GlassModal>

            {/* ── Delete confirmation ── */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(o) => !o && setDeleteTarget(null)}
                title="删除版本"
                description={`确定删除版本「${deleteTarget?.version_name ?? ""}」？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={deleting}
            />
        </>
    );
}
