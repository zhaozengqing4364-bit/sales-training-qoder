"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    ArrowLeft,
    CheckCircle2,
    FileText,
    Plus,
    RefreshCcw,
    RotateCcw,
    Search,
    ShieldAlert,
    UploadCloud,
} from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    CustomerFaqCard,
    CustomerFaqImportParseResponse,
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicRevisionSummary,
    NewcomerLearningTopicsConfigResponse,
    NewcomerLearningTopicsPreviewResponse,
} from "@/lib/api/types";

const TOPIC_KEY = "customer_faq";
const EMPTY_CARD: CustomerFaqCard = {
    card_key: "",
    source_question_number: null,
    question: "",
    short_answer: "",
    detailed_answer: "",
    scenario: "初次拜访",
    category: "产品能力",
    customer_intent: "",
    key_points: [],
    evidence_cases: [],
    forbidden_claims: ["不得把历史案例效果直接承诺给当前客户。"],
    escalation_required: false,
    difficulty_level: "newcomer",
    tags: [],
    duplicate_group_key: null,
    status: "published",
};

function topicFromConfig(config: NewcomerLearningTopicsConfigResponse | null) {
    return config?.payload.topics.find((topic) => topic.topic_key === TOPIC_KEY) ?? null;
}

function uniqueValues(cards: readonly CustomerFaqCard[], key: "scenario" | "category") {
    return Array.from(new Set(cards.map((card) => card[key]).filter(Boolean))).sort();
}

function commaList(value: readonly string[] | undefined): string {
    return (value ?? []).join("、");
}

function parseList(value: string): string[] {
    return value.split(/[、,\n]/).map((item) => item.trim()).filter(Boolean);
}

function nextCardKey(cards: readonly CustomerFaqCard[]) {
    const maxNumber = cards.reduce((max, card) => {
        const match = card.card_key.match(/(\d+)$/);
        return Math.max(max, match ? Number(match[1]) : 0);
    }, 0);
    return `customer_faq_custom_${String(maxNumber + 1).padStart(3, "0")}`;
}

function cardRiskBadge(card: CustomerFaqCard) {
    if (card.escalation_required || card.difficulty_level === "high_risk") {
        return <Badge variant="orange">需售前确认</Badge>;
    }
    if (card.difficulty_level === "advanced") {
        return <Badge variant="outline">进阶</Badge>;
    }
    return <Badge variant="green">新人必会</Badge>;
}

