"use client";

import Link from "next/link";
import { ArrowLeft, BookOpen } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";

export default function SalesTrainerLearnHubPage() {
    return (
        <div className="space-y-6 pb-20">
            <Link
                href="/sales-trainer"
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
            >
                <ArrowLeft className="h-4 w-4" />
                返回新人训练路径
            </Link>

            <div>
                <h1 className="text-3xl font-black tracking-tight text-slate-900">商务技巧</h1>
                <p className="mt-1 text-sm text-slate-500">
                    阅读见客户前商务礼仪文章，完成学习后进入对应商务技巧考卷。
                </p>
            </div>

            <GlassCard className="space-y-4 p-6">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">商务技巧学习入口已升级</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                        现在统一从后台配置的 Markdown 章节读取学习内容，并在完成全部章节后进入商务技巧考试。
                    </p>
                </div>
                <Button asChild variant="outline" className="rounded-full">
                    <Link href="/sales-trainer/business-skills">
                        <BookOpen className="mr-2 h-4 w-4" />
                        进入商务技巧学习
                    </Link>
                </Button>
            </GlassCard>
        </div>
    );
}
