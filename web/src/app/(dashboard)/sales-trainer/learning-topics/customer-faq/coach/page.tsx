"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, MessageSquareText, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { CustomerFaqCard, CustomerFaqLearningTopicResponse } from "@/lib/api/types";

function coachSuggestion(card: CustomerFaqCard, answer: string): string {
    if (!answer.trim()) {
        return "先用 30 秒答法回答客户问题，再补一个案例或边界。";
    }
    if (card.escalation_required || card.difficulty_level === "high_risk") {
        return "这题属于高风险口径。回答里必须保留边界，并明确需要售前或技术确认，不能给固定承诺。";
    }
    if (card.evidence_cases.length > 0) {
        return `可以补充案例依据：${card.evidence_cases.slice(0, 2).join("、")}。先讲标准口径，再讲案例，不要把案例效果承诺给当前客户。`;
    }
    return "回答方向可以，下一步请压缩成客户能听懂的一句话，并补充“下一步如何验证”。";
}

export default function CustomerFaqCoachPage() {
    const [topic, setTopic] = useState<CustomerFaqLearningTopicResponse | null>(null);
    const [selectedCardKey, setSelectedCardKey] = useState("");
    const [answer, setAnswer] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await api.newcomerTraining.getCustomerFaqTopic();
            setTopic(response);
            setSelectedCardKey(response.cards[0]?.card_key ?? "");
        } catch (loadError) {
            setTopic(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const selectedCard = useMemo(
        () => topic?.cards.find((card) => card.card_key === selectedCardKey) ?? topic?.cards[0] ?? null,
        [selectedCardKey, topic],
    );

    if (isLoading) {
        return <GlassCard className="p-8 text-sm text-slate-500">正在加载客户问答 AI 教练...</GlassCard>;
    }

    if (error || !topic || !selectedCard) {
        return (
            <div className="space-y-4 pb-20">
                <Link href="/sales-trainer/learning-topics/customer-faq" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                    <ArrowLeft className="h-4 w-4" />
                    返回客户常见问答
                </Link>
                <GlassCard className="border border-amber-200 bg-amber-50 p-6 text-amber-900">
                    <div className="flex gap-3">
                        <AlertTriangle className="mt-1 h-5 w-5 shrink-0" />
                        <div>
                            <h1 className="text-lg font-black text-amber-950">AI 教练暂不可用</h1>
                            <p className="mt-2 text-sm leading-6">{error || "后台尚未发布可用于训练的客户问答卡片。"}</p>
                        </div>
                    </div>
                </GlassCard>
            </div>
        );
    }

    return (
        <div className="space-y-6 pb-20">
            <Link href="/sales-trainer/learning-topics/customer-faq" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                <ArrowLeft className="h-4 w-4" />
                返回客户常见问答
            </Link>

            <div>
                <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">AI 教练</Badge>
                    <Badge variant="green">仅使用已发布卡片</Badge>
                    <Badge variant="outline">版本 #{topic.revision_no}</Badge>
                </div>
                <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">客户追问训练</h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                    选择一个客户问题，先写出口播回答，再根据卡片边界获得复练建议。高风险问题会优先提示售前确认。
                </p>
            </div>

            <section className="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
                <GlassCard className="space-y-4 p-5">
                    <h2 className="text-lg font-black text-slate-900">选择客户问题</h2>
                    <select
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                        value={selectedCard.card_key}
                        onChange={(event) => {
                            setSelectedCardKey(event.target.value);
                            setAnswer("");
                        }}
                    >
                        {topic.cards.map((card) => (
                            <option key={card.card_key} value={card.card_key}>{card.question}</option>
                        ))}
                    </select>
                    <div className="rounded-xl bg-slate-50 p-4">
                        <p className="font-bold leading-6 text-slate-900">{selectedCard.question}</p>
                        <p className="mt-3 text-sm leading-6 text-slate-600">{selectedCard.short_answer}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {selectedCard.escalation_required ? <Badge variant="orange">需售前确认</Badge> : null}
                        {selectedCard.evidence_cases.map((caseName) => <Badge key={caseName} variant="outline">{caseName}</Badge>)}
                    </div>
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                    <h2 className="flex items-center gap-2 text-lg font-black text-slate-900">
                        <MessageSquareText className="h-5 w-5" />
                        口播回答草稿
                    </h2>
                    <textarea
                        className="min-h-52 w-full rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-6 outline-none focus:border-slate-400"
                        value={answer}
                        onChange={(event) => setAnswer(event.target.value)}
                        placeholder="把你准备对客户说的话写在这里..."
                    />
                    <div className="rounded-xl bg-emerald-50 p-4 text-sm leading-6 text-emerald-900">
                        <div className="flex gap-2">
                            <Sparkles className="mt-1 h-4 w-4 shrink-0" />
                            <div>
                                <p className="font-bold">复练建议</p>
                                <p className="mt-1">{coachSuggestion(selectedCard, answer)}</p>
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button asChild variant="outline">
                            <Link href="/sales-trainer/learning-topics/customer-faq">回到卡片学习</Link>
                        </Button>
                        <Button asChild variant="outline">
                            <Link href="/sales-trainer">准备口播录音</Link>
                        </Button>
                    </div>
                </GlassCard>
            </section>
        </div>
    );
}
