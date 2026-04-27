"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    AlertTriangle,
    Database,
    ExternalLink,
    Loader2,
    Pencil,
    Plus,
    RefreshCw,
    Save,
    Star,
    Trash2,
    X,
} from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import type {
    RagProfile,
    RagProfileChunking,
    CreateRagProfileRequest,
    UpdateRagProfileRequest,
} from "@/lib/api/types";

// ── Constants ──

const STRATEGY_OPTIONS = [
    { value: "element_boundary", label: "元素边界", desc: "按文档结构自然分界（推荐）" },
    { value: "fixed_size", label: "固定大小", desc: "按字符数滑动窗口" },
    { value: "parent_child", label: "父子分块", desc: "小块检索 · 大块上下文" },
] as const;

const CROSS_ENCODER_BACKEND_OPTIONS = [
    { value: "", label: "禁用" },
    { value: "local", label: "本地模型" },
    { value: "cohere", label: "Cohere API" },
] as const;

const DEFAULT_CHUNKING: RagProfileChunking = {
    strategy: "element_boundary",
    chunk_size: 500,
    chunk_overlap: 50,
};

const DEFAULT_SEMANTIC_CACHE = {
    enabled: true,
    similarity_threshold: 0.95,
    ttl_seconds: 300,
};

const DEFAULT_CROSS_ENCODER = {
    backend: null as string | null,
    model: null as string | null,
    device: null as string | null,
    has_api_key: false,
};

// ── Component ──

