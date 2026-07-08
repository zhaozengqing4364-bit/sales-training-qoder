"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, Plus, RefreshCcw, RotateCcw, ShieldCheck } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    LearningContent,
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicsConfigResponse,
    NewcomerLearningTopicRevisionSummary,
    NewcomerLearningTopicsPreviewResponse,
} from "@/lib/api/types";

const BUSINESS_ETIQUETTE_SOURCE = "sales_trainer_business_etiquette";
const LEGACY_BUSINESS_SKILLS_SOURCE = "sales_trainer_business_skills";

function statusLabel(status: string): string {
    if (status === "published") return "已发布";
    if (status === "draft") return "草稿";
    if (status === "archived") return "已归档";
    return status;
}

function createBusinessEtiquetteArticlePayload() {
    return {
        title: "商务礼仪规范",
        summary: "新人训练路径商务礼仪规范学习文章。",
        owner: "新人训练路径",
        source: BUSINESS_ETIQUETTE_SOURCE,
        safety_flagged: false,
    };
}

function visibleLearningContent(item: LearningContent, boundContentId: string | null): boolean {
    return item.learning_content_id === boundContentId
        || item.source === BUSINESS_ETIQUETTE_SOURCE
        || item.source === LEGACY_BUSINESS_SKILLS_SOURCE
        || item.source === "seed_newcomer_training_path";
}

function topicFromConfig(config: NewcomerLearningTopicsConfigResponse | null): NewcomerLearningTopicConfig | null {
    return config?.payload.topics.find((topic) => topic.topic_key === "business_etiquette") ?? null;
}

