"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { Agent } from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";
import { GlassCard } from "@/components/ui/glass-card";

export default function PresentationTrainingPage() {
    const router = useRouter();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadAgents = async () => {
            try {
                const data = await api.agents.getList("presentation");
                setAgents(data);
            } catch (err) {
                console.error("Failed to load presentation agents:", err);
                setError("暂无演讲训练场景");
            } finally {
                setIsLoading(false);
            }
        };
        loadAgents();
    }, []);

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
                    onClick={() => router.back()}
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

            {/* Scenarios Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {isLoading ? (
                    Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="h-64 rounded-3xl bg-white/50 animate-pulse border border-white/60" />
                    ))
                ) : error || agents.length === 0 ? (
                    <GlassCard className="col-span-full p-12 text-center">
                        <p className="text-slate-500">{error || "暂无演讲训练场景，请联系管理员添加"}</p>
                    </GlassCard>
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
                            category="presentation"
                            actionText="进入演练场"
                            onClick={() => handleAgentClick(agent.id)}
                        />
                    ))
                )}
            </div>
        </div>
    );
}
