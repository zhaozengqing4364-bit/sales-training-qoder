"use client";

import { AlertTriangle, CheckCircle2, FileSearch, ShieldCheck, X, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type {
    PracticeTemplateRuntimeDossierPreview,
    RuntimeDossierStatus,
} from "@/lib/api/types";

interface TemplateRuntimeDossierPreviewProps {
    preview: PracticeTemplateRuntimeDossierPreview;
    onClose: () => void;
}

const summaryLabels: Array<[string, string]> = [
    ["persona_name", "Persona"],
    ["case_customer_role", "CaseItem"],
    ["role_name", "RoleProfile"],
    ["ruleset_version", "评分规则"],
    ["contract_version", "合同版本"],
    ["network_access_mode", "联网策略"],
    ["enable_internal_retrieval", "内部检索"],
    ["requires_kb_grounding", "KB grounding"],
];

function statusVariant(status: RuntimeDossierStatus): "green" | "orange" | "red" | "gray" {
    if (status === "passed") return "green";
    if (status === "warning") return "orange";
    if (status === "failed") return "red";
    return "gray";
}

function statusLabel(status: RuntimeDossierStatus): string {
    if (status === "passed") return "通过";
    if (status === "warning") return "需复核";
    if (status === "failed") return "未通过";
    return String(status);
}

function StatusIcon({ status }: { status: RuntimeDossierStatus }) {
    if (status === "passed") return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
    if (status === "warning") return <AlertTriangle className="h-4 w-4 text-orange-600" />;
    if (status === "failed") return <XCircle className="h-4 w-4 text-red-600" />;
    return <ShieldCheck className="h-4 w-4 text-slate-500" />;
}

function formatValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "未配置";
    if (typeof value === "boolean") return value ? "是" : "否";
    if (typeof value === "string" || typeof value === "number") return String(value);
    if (Array.isArray(value)) return value.map(formatValue).join("、") || "未配置";
    try {
        return JSON.stringify(value);
    } catch {
        return String(value);
    }
}

function sectionValue(
    preview: PracticeTemplateRuntimeDossierPreview,
    section: string,
    key: string,
): string {
    return formatValue(preview.sections[section]?.[key]);
}

export function TemplateRuntimeDossierPreview({ preview, onClose }: TemplateRuntimeDossierPreviewProps) {
    const probeFailures = preview.probes.filter((probe) => probe.status === "failed").length;
    const checkFailures = preview.consistency.checks.filter((check) => check.status === "failed").length;

    return (
        <GlassCard className="space-y-5 border border-slate-200 bg-white/85 p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <FileSearch className="h-5 w-5 text-slate-700" />
                        <h2 className="text-xl font-black text-slate-900">CIO runtime dossier 预览</h2>
                        <Badge variant={statusVariant(preview.consistency.status)}>
                            {statusLabel(preview.consistency.status)}
                        </Badge>
                    </div>
                    <p className="text-sm text-slate-600">{preview.name}</p>
                    <p className="text-xs text-slate-500">generated: {preview.generated_at}</p>
                </div>
                <Button variant="outline" onClick={onClose} aria-label="关闭 runtime dossier 预览">
                    <X className="mr-2 h-4 w-4" />
                    关闭
                </Button>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase text-slate-500">一致性失败</p>
                    <p className="mt-2 text-2xl font-black text-slate-900">{checkFailures}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase text-slate-500">probe 失败</p>
                    <p className="mt-2 text-2xl font-black text-slate-900">{probeFailures}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 md:col-span-2">
                    <p className="text-xs font-semibold uppercase text-slate-500">合同版本</p>
                    <p className="mt-2 break-words text-sm font-semibold text-slate-800">
                        {formatValue(preview.summary.contract_version)}
                    </p>
                </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
                {summaryLabels.map(([key, label]) => (
                    <div key={key} className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                        <p className="text-xs text-slate-500">{label}</p>
                        <p className="mt-1 break-words text-sm font-semibold text-slate-800">
                            {formatValue(preview.summary[key])}
                        </p>
                    </div>
                ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
                <section className="space-y-3">
                    <h3 className="text-sm font-black text-slate-900">资产一致性</h3>
                    <div className="space-y-2">
                        {preview.consistency.checks.map((check) => (
                            <div key={check.key} className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                                <div className="flex items-center gap-2">
                                    <StatusIcon status={check.status} />
                                    <Badge variant={statusVariant(check.status)}>{statusLabel(check.status)}</Badge>
                                    <span className="text-xs font-semibold text-slate-500">{check.key}</span>
                                </div>
                                <p className="mt-2 text-sm text-slate-700">{check.message}</p>
                            </div>
                        ))}
                    </div>
                </section>

                <section className="space-y-3">
                    <h3 className="text-sm font-black text-slate-900">固定 probe 自动测试</h3>
                    <div className="space-y-2">
                        {preview.probes.map((probe) => (
                            <div key={probe.key} className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                                <div className="flex flex-wrap items-center gap-2">
                                    <StatusIcon status={probe.status} />
                                    <Badge variant={statusVariant(probe.status)}>{statusLabel(probe.status)}</Badge>
                                    <span className="text-xs font-semibold text-slate-500">{probe.key}</span>
                                </div>
                                <p className="mt-2 text-sm font-semibold text-slate-800">{probe.expected_behavior}</p>
                                <p className="mt-1 text-xs text-slate-500">{probe.prompt}</p>
                                {probe.matched_evidence.length > 0 && (
                                    <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">
                                        {probe.matched_evidence.map((evidence) => (
                                            <li key={evidence}>{evidence}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        ))}
                    </div>
                </section>
            </div>

            <section className="space-y-3">
                <h3 className="text-sm font-black text-slate-900">最终 dossier 摘要</h3>
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                        <p className="text-xs font-semibold text-slate-500">Persona prompt</p>
                        <p className="mt-2 text-sm text-slate-700">{sectionValue(preview, "persona", "system_prompt_excerpt")}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                        <p className="text-xs font-semibold text-slate-500">CaseItem 公司档案</p>
                        <p className="mt-2 text-sm text-slate-700">{sectionValue(preview, "case_item", "company_profile_excerpt")}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                        <p className="text-xs font-semibold text-slate-500">RoleProfile 行为规则</p>
                        <p className="mt-2 text-sm text-slate-700">{sectionValue(preview, "role_profile", "behavior_rules")}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-100 bg-white/70 p-3">
                        <p className="text-xs font-semibold text-slate-500">ScoringRuleset 隐藏信息覆盖</p>
                        <p className="mt-2 text-sm text-slate-700">
                            {sectionValue(preview, "scoring_ruleset", "hidden_information_coverage_keys")}
                        </p>
                    </div>
                </div>
            </section>
        </GlassCard>
    );
}
