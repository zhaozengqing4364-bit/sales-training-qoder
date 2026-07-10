"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    ArrowLeft,
    BookOpen,
    CheckCircle2,
    ChevronDown,
    ClipboardCheck,
    MessageCircle,
    X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    CustomerFaqCard,
    CustomerFaqLearningTopicResponse,
    CustomerFaqShortAnswerAttemptResponse,
} from "@/lib/api/types";

type AnswerDrafts = Record<string, string>;
type CustomerFaqLearningUnit = CustomerFaqLearningTopicResponse["units"][number];

function difficultyLabel(card: CustomerFaqCard) {
    if (card.escalation_required || card.difficulty_level === "high_risk") return "高风险口径";
    if (card.difficulty_level === "advanced") return "进阶问题";
    return "新人必会";
}

function difficultyVariant(card: CustomerFaqCard): "green" | "orange" | "outline" {
    if (card.escalation_required || card.difficulty_level === "high_risk") return "orange";
    if (card.difficulty_level === "advanced") return "outline";
    return "green";
}

function sortUnits(topic: CustomerFaqLearningTopicResponse | null) {
    return [...(topic?.units ?? [])]
        .filter((unit) => unit.enabled)
        .sort((left, right) => left.order_index - right.order_index);
}

function buildCardMap(cards: readonly CustomerFaqCard[]) {
    return new Map(cards.map((card) => [card.card_key, card]));
}

