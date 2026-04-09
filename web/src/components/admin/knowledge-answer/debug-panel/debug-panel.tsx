"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { GlassCard } from "@/components/ui/glass-card";
import { ChevronDown, ChevronUp, Loader2, Bug, AlertCircle } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { useToast } from "@/components/ui/toast";
import { StructuredPayloadViewer } from "../shared/structured-payload-viewer";
import { NumberField } from "../shared/number-field";
import { DebugKbPicker } from "./debug-kb-picker";
import type { AdminKnowledgeDebugTriggerResponse } from "@/lib/api/types";

const ANSWERABILITY_BADGE_MAP: Record<string, { label: string; className: string }> = {
    sufficient: { label: "充分", className: "bg-green-100 text-green-800" },
    partial: { label: "部分", className: "bg-amber-100 text-amber-800" },
    insufficient: { label: "不足", className: "bg-slate-200 text-slate-600" },
    blocked: { label: "已阻止", className: "bg-red-100 text-red-700" },
};

function getAnswerabilityBadge(answerability: string | undefined) {
    if (!answerability) return null;
    const config = ANSWERABILITY_BADGE_MAP[answerability] ?? {
        label: answerability,
        className: "bg-slate-100 text-slate-600",
    };
    return (
        <Badge className={config.className}>
            {config.label}
        </Badge>
    );
}

