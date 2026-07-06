"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AlertTriangle, BookOpen, Plus, RefreshCcw } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import {
    CurrentArticleBindingCard,
    PendingArticleBindingCard,
} from "@/components/admin/sales-trainer/article-binding-cards";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    LearningContent,
    NewcomerArticleBinding,
    NewcomerPathConfigResponse,
    SalesTrainerAdminCapabilities,
} from "@/lib/api/types";

const BUSINESS_SKILLS_MODULE_KEY = "business_skills";
const NEWCOMER_PATH_KEY = "newcomer_training_path_v1";
const BUSINESS_SKILLS_CONTENT_SOURCE = "sales_trainer_business_skills";
const SEEDED_NEWCOMER_CONTENT_SOURCE = "seed_newcomer_training_path";

const STATUS_LABELS: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
};

function statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
}

function createBusinessSkillsArticlePayload() {
    return {
        title: "见客户前商务礼仪",
        summary: "新人训练路径商务技巧模块学习文章。",
        owner: "新人训练路径",
        source: BUSINESS_SKILLS_CONTENT_SOURCE,
        safety_flagged: false,
    };
}

function belongsToBusinessSkillsContent(
    item: LearningContent,
    boundContentId: string | null,
): boolean {
    return item.learning_content_id === boundContentId
        || item.source === BUSINESS_SKILLS_CONTENT_SOURCE
        || item.source === SEEDED_NEWCOMER_CONTENT_SOURCE;
}

function boundContentIdFromPathConfig(pathConfig: NewcomerPathConfigResponse): string | null {
    return pathConfig.path.modules.find(
        (module) => module.module_key === BUSINESS_SKILLS_MODULE_KEY,
    )?.learning_content_id ?? null;
}

function articleBindingActionLabel(
    contentId: string,
    boundContentId: string | null,
    pendingBinding: NewcomerArticleBinding | null,
): string {
    if (contentId === boundContentId) {
        return "当前生效";
    }
    if (contentId === pendingBinding?.learning_content_id) {
        return "待发布路径修订";
    }
    return "保存为待发布绑定";
}