export default function RagProfilesPage() {
    const router = useRouter();
    const toast = useToast();
    const [profiles, setProfiles] = useState<RagProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<RagProfile | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Edit state
    const [editingId, setEditingId] = useState<string | null>(null);
    const [showCreateForm, setShowCreateForm] = useState(false);

    // Form state
    const [formName, setFormName] = useState("");
    const [formDescription, setFormDescription] = useState("");
    const [formChunking, setFormChunking] = useState(DEFAULT_CHUNKING);
    const [formSemanticCache, setFormSemanticCache] = useState(DEFAULT_SEMANTIC_CACHE);
    const [formCrossEncoder, setFormCrossEncoder] = useState(DEFAULT_CROSS_ENCODER);

    // ── Data loading ──

    const loadProfiles = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const data = await api.admin.listRagProfiles();
            setProfiles(data ?? []);
        } catch (error) {
            const message = error instanceof Error ? error.message : "无法获取 RAG 配置列表";
            setLoadError(message);
            setProfiles([]);
            toast.error(`加载失败：${message}`);
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        void loadProfiles();
    }, [loadProfiles]);

    // ── Form helpers ──

    const resetForm = useCallback(() => {
        setFormName("");
        setFormDescription("");
        setFormChunking(DEFAULT_CHUNKING);
        setFormSemanticCache(DEFAULT_SEMANTIC_CACHE);
        setFormCrossEncoder(DEFAULT_CROSS_ENCODER);
        setEditingId(null);
        setShowCreateForm(false);
    }, []);

    const startEdit = useCallback((p: RagProfile) => {
        setEditingId(p.id);
        setShowCreateForm(false);
        setFormName(p.name);
        setFormDescription(p.description ?? "");
        setFormChunking({
            strategy: p.chunking.strategy,
            chunk_size: p.chunking.chunk_size,
            chunk_overlap: p.chunking.chunk_overlap,
        });
        setFormSemanticCache({
            enabled: p.semantic_cache.enabled,
            similarity_threshold: p.semantic_cache.similarity_threshold,
            ttl_seconds: p.semantic_cache.ttl_seconds,
        });
        setFormCrossEncoder({
            backend: p.cross_encoder.backend,
            model: p.cross_encoder.model,
            device: p.cross_encoder.device,
            has_api_key: p.cross_encoder.has_api_key,
        });
    }, []);

    // ── CRUD operations ──

    const handleSave = useCallback(async () => {
        if (!formName.trim()) {
            toast.error("名称必填");
            return;
        }
        setSaving(true);
        try {
            const payload: CreateRagProfileRequest | UpdateRagProfileRequest = {
                name: formName.trim(),
                description: formDescription.trim() || null,
                chunking: {
                    strategy: formChunking.strategy,
                    chunk_size: formChunking.chunk_size,
                    chunk_overlap: formChunking.chunk_overlap,
                },
                semantic_cache: {
                    enabled: formSemanticCache.enabled,
                    similarity_threshold: formSemanticCache.similarity_threshold,
                    ttl_seconds: formSemanticCache.ttl_seconds,
                },
                cross_encoder: {
                    backend: formCrossEncoder.backend || null,
                    model: formCrossEncoder.model || null,
                    device: formCrossEncoder.device || null,
                    has_api_key: formCrossEncoder.has_api_key,
                },
            };

            if (editingId) {
                await api.admin.updateRagProfile(editingId, payload);
                toast.success("更新成功");
            } else {
                await api.admin.createRagProfile(payload as CreateRagProfileRequest);
                toast.success("创建成功");
            }
            resetForm();
            await loadProfiles();
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : "操作失败";
            toast.error(`保存失败: ${msg}`);
        } finally {
            setSaving(false);
        }
    }, [editingId, formName, formDescription, formChunking, formSemanticCache, formCrossEncoder, loadProfiles, resetForm, toast]);

    const handleDelete = useCallback(async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await api.admin.deleteRagProfile(deleteTarget.id);
            toast.success("删除成功");
            setDeleteTarget(null);
            await loadProfiles();
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : "删除失败";
            toast.error(`删除失败: ${msg}`);
        } finally {
            setIsDeleting(false);
        }
    }, [deleteTarget, loadProfiles, toast]);

    const handleSetDefault = useCallback(async (id: string) => {
        try {
            await api.admin.setRagProfileDefault(id);
            toast.success("已设为默认");
            await loadProfiles();
        } catch {
            toast.error("操作失败");
        }
    }, [loadProfiles, toast]);

    // ── Render ──

    const isEditing = editingId !== null || showCreateForm;

    return (
        <div className="p-6 max-w-5xl mx-auto space-y-6">
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => {
                    if (!open) {
                        setDeleteTarget(null);
                    }
                }}
                title="删除 RAG 配置"
                description={deleteTarget ? `确认删除「${deleteTarget.name}」吗？` : "确认删除该配置？"}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {/* Deprecation Banner */}
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                    <p className="text-sm font-medium text-amber-800">
                        此页面已迁移
                    </p>
                    <p className="text-xs text-amber-700 mt-1">
                        RAG 配置管理已升级为「检索策略」，建议使用新版页面进行配置。此页面将在下个版本移除。
                    </p>
                    <button
                        type="button"
                        className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-amber-800 underline hover:text-amber-900"
                        onClick={() => router.push("/admin/retrieval-strategies")}
                    >
                        <ExternalLink className="h-3 w-3" />
                        前往检索策略页面
                    </button>
                </div>
            </div>

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-zinc-950">RAG 配置管理</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        统一管理知识库的分块策略、语义缓存和重排序配置
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={loadProfiles} disabled={loading}>
                        <RefreshCw className="w-4 h-4 mr-1" />
                        刷新
                    </Button>
                    {!isEditing && (
                        <Button
                            size="sm"
                            onClick={() => {
                                resetForm();
                                setShowCreateForm(true);
                            }}
                        >
                            <Plus className="w-4 h-4 mr-1" />
                            新建配置
                        </Button>
                    )}
                </div>
            </div>

            {/* Profile list */}
            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
                </div>
            ) : loadError ? (
                <GlassCard className="p-10 text-center border border-red-100 bg-red-50/70">
                    <AlertTriangle className="w-10 h-10 mx-auto text-red-400 mb-3" />
                    <p className="font-medium text-red-800">RAG 配置加载失败</p>
                    <p className="mt-2 text-sm text-red-700">
                        当前无法确认列表、权限或迁移状态：{loadError}
                    </p>
                    <div className="mt-4 flex justify-center gap-2">
                        <Button variant="outline" size="sm" onClick={loadProfiles}>
                            重试加载
                        </Button>
                        <Button size="sm" onClick={() => router.push("/admin/retrieval-strategies")}>
                            前往检索策略页面
                        </Button>
                    </div>
                </GlassCard>
            ) : profiles.length === 0 ? (
                <GlassCard className="p-10 text-center">
                    <Database className="w-10 h-10 mx-auto text-slate-300 mb-3" />
                    <p className="text-slate-500">暂无 RAG 配置</p>
                    <p className="mt-2 text-xs text-slate-400">
                        新版检索策略页面是首选管理入口；仅在确认需要维护旧 RAG 配置时创建。
                    </p>
                    <Button
                        size="sm"
                        className="mt-4"
                        onClick={() => {
                            resetForm();
                            setShowCreateForm(true);
                        }}
                    >
                        创建第一个配置
                    </Button>
                </GlassCard>
            ) : (
                <div className="space-y-3">
                    {profiles.map((p) => (
                        <GlassCard
                            key={p.id}
                            className="p-4 hover:shadow-md transition-shadow cursor-pointer"
                            onClick={() => startEdit(p)}
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-zinc-950">
                                            {p.name}
                                        </span>
                                        {p.is_system_default && (
                                            <Badge className="bg-amber-100 text-amber-800 text-xs">
                                                <Star className="w-3 h-3 mr-1" />
                                                系统默认
                                            </Badge>
                                        )}
                                    </div>
                                    {p.description && (
                                        <p className="text-xs text-slate-500 mt-1">
                                            {p.description}
                                        </p>
                                    )}
                                    <div className="flex gap-4 mt-2 text-xs text-slate-500">
                                        <span>
                                            分块:{" "}
                                            {STRATEGY_OPTIONS.find((o) => o.value === p.chunking.strategy)?.label ?? p.chunking.strategy}
                                        </span>
                                        <span>
                                            缓存: {p.semantic_cache.enabled ? "开启" : "关闭"}
                                        </span>
                                        <span>
                                            重排序: {p.cross_encoder.backend ?? "禁用"}
                                        </span>
                                        <span>关联知识库: {p.applied_kb_count}</span>
                                    </div>
                                </div>
                                <div className="flex gap-1">
                                    {!p.is_system_default && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleSetDefault(p.id);
                                            }}
                                            title="设为默认"
                                        >
                                            <Star className="w-4 h-4" />
                                        </Button>
                                    )}
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            startEdit(p);
                                        }}
                                    >
                                        <Pencil className="w-4 h-4" />
                                    </Button>
                                    {!p.is_system_default && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            aria-label={`删除配置 ${p.name}`}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setDeleteTarget(p);
                                            }}
                                        >
                                            <Trash2 className="w-4 h-4 text-red-500" />
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </GlassCard>
                    ))}
                </div>
            )}

            {/* Edit / Create Form */}
            {isEditing && (
                <GlassCard className="p-6 space-y-6">
                    <div className="flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-zinc-950">
                            {editingId ? "编辑配置" : "新建配置"}
                        </h2>
                        <Button variant="ghost" size="sm" onClick={resetForm}>
                            <X className="w-4 h-4" />
                        </Button>
                    </div>

                    {/* Basic info */}
                    <div className="space-y-3">
                        <div>
                            <label className="block text-xs text-slate-500 mb-1">名称 *</label>
                            <Input
                                value={formName}
                                onChange={(e) => setFormName(e.target.value)}
                                placeholder="如：高精度检索配置"
                            />
                        </div>
                        <div>
                            <label className="block text-xs text-slate-500 mb-1">描述</label>
                            <Input
                                value={formDescription}
                                onChange={(e) => setFormDescription(e.target.value)}
                                placeholder="配置用途说明"
                            />
                        </div>
                    </div>

                    {/* Chunking */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-800 mb-3">分块策略</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">策略</label>
                                <select
                                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white"
                                    value={formChunking.strategy}
                                    onChange={(e) =>
                                        setFormChunking((c) => ({
                                            ...c,
                                            strategy: e.target.value as typeof c.strategy,
                                        }))
                                    }
                                >
                                    {STRATEGY_OPTIONS.map((o) => (
                                        <option key={o.value} value={o.value}>
                                            {o.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">
                                    分块大小: {formChunking.chunk_size}
                                </label>
                                <input
                                    type="range"
                                    min={100}
                                    max={2000}
                                    step={50}
                                    value={formChunking.chunk_size}
                                    onChange={(e) =>
                                        setFormChunking((c) => ({
                                            ...c,
                                            chunk_size: Number(e.target.value),
                                        }))
                                    }
                                    className="w-full"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">
                                    重叠: {formChunking.chunk_overlap}
                                </label>
                                <input
                                    type="range"
                                    min={0}
                                    max={500}
                                    step={10}
                                    value={formChunking.chunk_overlap}
                                    onChange={(e) =>
                                        setFormChunking((c) => ({
                                            ...c,
                                            chunk_overlap: Number(e.target.value),
                                        }))
                                    }
                                    className="w-full"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Semantic Cache */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-800 mb-3">语义缓存</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label className="flex items-center gap-2 text-xs text-slate-500">
                                    <input
                                        type="checkbox"
                                        checked={formSemanticCache.enabled}
                                        onChange={(e) =>
                                            setFormSemanticCache((s) => ({
                                                ...s,
                                                enabled: e.target.checked,
                                            }))
                                        }
                                    />
                                    启用
                                </label>
                            </div>
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">
                                    相似度阈值: {formSemanticCache.similarity_threshold}
                                </label>
                                <input
                                    type="range"
                                    min={0.9}
                                    max={0.99}
                                    step={0.01}
                                    value={formSemanticCache.similarity_threshold}
                                    onChange={(e) =>
                                        setFormSemanticCache((s) => ({
                                            ...s,
                                            similarity_threshold: Number(e.target.value),
                                        }))
                                    }
                                    className="w-full"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">
                                    TTL (秒): {formSemanticCache.ttl_seconds}
                                </label>
                                <input
                                    type="range"
                                    min={60}
                                    max={3600}
                                    step={60}
                                    value={formSemanticCache.ttl_seconds}
                                    onChange={(e) =>
                                        setFormSemanticCache((s) => ({
                                            ...s,
                                            ttl_seconds: Number(e.target.value),
                                        }))
                                    }
                                    className="w-full"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Cross-Encoder */}
                    <div>
                        <h3 className="text-sm font-semibold text-slate-800 mb-3">
                            Cross-Encoder 重排序
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">后端</label>
                                <select
                                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white"
                                    value={formCrossEncoder.backend ?? ""}
                                    onChange={(e) =>
                                        setFormCrossEncoder((c) => ({
                                            ...c,
                                            backend: e.target.value || null,
                                        }))
                                    }
                                >
                                    {CROSS_ENCODER_BACKEND_OPTIONS.map((o) => (
                                        <option key={o.value} value={o.value}>
                                            {o.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            {formCrossEncoder.backend && (
                                <>
                                    <div>
                                        <label className="block text-xs text-slate-500 mb-1">
                                            模型名
                                        </label>
                                        <Input
                                            value={formCrossEncoder.model ?? ""}
                                            onChange={(e) =>
                                                setFormCrossEncoder((c) => ({
                                                    ...c,
                                                    model: e.target.value || null,
                                                }))
                                            }
                                            placeholder="BAAI/bge-reranker-v2-m3"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs text-slate-500 mb-1">
                                            设备
                                        </label>
                                        <Input
                                            value={formCrossEncoder.device ?? ""}
                                            onChange={(e) =>
                                                setFormCrossEncoder((c) => ({
                                                    ...c,
                                                    device: e.target.value || null,
                                                }))
                                            }
                                            placeholder="cpu / cuda"
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" onClick={resetForm}>
                            取消
                        </Button>
                        <Button onClick={handleSave} disabled={saving}>
                            {saving ? (
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                            ) : (
                                <Save className="w-4 h-4 mr-1" />
                            )}
                            {editingId ? "保存修改" : "创建"}
                        </Button>
                    </div>
                </GlassCard>
            )}
        </div>
    );
}
