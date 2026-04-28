"use client";
import { debug } from "@/lib/debug";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
    AlertCircle,
    ArrowLeft,
    CheckCircle,
    Clock,
    Database,
    Eye,
    FileText,
    Loader2,
    RefreshCcw,
    RotateCcw,
    Search,
    Trash2,
    Upload,

} from "lucide-react";

import { KnowledgeAnswerConsole } from "@/components/admin/knowledge-answer/knowledge-answer-console";

import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    AdminKnowledgeBase,
    AdminKnowledgeDocument,
    AdminKnowledgeSearchResult,
} from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";

const categoryLabels: Record<string, string> = {
    product: "产品",
    competitor: "竞品",
    faq: "FAQ",
    policy: "政策",
};

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    pending: {
        label: "待处理",
        color: "bg-yellow-50 text-yellow-700 border-yellow-200",
        icon: <Clock className="w-3 h-3" />,
    },
    processing: {
        label: "处理中",
        color: "bg-blue-50 text-blue-700 border-blue-200",
        icon: <Loader2 className="w-3 h-3 animate-spin" />,
    },
    ready: {
        label: "已就绪",
        color: "bg-green-50 text-green-700 border-green-200",
        icon: <CheckCircle className="w-3 h-3" />,
    },
    failed: {
        label: "失败",
        color: "bg-red-50 text-red-700 border-red-200",
        icon: <AlertCircle className="w-3 h-3" />,
    },
};

const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const ALLOWED_UPLOAD_EXTENSIONS = ["pdf", "docx", "txt", "md", "xlsx", "xls"] as const;
const MAX_UPLOAD_FILE_SIZE_BYTES = 50 * 1024 * 1024;
const BATCH_UPLOAD_CONCURRENCY = 3;

type UploadQueueStatus = "queued" | "uploading" | "success" | "failed";

interface UploadQueueItem {
    id: string;
    name: string;
    size: number;
    status: UploadQueueStatus;
    progress: number;
    message: string;
}

const uploadStatusConfig: Record<UploadQueueStatus, { label: string; color: string; progressColor: string }> = {
    queued: {
        label: "等待上传",
        color: "bg-slate-50 text-slate-600 border-slate-200",
        progressColor: "bg-slate-300",
    },
    uploading: {
        label: "上传中",
        color: "bg-blue-50 text-blue-700 border-blue-200",
        progressColor: "bg-blue-500",
    },
    success: {
        label: "已提交",
        color: "bg-green-50 text-green-700 border-green-200",
        progressColor: "bg-green-500",
    },
    failed: {
        label: "失败",
        color: "bg-red-50 text-red-700 border-red-200",
        progressColor: "bg-red-500",
    },
};

const formatDocumentError = (message?: string): string => {
    if (!message) return "";
    if (
        message.includes("Insufficient credits")
        || (message.includes("402") && message.includes("EMBEDDING_API_ERROR"))
    ) {
        return "文档文本已解析，但向量化失败：当前 Embedding 提供商额度不足，请补充额度或切换可用的 Embedding 配置后重试。";
    }
    if (message.includes("[EMBEDDING_NOT_CONFIGURED]")) {
        return "文档文本已解析，但未配置 Embedding 服务，暂时无法建立知识检索索引。";
    }
    return message;
};

