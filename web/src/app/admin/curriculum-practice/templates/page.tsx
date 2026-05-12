"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PracticeTemplateRecord } from "@/lib/api/types";
import { debug } from "@/lib/debug";

function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

export default function AdminPracticeTemplatesPage() {
    const [items, setItems] = useState<PracticeTemplateRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [busyTemplateId, setBusyTemplateId] = useState<string | null>(null);

    const loadTemplates = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.admin.listPracticeTemplates();
            setItems(response.items);
        } catch (err) {
            setError(`课程训练模板加载失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to load templates", { error: err });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(loadTemplates);
    }, [loadTemplates]);

    const handlePublish = async (template: PracticeTemplateRecord) => {
        setNotice(null);
        setActionError(null);
        setBusyTemplateId(template.template_id);
        try {
            const published = await api.admin.publishPracticeTemplate(template.template_id);
            setItems((current) => current.map((item) => (item.template_id === published.template_id ? published : item)));
            setNotice(`发布完成：${published.name} v${published.version}`);
        } catch (err) {
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to publish template", { templateId: template.template_id, error: err });
        } finally {
            setBusyTemplateId(null);
        }
    };

    if (loading) {
        return <div className="rounded-2xl border border-slate-100 bg-white/80 p-8 text-slate-600">正在加载课程训练模板...</div>;
    }

    if (error) {
        return (
            <GlassCard className="space-y-4 border border-amber-200 bg-amber-50/80 p-8">
                <h1 className="text-2xl font-black text-slate-900">课程训练模板</h1>
                <p className="text-sm text-amber-800">{error}</p>
                <Button onClick={loadTemplates}>重试加载</Button>
            </GlassCard>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">课程训练模板</h1>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        管理 PRD #46 最小 PracticeTemplate 骨架、发布门禁和运行时引用。当前页面只覆盖模板列表与发布入口。
                    </p>
                </div>
                <Button variant="outline" onClick={loadTemplates}>刷新模板</Button>
            </header>

            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{actionError}</div>}

            <GlassCard className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-black text-slate-900">模板列表</h2>
                    <Badge variant="gray">{items.length} templates</Badge>
                </div>
                <div className="grid gap-3">
                    {items.map((item) => (
                        <div key={item.template_id} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{item.name}</h3>
                                        <Badge variant={statusVariant(item.status)}>{item.status} · v{item.version}</Badge>
                                    </div>
                                    <p className="mt-1 text-sm text-slate-600">{item.mode} · {item.scenario_type}</p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        agent: {item.agent_id} · persona: {item.persona_id} · runtime: {item.runtime_profile_id}
                                    </p>
                                    {item.description ? <p className="mt-2 text-sm text-slate-600">{item.description}</p> : null}
                                </div>
                                <Button
                                    onClick={() => { void handlePublish(item); }}
                                    disabled={item.status === "published" || busyTemplateId !== null}
                                >
                                    {busyTemplateId === item.template_id ? "发布中..." : "发布模板"}
                                </Button>
                            </div>
                        </div>
                    ))}
                    {items.length === 0 && <p className="text-sm text-slate-500">暂无课程训练模板。</p>}
                </div>
            </GlassCard>
        </div>
    );
}
