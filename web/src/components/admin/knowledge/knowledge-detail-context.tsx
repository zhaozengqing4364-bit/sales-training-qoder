"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";

import { debug } from "@/lib/debug";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    AdminKnowledgeBase,
    AdminKnowledgeDictionaryEntry,
    AdminKnowledgeDocument,
    AdminKnowledgeSearchResult,
} from "@/lib/api/types";
import { useToast } from "@/components/ui/toast";
import {
    BATCH_UPLOAD_CONCURRENCY,
    normalizePreviewChunks,
    validateUploadFile,
    type PreviewChunk,
    type UploadQueueItem,
} from "./knowledge-detail-shared";

export interface KnowledgeDetailContextValue {
    kbId: string;
    kb: AdminKnowledgeBase | null;
    docs: AdminKnowledgeDocument[];
    dictionaryEntries: AdminKnowledgeDictionaryEntry[];
    isLoading: boolean;
    error: string | null;
    loadData: () => Promise<void>;
    uploadQueue: UploadQueueItem[];
    isUploadDragActive: boolean;
    setIsUploadDragActive: (v: boolean) => void;
    isUploading: boolean;
    uploadQueueSummary: { active: number; successful: number; failed: number };
    handleUploadInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    handleUploadDrop: (event: React.DragEvent<HTMLLabelElement>) => void;
    reprocessingDocId: string | null;
    handleReprocess: (doc: AdminKnowledgeDocument) => Promise<void>;
    previewDoc: AdminKnowledgeDocument | null;
    setPreviewDoc: (doc: AdminKnowledgeDocument | null) => void;
    previewChunks: PreviewChunk[];
    isLoadingPreview: boolean;
    handlePreview: (doc: AdminKnowledgeDocument) => Promise<void>;
    deleteTarget: AdminKnowledgeDocument | null;
    setDeleteTarget: (doc: AdminKnowledgeDocument | null) => void;
    isDeleting: boolean;
    handleDelete: () => Promise<void>;
    searchQuery: string;
    setSearchQuery: (v: string) => void;
    searchResults: AdminKnowledgeSearchResult[];
    isSearching: boolean;
    searchMessage: string | null;
    searchError: string | null;
    searchReadiness: { tone: string; title: string; description: string; actionable: boolean };
    handleSearch: () => Promise<void>;
    dictionaryForm: { canonical_term: string; aliases: string; term_type: string };
    setDictionaryForm: React.Dispatch<React.SetStateAction<{ canonical_term: string; aliases: string; term_type: string }>>;
    editingDictionaryEntry: AdminKnowledgeDictionaryEntry | null;
    isSavingDictionary: boolean;
    isGeneratingDictionary: boolean;
    dictionaryError: string | null;
    readyDocuments: AdminKnowledgeDocument[];
    resetDictionaryForm: () => void;
    handleSaveDictionaryEntry: () => Promise<void>;
    handleEditDictionaryEntry: (entry: AdminKnowledgeDictionaryEntry) => void;
    handleUpdateDictionaryStatus: (entry: AdminKnowledgeDictionaryEntry, status: "active" | "archived") => Promise<void>;
    handleDeleteDictionaryEntry: (entry: AdminKnowledgeDictionaryEntry) => Promise<void>;
    handleGenerateDictionaryDrafts: () => Promise<void>;
    ragProfiles: Array<{ id: string; name: string }>;
    savingProfile: boolean;
    handleAssignProfile: (profileId: string | null) => Promise<void>;
}

const KnowledgeDetailContext = createContext<KnowledgeDetailContextValue | null>(null);

export function useKnowledgeDetail() {
    const ctx = useContext(KnowledgeDetailContext);
    if (!ctx) throw new Error("useKnowledgeDetail must be used within KnowledgeDetailProvider");
    return ctx;
}

