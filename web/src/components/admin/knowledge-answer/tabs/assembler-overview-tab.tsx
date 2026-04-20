"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import {
    FileText,
    ListChecks,
    BookOpen,
    AlignLeft,
} from "lucide-react";

const ASSEMBLER_STEPS = [
    {
        icon: FileText,
        label: "组合引用来源",
        description: "将检索结果中的多个引用片段组合，生成结构化回答",
    },
    {
        icon: ListChecks,
        label: "提取 snippet",
        description: "提取检索结果中的 snippet 作为支持证据",
    },
    {
        icon: BookOpen,
        label: "提取 content",
        description: "提取 content 作为补充信息",
    },
    {
        icon: AlignLeft,
        label: "生成证据列表",
        description: "生成编号证据列表作为 final_text",
    },
];

const BLOCKED_TEXT = "当前无法基于知识库证据生成回答，请稍后重试。";

export function AssemblerOverviewTab() {
    return (
        <div className="space-y-4">
            <div>
                <h3 className="text-base font-semibold text-slate-900">输出组装（Assembler）</h3>
                <p className="mt-1 text-sm text-slate-500">
                    组装步骤负责将检索结果转换为最终回答文本。
                </p>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {ASSEMBLER_STEPS.map((step) => {
                    const Icon = step.icon;
                    return (
                        <GlassCard key={step.label} className="p-4 space-y-2">
                            <div className="flex items-center gap-2">
                                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50">
                                    <Icon className="h-4 w-4 text-blue-600" />
                                </div>
                                <span className="text-sm font-medium text-slate-900">
                                    {step.label}
                                </span>
                            </div>
                            <p className="text-xs text-slate-500">{step.description}</p>
                        </GlassCard>
                    );
                })}
            </div>

            <GlassCard className="p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="bg-amber-50 text-amber-700 border-amber-200">
                        被阻断时的默认文案
                    </Badge>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-sm text-slate-700">{BLOCKED_TEXT}</p>
                </div>
            </GlassCard>

            <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
                <p className="text-sm text-blue-800">
                    组装步骤当前无可配置参数。回答格式由 Persona 的系统提示控制。
                </p>
            </div>
        </div>
    );
}
