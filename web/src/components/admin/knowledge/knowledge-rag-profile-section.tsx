"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useKnowledgeDetail } from "./knowledge-detail-context";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";

export function KnowledgeRagProfileSection() {
    const { kb, ragProfiles, savingProfile, handleAssignProfile } = useKnowledgeDetail();
    return (
        <GlassCard className="space-y-3 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h2 className="font-bold text-slate-900">本库 RAG Profile（分块与缓存）</h2><p className="mt-0.5 text-xs text-slate-500">仅作用于当前知识库的分块预设与缓存参数</p></div>
                <div className="flex gap-2">
                    <Link href="/admin/retrieval-strategies" prefetch={false}><Button variant="outline" size="sm" className="rounded-full">去检索策略编辑</Button></Link>
                    <Link href="/admin/rag-profiles" prefetch={false}><Button variant="outline" size="sm" className="rounded-full">管理 RAG Profile</Button></Link>
                </div>
            </div>
            <p className="rounded-xl border border-amber-200 bg-amber-50/90 px-3 py-2 text-xs text-amber-900">全局检索引擎在 <Link href="/admin/retrieval-strategies" prefetch={false} className="font-semibold underline">检索策略</Link> 页配置。</p>
            <div className="flex items-center gap-3">
                <label className="shrink-0 text-sm text-slate-600">本库 RAG Profile</label>
                <select className="flex-1 rounded-lg border px-3 py-2 text-sm" value={kb?.rag_profile_id ?? ""} onChange={(e) => void handleAssignProfile(e.target.value || null)} disabled={savingProfile || ragProfiles.length === 0}>
                    <option value="">使用系统默认</option>
                    {ragProfiles.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                </select>
                {savingProfile && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
            </div>
        </GlassCard>
    );
}
