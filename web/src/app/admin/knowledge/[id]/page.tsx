"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { AdminKnowledgeBase, AdminKnowledgeDocument } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    ArrowLeft, Upload, FileText, Trash2, Eye, RefreshCcw,
    AlertCircle, CheckCircle, Clock, Loader2, Database
} from "lucide-react";
import {
    Dialog, DialogContent, DialogDescription,
    DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/glass-modal";
import Link from "next/link";

// Category labels
const categoryLabels: Record<string, string> = {
    product: "产品", competitor: "竞品", faq: "FAQ", policy: "政策",
};

// Status config
const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    pending: { label: "待处理", color: "bg-yellow-50 text-yellow-600", icon: <Clock className="w-3 h-3" /> },
    processing: { label: "处理中", color: "bg-blue-50 text-blue-600", icon: <Loader2 className="w-3 h-3 animate-spin" /> },
    ready: { label: "已就绪", color: "bg-green-50 text-green-600", icon: <CheckCircle className="w-3 h-3" /> },
    failed: { label: "失败", color: "bg-red-50 text-red-600", icon: <AlertCircle className="w-3 h-3" /> },
};

// Format file size
const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDocumentError = (message?: string): string => {
    if (!message) return "";
    if (message.includes("Insufficient credits") || (message.includes("402") && message.includes("EMBEDDING_API_ERROR"))) {
        return "文档文本已解析，但向量化失败：当前 Embedding 提供商额度不足，请补充额度或切换可用的 Embedding 配置后重试。";
    }
    if (message.includes("[EMBEDDING_NOT_CONFIGURED]")) {
        return "文档文本已解析，但未配置 Embedding 服务，暂时无法建立知识检索索引。";
    }
    return message;
};

type PreviewChunk = { index: number; content: string };

const normalizePreviewChunks = (chunks: unknown): PreviewChunk[] => {
    if (!Array.isArray(chunks)) {
        return [];
    }

    return chunks
        .map((chunk, fallbackIndex) => {
            if (typeof chunk === "string") {
                return { index: fallbackIndex, content: chunk };
            }

            if (chunk && typeof chunk === "object") {
                const chunkObject = chunk as { index?: unknown; content?: unknown };
                const safeIndex = typeof chunkObject.index === "number" ? chunkObject.index : fallbackIndex;
                const safeContent = typeof chunkObject.content === "string" ? chunkObject.content : "";

                return { index: safeIndex, content: safeContent };
            }

            return null;
        })
        .filter((chunk): chunk is PreviewChunk => !!chunk);
};

