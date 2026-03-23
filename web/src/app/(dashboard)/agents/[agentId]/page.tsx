"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Sparkles, Play, User, Presentation } from "lucide-react";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

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
    icon?: string;
    difficulty: string;
    is_default?: boolean;
}

interface AgentDetail {
    id: string;
    name: string;
    description: string;
    icon?: string;
    category: string;
    welcome_message?: string;
    personas: Persona[];
}

interface PresentationOption {
    presentation_id: string;
    title: string;
    page_count: number;
    total_pages?: number;
    version_number: number;
    status: "processing" | "ready" | "failed";
}

type VoiceMode = "legacy" | "stepfun_realtime";
const CREATE_SESSION_RETRY_DELAYS_MS = [200, 500, 1200] as const;

function isRetryableCreateSessionError(error: unknown): boolean {
    if (error instanceof ApiRequestError) {
        return error.status === 0 || error.status >= 500;
    }
    return true;
}

function getPresentationStatusLabel(status: PresentationOption["status"]): string {
    switch (status) {
        case "ready":
            return "可用";
        case "processing":
            return "处理中";
        case "failed":
            return "失败";
        default:
            return status;
    }
}

export default function AgentPersonaSelectPage() {
    const params = useParams();
    const router = useRouter();
    const agentId = params.agentId as string;

    const [agent, setAgent] = useState<AgentDetail | null>(null);
    const [selectedPersona, setSelectedPersona] = useState<string | null>(null);
    const [voiceMode, setVoiceMode] = useState<VoiceMode>("stepfun_realtime");
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [startError, setStartError] = useState<string | null>(null);
    const [availablePresentations, setAvailablePresentations] = useState<PresentationOption[]>([]);
    const [selectedPresentationId, setSelectedPresentationId] = useState<string>("");
    const [isLoadingPresentations, setIsLoadingPresentations] = useState(false);
    const [presentationLoadError, setPresentationLoadError] = useState<string | null>(null);

    useEffect(() => {
        const loadAgent = async () => {
            try {
                const data = await api.agents.getAgentWithPersonas(agentId);
                setAgent(data as AgentDetail);
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
        void loadAgent();
    }, [agentId]);

    useEffect(() => {
        let cancelled = false;

        const loadPresentations = async () => {
            if (!agent || agent.category !== "presentation") {
                setAvailablePresentations([]);
                setSelectedPresentationId("");
                setPresentationLoadError(null);
                return;
            }

            setIsLoadingPresentations(true);
            setPresentationLoadError(null);

            try {
                const presentations = await api.presentations.list({
                    limit: 100,
                });

                if (cancelled) {
                    return;
                }

                const normalized = presentations as PresentationOption[];
                const preferredSelection = normalized.find((item) => item.status === "ready")?.presentation_id
                    || normalized[0]?.presentation_id
                    || "";
                setAvailablePresentations(normalized);
                setSelectedPresentationId((prev) => {
                    if (prev && normalized.some((item) => item.presentation_id === prev)) {
                        return prev;
                    }
                    return preferredSelection;
                });
            } catch (error) {
                if (cancelled) {
                    return;
                }
                setAvailablePresentations([]);
                setSelectedPresentationId("");
                setPresentationLoadError(getApiErrorMessage(error));
            } finally {
                if (!cancelled) {
                    setIsLoadingPresentations(false);
                }
            }
        };

        void loadPresentations();

        return () => {
            cancelled = true;
        };
    }, [agent]);

    const selectedPresentation = useMemo(() => (
        availablePresentations.find((item) => item.presentation_id === selectedPresentationId) || null
    ), [availablePresentations, selectedPresentationId]);

    const handleStartPractice = async () => {
        if (!selectedPersona || !agent) return;

        setIsStarting(true);
        setStartError(null);
        try {
            const scenarioType = agent.category === "presentation" ? "presentation" : "sales";
            if (scenarioType === "presentation") {
                if (!selectedPresentationId) {
                    setStartError("请先选择一个标准PPT");
                    setIsStarting(false);
                    return;
                }
                if (!selectedPresentation || selectedPresentation.status !== "ready") {
                    setStartError("所选标准PPT尚未就绪，请等待其变为可用状态后再开始练习。");
                    setIsStarting(false);
                    return;
                }
            }

            const sessionPayload = {
                agent_id: agentId,
                persona_id: selectedPersona,
                scenario_type: scenarioType,
                presentation_id: scenarioType === "presentation" ? selectedPresentationId : undefined,
                voice_mode: voiceMode,
            } as const;

            let session: Awaited<ReturnType<typeof api.practice.createSession>> | null = null;
            let lastError: unknown = null;
            for (let attempt = 0; attempt <= CREATE_SESSION_RETRY_DELAYS_MS.length; attempt += 1) {
                try {
                    session = await api.practice.createSession(sessionPayload);
                    break;
                } catch (error) {
                    lastError = error;
                    const retryable = isRetryableCreateSessionError(error);
                    if (!retryable || attempt === CREATE_SESSION_RETRY_DELAYS_MS.length) {
                        throw error;
                    }
                    const delayMs = CREATE_SESSION_RETRY_DELAYS_MS[attempt];
                    await new Promise((resolve) => setTimeout(resolve, delayMs));
                }
            }

            if (!session) {
                throw lastError ?? new Error("创建会话失败");
            }

            const presentationParam =
                scenarioType === "presentation" && selectedPresentationId
                    ? `&presentation_id=${encodeURIComponent(selectedPresentationId)}`
                    : "";
            router.push(
                `/practice/${session.session_id}?agent_id=${agentId}&persona_id=${selectedPersona}&scenario_type=${scenarioType}&voice_mode=${voiceMode}${presentationParam}`,
            );
        } catch (error) {
            console.error("Failed to create session:", error);
            setStartError(getApiErrorMessage(error));
        } finally {
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
            <Button
                variant="ghost"
                className="w-fit pl-0 text-slate-500 hover:text-slate-900 hover:bg-transparent gap-2"
                onClick={() => router.back()}
            >
                <ArrowLeft className="w-4 h-4" />
                返回
            </Button>

            <GlassCard className="p-6">
                <div className="flex items-start gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center text-3xl">
                        {agent.icon || "🤖"}
                    </div>
                    <div className="flex-1">
                        <h1 className="text-2xl font-bold text-slate-900">{agent.name}</h1>
                        <p className="text-slate-500 mt-1">{agent.description}</p>
                        {agent.welcome_message && (
                            <p className="text-sm text-slate-400 mt-2 italic">&ldquo;{agent.welcome_message}&rdquo;</p>
                        )}
                    </div>
                </div>
            </GlassCard>

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
                                                : "border-transparent hover:border-slate-200",
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

            {agent.category === "presentation" && (
                <div>
                    <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <Presentation className="w-5 h-5" />
                        选择演练PPT
                    </h2>
                    <p className="text-sm text-slate-500 mb-4">
                        会展示标准PPT的当前版本与材料状态；仅可对可用状态发起新的演练。
                    </p>
                    <GlassCard className="p-5 space-y-3">
                        {isLoadingPresentations ? (
                            <p className="text-sm text-slate-500">正在加载标准PPT...</p>
                        ) : presentationLoadError ? (
                            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                                加载演练PPT失败：{presentationLoadError}
                            </div>
                        ) : availablePresentations.length === 0 ? (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                                当前没有标准PPT，请先到管理后台上传并处理为可用状态。
                            </div>
                        ) : (
                            <>
                                <label className="block space-y-2">
                                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                                        演练文稿
                                    </span>
                                    <select
                                        value={selectedPresentationId}
                                        onChange={(event) => setSelectedPresentationId(event.target.value)}
                                        className="w-full h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                                    >
                                        {availablePresentations.map((presentation) => {
                                            const pageCount = presentation.page_count || presentation.total_pages || 0;
                                            const statusLabel = getPresentationStatusLabel(presentation.status);
                                            return (
                                                <option key={presentation.presentation_id} value={presentation.presentation_id}>
                                                    {presentation.title}（v{presentation.version_number} · {statusLabel} · {pageCount} 页）
                                                </option>
                                            );
                                        })}
                                    </select>
                                </label>

                                {selectedPresentation ? (
                                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                                        <p>当前版本：v{selectedPresentation.version_number}</p>
                                        <p>材料状态：{getPresentationStatusLabel(selectedPresentation.status)}</p>
                                        <p>页数：{selectedPresentation.page_count || selectedPresentation.total_pages || 0} 页</p>
                                    </div>
                                ) : null}

                                {selectedPresentation && selectedPresentation.status !== "ready" ? (
                                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                                        当前版本尚未就绪，请等待材料处理完成后再开始新的演练。
                                    </div>
                                ) : null}
                            </>
                        )}
                    </GlassCard>
                </div>
            )}

            <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-700">
                知识库绑定已迁移到角色中心。请在角色页选择并维护知识库，当前页不再编辑智能体级知识库。
            </div>

            <div>
                <h2 className="text-lg font-bold text-slate-800 mb-3">语音模式</h2>
                <p className="text-sm text-slate-500 mb-4">可在“经典链路”和“StepFun Realtime 端到端”之间切换。</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <button
                        type="button"
                        onClick={() => setVoiceMode("legacy")}
                        className={cn(
                            "rounded-2xl border p-4 text-left transition-all",
                            voiceMode === "legacy"
                                ? "border-indigo-500 bg-indigo-50/40"
                                : "border-slate-200 bg-white hover:border-slate-300",
                        )}
                    >
                        <div className="font-semibold text-slate-900">经典模式</div>
                        <div className="text-sm text-slate-500 mt-1">ASR → LLM → TTS，稳定兼容现有能力模块。</div>
                    </button>
                    <button
                        type="button"
                        onClick={() => setVoiceMode("stepfun_realtime")}
                        className={cn(
                            "rounded-2xl border p-4 text-left transition-all",
                            voiceMode === "stepfun_realtime"
                                ? "border-indigo-500 bg-indigo-50/40"
                                : "border-slate-200 bg-white hover:border-slate-300",
                        )}
                    >
                        <div className="font-semibold text-slate-900">Realtime 模式（默认推荐）</div>
                        <div className="text-sm text-slate-500 mt-1">StepFun 端到端语音模型，适合对话真实感测试。</div>
                    </button>
                </div>
            </div>

            {agent.personas.length > 0 && (
                <div className="fixed bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-slate-50 via-slate-50/95 to-transparent md:static md:bg-none md:p-0">
                    <div className="max-w-md mx-auto md:max-w-none">
                        {startError ? (
                            <div className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                                {startError}
                            </div>
                        ) : null}
                        <Button
                            size="lg"
                            disabled={
                                !selectedPersona
                                || isStarting
                                || (agent.category === "presentation" && (!selectedPresentationId || selectedPresentation?.status !== "ready"))
                            }
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
