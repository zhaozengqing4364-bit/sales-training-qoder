"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import type { LearningContent, NewcomerArticleBinding } from "@/lib/api/types";

interface CurrentArticleBindingCardProps {
    readonly content: LearningContent;
    readonly statusLabel: string;
}

interface PendingArticleBindingCardProps {
    readonly binding: NewcomerArticleBinding;
    readonly content: LearningContent;
}

export function CurrentArticleBindingCard({
    content,
    statusLabel,
}: CurrentArticleBindingCardProps) {
    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                    <p className="text-xs font-bold uppercase text-slate-400">当前生效学习页绑定</p>
                    <h2 className="text-xl font-black text-slate-900">{content.title}</h2>
                    <p className="text-sm text-slate-500">{content.summary ?? "暂无摘要"}</p>
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-slate-500">
                        <span>{statusLabel}</span>
                        <span>{content.chapters.length} 节</span>
                        <span>v{content.version}</span>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href={`/admin/learning-contents/${content.learning_content_id}`}>
                            编辑章节
                            <ExternalLink className="ml-2 h-4 w-4" />
                        </Link>
                    </Button>
                    <Button asChild variant="outline" className="rounded-full">
                        <Link href="/sales-trainer/business-skills">
                            预览学习页
                        </Link>
                    </Button>
                </div>
            </div>
        </GlassCard>
    );
}

export function PendingArticleBindingCard({
    binding,
    content,
}: PendingArticleBindingCardProps) {
    const revisionLabel = binding.working_revision_no
        ? `路径配置 v${binding.working_revision_no}`
        : "路径配置新修订";

    return (
        <GlassCard className="border-emerald-200 bg-emerald-50/80 p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                    <p className="text-xs font-bold uppercase text-emerald-700">待发布路径修订已保存</p>
                    <h2 className="text-xl font-black text-slate-900">{content.title}</h2>
                    <p className="text-sm text-emerald-900">
                        {revisionLabel} 发布后，对后续学员生效；已开始学习或考试的记录继续使用当时快照。
                    </p>
                </div>
                <Button asChild className="rounded-full bg-emerald-700 text-white hover:bg-emerald-800">
                    <Link href="/admin/sales-trainer/paths">去路径配置中心发布</Link>
                </Button>
            </div>
        </GlassCard>
    );
}
