"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Sparkles, Play, User } from "lucide-react";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";

// 难度配置
const DIFFICULTY_CONFIG: Record<string, { label: string; className: string }> = {
    easy: { label: "简单", className: "text-emerald-600 border-emerald-200 bg-emerald-50" },
    medium: { label: "中等", className: "text-blue-600 border-blue-200 bg-blue-50" },
    hard: { label: "困难", className: "text-orange-600 border-orange-200 bg-orange-50" },
    expert: { label: "专家", className: "text-red-600 border-red-200 bg-red-50" },
};

interface Persona {
    id: string;
    name: string;
    description: string;
    icon: string;
    difficulty: string;
    is_default?: boolean;
}

interface AgentDetail {
    id: string;
    name: string;
    description: string;
    icon: string;
    category: string;
    welcome_message?: string;
    personas: Persona[];
}

export default function AgentPersonaSelectPage() {
    const params = useParams();
    const router = useRouter();
    const agentId = params.agentId as string;

    const [agent, setAgent] = useState<AgentDetail | null>(null);
    const [selectedPersona, setSelectedPersona] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);

    useEffect(() => {
        const loadAgent = async () => {
            try {
                // 获取智能体详情和关联的角色列表
                const data = await api.agents.getAgentWithPersonas(agentId);
                setAgent(data);
                // 默认选中第一个或标记为默认的角色
                const defaultPersona = data.personas.find((p: Persona) => p.is_default) || data.personas[0];
                if (defaultPersona) {
                    setSelectedPersona(defaultPersona.id);
                }
            } catch (error) {
                console.error("Failed to load agent:", error);
            } finally {
                setIsLoading(false);
            }
        };
        loadAgent();
    }, [agentId]);

    const handleStartPractice = async () => {
        if (!selectedPersona || !agent) return;
        
        setIsStarting(true);
        try {
            // 创建练习会话
            const scenarioType = agent.category === "presentation" ? "presentation" : "sales";
            const session = await api.practice.createSession({
                scenario_type: scenarioType,
                agent_id: agentId,
                persona_id: selectedPersona,
            });
            // 跳转到练习页面
            router.push(`/practice/${session.session_id}?agent_id=${agentId}&persona_id=${selectedPersona}`);
        } catch (error) {
            console.error("Failed to create session:", error);
            setIsStarting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
                <div className="h-8 w-32 bg-slate-100 rounded animate-pulse" />
                <div className="h-24 bg-slate-100 rounded-2xl animate-pulse" />
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-48 bg-slate-100 rounded-2xl animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    if (!agent) {
        return (
            <div className="flex flex-col items-center justify-center py-20">
                <p className="text-slate-500">智能体不存在</p>
                <Button variant="ghost" onClick={() => router.back()} className="mt-4">
                    返回
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            {/* 返回按钮 */}
            <Button 
                variant="ghost" 
                className="w-fit pl-0 text-slate-500 hover:text-slate-900 hover:bg-transparent gap-2"
                onClick={() => router.back()}
            >
                <ArrowLeft className="w-4 h-4" />
                返回
            </Button>

            {/* 智能体信息 */}
            <GlassCard className="p-6">
                <div className="flex items-start gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center text-3xl">
                        {agent.icon || "🤖"}
                    </div>
                    <div className="flex-1">
                        <h1 className="text-2xl font-bold text-slate-900">{agent.name}</h1>
                        <p className="text-slate-500 mt-1">{agent.description}</p>
                        {agent.welcome_message && (
                            <p className="text-sm text-slate-400 mt-2 italic">"{agent.welcome_message}"</p>
                        )}
                    </div>
                </div>
            </GlassCard>

            {/* 角色选择 */}
            <div>
                <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <User className="w-5 h-5" />
                    选择对练角色
                </h2>
                <p className="text-sm text-slate-500 mb-6">
                    不同角色有不同的性格特点和难度，选择一个开始练习
                </p>

                {agent.personas.length === 0 ? (
                    <div className="text-center py-12 text-slate-400">
                        <p>该智能体暂无可用角色</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {agent.personas.map((persona) => {
                            const isSelected = selectedPersona === persona.id;
                            const diffConfig = DIFFICULTY_CONFIG[persona.difficulty] || DIFFICULTY_CONFIG.medium;

                            return (
                                <div
                                    key={persona.id}
                                    onClick={() => setSelectedPersona(persona.id)}
                                    className="cursor-pointer"
                                >
                                    <GlassCard 
                                        className={cn(
                                            "p-5 transition-all border-2",
                                            isSelected 
                                                ? "border-indigo-500 bg-indigo-50/30" 
                                                : "border-transparent hover:border-slate-200"
                                        )}
                                    >
                                        <div className="flex items-start justify-between mb-3">
                                            <span className="text-3xl">{persona.icon || "👤"}</span>
                                            <Badge 
                                                variant="secondary" 
                                                className={cn("border", diffConfig.className)}
                                            >
                                                {diffConfig.label}
                                            </Badge>
                                        </div>
                                        <h3 className="font-bold text-slate-900 mb-1">{persona.name}</h3>
                                        <p className="text-sm text-slate-500 line-clamp-2">{persona.description}</p>
                                        
                                        {isSelected && (
                                            <div className="mt-3 pt-3 border-t border-indigo-100 flex items-center gap-1 text-xs text-indigo-600 font-medium">
                                                <Sparkles className="w-3 h-3" />
                                                已选择
                                            </div>
                                        )}
                                    </GlassCard>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* 开始按钮 */}
            {agent.personas.length > 0 && (
                <div className="fixed bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-slate-50 via-slate-50/95 to-transparent md:static md:bg-none md:p-0">
                    <div className="max-w-md mx-auto md:max-w-none">
                        <Button
                            size="lg"
                            disabled={!selectedPersona || isStarting}
                            onClick={handleStartPractice}
                            className="w-full md:w-auto rounded-full bg-indigo-600 hover:bg-indigo-700 text-white py-6 px-8 text-lg font-semibold shadow-lg"
                        >
                            {isStarting ? (
                                <>
                                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                                    创建会话中...
                                </>
                            ) : (
                                <>
                                    <Play className="w-5 h-5 mr-2" />
                                    开始对练
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
