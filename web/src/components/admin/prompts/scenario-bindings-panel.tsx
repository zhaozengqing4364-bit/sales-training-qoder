"use client";

import { useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PromptTemplate, PromptTemplateOptions, PromptType, ScenarioPrompt } from "@/lib/api/types";
import { PROMPT_TYPE_LABELS } from "./prompt-labels";

export function ScenarioBindingsPanel() {
    const toast = useToast();
    const [templates, setTemplates] = useState<PromptTemplate[]>([]);
    const [scenarioPrompts, setScenarioPrompts] = useState<ScenarioPrompt[]>([]);
    const [promptOptions, setPromptOptions] = useState<PromptTemplateOptions | null>(null);
    const [loading, setLoading] = useState(true);
    const [isOperating, setIsOperating] = useState(false);
    const [bindingTemplateId, setBindingTemplateId] = useState("");
    const [bindingScenarioType, setBindingScenarioType] = useState<"sales" | "presentation">("presentation");
    const [bindingPromptType, setBindingPromptType] = useState<PromptType>("interruption");
    const [bindingScenarioId, setBindingScenarioId] = useState("");
    const [deleteTarget, setDeleteTarget] = useState<ScenarioPrompt | null>(null);

    const salesAllowedPromptTypes = useMemo(
        () => new Set((promptOptions?.sales_allowed_prompt_types || []) as PromptType[]),
        [promptOptions],
    );
    const templateMap = useMemo(() => new Map(templates.map((item) => [item.id, item])), [templates]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [templatesResult, scenarioPromptsResult, optionsResult] = await Promise.all([
                api.admin.getPromptTemplates({ is_active: true }),
                api.admin.getScenarioPrompts(),
                api.admin.getPromptTemplateOptions(),
            ]);
            setTemplates(templatesResult);
            setScenarioPrompts(scenarioPromptsResult);
            setPromptOptions(optionsResult);
        } catch (err) {
            toast.error(getApiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { void loadData(); }, []);

    const handleCreate = async () => {
        if (!bindingTemplateId) { toast.error("请先选择模板"); return; }
        setIsOperating(true);
        try {
            await api.admin.createScenarioPrompt({
                scenario_type: bindingScenarioType,
                scenario_id: bindingScenarioId.trim() || undefined,
                prompt_type: bindingPromptType,
                template_id: bindingTemplateId,
                is_active: true,
            });
            setBindingScenarioId("");
            await loadData();
            toast.success("场景绑定已创建");
        } catch (err) {
            toast.error(getApiErrorMessage(err));
        } finally {
            setIsOperating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsOperating(true);
        try {
            await api.admin.deleteScenarioPrompt(deleteTarget.id);
            setDeleteTarget(null);
            await loadData();
            toast.success("场景绑定已删除");
        } catch (err) {
            toast.error(getApiErrorMessage(err));
        } finally {
            setIsOperating(false);
        }
    };

    return (
        <AdminFormShell backHref="/admin/prompts" backLabel="返回模板列表" title="场景绑定" description="将模板绑定到销售/演讲场景。">
            <ConfirmDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)} title="删除场景绑定" description="删除后该场景会回退到默认模板。" confirmText="确认删除" variant="warning" onConfirm={() => void handleDelete()} isLoading={isOperating} />
            <GlassCard className="space-y-4 p-5">
                <div className="flex items-center justify-between"><h3 className="text-lg font-bold">场景绑定</h3><Badge className="bg-slate-100 text-slate-700">{scenarioPrompts.length} 条</Badge></div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
                    <select value={bindingTemplateId} onChange={(e) => { setBindingTemplateId(e.target.value); const t = templateMap.get(e.target.value); if (t) setBindingPromptType(t.prompt_type); }} className="rounded-lg border px-3 py-2 text-sm">
                        <option value="">选择模板</option>
                        {templates.filter((t) => t.is_active).map((t) => (<option key={t.id} value={t.id}>{t.name}</option>))}
                    </select>
                    <select value={bindingScenarioType} onChange={(e) => setBindingScenarioType(e.target.value as "sales" | "presentation")} className="rounded-lg border px-3 py-2 text-sm"><option value="sales">销售场景</option><option value="presentation">演讲场景</option></select>
                    <select value={bindingPromptType} onChange={(e) => setBindingPromptType(e.target.value as PromptType)} className="rounded-lg border px-3 py-2 text-sm">
                        {Object.entries(PROMPT_TYPE_LABELS).filter(([type]) => bindingScenarioType !== "sales" || salesAllowedPromptTypes.size === 0 || salesAllowedPromptTypes.has(type as PromptType)).map(([type, label]) => (<option key={type} value={type}>{label}</option>))}
                    </select>
                    <Input value={bindingScenarioId} onChange={(e) => setBindingScenarioId(e.target.value)} placeholder="可选：scenario_id" />
                    <Button disabled={isOperating || loading} onClick={() => void handleCreate()}>新建绑定</Button>
                </div>
                {scenarioPrompts.length === 0 ? <div className="py-4 text-sm text-slate-500">暂无绑定记录</div> : scenarioPrompts.map((item) => {
                    const linked = templateMap.get(item.template_id);
                    return (
                        <div key={item.id} className="flex flex-col gap-2 rounded-lg border bg-slate-50 px-3 py-3 md:flex-row md:items-center md:justify-between">
                            <div className="text-sm"><span className="font-semibold">{linked?.name || item.template_id}</span> · {item.scenario_type === "sales" ? "销售" : "演讲"} · {PROMPT_TYPE_LABELS[item.prompt_type as PromptType] || item.prompt_type} · {item.scenario_id || "全场景"}</div>
                            <Button variant="outline" size="sm" disabled={isOperating} onClick={() => setDeleteTarget(item)}>删除绑定</Button>
                        </div>
                    );
                })}
            </GlassCard>
        </AdminFormShell>
    );
}
