"use client";

import { Loader2, Search } from "lucide-react";
import { useKnowledgeDetail } from "./knowledge-detail-context";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function KnowledgeSearchDiagnostics() {
    const { searchQuery, setSearchQuery, searchResults, isSearching, searchMessage, searchError, searchReadiness, handleSearch } = useKnowledgeDetail();
    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h2 className="font-bold text-slate-900">搜索诊断</h2><p className="text-sm text-slate-500">验证当前知识库检索命中情况。</p></div>
                <div className={`rounded-full border px-3 py-1 text-xs font-medium ${searchReadiness.tone}`}>{searchReadiness.title}</div>
            </div>
            <div className={`rounded-2xl border px-4 py-3 text-sm ${searchReadiness.tone}`}>{searchReadiness.description}</div>
            <div className="flex flex-col gap-3 md:flex-row">
                <label htmlFor="knowledge-search-input" className="sr-only">知识库搜索诊断</label><input id="knowledge-search-input" type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="例如：产品价格、实施周期？" className="flex-1 rounded-2xl border px-4 py-3 text-sm" />
                <Button onClick={() => void handleSearch()} disabled={isSearching} className="rounded-full">{isSearching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}执行诊断</Button>
            </div>
            {searchMessage && <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">{searchMessage}</div>}
            {searchError && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{searchError}</div>}
            {searchResults.map((result, index) => (
                <div key={`${result.metadata.document_id}-${index}`} className="rounded-2xl border bg-slate-50 p-4">
                    <div className="mb-2 flex items-center justify-between gap-2"><div className="text-sm font-semibold">{result.metadata.document_title}</div><Badge variant="secondary">相关度 {(result.score * 100).toFixed(0)}%</Badge></div>
                    <p className="whitespace-pre-wrap text-sm text-slate-700">{result.content}</p>
                </div>
            ))}
        </GlassCard>
    );
}
