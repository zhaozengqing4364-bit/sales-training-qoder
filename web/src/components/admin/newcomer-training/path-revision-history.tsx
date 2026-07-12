"use client";

import { useState } from "react";
import { History, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AssetRevisionSummary } from "@/lib/api/types/newcomer-training";

export function PathRevisionHistory({ currentRevisionId, onRestored }: { currentRevisionId: string | null; onRestored: (revision: AssetRevisionSummary) => void }) {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [items, setItems] = useState<AssetRevisionSummary[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [target, setTarget] = useState<AssetRevisionSummary | null>(null);
    const [restoring, setRestoring] = useState(false);

    async function toggle() {
        const next = !open;
        setOpen(next);
        if (!next || items.length) return;
        setLoading(true); setError(null);
        try { setItems(await api.admin.newcomerTraining.listRevisions()); }
        catch (cause) { setError(getApiErrorMessage(cause)); }
        finally { setLoading(false); }
    }

    async function restore() {
        if (!target) return;
        setRestoring(true); setError(null);
        try {
            const restored = await api.admin.newcomerTraining.restoreRevision(target.revision_id, `从版本 ${target.revision_no} 恢复为新草稿`, currentRevisionId);
            onRestored(restored);
            setTarget(null);
            setOpen(false);
        } catch (cause) { setError(getApiErrorMessage(cause)); }
        finally { setRestoring(false); }
    }

    return <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><Button type="button" variant="ghost" className="w-full justify-between" onClick={() => void toggle()}><span className="inline-flex items-center gap-2"><History className="h-4 w-4" />版本历史</span><span>{open ? "收起" : "查看"}</span></Button>{open ? <div className="mt-3 space-y-2">{loading ? <p className="text-sm text-slate-500">正在加载历史版本…</p> : null}{error ? <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}{!loading && !error && items.length === 0 ? <p className="text-sm text-slate-500">还没有历史版本。</p> : null}{items.map((item) => <div key={item.revision_id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3"><div><p className="text-sm font-medium text-slate-900">版本 {item.revision_no} · {item.status === "published" ? "已发布" : item.status === "working" ? "草稿" : "历史"}</p><p className="mt-1 text-xs text-slate-500">{item.reason ?? "未填写说明"}</p></div><Button type="button" size="sm" variant="outline" onClick={() => setTarget(item)}><RotateCcw className="mr-1 h-3.5 w-3.5" />恢复</Button></div>)}</div> : null}<ConfirmDialog open={target !== null} onOpenChange={(value) => { if (!value) setTarget(null); }} title="恢复为新草稿" description="当前已发布版本不会立即改变；系统会把所选版本复制为新的待编辑草稿。" confirmText="确认恢复" isLoading={restoring} onConfirm={() => void restore()} /></section>;
}
