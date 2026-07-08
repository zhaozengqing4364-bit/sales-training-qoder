"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { AlertTriangle, ArrowRight, BookOpen, RefreshCcw, UploadCloud } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    LearningContent,
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicsConfigResponse,
    SalesTrainerAdminCapabilities,
} from "@/lib/api/types";

const BUSINESS_ETIQUETTE_DETAIL_PATH = "/admin/sales-trainer/articles/business-etiquette";

function statusLabel(status: string): string {
    if (status === "published") return "已发布";
    if (status === "draft") return "草稿";
    if (status === "archived") return "已归档";
    return status;
}

function topicStatusLabel(topic: NewcomerLearningTopicConfig): string {
    if (!topic.enabled) return "已停用";
    if (!topic.learning_content_id) return "待绑定文章";
    if (topic.learning_units.length === 0) return "待配置小单元";
    return "可发布";
}

export default function LearningArticlesPage() {
    const pathname = usePathname();
    const toast = useToast();
    const [contents, setContents] = useState<LearningContent[]>([]);
    const [config, setConfig] = useState<NewcomerLearningTopicsConfigResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [capabilities, setCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessArticles = isSalesTrainerAdminPathAllowedForCapabilities(pathname, capabilities);

    const topics = useMemo(
        () => [...(config?.payload.topics ?? [])].sort((left, right) => left.order_index - right.order_index),
        [config],
    );
    const contentsById = useMemo(
        () => new Map(contents.map((item) => [item.learning_content_id, item])),
        [contents],
    );

    const load = useCallback(async () => {
        if (!canAccessArticles) return;
        setIsLoading(true);
        setError(null);
        try {
            const [contentResponse, topicConfig] = await Promise.all([
                api.learningContents.list(),
                api.admin.newcomerTraining.getLearningTopicsConfig(),
            ]);
            setContents(contentResponse.items);
            setConfig(topicConfig);
        } catch (loadError) {
            setContents([]);
            setConfig(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [canAccessArticles]);

    useEffect(() => {
        let isCurrent = true;
        void api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!isCurrent) return;
                setCapabilities(result);
                setCapabilityError(null);
            })
            .catch((capabilityLoadError) => {
                if (!isCurrent) return;
                setCapabilities(null);
                setCapabilityError(getApiErrorMessage(capabilityLoadError));
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsCapabilityLoading(false);
            });
        return () => {
            isCurrent = false;
        };
    }, []);

    useEffect(() => {
        if (isCapabilityLoading) return;
        if (!canAccessArticles) {
            setContents([]);
            setConfig(null);
            setIsLoading(false);
            return;
        }
        void load();
    }, [canAccessArticles, isCapabilityLoading, load]);

    async function generateDraft(overwriteWorking: boolean) {
        setIsSubmitting(true);
        try {
            const response = await api.admin.newcomerTraining.generateBusinessEtiquetteLearningTopicDraft({
                overwrite_working: overwriteWorking,
                reason: overwriteWorking ? "覆盖生成商务礼仪规范学习专题草稿" : "生成商务礼仪规范学习专题草稿",
            });
            setConfig(response);
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
            const response = await api.admin.newcomerTraining.publishLearningTopicsConfig({
                reason: "发布学习专题配置",
            });
            setConfig(response);
            toast.success("学习专题已发布");
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="学习文章"
                    description="按学习专题管理文章、章节、小单元和非阻塞得分展示；只有后台配置并发布的专题才会在前台出现。"
                    primaryAction={canAccessArticles ? (
                        <Button onClick={() => void generateDraft(false)} disabled={isSubmitting}>
                            <UploadCloud className="mr-2 h-4 w-4" />
                            从路径生成草稿
                        </Button>
                    ) : null}
                    secondaryActions={(
                        <div className="flex flex-wrap gap-2">
                            {canAccessArticles ? (
                                <Button variant="outline" onClick={() => void load()} disabled={isLoading}>
                                    <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                                    刷新
                                </Button>
                            ) : null}
                            <SalesTrainerAdminModuleNav currentPath={pathname} capabilities={capabilities} />
                        </div>
                    )}
                />
            )}
        >
            {isCapabilityLoading ? (
                <GlassCard className="p-5 text-sm text-slate-500">正在校验学习文章管理权限...</GlassCard>
            ) : capabilityError || !canAccessArticles ? (
                <GlassCard className="border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div>
                            <h2 className="font-bold text-amber-950">学习文章管理权限不足</h2>
                            <p className="mt-1 text-sm leading-6">
                                当前页不会在权限未确认时展示写入入口。请联系管理员开通内容管理权限后重试。
                            </p>
                            {capabilityError ? <p className="mt-2 text-sm font-medium">{capabilityError}</p> : null}
                        </div>
                    </div>
                </GlassCard>
            ) : null}

            {error ? <GlassCard className="p-4 text-sm font-medium text-red-700">{error}</GlassCard> : null}

            {canAccessArticles ? (
                <section className="space-y-4">
                    {config?.has_unpublished_revision ? (
                        <GlassCard className="flex flex-col gap-3 border border-amber-200 bg-amber-50 p-4 md:flex-row md:items-center md:justify-between">
                            <div>
                                <p className="font-bold text-amber-950">存在未发布草稿</p>
                                <p className="mt-1 text-sm text-amber-800">发布后才会影响前台学习专题展示，历史小测记录不会被改写。</p>
                            </div>
                            <Button onClick={() => void publish()} disabled={isSubmitting}>
                                发布学习专题
                            </Button>
                        </GlassCard>
                    ) : null}

                    {isLoading ? (
                        <GlassCard className="p-8 text-center text-sm text-slate-500">加载中...</GlassCard>
                    ) : topics.length === 0 ? (
                        <GlassCard className="space-y-4 p-6">
                            <div className="flex items-start gap-3">
                                <BookOpen className="mt-1 h-5 w-5 text-slate-500" />
                                <div>
                                    <h2 className="text-lg font-black text-slate-900">还没有可显示的学习专题</h2>
                                    <p className="mt-1 text-sm leading-6 text-slate-500">
                                        可以先从当前 active path 的 business_skills 模块生成商务礼仪规范草稿，再进入详情补齐文章和 7 个小单元。
                                    </p>
                                </div>
                            </div>
                            <Button onClick={() => void generateDraft(false)} disabled={isSubmitting}>
                                生成商务礼仪规范草稿
                            </Button>
                        </GlassCard>
                    ) : (
                        <div className="grid gap-4 xl:grid-cols-2">
                            {topics.map((topic) => {
                                const content = topic.learning_content_id
                                    ? contentsById.get(topic.learning_content_id)
                                    : null;
                                return (
                                    <GlassCard key={topic.topic_key} className="space-y-4 p-5">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="space-y-2">
                                                <div className="flex flex-wrap gap-2">
                                                    <Badge variant="gray">学习专题</Badge>
                                                    <Badge variant={topic.enabled ? "green" : "secondary"}>
                                                        {topicStatusLabel(topic)}
                                                    </Badge>
                                                    <Badge variant="outline">不阻塞训练路径</Badge>
                                                </div>
                                                <h2 className="text-xl font-black text-slate-900">{topic.title}</h2>
                                                <p className="text-sm leading-6 text-slate-500">
                                                    {topic.description || "管理商务礼仪规范文章、7 个小单元、测验规则和可选 AI 教练。"}
                                                </p>
                                            </div>
                                            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-right">
                                                <p className="text-xs text-slate-500">小单元</p>
                                                <p className="mt-1 text-lg font-black text-slate-900">{topic.learning_units.length}</p>
                                            </div>
                                        </div>
                                        <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
                                            当前文章：{content ? `${content.title}（${statusLabel(content.status)}）` : "未绑定"}
                                        </div>
                                        <Button asChild>
                                            <Link href={BUSINESS_ETIQUETTE_DETAIL_PATH}>
                                                <ArrowRight className="mr-2 h-4 w-4" />
                                                进入专题配置
                                            </Link>
                                        </Button>
                                    </GlassCard>
                                );
                            })}
                        </div>
                    )}
                </section>
            ) : null}
        </AdminIndexShell>
    );
}