export default function NewcomerArticleBindingPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [items, setItems] = useState<LearningContent[]>([]);
    const [boundContentId, setBoundContentId] = useState<string | null>(null);
    const [pendingBinding, setPendingBinding] = useState<NewcomerArticleBinding | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [capabilities, setCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessArticles = isSalesTrainerAdminPathAllowedForCapabilities(pathname, capabilities);

    const boundContent = useMemo(
        () => items.find((item) => item.learning_content_id === boundContentId) ?? null,
        [boundContentId, items],
    );
    const pendingContent = useMemo(
        () => items.find((item) => item.learning_content_id === pendingBinding?.learning_content_id) ?? null,
        [items, pendingBinding],
    );
    const visibleItems = useMemo(
        () => items.filter((item) => belongsToBusinessSkillsContent(item, boundContentId)),
        [boundContentId, items],
    );

    const load = useCallback(async () => {
        if (!canAccessArticles) {
            return;
        }
        setIsLoading(true);
        setError(null);
        setPendingBinding(null);
        try {
            const [contents, pathConfig] = await Promise.all([
                api.learningContents.list(),
                api.admin.newcomerTraining.getPathConfig(),
            ]);
            setItems(contents.items);
            const nextBoundContentId = boundContentIdFromPathConfig(pathConfig);
            setBoundContentId(nextBoundContentId);
            if (
                nextBoundContentId
                && !contents.items.some((item) => item.learning_content_id === nextBoundContentId)
            ) {
                setError(`当前路径配置绑定的商务技巧文章不在内容列表中：${nextBoundContentId}`);
            }
        } catch (loadError) {
            setItems([]);
            setBoundContentId(null);
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
            .catch((error) => {
                if (!isCurrent) return;
                setCapabilities(null);
                setCapabilityError(getApiErrorMessage(error));
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
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessArticles) {
            setItems([]);
            setBoundContentId(null);
            setPendingBinding(null);
            setError(null);
            setIsLoading(false);
            return;
        }
        void load();
    }, [canAccessArticles, isCapabilityLoading, load]);

    async function bindContent(content: LearningContent) {
        if (content.status !== "published") {
            toast.error("只能绑定已发布文章。请先进入内容详情完成发布。");
            return;
        }
        setIsSubmitting(true);
        try {
            const result = await api.admin.newcomerTraining.bindModuleArticle(
                BUSINESS_SKILLS_MODULE_KEY,
                {
                    learning_content_id: content.learning_content_id,
                    path_key: NEWCOMER_PATH_KEY,
                    reason: "更新商务技巧学习文章绑定",
                },
            );
            setPendingBinding(result);
            toast.success("已保存为待发布路径修订");
        } catch (bindError) {
            if (bindError instanceof Error) {
                toast.error(getApiErrorMessage(bindError));
            } else {
                throw bindError;
            }
        } finally {
            setIsSubmitting(false);
        }
    }

    async function createArticle() {
        setIsCreating(true);
        try {
            const created = await api.learningContents.create(createBusinessSkillsArticlePayload());
            toast.success("已创建商务技巧文章草稿");
            router.push(`/admin/learning-contents/${created.learning_content_id}`);
        } catch (createError) {
            if (createError instanceof Error) {
                toast.error(getApiErrorMessage(createError));
            } else {
                throw createError;
            }
        } finally {
            setIsCreating(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="商务技巧文章"
                    description="管理学习页展示的 Markdown 文章与章节；章节数量可随时扩展，不改变新人训练路径外层模块。"
                    primaryAction={canAccessArticles ? (
                        <Button className="rounded-full bg-slate-900 text-white" onClick={() => void createArticle()} disabled={isCreating}>
                            <Plus className="mr-2 h-4 w-4" />
                            新建商务技巧文章
                        </Button>
                    ) : null}
                    secondaryActions={(
                        <div className="flex flex-wrap gap-2">
                            {canAccessArticles ? (
                            <Button variant="outline" className="rounded-full" onClick={() => void load()} disabled={isLoading}>
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
                <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                    正在校验文章管理权限...
                </div>
            ) : capabilityError || !canAccessArticles ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div>
                            <h2 className="font-bold text-amber-950">文章管理权限不足</h2>
                            <p className="mt-1 text-sm leading-6">
                                当前页不会在权限未确认时展示文章写入入口。请联系管理员开通内容管理权限后重试。
                            </p>
                            {capabilityError ? (
                                <p className="mt-2 text-sm font-medium">{capabilityError}</p>
                            ) : null}
                        </div>
                    </div>
                </div>
            ) : null}
            {error ? <GlassCard className="p-4 text-sm font-medium text-red-700">{error}</GlassCard> : null}

            {pendingBinding && pendingContent ? (
                <PendingArticleBindingCard binding={pendingBinding} content={pendingContent} />
            ) : null}

            {boundContent ? (
                <CurrentArticleBindingCard content={boundContent} statusLabel={statusLabel(boundContent.status)} />
            ) : null}

            {canAccessArticles ? (
            <GlassCard className="overflow-hidden">
                <div className="border-b border-slate-100 px-6 py-4">
                    <h2 className="text-lg font-bold text-slate-900">可绑定学习内容</h2>
                    <p className="mt-1 text-sm text-slate-500">在内容详情中维护第一节、第二节、第三节及图片 Markdown，发布后即可绑定到商务技巧学习页。</p>
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
                                    <Button asChild variant="outline" className="rounded-full">
                                        <Link href={`/admin/learning-contents/${item.learning_content_id}`}>
                                            编辑章节
                                        </Link>
                                    </Button>
                                    <Button
                                        className="rounded-full bg-slate-900 text-white"
                                        disabled={
                                            isSubmitting
                                            || item.status !== "published"
                                            || item.learning_content_id === boundContentId
                                            || item.learning_content_id === pendingBinding?.learning_content_id
                                        }
                                        onClick={() => void bindContent(item)}
                                    >
                                        {articleBindingActionLabel(item.learning_content_id, boundContentId, pendingBinding)}
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
            ) : null}
        </AdminIndexShell>
    );
}
