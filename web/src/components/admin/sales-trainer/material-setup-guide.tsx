"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import {
    audioEvaluationScenarioForModule,
    isAudioEvaluationModuleKey,
} from "@/lib/sales-trainer/audio-evaluation-scenarios";

interface MaterialSetupGuideProps {
    readonly moduleKey: string | null;
}

export function MaterialSetupGuide({ moduleKey }: MaterialSetupGuideProps) {
    if (!isAudioEvaluationModuleKey(moduleKey)) {
        return null;
    }
    const scenario = audioEvaluationScenarioForModule(moduleKey);
    return (
        <GlassCard className="space-y-4 border-blue-100 bg-blue-50/70 p-6">
            <div>
                <p className="text-xs font-bold uppercase text-blue-500">来自配置诊断</p>
                <h2 className="mt-1 text-xl font-black text-slate-900">{scenario.title}材料配置</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                    材料库负责创建材料和发布版本；发布后回到训练任务治理页，保存并发布新的路径绑定修订。
                </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
                <StepCard
                    title="1. 新建材料主档"
                    detail="先创建长期材料档案，例如公司主胶片或金字塔演讲模板。"
                />
                <StepCard
                    title="2. 上传文件生成材料版本"
                    detail="选择 PPT 或文档，系统自动记录文件名、大小和存储位置，先生成草稿版本。"
                />
                <StepCard
                    title="3. 回到训练任务发布绑定"
                    detail="在对应关卡选择已发布材料，保存为待发布修订并发布生效。"
                />
            </div>
            <Button asChild variant="outline" className="rounded-full">
                <Link href={`/admin/sales-trainer/training-tasks/${scenario.slug}`}>去训练任务治理页发布绑定</Link>
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