export function KnowledgeDetailProvider({ children }: { children: ReactNode }) {

    const params = useParams();
    const toast = useToast();
    const kbId = params.id as string;

    const [kb, setKb] = useState<AdminKnowledgeBase | null>(null);
    const [docs, setDocs] = useState<AdminKnowledgeDocument[]>([]);
    const [dictionaryEntries, setDictionaryEntries] = useState<AdminKnowledgeDictionaryEntry[]>([]);
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

    const [dictionaryForm, setDictionaryForm] = useState({ canonical_term: "", aliases: "", term_type: "other" });
    const [editingDictionaryEntry, setEditingDictionaryEntry] = useState<AdminKnowledgeDictionaryEntry | null>(null);
    const [isSavingDictionary, setIsSavingDictionary] = useState(false);
    const [isGeneratingDictionary, setIsGeneratingDictionary] = useState(false);
    const [dictionaryError, setDictionaryError] = useState<string | null>(null);

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
            const [kbData, docsData, dictionaryData] = await Promise.all([
                api.admin.getKnowledgeBase(kbId),
                api.admin.getKnowledgeBaseDocuments(kbId),
                api.admin.getKnowledgeDictionaryEntries(kbId),
            ]);
            setKb(kbData);
            setDocs(docsData);
            setDictionaryEntries(dictionaryData.items);
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

    const parseDictionaryAliases = (value: string): string[] => value
        .split(/[，,\n]/)
        .map((item) => item.trim())
        .filter((item, index, all) => item && all.indexOf(item) === index);

    const resetDictionaryForm = () => {
        setDictionaryForm({ canonical_term: "", aliases: "", term_type: "other" });
        setEditingDictionaryEntry(null);
    };

    const handleSaveDictionaryEntry = async () => {
        const canonicalTerm = dictionaryForm.canonical_term.trim();
        if (!canonicalTerm) {
            setDictionaryError("请输入标准词。");
            return;
        }
        setIsSavingDictionary(true);
        setDictionaryError(null);
        try {
            const payload = {
                canonical_term: canonicalTerm,
                aliases: parseDictionaryAliases(dictionaryForm.aliases),
                term_type: dictionaryForm.term_type,
            };
            if (editingDictionaryEntry) {
                await api.admin.updateKnowledgeDictionaryEntry(kbId, editingDictionaryEntry.id, payload);
                toast.success("词典条目已更新。");
            } else {
                await api.admin.createKnowledgeDictionaryEntry(kbId, { ...payload, status: "draft" });
                toast.success("词典草稿已创建。");
            }
            resetDictionaryForm();
            await loadData();
        } catch (err) {
            setDictionaryError(getApiErrorMessage(err));
        } finally {
            setIsSavingDictionary(false);
        }
    };

    const handleEditDictionaryEntry = (entry: AdminKnowledgeDictionaryEntry) => {
        setEditingDictionaryEntry(entry);
        setDictionaryForm({
            canonical_term: entry.canonical_term,
            aliases: entry.aliases.join("，"),
            term_type: entry.term_type,
        });
        setDictionaryError(null);
    };

    const handleUpdateDictionaryStatus = async (entry: AdminKnowledgeDictionaryEntry, status: "active" | "archived") => {
        try {
            await api.admin.updateKnowledgeDictionaryEntry(kbId, entry.id, { status });
            toast.success(status === "active" ? "词条已发布。" : "词条已归档。");
            await loadData();
        } catch (err) {
            toast.error(getApiErrorMessage(err));
        }
    };

    const handleDeleteDictionaryEntry = async (entry: AdminKnowledgeDictionaryEntry) => {
        try {
            await api.admin.deleteKnowledgeDictionaryEntry(kbId, entry.id);
            toast.success("词典条目已删除。");
            if (editingDictionaryEntry?.id === entry.id) {
                resetDictionaryForm();
            }
            await loadData();
        } catch (err) {
            toast.error(getApiErrorMessage(err));
        }
    };

    const handleGenerateDictionaryDrafts = async () => {
        setIsGeneratingDictionary(true);
        setDictionaryError(null);
        try {
            const result = await api.admin.generateKnowledgeDictionaryEntries(kbId, 30);
            toast.success(`已生成 ${result.created} 个草稿，跳过 ${result.skipped} 个已有或低频候选。`);
            await loadData();
        } catch (err) {
            setDictionaryError(getApiErrorMessage(err));
        } finally {
            setIsGeneratingDictionary(false);
        }
    };
    const value: KnowledgeDetailContextValue = {
        kbId, kb, docs, dictionaryEntries, isLoading, error, loadData,
        uploadQueue, isUploadDragActive, setIsUploadDragActive, isUploading, uploadQueueSummary,
        handleUploadInputChange, handleUploadDrop, reprocessingDocId, handleReprocess,
        previewDoc, setPreviewDoc, previewChunks, isLoadingPreview, handlePreview,
        deleteTarget, setDeleteTarget, isDeleting, handleDelete,
        searchQuery, setSearchQuery, searchResults, isSearching, searchMessage, searchError, searchReadiness, handleSearch,
        dictionaryForm, setDictionaryForm, editingDictionaryEntry, isSavingDictionary, isGeneratingDictionary, dictionaryError,
        readyDocuments, resetDictionaryForm, handleSaveDictionaryEntry, handleEditDictionaryEntry,
        handleUpdateDictionaryStatus, handleDeleteDictionaryEntry, handleGenerateDictionaryDrafts,
        ragProfiles, savingProfile, handleAssignProfile,
    };

    return (
        <KnowledgeDetailContext.Provider value={value}>
            {children}
        </KnowledgeDetailContext.Provider>
    );
}
