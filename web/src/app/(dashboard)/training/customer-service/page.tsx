"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { Agent } from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";

export default function CustomerServiceTrainingPage() {
    const router = useRouter();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const loadAgents = async () => {
            try {
                const data = await api.training.getCustomerAgents();
                setAgents(data);
            } catch (error) {
                console.error("Failed to load customer service agents:", error);
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
                        <h1 className="text-3xl font-black text-slate-900 tracking-tight">客户服务训练</h1>
                        <p className="text-slate-500 mt-2 text-lg font-medium">选择一个智能体，然后选择对练角色开始训练。</p>
                    </div>
                </div>
            </div>

            {/* Agents Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {isLoading ? (
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
                            iconKey={agent.ui_metadata?.icon_key || "Headphones"}
                            themeColor={agent.ui_metadata?.theme_color}
                            tags={agent.ui_metadata?.tags}
                            category="customer-service"
                            actionText="选择角色开始训练"
                            onClick={() => handleAgentClick(agent.id)}
                        />
                    ))
                )}
            </div>
        </div>
    );
}