"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Users2, Target } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { Agent, SalesPersonaOption, ScenarioSummary } from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";

const CORE_COMBINATIONS: Array<{
    id: string;
    capability: string;
    role: string;
}> = [
    { id: "c1", capability: "破冰建立信任", role: "冷淡型客户" },
    { id: "c2", capability: "破冰建立信任", role: "强势质疑型客户" },
    { id: "c3", capability: "需求挖掘", role: "价格敏感型客户" },
    { id: "c4", capability: "需求挖掘", role: "拖延决策型客户" },
    { id: "c5", capability: "价值表达", role: "竞品比较型客户" },
    { id: "c6", capability: "价值表达", role: "价格敏感型客户" },
    { id: "c7", capability: "异议处理", role: "强势质疑型客户" },
    { id: "c8", capability: "异议处理", role: "竞品比较型客户" },
    { id: "c9", capability: "推进下一步行动", role: "拖延决策型客户" },
    { id: "c10", capability: "推进下一步行动", role: "冷淡型客户" },
];

export default function SalesTrainingPage() {
    const router = useRouter();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [salesScenarios, setSalesScenarios] = useState<ScenarioSummary[]>([]);
    const [salesPersonas, setSalesPersonas] = useState<SalesPersonaOption[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    const loadSalesTrainingData = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);

        try {
            const [agentResult, scenarioResult, personasResult] = await Promise.allSettled([
                api.training.getSalesAgents(),
                api.scenarios.list("sales"),
                api.scenarios.getSalesPersonas(),
            ]);

            const failedSections: string[] = [];

            if (agentResult.status === "fulfilled") {
                setAgents(agentResult.value);
            } else {
                failedSections.push("智能体");
            }
            if (scenarioResult.status === "fulfilled") {
                setSalesScenarios(scenarioResult.value);
            } else {
                failedSections.push("场景");
            }
            if (personasResult.status === "fulfilled") {
                setSalesPersonas(personasResult.value);
            } else {
                failedSections.push("角色画像");
            }

            if (failedSections.length > 0) {
                setLoadError(`部分数据加载失败（${failedSections.join("、")}），请重试。`);
            }
        } catch (error) {
            console.error("Failed to load sales training data:", error);
            setLoadError("训练入口加载失败，请稍后重试。");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadSalesTrainingData();
    }, [loadSalesTrainingData]);

    const handleAgentClick = (agentId: string) => {
        // 跳转到角色选择页面
        router.push(`/agents/${agentId}`);
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            {/* Header with Back Button */}
            <div className="flex flex-col gap-6">
                <Button 
                    variant="ghost" 
                    className="w-fit pl-0 text-slate-500 hover:text-slate-900 hover:bg-transparent gap-2"
                    onClick={() => router.back()}
                >
                    <ArrowLeft className="w-4 h-4" />
                    返回训练大厅
                </Button>
                
                <div className="flex justify-between items-end">
                    <div>
                        <h1 className="text-3xl font-black text-slate-900 tracking-tight">销售能力训练</h1>
                        <p className="text-slate-500 mt-2 text-lg font-medium">选择一个智能体，然后选择对练角色开始实战模拟。</p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
                    <div className="text-xs text-slate-500">可用销售场景</div>
                    <div className="mt-1 text-2xl font-black text-slate-900 flex items-center gap-2">
                        <Target className="w-5 h-5 text-blue-600" />
                        {salesScenarios.length}
                    </div>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
                    <div className="text-xs text-slate-500">可选客户画像</div>
                    <div className="mt-1 text-2xl font-black text-slate-900 flex items-center gap-2">
                        <Users2 className="w-5 h-5 text-purple-600" />
                        {salesPersonas.length}
                    </div>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
                    <div className="text-xs text-slate-500">发布中的智能体</div>
                    <div className="mt-1 text-2xl font-black text-slate-900">{agents.length}</div>
                </div>
            </div>

            {loadError && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-center justify-between gap-3">
                    <p className="text-sm text-amber-800">{loadError}</p>
                    <Button
                        variant="outline"
                        className="border-amber-300 text-amber-800 hover:bg-amber-100"
                        onClick={() => {
                            void loadSalesTrainingData();
                        }}
                        disabled={isLoading}
                    >
                        重试
                    </Button>
                </div>
            )}

            <div className="rounded-3xl border border-slate-100 bg-white/70 p-6">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                    <h2 className="text-lg font-bold text-slate-900">核心 10 组合（80/20）</h2>
                    <span className="text-xs text-slate-500">首期优先练这些组合，先拿稳定效果</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    {CORE_COMBINATIONS.map((item, idx) => (
                        <div
                            key={item.id}
                            className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3"
                        >
                            <p className="text-[11px] text-slate-500 font-semibold">
                                组合 {idx + 1}
                            </p>
                            <p className="text-sm font-bold text-slate-900 mt-1">
                                {item.capability}
                            </p>
                            <p className="text-xs text-slate-600 mt-1">
                                客户角色：{item.role}
                            </p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Agents Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {isLoading ? (
                    // Loading Skeletons
                    Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="h-64 rounded-3xl bg-white/50 animate-pulse border border-white/60" />
                    ))
                ) : (
                    agents.map((agent) => (
                        <AgentCard
                            key={agent.id}
                            id={agent.id}
                            name={agent.name}
                            description={agent.description}
                            role={agent.role}
                            difficulty={agent.difficulty}
                            iconKey={agent.ui_metadata?.icon_key}
                            themeColor={agent.ui_metadata?.theme_color}
                            tags={agent.ui_metadata?.tags}
                            category="sales"
                            actionText="选择角色开始对练"
                            onClick={() => handleAgentClick(agent.id)}
                        />
                    ))
                )}
            </div>
        </div>
    );
}
