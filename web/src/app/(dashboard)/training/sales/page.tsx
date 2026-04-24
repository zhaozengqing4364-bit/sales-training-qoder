"use client";
import { debug } from "@/lib/debug";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Users2, Target } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import {
    Agent,
    HistorySessionSummary,
    Recommendation,
    RetryFocusIntent,
    SalesPersonaOption,
    ScenarioSummary,
} from "@/lib/api/types";
import { AgentCard } from "@/components/ui/agent-card";
import {
    buildClientDefaultSalesCombinationResolution,
    formatSalesCombinationFallbackReason,
    resolveSalesCombinationRuleSet,
    type SalesCombinationResolution,
    type SalesCombinationViewModel,
} from "@/lib/api/sales-combinations";

type PersonalizedCombination = {
    combinationId: string;
    sourceLabel: string;
};

const normalizeCombinationText = (value: string) => value
    .toLowerCase()
    .replace(/客户/g, "")
    .replace(/[^\p{Letter}\p{Number}]/gu, "");

function textMatchesTarget(text: string | undefined, target: string): boolean {
    if (!text) return false;
    const normalizedText = normalizeCombinationText(text);
    const normalizedTarget = normalizeCombinationText(target);
    return normalizedText.includes(normalizedTarget) || normalizedTarget.includes(normalizedText);
}

function resolvePersonaForRole(personas: SalesPersonaOption[], role: string) {
    return personas.find((persona) => {
        const characteristics = persona.characteristics || [];
        return (
            textMatchesTarget(persona.name, role)
            || textMatchesTarget(persona.description, role)
            || characteristics.some((item) => textMatchesTarget(item, role))
        );
    }) || null;
}

function resolveAgentForCapability(agents: Agent[], capability: string) {
    return agents.find((agent) => {
        const tags = agent.ui_metadata?.tags || [];
        return (
            textMatchesTarget(agent.name, capability)
            || textMatchesTarget(agent.role, capability)
            || textMatchesTarget(agent.description, capability)
            || tags.some((tag) => textMatchesTarget(tag, capability))
        );
    }) || agents[0] || null;
}

function parseFocusIntentFromTargetPath(targetPath: string | undefined): RetryFocusIntent | null {
    if (!targetPath) return null;

    try {
        const url = new URL(targetPath, "https://local.sales-training");
        const rawFocusIntent = url.searchParams.get("focus_intent");
        if (!rawFocusIntent) return null;

        const parsed = JSON.parse(rawFocusIntent) as Partial<RetryFocusIntent>;
        if (typeof parsed.version !== "string" || typeof parsed.source_session_id !== "string") {
            return null;
        }

        return {
            version: parsed.version,
            source_session_id: parsed.source_session_id,
            main_issue: parsed.main_issue ?? null,
            next_goal: parsed.next_goal ?? null,
        };
    } catch {
        return null;
    }
}

function combinationMatchesEvidence(combination: CoreCombination, evidenceText: string): boolean {
    return textMatchesTarget(evidenceText, combination.capability)
        && textMatchesTarget(evidenceText, combination.role);
}

function resolveCombinationFromEvidence(evidenceParts: Array<string | null | undefined>): CoreCombination | null {
    const evidenceText = evidenceParts.filter(Boolean).join(" ");
    if (!evidenceText) return null;

    return CORE_COMBINATIONS.find((combination) => combinationMatchesEvidence(combination, evidenceText)) || null;
}

function resolvePersonalizedCombination(
    recommendation: Recommendation | null,
    historySessions: HistorySessionSummary[],
): PersonalizedCombination | null {
    const recommendationFocusIntent = parseFocusIntentFromTargetPath(recommendation?.target_path);
    const isSalesRecommendation = recommendation
        ? recommendation.recommendation_kind === "sales_retry"
            || recommendation.scenario_type === "sales"
            || recommendation.target_path.startsWith("/agents/")
        : false;

    if (recommendation && isSalesRecommendation) {
        const recommendedCombination = resolveCombinationFromEvidence([
            recommendation.focus,
            recommendation.title,
            recommendation.reason,
            recommendationFocusIntent?.main_issue?.issue_type,
            recommendationFocusIntent?.main_issue?.issue_text,
            recommendationFocusIntent?.main_issue?.recovery_rule,
            recommendationFocusIntent?.next_goal?.goal_type,
            recommendationFocusIntent?.next_goal?.goal_text,
            recommendationFocusIntent?.next_goal?.rule,
        ]);

        if (recommendedCombination) {
            return {
                combinationId: recommendedCombination.id,
                sourceLabel: "基于上次报告推荐",
            };
        }
    }

    for (const session of historySessions) {
        if (session.scenario_type !== "sales") continue;

        const historyCombination = resolveCombinationFromEvidence([
            session.persona_name,
            session.agent_name,
            session.feedback_summary,
            session.main_issue?.issue_type,
            session.main_issue?.issue_text,
            session.main_issue?.recovery_rule,
            session.next_goal?.goal_type,
            session.next_goal?.goal_text,
            session.next_goal?.rule,
        ]);

        if (historyCombination) {
            return {
                combinationId: historyCombination.id,
                sourceLabel: "基于上次报告推荐",
            };
        }
    }

    return null;
}

