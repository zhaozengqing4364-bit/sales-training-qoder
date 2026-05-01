"use client";
import { debug } from "@/lib/debug";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Users2, Target } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import {
    Agent,
    SalesPersonaOption,
    ScenarioSummary,
} from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";

export default function SalesTrainingPage() {
    const router = useRouter();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [salesScenarios, setSalesScenarios] = useState<ScenarioSummary[]>([]);
    const [salesPersonas, setSalesPersonas] = useState<SalesPersonaOption[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [failedSections, setFailedSections] = useState<string[]>([]);

    const loadSalesTrainingData = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        setFailedSections([]);

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
                setAgents([]);
                failedSections.push("智能体");
            }
            if (scenarioResult.status === "fulfilled") {
                setSalesScenarios(scenarioResult.value);
            } else {
                setSalesScenarios([]);
                failedSections.push("场景");
            }
            if (personasResult.status === "fulfilled") {
                setSalesPersonas(personasResult.value);
            } else {
                setSalesPersonas([]);
                failedSections.push("角色画像");
            }

            setFailedSections(failedSections);
            if (failedSections.length > 0) {
                setLoadError(`部分数据加载失败（${failedSections.join("、")}），请重试。`);
            }
        } catch (error) {
            debug.error("Failed to load sales training data:", error);
            setLoadError("训练入口加载失败，请稍后重试。");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(loadSalesTrainingData);
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
                    onClick={() => router.push("/training")}
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
                        {failedSections.includes("场景") ? "加载失败" : salesScenarios.length}
                    </div>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
                    <div className="text-xs text-slate-500">可选客户画像</div>
                    <div className="mt-1 text-2xl font-black text-slate-900 flex items-center gap-2">
                        <Users2 className="w-5 h-5 text-purple-600" />
                        {failedSections.includes("角色画像") ? "加载失败" : salesPersonas.length}
                    </div>
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
                    <div className="text-xs text-slate-500">发布中的智能体</div>
                    <div className="mt-1 text-2xl font-black text-slate-900">{failedSections.includes("智能体") ? "加载失败" : agents.length}</div>
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

            {/* Agents Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {isLoading ? (
                    // Loading Skeletons
                    Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="h-64 rounded-3xl bg-white/50 animate-pulse border border-white/60" />
                    ))
                ) : agents.length > 0 ? (
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
                ) : (
                    <div className="col-span-full rounded-3xl border border-slate-100 bg-white/70 p-8 text-center">
                        <h2 className="text-lg font-bold text-slate-900">
                            {loadError ? "销售训练入口加载不完整" : "暂无可用销售智能体"}
                        </h2>
                        <p className="mx-auto mt-2 max-w-xl text-sm text-slate-500">
                            {loadError
                                ? "部分训练数据未加载成功，页面不会把失败伪装成空列表。请重试，或返回训练大厅选择其他训练模式。"
                                : "当前没有发布中的销售智能体；请联系管理员发布智能体后再开始销售对练。"}
                        </p>
                        <div className="mt-4 flex justify-center gap-3">
                            {loadError && (
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        void loadSalesTrainingData();
                                    }}
                                >
                                    重试销售入口
                                </Button>
                            )}
                            <Button onClick={() => router.push("/training")}>返回训练大厅</Button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
