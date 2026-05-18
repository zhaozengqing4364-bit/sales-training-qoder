"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, RefreshCcw, Trash2 } from "lucide-react";

import { api } from "@/lib/api/client";
import type { LearningContent, LearningContentCreateRequest } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { debug } from "@/lib/debug";

const STATUS_LABELS: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
};

const STATUS_COLORS: Record<string, string> = {
    draft: "bg-slate-100 text-slate-700",
    published: "bg-emerald-100 text-emerald-700",
    archived: "bg-amber-100 text-amber-700",
};

const EMPTY_FORM: LearningContentCreateRequest = {
    title: "",
    summary: "",
    owner: "",
    source: "manual",
    safety_flagged: false,
};

export default function AdminLearningContentsPage() {
    const [items, setItems] = useState<LearningContent[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [form, setForm] = useState<LearningContentCreateRequest>(EMPTY_FORM);

    const loadData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.learningContents.list();
            setItems(result.items || []);
        } catch (err) {
            debug.error("Failed to load learning contents:", err);
            setError(err instanceof Error ? err.message : "加载失败");
            setItems([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadData();
    }, []);

    const handleCreate = async () => {
        const title = form.title.trim();
        if (!title) {
            setActionError("标题不能为空。");
            return;
        }
        setNotice(null);
        setActionError(null);
        try {
            const created = await api.learningContents.create({
                ...form,
                title,
                summary: form.summary?.trim() || null,
                owner: form.owner?.trim() || null,
                source: form.source?.trim() || "manual",
            });
            setItems((current) => [created, ...current]);
            setForm(EMPTY_FORM);
            setNotice(`创建完成：${created.title}`);
        } catch (err) {
            debug.error("Failed to create learning content:", err);
            setActionError(err instanceof Error ? err.message : "创建失败");
        }
    };

    const handleDelete = async (item: LearningContent) => {
        setNotice(null);
        setActionError(null);
        try {
            await api.learningContents.delete(item.learning_content_id);
            setItems((current) => current.filter((currentItem) => currentItem.learning_content_id !== item.learning_content_id));
            setNotice(`删除完成：${item.title}`);
        } catch (err) {
            debug.error("Failed to delete learning content:", err);
            setActionError(err instanceof Error ? err.message : "删除失败");
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">学习内容管理</h1>
                    <p className="mt-1 text-slate-500">管理课程学习内容</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" className="rounded-full" onClick={() => void loadData()} disabled={isLoading}>
                        <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                        刷新
                    </Button>
                </div>
            </div>

            {notice ? (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    {notice}
                </div>
            ) : null}

            {actionError ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    {actionError}
                </div>
            ) : null}

            <GlassCard className="space-y-4 p-6">
                <h2 className="text-xl font-black text-slate-900">新建学习内容</h2>
                <div className="grid gap-4 md:grid-cols-4">
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>标题</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.title}
                            onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>摘要</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.summary ?? ""}
                            onChange={(event) => setForm((current) => ({ ...current, summary: event.target.value }))}
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>负责人</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.owner ?? ""}
                            onChange={(event) => setForm((current) => ({ ...current, owner: event.target.value }))}
                        />
                    </label>
                    <label className="space-y-1 text-sm font-medium text-slate-700">
                        <span>来源</span>
                        <input
                            className="w-full rounded-xl border border-slate-200 px-3 py-2"
                            value={form.source ?? ""}
                            onChange={(event) => setForm((current) => ({ ...current, source: event.target.value }))}
                        />
                    </label>
                </div>
                <Button onClick={() => void handleCreate()} className="rounded-full">
                    创建内容
                </Button>
            </GlassCard>

            {error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-500">
                        <BookOpen className="h-8 w-8" />
                    </div>
                    <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                    <p className="mb-4 text-sm text-slate-500">{error}</p>
                    <Button onClick={() => void loadData()} className="rounded-full">
                        <RefreshCcw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                </GlassCard>
            ) : null}

            {isLoading && !error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-slate-500">加载中...</p>
                </GlassCard>
            ) : null}

            {!isLoading && !error ? (
                <GlassCard className="overflow-hidden">
                    <div className="overflow-x-auto">
                        {items.length === 0 ? (
                            <div className="py-12 text-center text-slate-500">暂无学习内容数据</div>
                        ) : (
                            <table className="w-full text-left text-sm">
                                <thead className="border-b border-slate-100 bg-slate-50/50 text-xs font-bold uppercase tracking-wider text-slate-400">
                                    <tr>
                                        <th className="px-6 py-4">标题</th>
                                        <th className="px-6 py-4">摘要</th>
                                        <th className="px-6 py-4">负责人</th>
                                        <th className="px-6 py-4">来源</th>
                                        <th className="px-6 py-4">状态</th>
                                        <th className="px-6 py-4">版本</th>
                                        <th className="px-6 py-4">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {items.map((item) => (
                                        <tr key={item.learning_content_id} className="transition-colors hover:bg-slate-50/50">
                                            <td className="px-6 py-4">
                                                <Link
                                                    href={`/admin/learning-contents/${item.learning_content_id}`}
                                                    className="flex items-center gap-3 hover:opacity-80 transition-opacity"
                                                >
                                                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                                                        <BookOpen className="h-5 w-5" />
                                                    </div>
                                                    <div className="font-bold text-slate-900">{item.title}</div>
                                                </Link>
                                            </td>
                                            <td className="max-w-xs truncate px-6 py-4 text-slate-500">{item.summary || "-"}</td>
                                            <td className="px-6 py-4 font-medium text-slate-700">{item.owner || "-"}</td>
                                            <td className="px-6 py-4 font-medium text-slate-700">{item.source || "-"}</td>
                                            <td className="px-6 py-4">
                                                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[item.status] || "bg-slate-100 text-slate-700"}`}>
                                                    {STATUS_LABELS[item.status] || item.status}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 font-medium text-slate-700">v{item.version}</td>
                                            <td className="px-6 py-4">
                                                <Button
                                                    variant="outline"
                                                    className="rounded-full text-red-600"
                                                    onClick={() => void handleDelete(item)}
                                                >
                                                    <Trash2 className="mr-2 h-4 w-4" />
                                                    删除
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </GlassCard>
            ) : null}
        </div>
    );
}