export default function CustomerFaqLearningTopicPage() {
    const [topic, setTopic] = useState<CustomerFaqLearningTopicResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [selectedUnitKey, setSelectedUnitKey] = useState<string | null>(null);
    const [answerDrafts, setAnswerDrafts] = useState<AnswerDrafts>({});
    const [attempt, setAttempt] = useState<CustomerFaqShortAnswerAttemptResponse | null>(null);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isQuizOpen, setIsQuizOpen] = useState(false);

    const load = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);
        try {
            const response = await api.newcomerTraining.getCustomerFaqTopic();
            const firstUnit = sortUnits(response)[0] ?? null;
            setTopic(response);
            setSelectedUnitKey(firstUnit?.unit_key ?? null);
        } catch (error) {
            setTopic(null);
            setSelectedUnitKey(null);
            setLoadError(getApiErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const units = useMemo(() => sortUnits(topic), [topic]);
    const cardMap = useMemo(() => buildCardMap(topic?.cards ?? []), [topic?.cards]);
    const selectedUnit = units.find((unit) => unit.unit_key === selectedUnitKey) ?? units[0] ?? null;
    const unitCards = useMemo(() => {
        if (!topic || !selectedUnit) return [];
        const selectedCards = (selectedUnit.source_card_keys ?? [])
            .map((cardKey) => cardMap.get(cardKey))
            .filter((card): card is CustomerFaqCard => Boolean(card))
            .filter((card) => card.status === "published");
        return selectedCards.length > 0
            ? selectedCards
            : topic.cards.filter((card) => card.status === "published");
    }, [cardMap, selectedUnit, topic]);
    const quizCards = useMemo(() => {
        if (!selectedUnit) return [];
        const count = Math.max(1, selectedUnit.quiz_question_count || 1);
        return unitCards.slice(0, count);
    }, [selectedUnit, unitCards]);
    const canSubmit = quizCards.some((card) => answerDrafts[card.card_key]?.trim());

    const handleUnitSelect = (unitKey: string) => {
        setSelectedUnitKey(unitKey);
        setAttempt(null);
        setSubmitError(null);
        setIsQuizOpen(false);
    };

    const submitShortAnswerQuiz = async () => {
        if (!selectedUnit) return;
        const answers = quizCards
            .map((card) => ({
                card_key: card.card_key,
                answer_text: answerDrafts[card.card_key]?.trim() ?? "",
            }))
            .filter((answer) => answer.answer_text);
        if (answers.length === 0) return;

        setIsSubmitting(true);
        setSubmitError(null);
        try {
            const response = await api.newcomerTraining.submitCustomerFaqShortAnswerAttempt(
                selectedUnit.unit_key,
                { answers },
            );
            setAttempt(response);
        } catch (error) {
            setAttempt(null);
            setSubmitError(getApiErrorMessage(error));
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isLoading) {
        return <GlassCard className="p-8 text-sm text-slate-500">正在加载客户常见问答...</GlassCard>;
    }

    if (loadError || !topic) {
        return (
            <div className="space-y-4 pb-20">
                <BackLink />
                <GlassCard className="border border-amber-200 bg-amber-50 p-6 text-amber-900">
                    <div className="flex gap-3">
                        <AlertTriangle className="mt-1 h-5 w-5 shrink-0" />
                        <div>
                            <h1 className="text-lg font-black text-amber-950">客户常见问答暂不可学习</h1>
                            <p className="mt-2 text-sm leading-6">{loadError || "后台尚未发布客户常见问答专题。"}</p>
                        </div>
                    </div>
                </GlassCard>
            </div>
        );
    }

    return (
        <div className="space-y-6 pb-20">
            <BackLink />

            <section className="space-y-4">
                <div className="max-w-4xl">
                    <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">学习专题</Badge>
                        <Badge variant="green">问答卡片</Badge>
                        <Badge variant="outline">简答小测</Badge>
                    </div>
                    <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">{topic.title}</h1>
                    <p className="mt-2 text-sm leading-6 text-slate-500">
                        {topic.description || "按单元学习客户常见问题、标准回答、关键要点和风险边界，完成单元简答小测后查看 AI 评分建议。"}
                    </p>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                    <MetricCard icon={<BookOpen className="h-5 w-5" />} label="学习单元" value={units.length} />
                    <MetricCard icon={<MessageCircle className="h-5 w-5" />} label="常见问题" value={topic.cards.length} />
                    <MetricCard icon={<ClipboardCheck className="h-5 w-5" />} label="单元小测" value={units.filter((unit) => unit.require_quiz).length} />
                </div>
            </section>

            <CustomerFaqLearningPathBar
                selectedUnitKey={selectedUnit?.unit_key ?? null}
                units={units}
                onSelect={handleUnitSelect}
            />

            <GlassCard className="space-y-5 p-5 md:p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="max-w-3xl">
                        <p className="text-sm font-black text-slate-900">本单元学习</p>
                        <h2 className="mt-1 text-2xl font-black text-slate-900">{selectedUnit?.title ?? "暂无学习单元"}</h2>
                        {selectedUnit?.description ? (
                            <p className="mt-2 text-sm leading-6 text-slate-500">{selectedUnit.description}</p>
                        ) : null}
                    </div>
                    <Button
                        type="button"
                        className="w-full rounded-full lg:w-auto"
                        disabled={quizCards.length === 0}
                        onClick={() => setIsQuizOpen(true)}
                    >
                        <ClipboardCheck className="mr-2 h-4 w-4" />
                        开始简答小测
                    </Button>
                </div>

                {unitCards.length > 0 ? (
                    <div className="grid gap-4 lg:grid-cols-2">
                        {unitCards.map((card, index) => (
                            <article key={card.card_key} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                                <div className="flex flex-wrap items-center gap-2">
                                    <Badge variant="outline">问题 {index + 1}</Badge>
                                    <Badge variant={difficultyVariant(card)}>{difficultyLabel(card)}</Badge>
                                    <Badge variant="outline">{card.scenario}</Badge>
                                    <Badge variant="outline">{card.category}</Badge>
                                </div>
                                <CardSection title="客户会这样问">
                                    <p className="text-lg font-black leading-7 text-slate-900">{card.question}</p>
                                </CardSection>
                                <CardSection title="标准回答">
                                    <p className="rounded-xl bg-emerald-50 p-4 text-sm font-semibold leading-7 text-emerald-900">
                                        {card.short_answer}
                                    </p>
                                </CardSection>
                                <CardSection title="必须讲到">
                                    <ul className="space-y-2">
                                        {card.key_points.map((point) => (
                                            <li key={point} className="flex gap-2 text-sm leading-6 text-slate-600">
                                                <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />
                                                {point}
                                            </li>
                                        ))}
                                    </ul>
                                </CardSection>
                                <CardSection title="详细答法">
                                    <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">{card.detailed_answer}</p>
                                </CardSection>
                                {card.forbidden_claims.length > 0 ? (
                                    <CardSection title="不要直接承诺">
                                        <div className="space-y-2">
                                            {card.forbidden_claims.map((claim) => (
                                                <p key={claim} className="rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-900">{claim}</p>
                                            ))}
                                        </div>
                                    </CardSection>
                                ) : null}
                                {card.evidence_cases.length > 0 ? (
                                    <CardSection title="可引用案例">
                                        <div className="flex flex-wrap gap-2">
                                            {card.evidence_cases.map((caseName) => (
                                                <Badge key={caseName} variant="outline">{caseName}</Badge>
                                            ))}
                                        </div>
                                    </CardSection>
                                ) : null}
                            </article>
                        ))}
                    </div>
                ) : (
                    <div className="rounded-xl bg-slate-50 p-6 text-sm text-slate-500">本单元暂未配置问答卡片。</div>
                )}
            </GlassCard>

            {isQuizOpen && selectedUnit ? (
                <ShortAnswerQuizDialog
                    answerDrafts={answerDrafts}
                    attempt={attempt}
                    canSubmit={canSubmit}
                    cards={quizCards}
                    isSubmitting={isSubmitting}
                    onAnswerChange={(cardKey, value) => {
                        setAnswerDrafts((current) => ({
                            ...current,
                            [cardKey]: value,
                        }));
                    }}
                    onClose={() => setIsQuizOpen(false)}
                    onSubmit={() => void submitShortAnswerQuiz()}
                    submitError={submitError}
                    unit={selectedUnit}
                />
            ) : null}
        </div>
    );
}

function CustomerFaqLearningPathBar({
    selectedUnitKey,
    units,
    onSelect,
}: {
    readonly selectedUnitKey: string | null;
    readonly units: readonly CustomerFaqLearningUnit[];
    readonly onSelect: (unitKey: string) => void;
}) {
    return (
        <section className="rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm" aria-label="客户常见问答训练路径">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-slate-400" />
                    <h2 className="text-sm font-black text-slate-900">训练路径</h2>
                    <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-500 ring-1 ring-slate-100">
                        {units.length} 个单元
                    </span>
                </div>
                <p className="text-xs text-slate-500">先学习问答卡片，再完成本单元简答小测。</p>
            </div>
            <div className="-mx-1 overflow-x-auto px-1 pb-1">
                <div className="flex min-w-max gap-2">
                    {units.map((unit) => {
                        const isSelected = selectedUnitKey === unit.unit_key;
                        const questionCount = unit.source_card_keys?.length ?? 0;
                        return (
                            <button
                                key={unit.unit_key}
                                type="button"
                                className={`w-[12.5rem] shrink-0 rounded-2xl border bg-white px-3.5 py-3 text-left transition-colors ${isSelected ? "border-slate-950 shadow-md shadow-slate-900/10" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"}`}
                                onClick={() => onSelect(unit.unit_key)}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-[11px] font-bold text-slate-400">第 {unit.order_index} 单元</span>
                                    {unit.require_quiz ? (
                                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 ring-1 ring-emerald-100">
                                            简答小测
                                        </span>
                                    ) : null}
                                </div>
                                <p className="mt-2 truncate text-sm font-black text-slate-900">{unit.title}</p>
                                <p className="mt-1 line-clamp-1 text-xs leading-relaxed text-slate-500">
                                    {unit.description || unit.empty_state_message || "暂无单元说明。"}
                                </p>
                                <div className="mt-3 flex items-center gap-2 text-xs font-bold text-slate-500">
                                    <span className="rounded-full bg-slate-50 px-2.5 py-1 ring-1 ring-slate-100">{questionCount} 个问题</span>
                                    <span className={isSelected ? "text-slate-900" : "text-slate-400"}>
                                        {isSelected ? "正在学习" : "点击切换"}
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

function ShortAnswerQuizDialog({
    answerDrafts,
    attempt,
    canSubmit,
    cards,
    isSubmitting,
    onAnswerChange,
    onClose,
    onSubmit,
    submitError,
    unit,
}: {
    readonly answerDrafts: AnswerDrafts;
    readonly attempt: CustomerFaqShortAnswerAttemptResponse | null;
    readonly canSubmit: boolean;
    readonly cards: readonly CustomerFaqCard[];
    readonly isSubmitting: boolean;
    readonly onAnswerChange: (cardKey: string, value: string) => void;
    readonly onClose: () => void;
    readonly onSubmit: () => void;
    readonly submitError: string | null;
    readonly unit: CustomerFaqLearningUnit;
}) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="customer-faq-quiz-title"
                className="flex max-h-[calc(100vh-3rem)] w-full max-w-3xl flex-col overflow-hidden rounded-[1.5rem] bg-white shadow-2xl"
            >
                <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
                    <div>
                        <p className="text-xs font-bold text-slate-500">单元小测</p>
                        <h2 id="customer-faq-quiz-title" className="mt-1 text-xl font-black text-slate-900">
                            {unit.title} · 简答小测
                        </h2>
                        <p className="mt-1 text-sm leading-6 text-slate-500">
                            可以使用电脑语音输入法把口述内容转成文字后提交，系统会按标准回答给出分数和建议。
                        </p>
                    </div>
                    <button
                        type="button"
                        aria-label="关闭简答小测"
                        className="rounded-full border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
                        onClick={onClose}
                    >
                        <X className="h-4 w-4" />
                    </button>
                </header>

                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                    {cards.length > 0 ? (
                        <div className="space-y-4">
                            {cards.map((card) => (
                                <label key={card.card_key} className="block space-y-2">
                                    <span className="text-sm font-bold text-slate-900">回答：{card.question}</span>
                                    <textarea
                                        className="min-h-32 w-full resize-y rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                                        value={answerDrafts[card.card_key] ?? ""}
                                        onChange={(event) => onAnswerChange(card.card_key, event.target.value)}
                                        placeholder="把你准备对客户说的话写在这里。"
                                    />
                                </label>
                            ))}
                            {submitError ? (
                                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-700">{submitError}</div>
                            ) : null}
                            {attempt ? <ShortAnswerResult attempt={attempt} /> : null}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-500">本单元暂未配置小测题。</p>
                    )}
                </div>

                <footer className="flex flex-col-reverse gap-2 border-t border-slate-100 px-5 py-4 sm:flex-row sm:justify-end">
                    <Button type="button" variant="outline" className="rounded-full" onClick={onClose}>
                        取消
                    </Button>
                    <Button
                        type="button"
                        className="rounded-full"
                        isLoading={isSubmitting}
                        disabled={!canSubmit || cards.length === 0}
                        onClick={onSubmit}
                    >
                        提交简答小测
                    </Button>
                </footer>
            </div>
        </div>
    );
}

function BackLink() {
    return (
        <Link href="/sales-trainer" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
            <ArrowLeft className="h-4 w-4" />
            返回新人训练路径
        </Link>
    );
}

function MetricCard({
    icon,
    label,
    value,
}: {
    readonly icon: ReactNode;
    readonly label: string;
    readonly value: number;
}) {
    return (
        <GlassCard className="flex items-center gap-4 p-4">
            <div className="rounded-xl bg-slate-100 p-3 text-slate-700">{icon}</div>
            <div>
                <p className="text-xs text-slate-500">{label}</p>
                <p className="mt-1 text-2xl font-black text-slate-900">{value}</p>
            </div>
        </GlassCard>
    );
}

function ShortAnswerResult({
    attempt,
}: {
    readonly attempt: CustomerFaqShortAnswerAttemptResponse;
}) {
    return (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="text-sm font-black text-emerald-950">AI 评分结果</p>
                    <p className="mt-1 text-sm text-emerald-800">
                        {attempt.passed === null ? "已完成本次评分" : attempt.passed ? "达到本单元建议分" : "建议补充后再练一次"}
                    </p>
                </div>
                <p className="text-2xl font-black text-emerald-950">{attempt.total_score} / {attempt.max_score}</p>
            </div>
            <div className="mt-4 space-y-3">
                {attempt.answers.map((answer) => (
                    <div key={answer.card_key} className="rounded-xl bg-white p-4">
                        <p className="text-sm font-bold leading-6 text-slate-900">{answer.question}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{answer.feedback}</p>
                        <p className="mt-2 text-xs font-semibold text-slate-500">得分：{answer.score} / {answer.max_score}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

function CardSection({
    children,
    title,
}: {
    readonly children: ReactNode;
    readonly title: string;
}) {
    return (
        <section className="mt-4 space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-black text-slate-900">
                <ChevronDown className="h-4 w-4" />
                {title}
            </h3>
            {children}
        </section>
    );
}
