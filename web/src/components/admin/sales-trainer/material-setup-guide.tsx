"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";

interface MaterialSetupGuideProps {
    readonly moduleKey: string | null;
}

const MODULE_COPY: Readonly<Record<string, { readonly title: string; readonly pathHref: string }>> = {
    ppt_explanation: {
        title: "PPT 讲解录音材料配置",
        pathHref: "/admin/sales-trainer/paths?module=ppt_explanation",
    },
    elevator_pitch: {
        title: "电梯演讲材料配置",
        pathHref: "/admin/sales-trainer/paths?module=elevator_pitch",
    },
};

export function MaterialSetupGuide({ moduleKey }: MaterialSetupGuideProps) {
    const copy = moduleKey ? MODULE_COPY[moduleKey] : undefined;
    if (!copy) {
        return null;
    }
    return (
        <GlassCard className="space-y-4 border-blue-100 bg-blue-50/70 p-6">
            <div>
                <p className="text-xs font-bold uppercase text-blue-500">来自配置诊断</p>
                <h2 className="mt-1 text-xl font-black text-slate-900">{copy.title}</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                    材料库负责创建材料和发布版本；发布后回到新人训练路径配置中心，保存并发布新的路径绑定修订。
                </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
                <StepCard title="1. 新建材料主档" detail="先创建长期材料档案，例如公司主胶片或电梯演讲模板。" />
                <StepCard title="2. 上传文件生成材料版本" detail="选择 PPT 或文档，系统自动记录文件名、大小和存储位置，先生成草稿版本。" />
                <StepCard title="3. 回到路径配置中心发布绑定" detail="在对应关卡选择已发布材料，保存为待发布修订并发布生效。" />
            </div>
            <Button asChild variant="outline" className="rounded-full">
                <Link href={copy.pathHref}>
                    去路径配置中心发布绑定
                </Link>
            </Button>
        </GlassCard>
    );
}

function StepCard({ title, detail }: { readonly title: string; readonly detail: string }) {
    return (
        <div className="rounded-2xl border border-blue-100 bg-white/80 p-4">
            <p className="font-bold text-slate-900">{title}</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">{detail}</p>
        </div>
    );
}
