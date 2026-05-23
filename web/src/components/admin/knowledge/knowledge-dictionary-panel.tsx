"use client";

import { BookOpen, Loader2, Plus } from "lucide-react";
import { useKnowledgeDetail } from "./knowledge-detail-context";
import { dictionaryStatusColors, dictionaryStatusLabels } from "./knowledge-detail-shared";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function KnowledgeDictionaryPanel() {
    const {
        dictionaryEntries, dictionaryForm, setDictionaryForm, editingDictionaryEntry,
        isSavingDictionary, isGeneratingDictionary, dictionaryError, readyDocuments,
        resetDictionaryForm, handleSaveDictionaryEntry, handleEditDictionaryEntry,
        handleUpdateDictionaryStatus, handleDeleteDictionaryEntry, handleGenerateDictionaryDrafts,
    } = useKnowledgeDetail();

    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h2 className="font-bold text-slate-900">知识库词典</h2><p className="text-sm text-slate-500">管理标准词与 ASR 误识别别名。</p></div>
                <Button variant="outline" size="sm" className="rounded-full" onClick={() => void handleGenerateDictionaryDrafts()} disabled={isGeneratingDictionary || readyDocuments.length === 0}>
                    {isGeneratingDictionary ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <BookOpen className="mr-2 h-4 w-4" />}从文档生成草稿
                </Button>
            </div>
            <div className="grid gap-3 rounded-2xl border border-slate-100 bg-slate-50/60 p-4 md:grid-cols-[1fr_1fr_10rem_auto] md:items-end">
                <div><label className="mb-1 block text-xs font-medium text-slate-600">标准词</label><input placeholder="例如：石犀科技" value={dictionaryForm.canonical_term} onChange={(e) => setDictionaryForm((p) => ({ ...p, canonical_term: e.target.value }))} className="w-full rounded-xl border px-3 py-2 text-sm" /></div>
                <div><label className="mb-1 block text-xs font-medium text-slate-600">别名</label><input placeholder="实习科技，石溪科技" value={dictionaryForm.aliases} onChange={(e) => setDictionaryForm((p) => ({ ...p, aliases: e.target.value }))} className="w-full rounded-xl border px-3 py-2 text-sm" /></div>
                <div><label className="mb-1 block text-xs font-medium text-slate-600">类型</label><select value={dictionaryForm.term_type} onChange={(e) => setDictionaryForm((p) => ({ ...p, term_type: e.target.value }))} className="w-full rounded-xl border px-3 py-2 text-sm"><option value="other">其他</option><option value="organization">组织</option><option value="product">产品</option><option value="feature">功能</option></select></div>
                <div className="flex gap-2">
                    <Button onClick={() => void handleSaveDictionaryEntry()} disabled={isSavingDictionary} className="rounded-full">{editingDictionaryEntry ? "保存" : "添加"}</Button>
                    {editingDictionaryEntry && <Button variant="outline" onClick={resetDictionaryForm} className="rounded-full">取消</Button>}
                </div>
            </div>
            {dictionaryError && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{dictionaryError}</div>}
            {dictionaryEntries.length === 0 ? <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-slate-500">暂无词典条目</div> : dictionaryEntries.map((entry) => (
                <div key={entry.id} className="flex flex-col gap-3 rounded-2xl border bg-white/80 p-4 md:flex-row md:items-center md:justify-between">
                    <div><div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{entry.canonical_term}</span><Badge className={`${dictionaryStatusColors[entry.status] || dictionaryStatusColors.draft} border`}>{dictionaryStatusLabels[entry.status] || entry.status}</Badge></div><p className="mt-1 text-sm text-slate-500">别名：{entry.aliases.join("、") || "未配置"}</p></div>
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={() => handleEditDictionaryEntry(entry)}>编辑</Button>
                        {entry.status !== "active" && <Button size="sm" onClick={() => void handleUpdateDictionaryStatus(entry, "active")}>发布</Button>}
                        {entry.status !== "archived" && <Button variant="outline" size="sm" onClick={() => void handleUpdateDictionaryStatus(entry, "archived")}>归档</Button>}
                        <Button variant="ghost" size="sm" className="text-red-600" onClick={() => void handleDeleteDictionaryEntry(entry)}>删除</Button>
                    </div>
                </div>
            ))}
        </GlassCard>
    );
}
