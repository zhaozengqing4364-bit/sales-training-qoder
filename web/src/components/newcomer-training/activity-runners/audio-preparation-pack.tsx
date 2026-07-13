"use client";

import { ExternalLink, FileText, ListChecks, Quote } from "lucide-react";

import type { ActivityRunnerDescriptor } from "@/lib/api/types/newcomer-training";

type AudioRunner = Extract<ActivityRunnerDescriptor, { type: "audio_assessment" }>;

const LEGACY_EXPRESSION_STRUCTURE =
    "建议按四段展开：先说明客户正在面对的问题；再用本次材料中的事实讲清方案；接着结合一个客户场景解释价值；最后确认客户问题并约定下一步。";

interface AudioPreparationPackProps {
    runner: AudioRunner;
    materialUrl: string | null;
    confirmed: boolean;
    disabled?: boolean;
    onConfirmedChange: (confirmed: boolean) => void;
}

function originalFileLabel(runner: AudioRunner): string {
    const isPresentation =
        runner.material_content_type?.includes("presentation") ||
        /\.pptx?$/i.test(runner.material_file_name ?? "");
    return isPresentation
        ? "在新标签页查看 PPT 原文件"
        : "在新标签页查看材料原文件";
}

export function AudioPreparationPack({
    runner,
    materialUrl,
    confirmed,
    disabled,
    onConfirmedChange,
}: AudioPreparationPackProps) {
    const focuses = runner.scoring_focuses ?? [];
    const configuredExample = runner.example_transcript?.trim() || null;

    return (
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <header className="border-b border-slate-100 px-5 py-4 sm:px-6">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
                    讲解前准备
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-950">
                    录音前，先看完这 3 项
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                    材料、评分重点和参考表达都在当前页，确认后即可开始。
                </p>
            </header>

            <div className="divide-y divide-slate-100">
                <div className="grid gap-3 px-5 py-5 sm:grid-cols-[2.25rem_1fr] sm:px-6">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                        <FileText className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-500">1 · 本次材料</p>
                        <h3 className="mt-1 font-semibold text-slate-950">
                            {runner.material_title ?? "本次讲解材料"}
                        </h3>
                        {runner.material_file_name ? (
                            <p className="mt-1 break-all text-sm text-slate-600">
                                {runner.material_file_name}
                            </p>
                        ) : null}
                        {runner.material_version_label ? (
                            <p className="mt-1 text-xs text-slate-500">
                                当前使用 {runner.material_version_label}
                            </p>
                        ) : null}
                        {materialUrl ? (
                            <a
                                href={materialUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                            >
                                {originalFileLabel(runner)}
                                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                            </a>
                        ) : (
                            <p className="mt-2 text-sm text-amber-700">
                                材料原文件暂时无法打开，请联系培训管理员。
                            </p>
                        )}
                    </div>
                </div>

                <div className="grid gap-3 px-5 py-5 sm:grid-cols-[2.25rem_1fr] sm:px-6">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                        <ListChecks className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-500">2 · 评分会关注</p>
                        <h3 className="mt-1 font-semibold text-slate-950">
                            {runner.scoring_rubric_title ?? "本次讲解的关键表现"}
                        </h3>
                        {focuses.length ? (
                            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                                {focuses.map((focus) => (
                                    <li key={`${focus.label}-${focus.description ?? ""}`} className="rounded-xl bg-slate-50 px-3 py-2.5">
                                        <div className="flex items-baseline justify-between gap-2">
                                            <span className="text-sm font-medium text-slate-900">{focus.label}</span>
                                            {focus.weight !== null ? (
                                                <span className="text-xs tabular-nums text-slate-400">{focus.weight}%</span>
                                            ) : null}
                                        </div>
                                        {focus.description ? (
                                            <p className="mt-1 text-xs leading-5 text-slate-500">{focus.description}</p>
                                        ) : null}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                本任务暂未提供分项说明，提交后会按页面上方的完成标准评测。
                            </p>
                        )}
                    </div>
                </div>

                <div className="grid gap-3 px-5 py-5 sm:grid-cols-[2.25rem_1fr] sm:px-6">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
                        <Quote className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-500">3 · 参考表达</p>
                        <h3 className="mt-1 font-semibold text-slate-950">
                            {configuredExample
                                ? "优秀讲解示例（文字版）"
                                : "参考表达结构（系统默认）"}
                        </h3>
                        {!configuredExample ? (
                            <p className="mt-1 text-xs leading-5 text-amber-700">
                                旧版任务未配置专属示例，以下仅作为表达结构参考，不代表正式范例。
                            </p>
                        ) : null}
                        <blockquote className="mt-3 whitespace-pre-wrap rounded-xl border-l-2 border-amber-300 bg-amber-50/60 px-4 py-3 text-sm leading-7 text-slate-700">
                            {configuredExample ?? LEGACY_EXPRESSION_STRUCTURE}
                        </blockquote>
                    </div>
                </div>
            </div>

            <label className="flex cursor-pointer items-start gap-3 border-t border-blue-100 bg-blue-50/70 px-5 py-4 text-sm font-medium text-blue-950 sm:px-6">
                <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 rounded border-blue-300 text-blue-700 focus:ring-blue-500"
                    checked={confirmed}
                    disabled={disabled}
                    onChange={(event) => onConfirmedChange(event.target.checked)}
                />
                <span>我已看过材料、评分重点和讲解示例</span>
            </label>
        </section>
    );
}
