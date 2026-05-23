"use client";

import { usePathname, useParams } from "next/navigation";
import { Database, Loader2 } from "lucide-react";

import { AdminDetailShell } from "@/components/admin/admin-layout-shells";
import { KnowledgeDetailProvider, useKnowledgeDetail } from "@/components/admin/knowledge/knowledge-detail-context";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { AlertCircle } from "lucide-react";

function KnowledgeDetailLayoutInner({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const params = useParams();
    const kbId = params.id as string;
    const { kb, isLoading, error, loadData } = useKnowledgeDetail();

    const base = `/admin/knowledge/${kbId}`;
    const tabs = [
        { label: "概览", href: base, isActive: pathname === base },
        { label: "文档", href: `${base}/documents`, isActive: pathname === `${base}/documents` },
        { label: "词典", href: `${base}/dictionary`, isActive: pathname === `${base}/dictionary` },
        { label: "诊断", href: `${base}/diagnostics`, isActive: pathname === `${base}/diagnostics` },
        { label: "设置", href: `${base}/settings`, isActive: pathname === `${base}/settings` },
    ];

    if (isLoading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
        );
    }

    if (error || !kb) {
        return (
            <GlassCard className="p-8 text-center">
                <AlertCircle className="mx-auto mb-4 h-12 w-12 text-red-500" />
                <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                <p className="mb-4 text-slate-500">{error || "知识库不存在"}</p>
            </GlassCard>
        );
    }

    return (
        <AdminDetailShell
            backHref="/admin/knowledge"
            backLabel="返回知识库列表"
            title={kb.name}
            description={`${kb.document_count || 0} 个文档 · ${kb.total_chunks || 0} 个分块 · ${kb.category}`}
            tabs={tabs}
            actions={(
                <Button variant="outline" className="rounded-full" onClick={() => void loadData()}>刷新</Button>
            )}
        >
            {children}
        </AdminDetailShell>
    );
}

export default function KnowledgeDetailLayout({ children }: { children: React.ReactNode }) {
    return (
        <KnowledgeDetailProvider>
            <KnowledgeDetailLayoutInner>{children}</KnowledgeDetailLayoutInner>
        </KnowledgeDetailProvider>
    );
}
