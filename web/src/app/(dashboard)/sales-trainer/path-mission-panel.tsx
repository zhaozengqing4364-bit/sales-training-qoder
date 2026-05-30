"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import { persistLearnReturn } from "@/lib/sales-trainer/coo-learn-navigation";
import {
    findFocusLevel,
    formatPassThresholdLine,
    getAudioPassThreshold,
    getLearnerChapterHint,
    getLearnerChapterLink,
    getUnitTypeLabel,
    resolvePrimaryAction,
} from "@/lib/sales-trainer/learner-presenter";

interface PathMissionPanelProps {
    path: SalesTrainerPath;
    unitsById: Map<string, SalesTrainerUnit>;
}

export function PathMissionPanel({ path, unitsById }: PathMissionPanelProps) {
    const primaryAction = resolvePrimaryAction(path);
    const focusLevel = findFocusLevel(path);
    const firstWeakPoint = path.goal_context.weak_points[0];
    const evidenceCount = path.goal_context.evidence_items.length;
    const focusUnit = focusLevel ? unitsById.get(focusLevel.unit_id) : undefined;
    const passThreshold = focusLevel?.unit_type === "audio_scoring"
        ? getAudioPassThreshold(focusUnit)
        : null;
    const chapterHint = getLearnerChapterHint(focusUnit);
    const chapterHref = getLearnerChapterLink(focusUnit);

    const supplementalReason = firstWeakPoint
        && firstWeakPoint.issue_text !== primaryAction?.reason
        ? `${firstWeakPoint.level_title}：${firstWeakPoint.issue_text}`
        : null;

    if (!primaryAction) {
        return (
            <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-5">
                <p className="text-xs font-semibold text-emerald-700">当前要练</p>
                <h3 className="mt-2 text-xl font-black text-emerald-950">路径已完成</h3>
                <p className="mt-1 text-sm text-emerald-800">
                    已完成 {path.completed_levels}/{path.total_levels} 个关卡，可以回看结果或等待管理员发布新的训练路径。
                </p>
                <p className="mt-3 text-sm text-emerald-800">
                    已完成 {evidenceCount} 次有效训练
                </p>
            </div>
        );
    }

    return (
        <div className="rounded-lg bg-slate-900 p-5 text-white">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-3">
                    <div>
                        <p className="text-xs font-semibold text-slate-300">当前要练</p>
                        <h3 className="mt-2 text-xl font-black">{primaryAction.title}</h3>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{primaryAction.reason}</p>
                        {chapterHint ? (
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                                {chapterHint}
                                {chapterHref ? (
                                    <>
                                        {" "}
                                        <Link
                                            href={chapterHref}
                                            className="font-medium text-white underline underline-offset-2"
                                            onClick={() => persistLearnReturn("/sales-trainer")}
                                        >
                                            阅读本章
                                        </Link>
                                    </>
                                ) : null}
                            </p>
                        ) : null}
                        {supplementalReason ? (
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{supplementalReason}</p>
                        ) : null}
                    </div>
                    <div className="space-y-1 text-sm text-slate-300">
                        <p>已完成 {evidenceCount} 次有效训练</p>
                        {focusLevel ? (
                            <p>训练形式：{getUnitTypeLabel(focusLevel.unit_type)}</p>
                        ) : null}
                        {passThreshold !== null ? (
                            <p>{formatPassThresholdLine(passThreshold)}</p>
                        ) : null}
                    </div>
                </div>
                <Link href={primaryAction.targetPath}>
                    <Button className="rounded-full bg-white text-slate-900 hover:bg-slate-100">
                        {primaryAction.actionLabel}
                    </Button>
                </Link>
            </div>
        </div>
    );
}