export default function CustomerFaqLearningTopicAdminPage() {
    const toast = useToast();
    const [config, setConfig] = useState<NewcomerLearningTopicsConfigResponse | null>(null);
    const [revisions, setRevisions] = useState<NewcomerLearningTopicRevisionSummary[]>([]);
    const [preview, setPreview] = useState<NewcomerLearningTopicsPreviewResponse | null>(null);
    const [parsePreview, setParsePreview] = useState<CustomerFaqImportParseResponse | null>(null);
    const [rawText, setRawText] = useState("");
    const [query, setQuery] = useState("");
    const [scenarioFilter, setScenarioFilter] = useState("");
    const [categoryFilter, setCategoryFilter] = useState("");
    const [riskFilter, setRiskFilter] = useState<"all" | "risk" | "normal">("all");
    const [selectedCardKey, setSelectedCardKey] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const topic = useMemo(() => topicFromConfig(config), [config]);
    const cards = useMemo(() => [...(topic?.faq_cards ?? [])], [topic]);
    const selectedCard = cards.find((card) => card.card_key === selectedCardKey) ?? null;
    const scenarioOptions = useMemo(() => uniqueValues(cards, "scenario"), [cards]);
    const categoryOptions = useMemo(() => uniqueValues(cards, "category"), [cards]);
    const filteredCards = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        return cards.filter((card) => {
            if (scenarioFilter && card.scenario !== scenarioFilter) return false;
            if (categoryFilter && card.category !== categoryFilter) return false;
            if (riskFilter === "risk" && !card.escalation_required && card.difficulty_level !== "high_risk") return false;
            if (riskFilter === "normal" && (card.escalation_required || card.difficulty_level === "high_risk")) return false;
            if (!normalizedQuery) return true;
            return [
                card.question,
                card.short_answer,
                card.detailed_answer,
                card.category,
                card.scenario,
                ...card.tags,
            ].some((value) => value.toLowerCase().includes(normalizedQuery));
        });
    }, [cards, categoryFilter, query, riskFilter, scenarioFilter]);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [topicConfig, revisionResponse] = await Promise.all([
                api.admin.newcomerTraining.getLearningTopicsConfig(),
                api.admin.newcomerTraining.listLearningTopicsRevisions(),
            ]);
            setConfig(topicConfig);
            setRevisions([...revisionResponse.items]);
            setPreview(null);
        } catch (loadError) {
            setConfig(null);
            setRevisions([]);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    async function parseMaterial() {
        if (!rawText.trim()) {
            toast.error("请先粘贴客户常见问答材料。");
            return;
        }
        setIsSubmitting(true);
        try {
            const result = await api.admin.newcomerTraining.parseCustomerFaqMaterial({ raw_text: rawText });
            setParsePreview(result);
            toast.success(`已解析 ${result.total_questions} 个问题`);
        } catch (parseError) {
            toast.error(getApiErrorMessage(parseError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function generateDraft(overwriteWorking: boolean) {
        if (!rawText.trim()) {
            toast.error("请先粘贴客户常见问答材料。");
            return;
        }
        setIsSubmitting(true);
        try {
            const response = await api.admin.newcomerTraining.generateCustomerFaqLearningTopicDraft({
                raw_text: rawText,
                overwrite_working: overwriteWorking,
                reason: overwriteWorking ? "覆盖生成客户常见问答专题草稿" : "生成客户常见问答专题草稿",
            });
            setConfig(response);
            setPreview(null);
            const nextTopic = topicFromConfig(response);
            setSelectedCardKey(nextTopic?.faq_cards?.[0]?.card_key ?? null);
            toast.success("已生成客户常见问答专题草稿");
            await load();
        } catch (generateError) {
            toast.error(getApiErrorMessage(generateError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function saveTopic(nextTopic: NewcomerLearningTopicConfig, reason: string) {
        if (!config) return;
        setIsSubmitting(true);
        try {
            const existingTopics = config.payload.topics.filter((item) => item.topic_key !== TOPIC_KEY);
            const response = await api.admin.newcomerTraining.saveLearningTopicsConfig({
                schema_version: config.payload.schema_version,
                topics: [...existingTopics, nextTopic].sort((left, right) => left.order_index - right.order_index),
                reason,
            });
            setConfig(response);
            setPreview(null);
            toast.success("已保存为学习专题草稿");
        } catch (saveError) {
            toast.error(getApiErrorMessage(saveError));
        } finally {
            setIsSubmitting(false);
        }
    }

    function ensureTopic(): NewcomerLearningTopicConfig | null {
        if (!topic) {
            toast.error("请先导入材料生成客户常见问答专题草稿。");
            return null;
        }
        return topic;
    }

    async function updateCard(cardKey: string, patch: Partial<CustomerFaqCard>) {
        const currentTopic = ensureTopic();
        if (!currentTopic) return;
        await saveTopic({
            ...currentTopic,
            faq_cards: (currentTopic.faq_cards ?? []).map((card) => (
                card.card_key === cardKey ? { ...card, ...patch } : card
            )),
        }, "更新客户常见问答卡片");
    }

    async function addCard() {
        const currentTopic = ensureTopic();
        if (!currentTopic) return;
        const card: CustomerFaqCard = {
            ...EMPTY_CARD,
            card_key: nextCardKey(currentTopic.faq_cards ?? []),
        };
        await saveTopic({
            ...currentTopic,
            faq_cards: [card, ...(currentTopic.faq_cards ?? [])],
        }, "新增客户常见问答卡片");
        setSelectedCardKey(card.card_key);
    }

    async function publishPreview() {
        setIsSubmitting(true);
        try {
            const result = await api.admin.newcomerTraining.previewLearningTopicsPublish();
            setPreview(result);
            toast.success("已生成发布预览");
        } catch (previewError) {
            toast.error(getApiErrorMessage(previewError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function publish() {
        setIsSubmitting(true);
        try {
            const response = await api.admin.newcomerTraining.publishLearningTopicsConfig({
                reason: "发布客户常见问答学习专题",
            });
            setConfig(response);
            setPreview(null);
            await load();
            toast.success("客户常见问答专题已发布");
        } catch (publishError) {
            toast.error(getApiErrorMessage(publishError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function rollback(revisionId: string) {
        setIsSubmitting(true);
        try {
            const response = await api.admin.newcomerTraining.rollbackLearningTopicsConfig({
                revision_id: revisionId,
                reason: "回滚客户常见问答学习专题",
            });
            setConfig(response);
            setPreview(null);
            await load();
            toast.success("学习专题已回滚");
        } catch (rollbackError) {
            toast.error(getApiErrorMessage(rollbackError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="客户常见问答"
                    description="用问答卡片库治理客户常见问题、风险口径、案例依据、小单元、AI 教练和口播演练。"
                    primaryAction={(
                        <Button onClick={() => void generateDraft(false)} disabled={isSubmitting || !rawText.trim()}>
                            <UploadCloud className="mr-2 h-4 w-4" />
                            生成专题草稿
                        </Button>
                    )}
                    secondaryActions={(
                        <div className="flex flex-wrap gap-2">
                            <Button asChild variant="outline">
                                <Link href="/admin/sales-trainer/learning-topics">
                                    <ArrowLeft className="mr-2 h-4 w-4" />
                                    返回专题
                                </Link>
                            </Button>
                            <Button variant="outline" onClick={() => void load()} disabled={isLoading}>
                                <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                                刷新
                            </Button>
                        </div>
                    )}
                />
            )}
        >
            {error ? (
                <GlassCard className="border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-700">
                    {error}
                </GlassCard>
            ) : null}

            <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
                <GlassCard className="space-y-4 p-5">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-black text-slate-900">材料导入与解析</h2>
                            <p className="mt-1 text-sm leading-6 text-slate-500">
                                粘贴客户常见问答材料后先解析预览，再生成学习专题草稿。草稿不会影响前台，发布后才显示。
                            </p>
                        </div>
                        <Badge variant={config?.has_unpublished_revision ? "orange" : "gray"}>
                            {config?.has_unpublished_revision ? "有未发布草稿" : "无未发布草稿"}
                        </Badge>
                    </div>
                    <textarea
                        className="min-h-56 w-full rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-6 outline-none focus:border-slate-400"
                        value={rawText}
                        onChange={(event) => setRawText(event.target.value)}
                        placeholder="粘贴“客户常见100问”材料..."
                    />
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => void parseMaterial()} disabled={isSubmitting || !rawText.trim()}>
                            <FileText className="mr-2 h-4 w-4" />
                            解析预览
                        </Button>
                        <Button onClick={() => void generateDraft(false)} disabled={isSubmitting || !rawText.trim()}>
                            生成草稿
                        </Button>
                        <Button variant="outline" onClick={() => void generateDraft(true)} disabled={isSubmitting || !rawText.trim()}>
                            覆盖草稿
                        </Button>
                    </div>
                    {parsePreview ? (
                        <div className="grid gap-3 md:grid-cols-4">
                            <div className="rounded-xl bg-slate-50 p-3">
                                <p className="text-xs text-slate-500">解析问题</p>
                                <p className="mt-1 text-xl font-black text-slate-900">{parsePreview.total_questions}</p>
                            </div>
                            <div className="rounded-xl bg-slate-50 p-3">
                                <p className="text-xs text-slate-500">重复组</p>
                                <p className="mt-1 text-xl font-black text-slate-900">{parsePreview.duplicate_groups.length}</p>
                            </div>
                            <div className="rounded-xl bg-amber-50 p-3">
                                <p className="text-xs text-amber-700">高风险</p>
                                <p className="mt-1 text-xl font-black text-amber-950">{parsePreview.high_risk_count}</p>
                            </div>
                            <div className="rounded-xl bg-slate-50 p-3">
                                <p className="text-xs text-slate-500">案例块</p>
                                <p className="mt-1 text-xl font-black text-slate-900">{parsePreview.evidence_cases.length}</p>
                            </div>
                        </div>
                    ) : null}
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                    <h2 className="text-lg font-black text-slate-900">发布治理</h2>
                    <div className="space-y-2 text-sm text-slate-600">
                        <p>active revision：{config?.active_revision_no ? `#${config.active_revision_no}` : "未发布"}</p>
                        <p>working revision：{config?.working_revision_no ? `#${config.working_revision_no}` : "无草稿"}</p>
                        <p>前台展示：{topic?.enabled ? "启用后按发布版本显示" : "未启用或未配置"}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => void publishPreview()} disabled={isSubmitting || !config?.has_unpublished_revision}>
                            <ShieldAlert className="mr-2 h-4 w-4" />
                            发布预览
                        </Button>
                        <Button onClick={() => void publish()} disabled={isSubmitting || !config?.has_unpublished_revision}>
                            <CheckCircle2 className="mr-2 h-4 w-4" />
                            发布
                        </Button>
                    </div>
                    {preview ? (
                        <div className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                            <p className="font-bold text-slate-900">风险等级：{preview.risk_level}</p>
                            <p>影响后续学员：{preview.future_only ? "是" : "否"}</p>
                            <p>历史记录改写：{preview.impact_scope?.historical_attempts_changed ? "是" : "否"}</p>
                        </div>
                    ) : null}
                    <div className="space-y-2">
                        <p className="text-sm font-bold text-slate-900">历史版本</p>
                        {revisions.slice(0, 5).map((revision) => (
                            <div key={revision.revision_id} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 text-sm">
                                <span>#{revision.revision_no} {revision.status === "published" ? "已发布" : revision.status}</span>
                                {revision.status === "published" && !revision.is_active ? (
                                    <button
                                        className="inline-flex items-center gap-1 font-semibold text-slate-700 hover:text-slate-950"
                                        type="button"
                                        onClick={() => void rollback(revision.revision_id)}
                                        disabled={isSubmitting}
                                    >
                                        <RotateCcw className="h-3.5 w-3.5" />
                                        回滚
                                    </button>
                                ) : null}
                            </div>
                        ))}
                    </div>
                </GlassCard>
            </section>

            <section className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                <GlassCard className="space-y-4 p-5">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div>
                            <h2 className="text-lg font-black text-slate-900">问答卡片库</h2>
                            <p className="mt-1 text-sm text-slate-500">搜索、筛选、标记风险、归档和快速新增。</p>
                        </div>
                        <Button variant="outline" onClick={() => void addCard()} disabled={!topic || isSubmitting}>
                            <Plus className="mr-2 h-4 w-4" />
                            新增卡片
                        </Button>
                    </div>
                    <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_160px_160px_140px]">
                        <label className="relative block">
                            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                            <Input value={query} onChange={(event) => setQuery(event.target.value)} className="pl-9" placeholder="搜索问题、答案、标签" />
                        </label>
                        <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={scenarioFilter} onChange={(event) => setScenarioFilter(event.target.value)}>
                            <option value="">全部场景</option>
                            {scenarioOptions.map((scenario) => <option key={scenario} value={scenario}>{scenario}</option>)}
                        </select>
                        <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                            <option value="">全部分类</option>
                            {categoryOptions.map((category) => <option key={category} value={category}>{category}</option>)}
                        </select>
                        <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={riskFilter} onChange={(event) => setRiskFilter(event.target.value as typeof riskFilter)}>
                            <option value="all">全部风险</option>
                            <option value="risk">需确认</option>
                            <option value="normal">普通</option>
                        </select>
                    </div>
                    <div className="max-h-[640px] space-y-3 overflow-auto pr-1">
                        {filteredCards.length === 0 ? (
                            <div className="rounded-xl bg-slate-50 p-5 text-sm text-slate-500">暂无匹配卡片。</div>
                        ) : filteredCards.map((card) => (
                            <button
                                key={card.card_key}
                                className={`w-full rounded-xl border p-4 text-left transition ${selectedCardKey === card.card_key ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-white hover:border-slate-300"}`}
                                type="button"
                                onClick={() => setSelectedCardKey(card.card_key)}
                            >
                                <div className="flex flex-wrap items-center gap-2">
                                    <Badge variant={card.status === "published" ? "green" : card.status === "archived" ? "gray" : "outline"}>
                                        {card.status === "published" ? "已发布" : card.status === "archived" ? "已归档" : "草稿"}
                                    </Badge>
                                    {cardRiskBadge(card)}
                                    <Badge variant="outline">{card.scenario}</Badge>
                                    <Badge variant="outline">{card.category}</Badge>
                                </div>
                                <p className="mt-3 font-bold leading-6 text-slate-900">{card.question}</p>
                                <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500">{card.short_answer}</p>
                            </button>
                        ))}
                    </div>
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                    <h2 className="text-lg font-black text-slate-900">卡片编辑</h2>
                    {!selectedCard ? (
                        <div className="rounded-xl bg-slate-50 p-6 text-sm text-slate-500">
                            请选择左侧卡片。编辑后会保存为学习专题草稿，发布前不会影响学员。
                        </div>
                    ) : (
                        <CardEditor
                            card={selectedCard}
                            isSubmitting={isSubmitting}
                            onChange={(patch) => void updateCard(selectedCard.card_key, patch)}
                        />
                    )}
                </GlassCard>
            </section>

            <section className="grid gap-4 xl:grid-cols-3">
                <GlassCard className="space-y-3 p-5">
                    <h2 className="text-lg font-black text-slate-900">小单元配置</h2>
                    {(topic?.learning_units ?? []).map((unit) => (
                        <div key={unit.unit_key} className="rounded-xl bg-slate-50 p-3">
                            <p className="font-bold text-slate-900">{unit.order_index}. {unit.title}</p>
                            <p className="mt-1 text-sm text-slate-500">绑定卡片 {unit.source_card_keys?.length ?? 0} 张，小测 {unit.quiz_question_count} 题。</p>
                        </div>
                    ))}
                    {!topic ? <p className="text-sm text-slate-500">生成草稿后自动创建 8 个推荐单元。</p> : null}
                </GlassCard>
                <GlassCard className="space-y-3 p-5">
                    <h2 className="text-lg font-black text-slate-900">重复与风险提示</h2>
                    {(topic?.duplicate_groups ?? []).slice(0, 8).map((group) => (
                        <div key={group.group_key} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                            <p className="font-bold">{group.title}</p>
                            <p className="mt-1">{group.reason}</p>
                        </div>
                    ))}
                    {!topic?.duplicate_groups?.length ? <p className="text-sm text-slate-500">导入后会展示重复项提示。</p> : null}
                </GlassCard>
                <GlassCard className="space-y-3 p-5">
                    <h2 className="text-lg font-black text-slate-900">配套训练</h2>
                    <div className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                        <p>AI 教练：{topic?.ai_coach?.enabled ? "已启用" : "未启用"}</p>
                        <p>口播演练：{topic?.audio_scenario_key || "customer_faq_oral_drill"}</p>
                        <p>题库/考卷：{topic?.quiz_paper_id ? "已绑定" : "待快速生成或绑定"}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button asChild variant="outline">
                            <Link href="/admin/sales-trainer/learning-topics/questions">管理题目</Link>
                        </Button>
                        <Button asChild variant="outline">
                            <Link href="/admin/sales-trainer/audio/customer-faq-oral-drill">录音管理</Link>
                        </Button>
                    </div>
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                        <div className="flex gap-2">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                            <p>高风险卡片必须保留“需售前确认”和禁说项，不能把历史案例当成当前客户承诺。</p>
                        </div>
                    </div>
                </GlassCard>
            </section>
        </AdminIndexShell>
    );
}

function CardEditor({
    card,
    isSubmitting,
    onChange,
}: {
    readonly card: CustomerFaqCard;
    readonly isSubmitting: boolean;
    readonly onChange: (patch: Partial<CustomerFaqCard>) => void;
}) {
    const [draft, setDraft] = useState(card);

    useEffect(() => {
        setDraft(card);
    }, [card]);

    function patch(next: Partial<CustomerFaqCard>) {
        setDraft((current) => ({ ...current, ...next }));
    }

    return (
        <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                    场景
                    <Input value={draft.scenario} onChange={(event) => patch({ scenario: event.target.value })} />
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                    分类
                    <Input value={draft.category} onChange={(event) => patch({ category: event.target.value })} />
                </label>
            </div>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
                客户问题
                <Input value={draft.question} onChange={(event) => patch({ question: event.target.value })} />
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
                30 秒答法
                <textarea className="min-h-24 w-full rounded-xl border border-slate-200 p-3 text-sm leading-6" value={draft.short_answer} onChange={(event) => patch({ short_answer: event.target.value })} />
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
                详细答法
                <textarea className="min-h-36 w-full rounded-xl border border-slate-200 p-3 text-sm leading-6" value={draft.detailed_answer} onChange={(event) => patch({ detailed_answer: event.target.value })} />
            </label>
            <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                    必讲要点
                    <textarea className="min-h-24 w-full rounded-xl border border-slate-200 p-3 text-sm leading-6" value={commaList(draft.key_points)} onChange={(event) => patch({ key_points: parseList(event.target.value) })} />
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                    禁说/边界
                    <textarea className="min-h-24 w-full rounded-xl border border-slate-200 p-3 text-sm leading-6" value={commaList(draft.forbidden_claims)} onChange={(event) => patch({ forbidden_claims: parseList(event.target.value) })} />
                </label>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                    难度
                    <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={draft.difficulty_level} onChange={(event) => patch({ difficulty_level: event.target.value as CustomerFaqCard["difficulty_level"] })}>
                        <option value="newcomer">新人</option>
                        <option value="advanced">进阶</option>
                        <option value="high_risk">高风险</option>
                    </select>
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                    状态
                    <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm" value={draft.status} onChange={(event) => patch({ status: event.target.value as CustomerFaqCard["status"] })}>
                        <option value="published">已发布</option>
                        <option value="draft">草稿</option>
                        <option value="archived">归档</option>
                    </select>
                </label>
                <label className="flex items-center gap-2 pt-7 text-sm font-semibold text-slate-700">
                    <input type="checkbox" checked={draft.escalation_required} onChange={(event) => patch({ escalation_required: event.target.checked })} />
                    需售前确认
                </label>
            </div>
            <div className="flex flex-wrap gap-2">
                <Button onClick={() => onChange(draft)} disabled={isSubmitting}>
                    保存卡片
                </Button>
                <Button variant="outline" onClick={() => onChange({ status: "archived" })} disabled={isSubmitting}>
                    归档
                </Button>
            </div>
        </div>
    );
}
