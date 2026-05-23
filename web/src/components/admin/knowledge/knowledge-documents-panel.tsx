"use client";

import { Eye, FileText, Loader2, RotateCcw, Trash2, Upload } from "lucide-react";

import { useKnowledgeDetail } from "./knowledge-detail-context";
import { formatDocumentError, formatFileSize, statusConfig, uploadStatusConfig } from "./knowledge-detail-shared";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/glass-modal";

export function KnowledgeDocumentsPanel() {
    const {
        uploadQueue, isUploadDragActive, setIsUploadDragActive, isUploading, uploadQueueSummary,
        handleUploadInputChange, handleUploadDrop, docs, reprocessingDocId, handleReprocess,
        previewDoc, setPreviewDoc, previewChunks, isLoadingPreview, handlePreview,
        deleteTarget, setDeleteTarget, isDeleting, handleDelete,
    } = useKnowledgeDetail();

    return (
        <div className="space-y-6">
            <ConfirmDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)} title="删除文档" description={`确定要删除「${deleteTarget?.file_name}」吗？此操作不可撤销。`} confirmText="删除" variant="danger" onConfirm={() => void handleDelete()} isLoading={isDeleting} />
            <Dialog open={!!previewDoc} onOpenChange={(open) => !open && setPreviewDoc(null)}>
                <DialogContent className="flex max-h-[80vh] max-w-3xl flex-col overflow-hidden">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2"><FileText className="h-5 w-5 text-blue-600" />{previewDoc?.file_name}</DialogTitle>
                        <DialogDescription>共 {previewChunks.length} 个分块</DialogDescription>
                    </DialogHeader>
                    <div className="flex-1 space-y-3 overflow-y-auto py-4">
                        {isLoadingPreview ? <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div> : previewChunks.length === 0 ? <div className="py-12 text-center text-slate-500">暂无分块数据</div> : previewChunks.map((chunk, idx) => (
                            <div key={idx} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                                <Badge variant="secondary" className="mb-2 bg-slate-200 text-xs text-slate-600">分块 #{chunk.index + 1}</Badge>
                                <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{chunk.content}</p>
                            </div>
                        ))}
                    </div>
                    <DialogFooter><Button onClick={() => setPreviewDoc(null)} className="rounded-full">关闭</Button></DialogFooter>
                </DialogContent>
            </Dialog>

            <div className="flex flex-wrap gap-3">
                <label className={`cursor-pointer rounded-2xl border border-dashed p-2 ${isUploadDragActive ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white/60"}`} onDragOver={(e) => { e.preventDefault(); setIsUploadDragActive(true); }} onDragLeave={() => setIsUploadDragActive(false)} onDrop={handleUploadDrop}>
                    <input type="file" className="hidden" accept=".pdf,.docx,.txt,.md,.xlsx,.xls" multiple onChange={handleUploadInputChange} disabled={isUploading} />
                    <Button className="rounded-full" disabled={isUploading} asChild><span>{isUploading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />上传中</> : <><Upload className="mr-2 h-4 w-4" />批量上传文档</>}</span></Button>
                </label>
            </div>

            {uploadQueue.length > 0 && (
                <GlassCard className="space-y-3 p-4">
                    <h2 className="font-bold text-slate-900">批量上传队列</h2><p className="text-sm text-slate-500">成功 {uploadQueueSummary.successful} · 失败 {uploadQueueSummary.failed}</p>
                    {uploadQueue.map((item) => {
                        const queueStatus = uploadStatusConfig[item.status];
                        return (
                            <div key={item.id} className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div><p className="truncate font-semibold text-slate-900">{item.name}</p><p className="text-xs text-slate-500">{formatFileSize(item.size)}</p></div>
                                    <Badge variant="secondary" className={queueStatus.color}>{queueStatus.label}</Badge>
                                </div>
                                <p className={`mt-2 text-xs ${item.status === "failed" ? "text-red-600" : "text-slate-500"}`}>{item.message}</p>
                            </div>
                        );
                    })}
                </GlassCard>
            )}

            <GlassCard className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4"><h2 className="font-bold text-slate-900">文档列表</h2></div>
                {docs.length === 0 ? <div className="p-12 text-center text-slate-500">暂无文档</div> : (
                    <div className="divide-y divide-slate-100">
                        {docs.map((doc) => {
                            const status = statusConfig[doc.status] || statusConfig.pending;
                            return (
                                <div key={doc.id} className="flex flex-col gap-4 px-6 py-4 lg:flex-row lg:items-start lg:justify-between">
                                    <div>
                                        <div className="font-medium text-slate-900">{doc.file_name}</div>
                                        <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500"><span>{doc.file_type.toUpperCase()}</span><span>{formatFileSize(doc.file_size)}</span><span>{doc.chunk_count || 0} 分块</span></div>
                                        {doc.status === "failed" && doc.error_message && <div className="mt-2 text-xs text-red-600">{formatDocumentError(doc.error_message)}</div>}
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Badge className={`${status.color} border flex items-center gap-1`}>{status.icon}{status.label}</Badge>
                                        {(doc.status === "failed" || doc.status === "pending") && (
                                            <Button variant="outline" size="sm" className="rounded-full" onClick={() => void handleReprocess(doc)} disabled={reprocessingDocId === doc.id}>
                                                {reprocessingDocId === doc.id ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <RotateCcw className="mr-1 h-4 w-4" />}重试处理
                                            </Button>
                                        )}
                                        <Button variant="ghost" size="sm" className="rounded-full" onClick={() => void handlePreview(doc)} disabled={doc.status === "processing" || doc.status === "pending"}><Eye className="mr-1 h-4 w-4" />预览</Button>
                                        <Button variant="ghost" size="icon" className="rounded-full text-red-500" onClick={() => setDeleteTarget(doc)} aria-label={`删除 ${doc.file_name}`}><Trash2 className="h-4 w-4" /></Button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
