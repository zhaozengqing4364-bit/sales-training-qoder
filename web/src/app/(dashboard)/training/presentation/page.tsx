"use client";
import { debug } from "@/lib/debug";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { Agent } from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";
import { GlassCard } from "@/components/ui/glass-card";

type PresentationOption = Awaited<ReturnType<typeof api.presentations.list>>[number];

export default function PresentationTrainingPage() {
    const router = useRouter();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [presentations, setPresentations] = useState<PresentationOption[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [reloadVersion, setReloadVersion] = useState(0);

    useEffect(() => {
        let cancelled = false;

        const loadAgents = async () => {
            setIsLoading(true);
            setLoadError(null);
            try {
                const [agentResult, presentationResult] = await Promise.allSettled([
                    api.agents.getList("presentation"),
                    api.presentations.list({ status: "ready", limit: 100 }),
                ]);

                if (cancelled) {
                    return;
                }

                const failedSections: string[] = [];
                if (agentResult.status === "fulfilled") {
                    setAgents(agentResult.value);
                } else {
                    setAgents([]);
                    failedSections.push("演讲智能体");
                }

                if (presentationResult.status === "fulfilled") {
                    setPresentations(presentationResult.value);
                } else {
                    setPresentations([]);
                    failedSections.push("PPT 列表");
                }
                if (failedSections.length > 0) {
                    setLoadError(`部分演讲训练数据加载失败（${failedSections.join("、")}），请重试。`);
                } else {
                    setLoadError(null);
                }
            } catch (err) {
                debug.error("Failed to load presentation agents:", err);
                if (!cancelled) {
                    setLoadError("演讲训练场景加载失败，请稍后重试");
                    setAgents([]);
                    setPresentations([]);
                }
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        };

        void loadAgents();

        return () => {
            cancelled = true;
        };
    }, [reloadVersion]);

    const handleAgentClick = (agentId: string) => {
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
                        <h1 className="text-3xl font-black text-slate-900 tracking-tight">演讲与表达训练</h1>
                        <p className="text-slate-500 mt-2 text-lg font-medium">选择一个演讲场景开始演练。</p>
                    </div>
                </div>
            </div>

            {loadError && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-center justify-between gap-3">
                    <p className="text-sm text-amber-800">{loadError}</p>
                    <Button
                        variant="outline"
                        className="border-amber-300 text-amber-800 hover:bg-amber-100"
                        onClick={() => setReloadVersion((version) => version + 1)}
                        disabled={isLoading}
                    >
                        重试
                    </Button>
                </div>
            )}

            {/* Scenarios Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {isLoading ? (
                    Array.from({ length: 4 }).map((_, i) => (
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
                            category="presentation"
                            actionText="进入演练场"
                            onClick={() => handleAgentClick(agent.id)}
                        />
                    ))
                ) : presentations.length > 0 ? (
                    <div className="col-span-full space-y-4">
                        <GlassCard className="p-6 border-amber-100/70 bg-amber-50/40">
                            <p className="text-sm text-amber-700 font-medium">
                                当前没有发布中的演讲智能体。为保证角色稳定与策略生效，请先配置“智能体 + 角色”后再开始演练。
                            </p>
                        </GlassCard>

                        <GlassCard className="p-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900">可用 PPT：{presentations.length} 份</h3>
                                <p className="mt-1 text-sm text-slate-500">
                                    PPT 已准备完成，但仍需先发布演讲智能体并关联角色，系统才可严格按设定进行演练。
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    variant="outline"
                                    onClick={() => router.push("/admin/presentations")}
                                    className="rounded-full px-5"
                                >
                                    管理 PPT
                                </Button>
                                <Button
                                    onClick={() => router.push("/admin/agents")}
                                    className="rounded-full px-5"
                                >
                                    去配置智能体
                                </Button>
                            </div>
                        </GlassCard>
                    </div>
                ) : (
                    <GlassCard className="col-span-full p-12 text-center">
                        <p className="text-slate-500">
                            {loadError
                                ? "演讲训练入口暂不可用，不代表没有可练内容；请重试或返回训练大厅。"
                                : "暂无演讲训练场景，请联系管理员添加演讲智能体或上传可用 PPT"}
                        </p>
                    </GlassCard>
                )}
            </div>
        </div>
    );
}
