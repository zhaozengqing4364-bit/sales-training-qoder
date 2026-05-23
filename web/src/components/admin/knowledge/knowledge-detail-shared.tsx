"use client";
import { debug } from "@/lib/debug";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
    AlertCircle,
    ArrowLeft,
    BookOpen,
    CheckCircle,
    Clock,
    Database,
    Eye,
    FileText,
    Loader2,
    Plus,
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
    AdminKnowledgeDictionaryEntry,
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

export const categoryLabels: Record<string, string> = {
    product: "产品",
    competitor: "竞品",
    faq: "FAQ",
    policy: "政策",
};

export const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
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

export const dictionaryStatusLabels: Record<string, string> = {
    draft: "草稿",
    active: "已发布",
    archived: "已归档",
};

export const dictionaryStatusColors: Record<string, string> = {
    draft: "bg-amber-50 text-amber-700 border-amber-100",
    active: "bg-green-50 text-green-700 border-green-100",
    archived: "bg-slate-50 text-slate-500 border-slate-100",
};

export const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const ALLOWED_UPLOAD_EXTENSIONS = ["pdf", "docx", "txt", "md", "xlsx", "xls"] as const;
export const MAX_UPLOAD_FILE_SIZE_BYTES = 50 * 1024 * 1024;
export const BATCH_UPLOAD_CONCURRENCY = 3;

export type UploadQueueStatus = "queued" | "uploading" | "success" | "failed";

export interface UploadQueueItem {
    id: string;
    name: string;
    size: number;
    status: UploadQueueStatus;
    progress: number;
    message: string;
}

export const uploadStatusConfig: Record<UploadQueueStatus, { label: string; color: string; progressColor: string }> = {
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

export const formatDocumentError = (message?: string): string => {
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

export const validateUploadFile = (file: File): string | null => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !ALLOWED_UPLOAD_EXTENSIONS.includes(ext as typeof ALLOWED_UPLOAD_EXTENSIONS[number])) {
        return "不支持的文件类型，请上传 PDF、DOCX、TXT、MD、XLSX 或 XLS 文件";
    }

    if (file.size > MAX_UPLOAD_FILE_SIZE_BYTES) {
        return "文件大小不能超过 50MB";
    }

    return null;
};

export type PreviewChunk = { index: number; content: string };

export const normalizePreviewChunks = (chunks: unknown): PreviewChunk[] => {
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