function buildCombinationFocusIntent(
    combination: CoreCombination,
): RetryFocusIntent {
    return {
        version: "sales_core_combination_v1",
        source_session_id: `sales-core-combination-${combination.id}`,
        main_issue: {
            issue_type: combination.capability,
            issue_text: `本轮重点练习「${combination.capability}」在「${combination.role}」场景下的对话短板。`,
            recovery_rule: `围绕${combination.role}，优先演练${combination.capability}。`,
        },
        next_goal: {
            goal_type: combination.capability,
            goal_text: `用一轮完整销售对练完成「${combination.capability} × ${combination.role}」。`,
            rule: "sales_core_combination",
        },
    };
}

export default function SalesTrainingPage() {
    const router = useRouter();
    const [agents, setAgents] = useState<Agent[]>([]);
    const [salesScenarios, setSalesScenarios] = useState<ScenarioSummary[]>([]);
    const [salesPersonas, setSalesPersonas] = useState<SalesPersonaOption[]>([]);
    const [latestRecommendation, setLatestRecommendation] = useState<Recommendation | null>(null);
    const [salesHistory, setSalesHistory] = useState<HistorySessionSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [failedSections, setFailedSections] = useState<string[]>([]);

    const loadSalesTrainingData = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        setFailedSections([]);
        setLatestRecommendation(null);
        setSalesHistory([]);

        try {
            const [agentResult, scenarioResult, personasResult, recommendationResult, historyResult] = await Promise.allSettled([
                api.training.getSalesAgents(),
                api.scenarios.list("sales"),
                api.scenarios.getSalesPersonas(),
                api.dashboard.getRecommendation(),
                api.user.getMyHistory({ page: 1, page_size: 5, scenario_type: "sales" }),
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
            if (recommendationResult.status === "fulfilled") {
                setLatestRecommendation(recommendationResult.value);
            }
            if (historyResult.status === "fulfilled") {
                setSalesHistory(historyResult.value.sessions || []);
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
        void loadSalesTrainingData();
    }, [loadSalesTrainingData]);

    const handleAgentClick = (agentId: string) => {
        // 跳转到角色选择页面
        router.push(`/agents/${agentId}`);
    };

    const personalizedCombination = useMemo(
        () => resolvePersonalizedCombination(latestRecommendation, salesHistory),
        [latestRecommendation, salesHistory],
    );

    const combinationCards = useMemo(() => {
        const cards = CORE_COMBINATIONS.map((combination) => {
            const agent = resolveAgentForCapability(agents, combination.capability);
            const persona = resolvePersonaForRole(salesPersonas, combination.role);
            const focusIntent = buildCombinationFocusIntent(combination);
            const focusIntentParam = encodeURIComponent(JSON.stringify(focusIntent));
            const href = agent && persona
                ? `/agents/${agent.id}?persona_id=${encodeURIComponent(persona.id)}&focus_intent=${focusIntentParam}`
                : null;

            return {
                ...combination,
                href,
                agentName: agent?.name || null,
                personaName: persona?.name || null,
                isPersonalized: personalizedCombination?.combinationId === combination.id,
                sourceLabel: personalizedCombination?.combinationId === combination.id
                    ? personalizedCombination.sourceLabel
                    : null,
                unavailableReason: agent
                    ? `管理员尚未配置「${combination.role}」角色`
                    : "管理员尚未发布销售智能体",
            };
        });

        if (!personalizedCombination) {
            return cards;
        }

        return [...cards].sort((left, right) => {
            if (left.id === personalizedCombination.combinationId) return -1;
            if (right.id === personalizedCombination.combinationId) return 1;
            return 0;
        });
    }, [agents, personalizedCombination, salesPersonas]);

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

            <div className="rounded-3xl border border-slate-100 bg-white/70 p-6">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                    <h2 className="text-lg font-bold text-slate-900">核心 10 组合（80/20）</h2>
                    <span className="text-xs text-slate-500">首期优先练这些组合，先拿稳定效果</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    {combinationCards.map((item, idx) => (
                        <button
                            key={item.id}
                            type="button"
                            disabled={!item.href}
                            onClick={() => {
                                if (item.href) {
                                    router.push(item.href);
                                }
                            }}
                            className={`rounded-2xl border p-3 text-left transition-colors ${
                                item.href
                                    ? "border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50"
                                    : "cursor-not-allowed border-amber-200 bg-amber-50/60"
                            }`}
                        >
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-[11px] text-slate-500 font-semibold">
                                    组合 {idx + 1}
                                </p>
                                {item.sourceLabel && (
                                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-bold text-blue-700">
                                        {item.sourceLabel}
                                    </span>
                                )}
                            </div>
                            <p className="text-sm font-bold text-slate-900 mt-1">
                                {item.capability}
                            </p>
                            <p className="text-xs text-slate-600 mt-1">
                                客户角色：{item.role}
                            </p>
                            {item.href ? (
                                <p className="mt-2 text-xs font-bold text-blue-600">
                                    去开练：{item.agentName} · {item.personaName}
                                </p>
                            ) : (
                                <p className="mt-2 text-xs font-bold text-amber-700">
                                    {item.unavailableReason}
                                </p>
                            )}
                        </button>
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