export default function KnowledgeDetailPage() {
    const params = useParams();
    const router = useRouter();
    const toast = useToast();
    const kbId = params.id as string;

    const [kb, setKb] = useState<AdminKnowledgeBase | null>(null);
    const [docs, setDocs] = useState<AdminKnowledgeDocument[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Upload state
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);

    // Preview state
    const [previewDoc, setPreviewDoc] = useState<AdminKnowledgeDocument | null>(null);
    const [previewChunks, setPreviewChunks] = useState<PreviewChunk[]>([]);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    // Delete state
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeDocument | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [kbData, docsData] = await Promise.all([
                api.admin.getKnowledgeBase(kbId),
                api.admin.getKnowledgeBaseDocuments(kbId),
            ]);
            setKb(kbData);
            setDocs(docsData);
        } catch (err) {
            console.error("Failed to load knowledge base:", err);
            setError(err instanceof Error ? err.message : "加载失败");
        } finally {
            setIsLoading(false);
        }
    }, [kbId]);

    useEffect(() => { loadData(); }, [loadData]);

    // Auto-refresh for processing documents
    useEffect(() => {
        const hasProcessing = docs.some(d => d.status === "processing" || d.status === "pending");
        if (!hasProcessing) return;
        const interval = setInterval(loadData, 5000);
        return () => clearInterval(interval);
    }, [docs, loadData]);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const allowedTypes = ["pdf", "docx", "txt", "md"];
        const ext = file.name.split(".").pop()?.toLowerCase();
        if (!ext || !allowedTypes.includes(ext)) {
            toast.error("不支持的文件类型，请上传 PDF、DOCX、TXT 或 MD 文件");
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            toast.error("文件大小不能超过 50MB");
            return;
        }

        setIsUploading(true);
        setUploadProgress(0);

        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("title", file.name);

            // Simulate progress
            const progressInterval = setInterval(() => {
                setUploadProgress(prev => Math.min(prev + 10, 90));
            }, 200);

            await api.admin.uploadDocument(kbId, formData);
            clearInterval(progressInterval);
            setUploadProgress(100);

            toast.success("文档上传成功，正在处理中...");
            loadData();
        } catch (err) {
            console.error("Upload failed:", err);
            toast.error(`上传失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            e.target.value = "";
        }
    };

    const handlePreview = async (doc: AdminKnowledgeDocument) => {
        if (doc.status === "processing" || doc.status === "pending") {
            toast.error("文档尚未处理完成，暂时无法预览");
            return;
        }

        setPreviewDoc(doc);
        setIsLoadingPreview(true);

        try {
            const data = await api.admin.getDocumentPreview(kbId, doc.id);
            setPreviewChunks(normalizePreviewChunks(data.chunks));
        } catch (err) {
            console.error("Failed to load preview:", err);
            toast.error("加载预览失败");
            setPreviewDoc(null);
        } finally {
            setIsLoadingPreview(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.admin.deleteDocument(kbId, deleteTarget.id);
            setDocs(prev => prev.filter(d => d.id !== deleteTarget.id));
            toast.success("文档删除成功");
            setDeleteTarget(null);
        } catch (err) {
            console.error("Delete failed:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="animate-spin w-8 h-8 border-2 border-slate-200 border-t-slate-900 rounded-full" />
            </div>
        );
    }

    if (error || !kb) {
        return (
            <GlassCard className="p-8 text-center">
                <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                <h3 className="text-lg font-bold text-slate-900 mb-2">加载失败</h3>
                <p className="text-slate-500 mb-4">{error || "知识库不存在"}</p>
                <Button onClick={() => router.back()} className="rounded-full">
                    <ArrowLeft className="w-4 h-4 mr-2" /> 返回
                </Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Delete Confirm */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除文档"
                description={`确定要删除「${deleteTarget?.file_name}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {/* Preview Dialog */}
            <Dialog open={!!previewDoc} onOpenChange={(open) => !open && setPreviewDoc(null)}>
                <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FileText className="w-5 h-5 text-blue-600" />
                            {previewDoc?.file_name}
                        </DialogTitle>
                        <DialogDescription>
                            共 {previewChunks.length} 个分块
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex-1 overflow-y-auto py-4 space-y-3">
                        {isLoadingPreview ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
                            </div>
                        ) : previewChunks.length === 0 ? (
                            <div className="text-center py-12 text-slate-500">暂无分块数据</div>
                        ) : (
                            previewChunks.map((chunk, idx) => (
                                <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Badge variant="secondary" className="bg-slate-200 text-slate-600 text-xs">
                                            分块 #{chunk.index + 1}
                                        </Badge>
                                    </div>
                                    <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                                        {chunk.content}
                                    </p>
                                </div>
                            ))
                        )}
                    </div>
                    <DialogFooter>
                        <Button onClick={() => setPreviewDoc(null)} className="rounded-full">
                            关闭
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Link href="/admin/knowledge">
                        <Button variant="ghost" size="icon" className="rounded-full">
                            <ArrowLeft className="w-5 h-5" />
                        </Button>
                    </Link>
                    <div>
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
                                <Database className="w-5 h-5" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-black text-slate-900">{kb.name}</h1>
                                <div className="flex items-center gap-2 mt-1">
                                    <Badge variant="secondary" className="bg-slate-100 text-slate-600">
                                        {categoryLabels[kb.category] || kb.category}
                                    </Badge>
                                    <span className="text-sm text-slate-500">
                                        {kb.document_count || 0} 个文档 · {kb.total_chunks || 0} 个分块
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="flex gap-3">
                    <Button onClick={loadData} variant="outline" className="rounded-full">
                        <RefreshCcw className="w-4 h-4 mr-2" /> 刷新
                    </Button>
                    <label>
                        <input
                            type="file"
                            className="hidden"
                            accept=".pdf,.docx,.txt,.md"
                            onChange={handleUpload}
                            disabled={isUploading}
                        />
                        <Button
                            className="rounded-full bg-slate-900 hover:bg-slate-800 text-white cursor-pointer"
                            disabled={isUploading}
                            asChild
                        >
                            <span>
                                {isUploading ? (
                                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 上传中 {uploadProgress}%</>
                                ) : (
                                    <><Upload className="w-4 h-4 mr-2" /> 上传文档</>
                                )}
                            </span>
                        </Button>
                    </label>
                </div>
            </div>

            {/* Description */}
            {kb.description && (
                <GlassCard className="p-4">
                    <p className="text-slate-600">{kb.description}</p>
                </GlassCard>
            )}

            {/* Documents List */}
            <GlassCard className="overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                    <h2 className="font-bold text-slate-900">文档列表</h2>
                    <span className="text-xs text-slate-400">支持 PDF, DOCX, TXT, MD</span>
                </div>

                {docs.length === 0 ? (
                    <div className="p-12 text-center">
                        <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                        <h3 className="text-lg font-bold text-slate-900 mb-2">暂无文档</h3>
                        <p className="text-slate-500 mb-4">上传文档后，系统将自动进行分块和向量化处理</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100">
                        {docs.map((doc) => {
                            const status = statusConfig[doc.status] || statusConfig.pending;
                            return (
                                <div key={doc.id} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50/50 transition-colors">
                                    <div className="flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
                                            <FileText className="w-5 h-5 text-slate-500" />
                                        </div>
                                        <div>
                                            <div className="font-medium text-slate-900">{doc.file_name}</div>
                                            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                                                <span>{doc.file_type.toUpperCase()}</span>
                                                <span>{formatFileSize(doc.file_size)}</span>
                                                {doc.chunk_count !== undefined && doc.chunk_count > 0 && (
                                                    <span>{doc.chunk_count} 分块</span>
                                                )}
                                            </div>
                                            {doc.status === "failed" && doc.error_message && (
                                                <div className="mt-2 max-w-3xl text-xs leading-5 text-red-600">
                                                    {formatDocumentError(doc.error_message)}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <Badge className={`${status.color} flex items-center gap-1`}>
                                            {status.icon} {status.label}
                                        </Badge>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="rounded-full text-slate-500 hover:text-blue-600"
                                            onClick={() => handlePreview(doc)}
                                            disabled={doc.status === "processing" || doc.status === "pending"}
                                        >
                                            <Eye className="w-4 h-4 mr-1" /> 预览
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="rounded-full text-slate-400 hover:text-red-600 hover:bg-red-50"
                                            onClick={() => setDeleteTarget(doc)}
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
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
