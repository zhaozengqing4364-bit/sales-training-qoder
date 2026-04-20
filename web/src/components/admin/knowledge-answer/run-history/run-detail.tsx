"use client";

import { AlertCircle, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { StructuredPayloadViewer } from "../shared/structured-payload-viewer";
import type {
    AdminKnowledgeAnswerRunDetail,
    AdminKnowledgeAnswerRunStep,
} from "@/lib/api/types";

const STATUS_BADGE_MAP: Record<string, string> = {
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-700",
    blocked: "bg-amber-100 text-amber-800",
    running: "bg-blue-100 text-blue-700",
    pending: "bg-slate-200 text-slate-600",
};

const ANSWERABILITY_BADGE_MAP: Record<string, string> = {
    sufficient: "bg-green-100 text-green-800",
    partial: "bg-amber-100 text-amber-800",
    insufficient: "bg-slate-200 text-slate-600",
    blocked: "bg-red-100 text-red-700",
};

function formatTimestamp(ts: string): string {
    return new Date(ts).toLocaleString("zh-CN", { hour12: false });
}

interface RunDetailProps {
    detail: AdminKnowledgeAnswerRunDetail;
    steps: AdminKnowledgeAnswerRunStep[];
}

export function RunDetail({ detail, steps }: RunDetailProps) {
    const sortedSteps = [...steps].sort((a, b) => a.step_order - b.step_order);

    return (
        <div className="space-y-4">
            {/* Metadata strip */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <GlassCard className="p-2.5">
                    <p className="text-xs text-slate-400">运行 ID</p>
                    <p className="mt-0.5 truncate font-mono text-xs font-medium text-slate-900" title={detail.id}>
                        {detail.id}
                    </p>
                </GlassCard>
                <GlassCard className="p-2.5">
                    <p className="text-xs text-slate-400">会话 ID</p>
                    <p className="mt-0.5 truncate font-mono text-xs font-medium text-slate-900" title={detail.session_id}>
                        {detail.session_id}
                    </p>
                </GlassCard>
                <GlassCard className="p-2.5">
                    <p className="text-xs text-slate-400">执行入口</p>
                    <p className="mt-0.5 text-sm font-medium text-slate-900">{detail.entrypoint}</p>
                </GlassCard>
                <GlassCard className="p-2.5">
                    <p className="text-xs text-slate-400">配置版本</p>
                    <p className="mt-0.5 truncate font-mono text-xs font-medium text-slate-900">
                        {detail.config_version_id || "\u2014"}
                    </p>
                </GlassCard>
            </div>

            {/* Status badges */}
            <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">状态:</span>
                <Badge className={STATUS_BADGE_MAP[detail.final_status] || "bg-slate-100 text-slate-600"}>
                    {detail.final_status}
                </Badge>
                <span className="text-xs text-slate-500">可回答性:</span>
                <Badge className={ANSWERABILITY_BADGE_MAP[detail.answerability] || "bg-slate-100 text-slate-600"}>
                    {detail.answerability}
                </Badge>
                <span className="ml-auto text-xs text-slate-400">
                    {formatTimestamp(detail.created_at)}
                </span>
            </div>

            {/* Blocked reason */}
            {detail.blocked_reason && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                    <div>
                        <p className="text-sm font-medium text-amber-800">阻止原因</p>
                        <p className="mt-0.5 text-sm text-amber-700">{detail.blocked_reason}</p>
                    </div>
                </div>
            )}

            {/* Retrieval summary */}
            {detail.retrieval_summary && Object.keys(detail.retrieval_summary).length > 0 && (
                <div className="space-y-1.5">
                    <p className="text-xs font-medium text-slate-500">检索摘要</p>
                    <StructuredPayloadViewer data={detail.retrieval_summary} />
                </div>
            )}

            {/* Citations */}
            {detail.citations && detail.citations.length > 0 && (
                <div className="space-y-2">
                    <p className="text-xs font-medium text-slate-500">引用来源</p>
                    <div className="space-y-2">
                        {detail.citations.map((citation, i) => (
                            <GlassCard key={i} className="p-3">
                                <div className="flex items-start gap-2">
                                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                                    <div className="min-w-0 flex-1 space-y-1">
                                        <p className="text-sm font-medium text-slate-900">
                                            {(citation.document_title as string) || `来源 ${i + 1}`}
                                        </p>
                                        {(citation.snippet as string) && (
                                            <p className="text-xs leading-relaxed text-slate-600">
                                                {citation.snippet as string}
                                            </p>
                                        )}
                                    </div>
                                </div>
                                {/* Show other citation fields */}
                                <StructuredPayloadViewer
                                    data={Object.fromEntries(
                                        Object.entries(citation).filter(
                                            ([k]) => k !== "document_title" && k !== "snippet",
                                        ),
                                    )}
                                />
                            </GlassCard>
                        ))}
                    </div>
                </div>
            )}

            {/* Steps */}
            {sortedSteps.length > 0 && (
                <div className="space-y-3">
                    <p className="text-xs font-medium text-slate-500">
                        执行步骤 ({sortedSteps.length})
                    </p>
                    {sortedSteps.map((step) => (
                        <details
                            key={step.id}
                            className="group rounded-lg border border-slate-200 bg-white"
                        >
                            <summary className="flex cursor-pointer items-center justify-between px-3 py-2.5 text-sm select-none">
                                <div className="flex items-center gap-2">
                                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-xs font-medium text-slate-600">
                                        {step.step_order}
                                    </span>
                                    <span className="font-medium text-slate-900">{step.step_name}</span>
                                    <Badge
                                        className={
                                            STATUS_BADGE_MAP[step.status] || "bg-slate-100 text-slate-600"
                                        }
                                    >
                                        {step.status}
                                    </Badge>
                                    {step.duration_ms != null && (
                                        <span className="text-xs text-slate-400">
                                            {step.duration_ms}ms
                                        </span>
                                    )}
                                </div>
                            </summary>
                            <div className="space-y-3 border-t border-slate-100 px-3 py-3">
                                {/* Input payload */}
                                <div className="space-y-1">
                                    <p className="text-xs font-medium text-slate-500">输入</p>
                                    <StructuredPayloadViewer data={step.input_payload} />
                                </div>
                                {/* Output payload */}
                                <div className="space-y-1">
                                    <p className="text-xs font-medium text-slate-500">输出</p>
                                    <StructuredPayloadViewer data={step.output_payload} />
                                </div>
                            </div>
                        </details>
                    ))}
                </div>
            )}
        </div>
    );
}
