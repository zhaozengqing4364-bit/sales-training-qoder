"use client";

import { useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { ChevronRight } from "lucide-react";

interface RetrievalParameter {
    name: string;
    value: string;
    description: string;
}

const RETRIEVAL_PARAMETERS: RetrievalParameter[] = [
    {
        name: "top_k",
        value: "5",
        description: "检索返回的最大结果数",
    },
    {
        name: "similarity_threshold",
        value: "0.58",
        description: "语义相似度最低阈值",
    },
    {
        name: "enable_hybrid",
        value: "true",
        description: "启用混合检索模式",
    },
    {
        name: "keyword_candidate_limit",
        value: "32",
        description: "关键词检索候选上限",
    },
    {
        name: "embedding_timeout_ms",
        value: "0",
        description: "向量编码超时，0=无限",
    },
    {
        name: "enable_rerank",
        value: "true",
        description: "启用重排序",
    },
    {
        name: "rerank_top_k",
        value: "8",
        description: "重排序后保留的结果数",
    },
    {
        name: "metadata_filter",
        value: "无",
        description: "元数据过滤条件",
    },
];

export function RetrievalConfigTab() {
    const router = useRouter();

    return (
        <div className="space-y-4">
            <div>
                <h3 className="text-base font-semibold text-slate-900">检索运行参数</h3>
                <p className="mt-1 text-sm text-slate-500">
                    这些参数由语音运行时策略（Voice Runtime Profile）控制，不在知识问答配置版本中管理。以下展示的是引擎默认值。
                </p>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {RETRIEVAL_PARAMETERS.map((param) => (
                    <GlassCard key={param.name} className="p-3 space-y-1.5">
                        <p className="text-xs font-medium text-slate-400">{param.name}</p>
                        <p className="text-sm font-semibold text-slate-900">
                            {param.value === "true" ? (
                                <span className="text-green-700">true</span>
                            ) : param.value === "false" ? (
                                <span className="text-red-600">false</span>
                            ) : (
                                param.value
                            )}
                        </p>
                        <p className="text-xs text-slate-500">{param.description}</p>
                    </GlassCard>
                ))}
            </div>

            <div className="pt-2">
                <Button
                    variant="outline"
                    className="rounded-full"
                    onClick={() => router.push("/admin/voice-runtime")}
                >
                    前往语音运行时策略配置 <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
            </div>
        </div>
    );
}
