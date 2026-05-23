"use client";

import Link from "next/link";
import { Database } from "lucide-react";

import { useKnowledgeDetail } from "@/components/admin/knowledge/knowledge-detail-context";
import { KnowledgeAnswerConsole } from "@/components/admin/knowledge-answer/knowledge-answer-console";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { categoryLabels } from "@/components/admin/knowledge/knowledge-detail-shared";

export default function KnowledgeHubPage() {
    const { kb, docs, dictionaryEntries, kbId, isLoading, error } = useKnowledgeDetail();
    if (isLoading) return <p className="text-slate-500">加载中...</p>;
    if (error || !kb) return <p className="text-red-600">{error || "知识库不存在"}</p>;

    const base = `/admin/knowledge/${kbId}`;

    return (
        <div className="space-y-6">
            <GlassCard className="p-6">
                <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                        <Database className="h-6 w-6" />
                    </div>
                    <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="secondary">{categoryLabels[kb.category] || kb.category}</Badge>
                            <span className="text-sm text-slate-500">状态：{kb.status}</span>
                        </div>
                        {kb.description ? <p className="text-slate-600">{kb.description}</p> : null}
                        <div className="flex flex-wrap gap-4 text-sm text-slate-600">
                            <Link href={`${base}/documents`} className="font-medium text-blue-700 hover:underline">文档 {docs.length}</Link>
                            <Link href={`${base}/dictionary`} className="font-medium text-blue-700 hover:underline">词典 {dictionaryEntries.length}</Link>
                            <Link href={`${base}/diagnostics`} className="font-medium text-blue-700 hover:underline">搜索诊断</Link>
                            <Link href={`${base}/settings`} className="font-medium text-blue-700 hover:underline">RAG 设置</Link>
                            <Link href="/admin/retrieval-strategies" className="font-medium text-amber-700 hover:underline">全局检索策略</Link>
                        </div>
                    </div>
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-6">
                <div className="rounded-2xl border border-blue-200 bg-blue-50/90 px-4 py-3 text-sm text-blue-900">
                    <p className="font-semibold">全局检索策略预览（只读）</p>
                    <p className="mt-1 text-blue-800">修改检索管线请前往 <Link href="/admin/retrieval-strategies" className="font-semibold underline">检索策略</Link>；本库 RAG Profile 在设置页管理。</p>
                </div>
                <KnowledgeAnswerConsole readOnly />
            </GlassCard>
        </div>
    );
}