const validateUploadFile = (file: File): string | null => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !ALLOWED_UPLOAD_EXTENSIONS.includes(ext as typeof ALLOWED_UPLOAD_EXTENSIONS[number])) {
        return "不支持的文件类型，请上传 PDF、DOCX、TXT、MD、XLSX 或 XLS 文件";
    }

    if (file.size > MAX_UPLOAD_FILE_SIZE_BYTES) {
        return "文件大小不能超过 50MB";
    }

    return null;
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
        .filter((chunk): chunk is PreviewChunk => Boolean(chunk));
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

    const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
    const [isUploadDragActive, setIsUploadDragActive] = useState(false);
    const [reprocessingDocId, setReprocessingDocId] = useState<string | null>(null);

    const [previewDoc, setPreviewDoc] = useState<AdminKnowledgeDocument | null>(null);
    const [previewChunks, setPreviewChunks] = useState<PreviewChunk[]>([]);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeDocument | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<AdminKnowledgeSearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [searchMessage, setSearchMessage] = useState<string | null>(null);
    const [searchError, setSearchError] = useState<string | null>(null);

    // ── RAG Profile State ──
    const [ragProfiles, setRagProfiles] = useState<Array<{ id: string; name: string }>>([]);
    const [savingProfile, setSavingProfile] = useState(false);

    // Load available RAG profiles
    useEffect(() => {
        api.admin.listRagProfiles()
            .then(profiles => setRagProfiles(profiles?.map(p => ({ id: p.id, name: p.name })) ?? []))
            .catch(() => { /* non-blocking */ });
    }, []);

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
            debug.error("Failed to load knowledge base:", err);
            setError(getApiErrorMessage(err));
        } finally {
            setIsLoading(false);
        }
    }, [kbId]);

    const handleAssignProfile = useCallback(async (profileId: string | null) => {
        if (!kb) return;
        setSavingProfile(true);
        try {
            await api.admin.assignRagProfileToKb(kb.id, profileId);
            toast.success(profileId ? "已切换 RAG 配置" : "已取消 RAG 配置关联");
            await loadData();
        } catch (err) {
            toast.error(getApiErrorMessage(err));
        } finally {
            setSavingProfile(false);
        }
    }, [kb, toast, loadData]);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    useEffect(() => {
        const hasProcessing = docs.some((doc) => doc.status === "processing" || doc.status === "pending");
        if (!hasProcessing) return undefined;
        const interval = setInterval(() => {
            void loadData();
        }, 5000);
        return () => clearInterval(interval);
    }, [docs, loadData]);

    const readyDocuments = useMemo(
        () => docs.filter((doc) => doc.status === "ready"),
        [docs],
    );
    const pendingDocuments = useMemo(
        () => docs.filter((doc) => doc.status === "pending" || doc.status === "processing"),
        [docs],
    );
    const failedDocuments = useMemo(
        () => docs.filter((doc) => doc.status === "failed"),
        [docs],
    );
    const uploadQueueSummary = useMemo(() => ({
        active: uploadQueue.filter((item) => item.status === "queued" || item.status === "uploading").length,
        successful: uploadQueue.filter((item) => item.status === "success").length,
        failed: uploadQueue.filter((item) => item.status === "failed").length,
    }), [uploadQueue]);
    const isUploading = uploadQueueSummary.active > 0;

    const searchReadiness = useMemo(() => {
        if (readyDocuments.length > 0) {
            return {
                tone: "border-green-200 bg-green-50 text-green-700",
                title: "可执行搜索诊断",
                description: `已有 ${readyDocuments.length} 份文档就绪，可直接验证命中情况。`,
                actionable: true,
            };
        }
        if (pendingDocuments.length > 0) {
            return {
                tone: "border-amber-200 bg-amber-50 text-amber-700",
                title: "知识库尚未就绪",
                description: `还有 ${pendingDocuments.length} 份文档处于待处理/处理中，完成后再执行搜索诊断。`,
                actionable: false,
            };
        }
        if (failedDocuments.length > 0) {
            return {
                tone: "border-red-200 bg-red-50 text-red-700",
                title: "当前无可检索文档",
                description: `有 ${failedDocuments.length} 份文档处理失败，请先就地重试。`,
                actionable: false,
            };
        }
        return {
            tone: "border-slate-200 bg-slate-50 text-slate-600",
            title: "等待上传文档",
            description: "上传至少一份产品资料后，才能执行搜索诊断。",
            actionable: false,
        };
    }, [failedDocuments.length, pendingDocuments.length, readyDocuments.length]);

    const patchUploadQueueItem = useCallback((id: string, patch: Partial<UploadQueueItem>) => {
        setUploadQueue((prev) => prev.map((item) => (
            item.id === id ? { ...item, ...patch } : item
        )));
    }, []);

    const advanceUploadProgress = useCallback((id: string) => {
        setUploadQueue((prev) => prev.map((item) => (
            item.id === id
                ? { ...item, progress: Math.min(item.progress + 12, 90) }
                : item
        )));
    }, []);

    const uploadFiles = useCallback(async (selectedFiles: File[]) => {
        if (selectedFiles.length === 0) return;

        const queueItems = selectedFiles.map((file, index): UploadQueueItem => {
            const validationMessage = validateUploadFile(file);
            return {
                id: `${file.name}-${file.size}-${file.lastModified}-${index}`,
                name: file.name,
                size: file.size,
                status: validationMessage ? "failed" : "queued",
                progress: validationMessage ? 100 : 0,
                message: validationMessage || "等待上传",
            };
        });
        const uploadTargets = selectedFiles
            .map((file, index) => ({ file, item: queueItems[index] }))
            .filter(({ item }) => item.status === "queued");

        setUploadQueue(queueItems);

        const invalidCount = queueItems.length - uploadTargets.length;
        if (invalidCount > 0) {
            toast.error(`${invalidCount} 个文件未加入上传队列，请检查类型或大小。`);
        }
        if (uploadTargets.length === 0) {
            return;
        }

        let nextIndex = 0;
        let successCount = 0;
        let failedCount = invalidCount;

        const uploadOne = async ({ file, item }: { file: File; item: UploadQueueItem }) => {
            let progressInterval: ReturnType<typeof setInterval> | null = null;

            patchUploadQueueItem(item.id, {
                status: "uploading",
                progress: 8,
                message: "正在上传并提交解析任务…",
            });

            try {
                progressInterval = setInterval(() => {
                    advanceUploadProgress(item.id);
                }, 250);

                const formData = new FormData();
                formData.append("file", file);
                formData.append("title", file.name);

                await api.admin.uploadDocument(kbId, formData);
                successCount += 1;
                patchUploadQueueItem(item.id, {
                    status: "success",
                    progress: 100,
                    message: "上传成功，已提交解析与建索引。",
                });
            } catch (err) {
                failedCount += 1;
                debug.error("Upload failed:", err);
                patchUploadQueueItem(item.id, {
                    status: "failed",
                    progress: 100,
                    message: `失败：${getApiErrorMessage(err)}`,
                });
            } finally {
                if (progressInterval) {
                    clearInterval(progressInterval);
                }
            }
        };

        const runNext = async () => {
            while (nextIndex < uploadTargets.length) {
                const target = uploadTargets[nextIndex];
                nextIndex += 1;
                await uploadOne(target);
            }
        };

        await Promise.all(Array.from(
            { length: Math.min(BATCH_UPLOAD_CONCURRENCY, uploadTargets.length) },
            () => runNext(),
        ));

        if (successCount > 0) {
            await loadData();
            toast.success(
                failedCount > 0
                    ? `${successCount} 个文件上传成功，${failedCount} 个失败。`
                    : `${successCount} 个文件上传成功，系统已开始解析与建索引。`,
            );
        }
        if (failedCount > 0) {
            toast.error(`${failedCount} 个文件上传失败，请查看队列详情后重试。`);
        }
    }, [advanceUploadProgress, kbId, loadData, patchUploadQueueItem, toast]);

    const handleUploadInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(e.target.files ?? []);
        e.target.value = "";
        if (isUploading) {
            toast.error("当前上传队列仍在处理，请完成后再选择新文件。");
            return;
        }
        void uploadFiles(selectedFiles);
    };

    const handleUploadDrop = (event: React.DragEvent<HTMLLabelElement>) => {
        event.preventDefault();
        setIsUploadDragActive(false);
        if (isUploading) {
            toast.error("当前上传队列仍在处理，请完成后再拖入新文件。");
            return;
        }
        void uploadFiles(Array.from(event.dataTransfer.files));
    };

    const handlePreview = async (doc: AdminKnowledgeDocument) => {
        if (doc.status === "processing" || doc.status === "pending") {
            toast.error("文档尚未处理完成，暂时无法预览。");
            return;
        }

        setPreviewDoc(doc);
        setIsLoadingPreview(true);

        try {
            const data = await api.admin.getDocumentPreview(kbId, doc.id);
            setPreviewChunks(normalizePreviewChunks(data.chunks));
        } catch (err) {
            debug.error("Failed to load preview:", err);
            toast.error(`加载预览失败：${getApiErrorMessage(err)}`);
            setPreviewDoc(null);
        } finally {
            setIsLoadingPreview(false);
        }
    };

    const handleReprocess = async (doc: AdminKnowledgeDocument) => {
        setReprocessingDocId(doc.id);
        try {
            await api.adminTools.reprocessKnowledgeDocument(kbId, doc.id);
            setDocs((prev) => prev.map((item) => (
                item.id === doc.id
                    ? { ...item, status: "pending", chunk_count: 0, error_message: undefined }
                    : item
            )));
            setSearchError(null);
            setSearchMessage("已重新提交文档处理，请等待状态变为“已就绪”后再执行搜索诊断。");
            toast.success("文档已重新提交处理。");
            await loadData();
        } catch (err) {
            debug.error("Reprocess failed:", err);
            toast.error(`重试失败：${getApiErrorMessage(err)}`);
        } finally {
            setReprocessingDocId(null);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.admin.deleteDocument(kbId, deleteTarget.id);
            setDocs((prev) => prev.filter((doc) => doc.id !== deleteTarget.id));
            toast.success("文档删除成功。");
            setDeleteTarget(null);
        } catch (err) {
            debug.error("Delete failed:", err);
            toast.error(`删除失败：${getApiErrorMessage(err)}`);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleSearch = async () => {
        const normalizedQuery = searchQuery.trim();
        if (!normalizedQuery) {
            setSearchError("请输入需要验证的检索问题。");
            setSearchMessage(null);
            setSearchResults([]);
            return;
        }

        if (!searchReadiness.actionable) {
            setSearchError(searchReadiness.description);
            setSearchMessage(null);
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        setSearchError(null);
        setSearchMessage(`正在检索「${normalizedQuery}」...`);

        try {
            const data = await api.admin.searchKnowledgeBase(kbId, normalizedQuery, 5, 0.7);
            setSearchResults(data.results);
            if (data.total > 0) {
                setSearchMessage(`命中 ${data.total} 个片段，来自 ${readyDocuments.length} 份已就绪文档。`);
            } else {
                setSearchMessage("未命中结果。请尝试更具体的问题，或先确认最新文档已处理完成。");
            }
        } catch (err) {
            debug.error("Search failed:", err);
            setSearchResults([]);
            setSearchMessage(null);
            setSearchError(getApiErrorMessage(err));
        } finally {
            setIsSearching(false);
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

            <Dialog open={!!previewDoc} onOpenChange={(open) => !open && setPreviewDoc(null)}>
                <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FileText className="w-5 h-5 text-blue-600" />
                            {previewDoc?.file_name}
                        </DialogTitle>
                        <DialogDescription>共 {previewChunks.length} 个分块</DialogDescription>
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

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Link href="/admin/knowledge">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="rounded-full"
                            aria-label="返回知识库列表"
                        >
                            <ArrowLeft className="w-5 h-5" />
                        </Button>
                    </Link>
                    <div>
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
                                <Database className="w-5 h-5" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-black text-slate-900 text-balance">{kb.name}</h1>
                                <div className="flex items-center gap-2 mt-1 flex-wrap text-pretty">
                                    <Badge variant="secondary" className="bg-slate-100 text-slate-600">
                                        {categoryLabels[kb.category] || kb.category}
                                    </Badge>
                                    <span className="text-sm text-slate-500 tabular-nums">
                                        {kb.document_count || 0} 个文档 · {kb.total_chunks || 0} 个分块
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="flex gap-3 flex-wrap">
                    <Button onClick={() => void loadData()} variant="outline" className="rounded-full">
                        <RefreshCcw className="w-4 h-4 mr-2" /> 刷新
                    </Button>
                    <label
                        className={`cursor-pointer rounded-2xl border border-dashed p-2 transition-colors ${
                            isUploadDragActive
                                ? "border-blue-300 bg-blue-50"
                                : "border-slate-200 bg-white/60 hover:border-slate-300 hover:bg-white"
                        } ${isUploading ? "opacity-75" : ""}`}
                        onDragOver={(event) => {
                            event.preventDefault();
                            setIsUploadDragActive(true);
                        }}
                        onDragLeave={() => setIsUploadDragActive(false)}
                        onDrop={handleUploadDrop}
                        aria-label="批量上传知识文档"
                    >
                        <input
                            type="file"
                            className="hidden"
                            accept=".pdf,.docx,.txt,.md,.xlsx,.xls"
                            multiple
                            onChange={handleUploadInputChange}
                            disabled={isUploading}
                        />
                        <Button
                            className="rounded-full bg-slate-900 hover:bg-slate-800 text-white cursor-pointer"
                            disabled={isUploading}
                            asChild
                        >
                            <span>
                                {isUploading ? (
                                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 队列上传中 {uploadQueueSummary.successful + uploadQueueSummary.failed}/{uploadQueue.length}</>
                                ) : (
                                    <><Upload className="w-4 h-4 mr-2" /> 批量上传文档</>
                                )}
                            </span>
                        </Button>
                        <span className="mt-1 block px-2 text-center text-[11px] font-medium text-slate-500">
                            支持多选/拖拽 · 最多 3 个并发
                        </span>
                    </label>
                </div>
            </div>

            {kb.description && (
                <GlassCard className="p-4">
                    <p className="text-slate-600 text-pretty">{kb.description}</p>
                </GlassCard>
            )}

            {uploadQueue.length > 0 && (
                <GlassCard className="p-4 space-y-3">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div>
                            <h2 className="font-bold text-slate-900">批量上传队列</h2>
                            <p className="text-sm text-slate-500">
                                {uploadQueue.length} 个文件 · 并发上限 {BATCH_UPLOAD_CONCURRENCY} · 成功 {uploadQueueSummary.successful} · 失败 {uploadQueueSummary.failed}
                            </p>
                        </div>
                        {isUploading ? (
                            <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-blue-100">
                                <Loader2 className="w-3 h-3 mr-1 animate-spin" /> 处理中
                            </Badge>
                        ) : null}
                    </div>
                    <div className="space-y-2">
                        {uploadQueue.map((item) => {
                            const queueStatus = uploadStatusConfig[item.status];
                            return (
                                <div key={item.id} className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex items-start gap-3 min-w-0">
                                            <div className="mt-0.5 rounded-lg bg-slate-50 p-2 text-slate-500">
                                                <FileText className="w-4 h-4" />
                                            </div>
                                            <div className="min-w-0">
                                                <p className="font-semibold text-slate-900 truncate">{item.name}</p>
                                                <p className="text-xs text-slate-500">{formatFileSize(item.size)}</p>
                                            </div>
                                        </div>
                                        <Badge variant="secondary" className={`${queueStatus.color} shrink-0`}>
                                            {queueStatus.label}
                                        </Badge>
                                    </div>
                                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                                        <div
                                            className={`h-full rounded-full transition-all ${queueStatus.progressColor}`}
                                            style={{ width: `${item.progress}%` }}
                                        />
                                    </div>
                                    <p className={`mt-2 text-xs ${item.status === "failed" ? "text-red-600" : "text-slate-500"}`}>
                                        {item.message}
                                    </p>
                                </div>
                            );
                        })}
                    </div>
                </GlassCard>
            )}

            <GlassCard className="p-6 space-y-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                        <h2 className="font-bold text-slate-900">搜索诊断</h2>
                        <p className="text-sm text-slate-500">输入管理员问题，直接验证当前知识库是否能命中最新产品资料。</p>
                    </div>
                    <div className={`rounded-full border px-3 py-1 text-xs font-medium ${searchReadiness.tone}`}>
                        {searchReadiness.title}
                    </div>
                </div>

                <div className={`rounded-2xl border px-4 py-3 text-sm ${searchReadiness.tone}`}>
                    {searchReadiness.description}
                </div>

                <div className="flex flex-col md:flex-row gap-3">
                    <div className="flex-1">
                        <label htmlFor="knowledge-search-input" className="mb-2 block text-sm font-medium text-slate-700">
                            知识库搜索诊断
                        </label>
                        <div className="relative">
                            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                            <input
                                id="knowledge-search-input"
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="例如：产品价格、实施周期、标准版包含哪些功能？"
                                className="w-full rounded-2xl border border-slate-200 bg-white px-10 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                            />
                        </div>
                    </div>
                    <div className="flex items-end">
                        <Button
                            onClick={() => void handleSearch()}
                            disabled={isSearching}
                            className="rounded-full"
                        >
                            {isSearching ? (
                                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 执行中</>
                            ) : (
                                <><Search className="w-4 h-4 mr-2" /> 执行诊断</>
                            )}
                        </Button>
                    </div>
                </div>

                {searchMessage && (
                    <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                        {searchMessage}
                    </div>
                )}
                {searchError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        {searchError}
                    </div>
                )}

                {searchResults.length > 0 && (
                    <div className="space-y-3">
                        {searchResults.map((result, index) => (
                            <div key={`${result.metadata.document_id}-${result.metadata.chunk_index}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
                                    <div className="text-sm font-semibold text-slate-900">
                                        {result.metadata.document_title}
                                    </div>
                                    <div className="flex items-center gap-2 text-xs text-slate-500 tabular-nums">
                                        <Badge variant="secondary" className="bg-slate-200 text-slate-700">
                                            片段 #{result.metadata.chunk_index + 1}
                                        </Badge>
                                        <span>相关度 {(result.score * 100).toFixed(0)}%</span>
                                    </div>
                                </div>
                                <p className="text-sm leading-6 text-slate-700 whitespace-pre-wrap text-pretty">
                                    {result.content}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </GlassCard>


            <KnowledgeAnswerConsole />

            {/* ── RAG Profile Reference ── */}
            <GlassCard className="p-6 space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h2 className="font-bold text-slate-900">RAG 配置</h2>
                        <p className="text-xs text-slate-500 mt-0.5">
                            分块策略、语义缓存和重排序由统一的 RAG 配置管理
                        </p>
                    </div>
                    <div className="flex gap-2">
                        <Link href="/admin/retrieval-strategies">
                            <Button variant="outline" size="sm" className="rounded-full">
                                检索策略
                            </Button>
                        </Link>
                        <Link href="/admin/rag-profiles">
                            <Button variant="outline" size="sm" className="rounded-full">
                                管理配置
                            </Button>
                        </Link>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <label className="text-sm text-slate-600 shrink-0">当前配置</label>
                    <select
                        className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white"
                        value={kb?.rag_profile_id ?? ""}
                        onChange={e => void handleAssignProfile(e.target.value || null)}
                        disabled={savingProfile || ragProfiles.length === 0}
                    >
                        <option value="">使用系统默认</option>
                        {ragProfiles.map(p => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                    </select>
                    {savingProfile && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
                </div>
            </GlassCard>

            <GlassCard className="overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between gap-3 flex-wrap">
                    <h2 className="font-bold text-slate-900">文档列表</h2>
                    <span className="text-xs text-slate-400">支持 PDF、DOCX、TXT、MD、XLSX、XLS</span>
                </div>

                {docs.length === 0 ? (
                    <div className="p-12 text-center">
                        <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                        <h3 className="text-lg font-bold text-slate-900 mb-2">暂无文档</h3>
                        <p className="text-slate-500 mb-4 text-pretty">上传文档后，系统会自动分块、向量化并在这里反馈处理状态。</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100">
                        {docs.map((doc) => {
                            const status = statusConfig[doc.status] || statusConfig.pending;
                            const canRetry = doc.status === "failed" || doc.status === "pending";
                            return (
                                <div key={doc.id} className="px-6 py-4 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                                    <div className="flex items-start gap-4">
                                        <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center shrink-0 mt-1">
                                            <FileText className="w-5 h-5 text-slate-500" />
                                        </div>
                                        <div className="space-y-2">
                                            <div>
                                                <div className="font-medium text-slate-900 text-pretty">{doc.file_name}</div>
                                                <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 flex-wrap tabular-nums">
                                                    <span>{doc.file_type.toUpperCase()}</span>
                                                    <span>{formatFileSize(doc.file_size)}</span>
                                                    <span>{doc.chunk_count || 0} 分块</span>
                                                </div>
                                            </div>

                                            {doc.status === "ready" && (
                                                <div className="text-xs text-green-700">文档已完成建索引，可用于搜索诊断与新建训练。</div>
                                            )}
                                            {(doc.status === "pending" || doc.status === "processing") && (
                                                <div className="text-xs text-amber-700">文档仍在排队/处理中，处理完成后才会参与检索。</div>
                                            )}
                                            {doc.status === "failed" && doc.error_message && (
                                                <div className="max-w-3xl text-xs leading-5 text-red-600">
                                                    {formatDocumentError(doc.error_message)}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3 flex-wrap lg:justify-end">
                                        <Badge className={`${status.color} border flex items-center gap-1`}>
                                            {status.icon} {status.label}
                                        </Badge>
                                        {canRetry && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="rounded-full"
                                                onClick={() => void handleReprocess(doc)}
                                                disabled={reprocessingDocId === doc.id}
                                            >
                                                {reprocessingDocId === doc.id ? (
                                                    <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> 重试中</>
                                                ) : (
                                                    <><RotateCcw className="w-4 h-4 mr-1" /> 重试处理</>
                                                )}
                                            </Button>
                                        )}
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="rounded-full text-slate-500 hover:text-blue-600"
                                            onClick={() => void handlePreview(doc)}
                                            disabled={doc.status === "processing" || doc.status === "pending"}
                                        >
                                            <Eye className="w-4 h-4 mr-1" /> 预览
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="rounded-full text-slate-400 hover:text-red-600 hover:bg-red-50"
                                            onClick={() => setDeleteTarget(doc)}
                                            aria-label={`删除 ${doc.file_name}`}
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