export default function BusinessEtiquetteLearningTopicPage() {
    const router = useRouter();
    const toast = useToast();
    const [contents, setContents] = useState<LearningContent[]>([]);
    const [config, setConfig] = useState<NewcomerLearningTopicsConfigResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [preview, setPreview] = useState<NewcomerLearningTopicsPreviewResponse | null>(null);
    const [revisions, setRevisions] = useState<NewcomerLearningTopicRevisionSummary[]>([]);
    const [error, setError] = useState<string | null>(null);

    const topic = useMemo(() => topicFromConfig(config), [config]);
    const boundContentId = topic?.learning_content_id ?? null;
    const visibleItems = useMemo(
        () => contents.filter((item) => visibleLearningContent(item, boundContentId)),
        [boundContentId, contents],
    );
    const boundContent = useMemo(
        () => contents.find((item) => item.learning_content_id === boundContentId) ?? null,
        [boundContentId, contents],
    );

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [contentResponse, topicConfig] = await Promise.all([
                api.learningContents.list(),
                api.admin.newcomerTraining.getLearningTopicsConfig(),
            ]);
            setContents(contentResponse.items);
            setConfig(topicConfig);
            const revisionResponse = await api.admin.newcomerTraining.listLearningTopicsRevisions();
            setRevisions([...revisionResponse.items]);
        } catch (loadError) {
            setContents([]);
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

    async function createArticle() {
        setIsCreating(true);
        try {
            const created = await api.learningContents.create(createBusinessEtiquetteArticlePayload());
            toast.success("已创建商务礼仪规范文章草稿");
            router.push(`/admin/learning-contents/${created.learning_content_id}`);
        } catch (createError) {
            toast.error(getApiErrorMessage(createError));
        } finally {
            setIsCreating(false);
        }
    }

    async function bindContent(content: LearningContent) {
        if (!config || !topic) return;
        if (content.status !== "published") {
            toast.error("只能绑定已发布文章。请先进入内容详情完成发布。");
            return;
        }
        setIsSubmitting(true);
        try {
            const response = await api.admin.newcomerTraining.saveLearningTopicsConfig({
                schema_version: config.payload.schema_version,
                topics: config.payload.topics.map((item) => (
                    item.topic_key === "business_etiquette"
                        ? {
                            ...item,
                            learning_content_id: content.learning_content_id,
                        }
                        : item
                )),
                reason: "更新商务礼仪规范学习文章绑定",
            });
            setConfig(response);
            setPreview(null);
            toast.success("已保存为学习专题待发布草稿");
        } catch (bindError) {
            toast.error(getApiErrorMessage(bindError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function generateDraft(overwriteWorking: boolean) {
        setIsSubmitting(true);
        try {
            const response = await api.admin.newcomerTraining.generateBusinessEtiquetteLearningTopicDraft({
                overwrite_working: overwriteWorking,
                reason: overwriteWorking ? "覆盖生成商务礼仪规范学习专题草稿" : "生成商务礼仪规范学习专题草稿",
            });
            setConfig(response);
            setPreview(null);
            toast.success("已生成商务礼仪规范草稿");
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function publish() {
        setIsSubmitting(true);
        try {
            const impact = await api.admin.newcomerTraining.previewLearningTopicsPublish();
            setPreview(impact);
            const response = await api.admin.newcomerTraining.publishLearningTopicsConfig({
                reason: "发布商务礼仪规范学习专题",
            });
            setConfig(response);
            const revisionResponse = await api.admin.newcomerTraining.listLearningTopicsRevisions();
            setRevisions([...revisionResponse.items]);
            toast.success("商务礼仪规范已发布");
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function previewPublish() {
        setIsSubmitting(true);
        try {
            setPreview(await api.admin.newcomerTraining.previewLearningTopicsPublish());
        } catch (previewError) {
            toast.error(getApiErrorMessage(previewError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function previewRollback(revisionId: string) {
        setIsSubmitting(true);
        try {
            setPreview(await api.admin.newcomerTraining.previewLearningTopicsRollback(revisionId));
        } catch (previewError) {
            toast.error(getApiErrorMessage(previewError));
        } finally {
            setIsSubmitting(false);
        }
    }

    async function rollback(revisionId: string) {
        setIsSubmitting(true);
        try {
            const impact = await api.admin.newcomerTraining.previewLearningTopicsRollback(revisionId);
            setPreview(impact);
            const response = await api.admin.newcomerTraining.rollbackLearningTopicsConfig({
                revision_id: revisionId,
                reason: "回滚商务礼仪规范学习专题",
            });
            setConfig(response);
            const revisionResponse = await api.admin.newcomerTraining.listLearningTopicsRevisions();
            setRevisions([...revisionResponse.items]);
            toast.success("已回滚学习专题配置");
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
                    title="商务礼仪规范"
                    description="配置学习文章、7 个小单元、题目规则和可选 AI 教练。发布后前台才会显示，且不会阻塞后续必修训练。"
                    primaryAction={(
                        <Button onClick={() => void createArticle()} disabled={isCreating}>
                            <Plus className="mr-2 h-4 w-4" />
                            新建学习文章
                        </Button>
                    )}
                    secondaryActions={(
                        <div className="flex flex-wrap gap-2">
                            <Button asChild variant="outline">
                                <Link href="/admin/sales-trainer/articles">
                                    <ArrowLeft className="mr-2 h-4 w-4" />
                                    返回专题列表
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
            {error ? <GlassCard className="p-4 text-sm font-medium text-red-700">{error}</GlassCard> : null}

            {!isLoading && !topic ? (
                <GlassCard className="space-y-4 p-6">
                    <h2 className="text-lg font-black text-slate-900">商务礼仪规范尚未生成</h2>
                    <p className="text-sm leading-6 text-slate-500">
                        先从 active path 的 business_skills 模块生成草稿，再在这里绑定学习文章和维护小单元。
                    </p>
                    <Button onClick={() => void generateDraft(false)} disabled={isSubmitting}>
                        生成草稿
                    </Button>
                </GlassCard>
            ) : null}

            {topic ? (
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
                    <GlassCard className="space-y-4 p-5">
                        <div>
                            <h2 className="text-lg font-black text-slate-900">当前专题配置</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                当前文章：{boundContent ? `${boundContent.title}（${statusLabel(boundContent.status)}）` : "未绑定"}
                            </p>
                        </div>
                        <div className="grid gap-3 sm:grid-cols-3">
                            <div className="rounded-xl bg-slate-50 p-3">
                                <p className="text-xs text-slate-500">小单元</p>
                                <p className="mt-1 text-xl font-black text-slate-900">{topic.learning_units.length}</p>
                            </div>
                            <div className="rounded-xl bg-slate-50 p-3">
                                <p className="text-xs text-slate-500">得分展示</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">小测得分</p>
                            </div>
                            <div className="rounded-xl bg-slate-50 p-3">
                                <p className="text-xs text-slate-500">阻塞路径</p>
                                <p className="mt-1 text-sm font-bold text-slate-900">否</p>
                            </div>
                        </div>
                        {config?.has_unpublished_revision ? (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                                当前存在未发布草稿。发布后才会影响前台展示，历史小测记录不会被改写。
                            </div>
                        ) : null}
                        {preview ? (
                            <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
                                <div className="flex items-start gap-2">
                                    <ShieldCheck className="mt-0.5 h-4 w-4" />
                                    <div>
                                        <p className="font-bold">
                                            {preview.action === "newcomer_learning_topics.publish" ? "发布预览" : "回滚预览"}
                                            ：版本 {preview.target_revision_no}
                                        </p>
                                        <p className="mt-1">
                                            风险等级 {preview.risk_level} · 仅影响未来前台展示，不改写历史小测记录。
                                        </p>
                                        {preview.risk_reasons.length ? (
                                            <p className="mt-1">{preview.risk_reasons.join("；")}</p>
                                        ) : null}
                                    </div>
                                </div>
                            </div>
                        ) : null}
                        <div className="flex flex-wrap gap-2">
                            <Button
                                variant="outline"
                                onClick={() => void previewPublish()}
                                disabled={isSubmitting || !config?.has_unpublished_revision}
                            >
                                发布预览
                            </Button>
                            <Button onClick={() => void publish()} disabled={isSubmitting || !config?.has_unpublished_revision}>
                                发布专题配置
                            </Button>
                            <Button variant="outline" onClick={() => void generateDraft(true)} disabled={isSubmitting}>
                                重新从路径覆盖草稿
                            </Button>
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-3 p-5">
                        <h2 className="text-lg font-black text-slate-900">小单元</h2>
                        <div className="space-y-2">
                            {topic.learning_units.map((unit) => (
                                <div key={unit.unit_key} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                                    <p className="font-bold text-slate-900">第 {unit.order_index} 单元：{unit.title}</p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        题数 {unit.quiz_question_count} · 通过线 {unit.quiz_pass_threshold ?? "能力点达标"}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-3 p-5 xl:col-span-2">
                        <h2 className="text-lg font-black text-slate-900">发布历史与回滚</h2>
                        <div className="divide-y divide-slate-100">
                            {revisions.map((revision) => (
                                <div key={revision.revision_id} className="flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between">
                                    <div>
                                        <p className="font-bold text-slate-900">
                                            版本 {revision.revision_no}
                                            {revision.is_active ? " · 当前发布" : ""}
                                            {revision.is_working ? " · 草稿" : ""}
                                        </p>
                                        <p className="mt-1 text-sm text-slate-500">
                                            {revision.reason || "未填写原因"} · {revision.change_class}
                                        </p>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Button
                                            variant="outline"
                                            onClick={() => void previewRollback(revision.revision_id)}
                                            disabled={isSubmitting || revision.is_active || revision.is_working}
                                        >
                                            回滚预览
                                        </Button>
                                        <Button
                                            variant="outline"
                                            onClick={() => void rollback(revision.revision_id)}
                                            disabled={isSubmitting || revision.is_active || revision.is_working}
                                        >
                                            <RotateCcw className="mr-2 h-4 w-4" />
                                            回滚到此版本
                                        </Button>
                                    </div>
                                </div>
                            ))}
                            {revisions.length === 0 ? (
                                <div className="py-4 text-sm text-slate-500">暂无历史版本。</div>
                            ) : null}
                        </div>
                    </GlassCard>
                </div>
            ) : null}

            <GlassCard className="overflow-hidden">
                <div className="border-b border-slate-100 px-6 py-4">
                    <h2 className="text-lg font-bold text-slate-900">可绑定学习内容</h2>
                    <p className="mt-1 text-sm text-slate-500">先在内容详情维护 Markdown 章节，发布后即可绑定到商务礼仪规范。</p>
                </div>
                {isLoading ? (
                    <div className="p-8 text-center text-sm text-slate-500">加载中...</div>
                ) : (
                    <div className="divide-y divide-slate-100">
                        {visibleItems.map((item) => (
                            <div key={item.learning_content_id} className="flex flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
                                <div className="flex items-start gap-3">
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                        <BookOpen className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-slate-900">{item.title}</h3>
                                        <p className="mt-1 text-sm text-slate-500">{item.summary ?? "暂无摘要"}</p>
                                        <div className="mt-2 flex flex-wrap gap-2 text-xs font-medium text-slate-500">
                                            <span>{statusLabel(item.status)}</span>
                                            <span>{item.chapters.length} 节</span>
                                            <span>{item.owner ?? "未设置负责人"}</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Button asChild variant="outline">
                                        <Link href={`/admin/learning-contents/${item.learning_content_id}`}>
                                            编辑章节
                                        </Link>
                                    </Button>
                                    <Button
                                        disabled={
                                            isSubmitting
                                            || item.status !== "published"
                                            || item.learning_content_id === boundContentId
                                            || !topic
                                        }
                                        onClick={() => void bindContent(item)}
                                    >
                                        {item.learning_content_id === boundContentId ? "当前绑定" : "保存为专题草稿"}
                                    </Button>
                                </div>
                            </div>
                        ))}
                        {visibleItems.length === 0 ? (
                            <div className="p-8 text-center text-sm text-slate-500">暂无学习内容，请先新建文章草稿。</div>
                        ) : null}
                    </div>
                )}
            </GlassCard>
        </AdminIndexShell>
    );
}