export function DebugPanel() {
    const toast = useToast();

    const [expanded, setExpanded] = useState(false);
    const [runtimeExpanded, setRuntimeExpanded] = useState(false);
    const [jsonExpanded, setJsonExpanded] = useState(false);

    const [query, setQuery] = useState("");
    const [selectedKBIds, setSelectedKBIds] = useState<string[]>([]);
    const [topK, setTopK] = useState(5);
    const [similarityThreshold, setSimilarityThreshold] = useState(0.58);
    const [enableHybrid, setEnableHybrid] = useState(true);
    const [enableRerank, setEnableRerank] = useState(true);

    const [executing, setExecuting] = useState(false);
    const [debugResult, setDebugResult] = useState<AdminKnowledgeDebugTriggerResponse | null>(null);

    async function handleExecute() {
        if (!query.trim()) {
            toast.error("请输入测试查询");
            return;
        }
        if (selectedKBIds.length === 0) {
            toast.error("请至少选择一个知识库");
            return;
        }

        setExecuting(true);
        setDebugResult(null);
        try {
            const runtimeOptions: Record<string, unknown> = {};
            if (topK !== 5) runtimeOptions.top_k = topK;
            if (similarityThreshold !== 0.58) runtimeOptions.similarity_threshold = similarityThreshold;
            if (!enableHybrid) runtimeOptions.enable_hybrid = false;
            if (!enableRerank) runtimeOptions.enable_rerank = false;

            const result = await api.admin.debugTriggerKnowledgeAnswer({
                query: query.trim(),
                knowledge_base_ids: selectedKBIds,
                runtime_options: Object.keys(runtimeOptions).length > 0 ? runtimeOptions : undefined,
            });
            setDebugResult(result);
        } catch (err) {
            toast.error("调试执行失败: " + getApiErrorMessage(err));
        } finally {
            setExecuting(false);
        }
    }

    const answerability = debugResult?._answerability as Record<string, unknown> | undefined;
    const rawFinalText: unknown = answerability?.final_text;
    const finalText: string | undefined = typeof rawFinalText === "string" ? rawFinalText : undefined;
    const rawCitations: unknown = answerability?.citations;
    const citations: Array<Record<string, unknown>> | undefined = Array.isArray(rawCitations)
        ? (rawCitations as Array<Record<string, unknown>>)
        : undefined;
    const rawAnswerabilityValue: unknown = answerability?.answerability;
    const answerabilityValue: string | undefined = typeof rawAnswerabilityValue === "string" ? rawAnswerabilityValue : undefined;

    return (
        <div className="space-y-3">
            <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left transition-colors hover:bg-slate-50"
            >
                <div className="flex items-center gap-2">
                    <Bug className="h-4 w-4 text-indigo-600" />
                    <span className="font-medium text-slate-900">调试面板</span>
                </div>
                {expanded ? (
                    <ChevronUp className="h-4 w-4 text-slate-500" />
                ) : (
                    <ChevronDown className="h-4 w-4 text-slate-500" />
                )}
            </button>

            {expanded && (
                <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
                    <div className="space-y-1.5">
                        <label className="block text-sm font-medium text-slate-700">
                            测试查询
                        </label>
                        <Input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="输入要测试的查询文本..."
                            className="h-10"
                        />
                    </div>

                    <DebugKbPicker
                        selectedIds={selectedKBIds}
                        onChange={setSelectedKBIds}
                    />

                    <div>
                        <button
                            type="button"
                            onClick={() => setRuntimeExpanded((v) => !v)}
                            className="flex items-center gap-1.5 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
                        >
                            {runtimeExpanded ? (
                                <ChevronUp className="h-3.5 w-3.5" />
                            ) : (
                                <ChevronDown className="h-3.5 w-3.5" />
                            )}
                            运行时参数覆盖
                        </button>

                        {runtimeExpanded && (
                            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                                <NumberField
                                    label="top_k"
                                    description="检索返回最大结果数"
                                    value={topK}
                                    onChange={setTopK}
                                    min={1}
                                    max={50}
                                    step={1}
                                />
                                <NumberField
                                    label="similarity_threshold"
                                    description="语义相似度最低阈值"
                                    value={similarityThreshold}
                                    onChange={setSimilarityThreshold}
                                    min={0}
                                    max={1}
                                    step={0.01}
                                />
                                <div className="space-y-1.5">
                                    <label className="block text-sm font-medium text-slate-700">
                                        enable_hybrid
                                    </label>
                                    <p className="text-xs text-slate-500">启用混合检索模式</p>
                                    <Switch
                                        checked={enableHybrid}
                                        onCheckedChange={setEnableHybrid}
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="block text-sm font-medium text-slate-700">
                                        enable_rerank
                                    </label>
                                    <p className="text-xs text-slate-500">启用重排序</p>
                                    <Switch
                                        checked={enableRerank}
                                        onCheckedChange={setEnableRerank}
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    <Button
                        onClick={handleExecute}
                        disabled={executing || !query.trim() || selectedKBIds.length === 0}
                        className="rounded-full"
                    >
                        {executing ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                执行中...
                            </>
                        ) : (
                            <>
                                <Bug className="mr-2 h-4 w-4" />
                                执行调试
                            </>
                        )}
                    </Button>

                    {debugResult && (
                        <div className="space-y-4 border-t border-slate-100 pt-4">
                            <h4 className="text-sm font-semibold text-slate-900">调试结果</h4>

                            <div className="flex items-center gap-3">
                                <span className="text-sm text-slate-500">可回答性:</span>
                                {getAnswerabilityBadge(answerabilityValue)}
                            </div>

                            {finalText !== undefined && finalText !== "" ? (
                                <GlassCard className="p-3">
                                    <p className="mb-1 text-xs font-medium text-slate-400">最终回答</p>
                                    <p className="text-sm leading-relaxed text-slate-800">{finalText}</p>
                                </GlassCard>
                            ) : null}

                            {answerability?.blocked_reason ? (
                                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                                    <div>
                                        <p className="text-sm font-medium text-amber-800">阻止原因</p>
                                        <p className="mt-0.5 text-sm text-amber-700">
                                            {String(answerability.blocked_reason)}
                                        </p>
                                    </div>
                                </div>
                            ) : null}

                            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                <GlassCard className="p-2.5 text-center">
                                    <p className="text-xs text-slate-400">检索模式</p>
                                    <p className="mt-0.5 text-sm font-semibold text-slate-900">
                                        {debugResult.retrieval_mode || "\u2014"}
                                    </p>
                                </GlassCard>
                                <GlassCard className="p-2.5 text-center">
                                    <p className="text-xs text-slate-400">结果数量</p>
                                    <p className="mt-0.5 text-sm font-semibold text-slate-900">
                                        {debugResult.count}
                                    </p>
                                </GlassCard>
                                <GlassCard className="p-2.5 text-center">
                                    <p className="text-xs text-slate-400">改写查询</p>
                                    <p className="mt-0.5 text-sm font-semibold text-slate-900">
                                        {debugResult.rewritten_queries?.length ?? 0}
                                    </p>
                                </GlassCard>
                                <GlassCard className="p-2.5 text-center">
                                    <p className="text-xs text-slate-400">状态</p>
                                    <p className="mt-0.5 text-sm font-semibold text-slate-900">
                                        {debugResult.status}
                                    </p>
                                </GlassCard>
                            </div>

                            {debugResult.rewritten_queries && debugResult.rewritten_queries.length > 0 ? (
                                <div className="space-y-1.5">
                                    <p className="text-xs font-medium text-slate-500">改写查询</p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {debugResult.rewritten_queries.map((q, i) => (
                                            <Badge key={i} variant="outline" className="text-xs font-normal">
                                                {q}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            ) : null}

                            {citations && citations.length > 0 ? (
                                <div className="space-y-2">
                                    <p className="text-xs font-medium text-slate-500">引用来源</p>
                                    <div className="space-y-2">
                                        {citations.map((citation, i) => (
                                            <GlassCard key={i} className="p-3">
                                                <p className="text-sm font-medium text-slate-900">
                                                    {(citation.document_title as string) || `来源 ${i + 1}`}
                                                </p>
                                                <p className="mt-1 text-xs leading-relaxed text-slate-600">
                                                    {(citation.snippet as string) || ""}
                                                </p>
                                            </GlassCard>
                                        ))}
                                    </div>
                                </div>
                            ) : null}

                            <details className="rounded-lg border border-slate-200 bg-slate-50">
                                <summary
                                    className="cursor-pointer list-none px-3 py-2 text-xs font-medium text-slate-500 select-none"
                                    onClick={(e) => {
                                        e.preventDefault();
                                        setJsonExpanded((v) => !v);
                                    }}
                                >
                                    {jsonExpanded ? (
                                        <ChevronUp className="inline h-3.5 w-3.5 mr-1" />
                                    ) : (
                                        <ChevronDown className="inline h-3.5 w-3.5 mr-1" />
                                    )}
                                    查看完整 JSON
                                </summary>
                                {jsonExpanded ? (
                                    <pre className="overflow-x-auto whitespace-pre-wrap break-all p-3 text-xs text-slate-700">
                                        {JSON.stringify(debugResult, null, 2)}
                                    </pre>
                                ) : null}
                            </details>

                            {answerability ? (
                                <div className="space-y-1.5">
                                    <p className="text-xs font-medium text-slate-500">可回答性详情</p>
                                    <StructuredPayloadViewer data={answerability} />
                                </div>
                            ) : null}

                            {debugResult._diagnostics ? (
                                <div className="space-y-1.5">
                                    <p className="text-xs font-medium text-slate-500">诊断信息</p>
                                    <StructuredPayloadViewer data={debugResult._diagnostics} />
                                </div>
                            ) : null}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
