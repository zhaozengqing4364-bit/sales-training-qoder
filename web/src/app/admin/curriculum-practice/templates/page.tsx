"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { TemplateList } from "@/components/admin/curriculum-practice/template-list";
import { TemplateRuntimeDossierPreview } from "@/components/admin/curriculum-practice/template-runtime-dossier-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage, getPracticeTemplateErrorDetails } from "@/lib/api/client";
import type { PracticeTemplateGateResult, PracticeTemplateRecord, PracticeTemplateRuntimeDossierPreview } from "@/lib/api/types";
import { debug } from "@/lib/debug";

export default function AdminPracticeTemplatesPage() {
    const router = useRouter();
    const [items, setItems] = useState<PracticeTemplateRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [gateResults, setGateResults] = useState<PracticeTemplateGateResult[]>([]);
    const [notice, setNotice] = useState<string | null>(null);
    const [busyTemplateId, setBusyTemplateId] = useState<string | null>(null);
    const [previewLoadingTemplateId, setPreviewLoadingTemplateId] = useState<string | null>(null);
    const [runtimeDossierPreview, setRuntimeDossierPreview] = useState<PracticeTemplateRuntimeDossierPreview | null>(null);
    const [runtimeDossierError, setRuntimeDossierError] = useState<string | null>(null);
    const [confirmTarget, setConfirmTarget] = useState<{ type: "publish" | "archive"; template: PracticeTemplateRecord } | null>(null);

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
            setGateResults(getPracticeTemplateErrorDetails(err)?.gate_results ?? []);
            setActionError(`发布失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyTemplateId(null);
        }
    };

    const handlePreviewRuntimeDossier = async (template: PracticeTemplateRecord) => {
        setNotice(null);
        setActionError(null);
        setRuntimeDossierError(null);
        setPreviewLoadingTemplateId(template.template_id);
        try {
            const preview = await api.admin.getPracticeTemplateRuntimeDossierPreview(template.template_id);
            setRuntimeDossierPreview(preview);
        } catch (err) {
            setRuntimeDossierPreview(null);
            setRuntimeDossierError(`角色档案预览失败：${getApiErrorMessage(err)}`);
            debug.warn("[AdminPracticeTemplatesPage] failed to preview runtime dossier", { error: err, templateId: template.template_id });
        } finally {
            setPreviewLoadingTemplateId(null);
        }
    };

    const handleArchive = async (template: PracticeTemplateRecord) => {
        setNotice(null);
        setActionError(null);
        setGateResults([]);
        setBusyTemplateId(template.template_id);
        try {
            const archived = await api.admin.archivePracticeTemplate(template.template_id);
            setItems((current) => current.map((item) => (item.template_id === archived.template_id ? archived : item)));
            setNotice(`归档完成：${archived.name}`);
        } catch (err) {
            setActionError(`归档失败：${getApiErrorMessage(err)}`);
        } finally {
            setBusyTemplateId(null);
        }
    };

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
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="课程训练模板"
                    description="管理课程训练模板、发布检查和角色配置。列表页展示模板状态与发布操作。"
                    primaryAction={(
                        <Button className="rounded-full" onClick={() => router.push("/admin/curriculum-practice/templates/new")}>
                            <Plus className="mr-2 h-4 w-4" />
                            新建模板
                        </Button>
                    )}
                    secondaryActions={(
                        <Button variant="outline" onClick={loadTemplates} disabled={loading}>刷新模板</Button>
                    )}
                />
            )}
        >
            <ConfirmDialog
                open={!!confirmTarget}
                onOpenChange={(open) => { if (!open) setConfirmTarget(null); }}
                title={confirmTarget?.type === "archive" ? "确认归档模板" : "确认发布模板"}
                description={confirmTarget
                    ? confirmTarget.type === "archive"
                        ? `将「${confirmTarget.template.name}」归档，归档后不能继续作为可编辑草稿使用。`
                        : `将「${confirmTarget.template.name}」发布为可用训练模板，发布门禁会再次校验引用与阶段配置。`
                    : "确认执行该模板操作。"}
                confirmText={confirmTarget?.type === "archive" ? "确认归档" : "确认发布"}
                variant={confirmTarget?.type === "archive" ? "warning" : "danger"}
                onConfirm={() => {
                    const target = confirmTarget;
                    setConfirmTarget(null);
                    if (!target) return;
                    if (target.type === "archive") void handleArchive(target.template);
                    else void handlePublish(target.template);
                }}
                isLoading={busyTemplateId !== null}
            />

            {notice && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
            {actionError && (
                <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <p>{actionError}</p>
                    {gateResults.length > 0 && (
                        <div className="space-y-2">
                            {gateResults.some((result) => result.gate_name.startsWith("curriculum_plan")) && (
                                <Badge variant="red">Stage validation errors</Badge>
                            )}
                            <ul className="list-disc space-y-1 pl-5">
                                {gateResults.map((result) => (
                                    <li key={`${result.gate_name}-${result.reason_code}-${result.message}`}>
                                        <span className="font-semibold">{result.reason_code}</span>：{result.message}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            {runtimeDossierError && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                    {runtimeDossierError}
                </div>
            )}

            {runtimeDossierPreview && (
                <TemplateRuntimeDossierPreview
                    preview={runtimeDossierPreview}
                    onClose={() => setRuntimeDossierPreview(null)}
                />
            )}

            {loading ? (
                <div role="status" aria-live="polite" className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-500">
                    正在加载课程训练模板…
                </div>
            ) : (
                <TemplateList
                    items={items}
                    busyTemplateId={busyTemplateId}
                    previewLoadingTemplateId={previewLoadingTemplateId}
                    onEdit={(template) => router.push(`/admin/curriculum-practice/templates/${template.template_id}/edit`)}
                    onPreview={(template) => { void handlePreviewRuntimeDossier(template); }}
                    onPublish={(template) => setConfirmTarget({ type: "publish", template })}
                    onArchive={(template) => setConfirmTarget({ type: "archive", template })}
                />
            )}
        </AdminIndexShell>
    );
}
