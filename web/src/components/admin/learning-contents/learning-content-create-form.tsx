"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api/client";
import type { LearningContentCreateRequest } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { debug } from "@/lib/debug";

const EMPTY_FORM: LearningContentCreateRequest = {
    title: "",
    summary: "",
    owner: "",
    source: "manual",
    safety_flagged: false,
};

export function LearningContentCreateForm() {
    const router = useRouter();
    const [form, setForm] = useState<LearningContentCreateRequest>(EMPTY_FORM);
    const [error, setError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    const handleCreate = async () => {
        const title = form.title.trim();
        if (!title) {
            setError("标题不能为空。");
            return;
        }
        setError(null);
        setSubmitting(true);
        try {
            const created = await api.learningContents.create({
                ...form,
                title,
                summary: form.summary?.trim() || null,
                owner: form.owner?.trim() || null,
                source: form.source?.trim() || "manual",
            });
            router.push(`/admin/learning-contents/${created.learning_content_id}`);
        } catch (err) {
            debug.error("Failed to create learning content:", err);
            setError(err instanceof Error ? err.message : "创建失败");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <GlassCard className="space-y-4 p-6">
            {error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>
            ) : null}
            <div className="grid gap-4 md:grid-cols-2">
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
                    <select
                        className="w-full rounded-xl border border-slate-200 px-3 py-2"
                        value={form.source ?? ""}
                        onChange={(event) => setForm((current) => ({ ...current, source: event.target.value }))}
                    >
                        <option value="manual">手动录入</option>
                        <option value="imported">批量导入</option>
                        <option value="generated">系统生成</option>
                    </select>
                </label>
            </div>
            <Button onClick={() => void handleCreate()} className="rounded-full" disabled={submitting}>
                {submitting ? "创建中..." : "创建内容"}
            </Button>
        </GlassCard>
    );
}
