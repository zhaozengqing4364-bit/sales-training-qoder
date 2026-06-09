"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SalesTrainerPath, SalesTrainerPathLevel } from "@/lib/api/types";
import type { SalesTrainerUnit } from "@/lib/api/types";
import { persistLearnReturn } from "@/lib/sales-trainer/coo-learn-navigation";
import {
    getLearnerChapterLink,
    getLevelAction,
    getLevelStatusLabel,
    isCurrentFocusLevel,
} from "@/lib/sales-trainer/learner-presenter";

interface PathLevelTimelineProps {
    path: SalesTrainerPath;
    unitsById?: Map<string, SalesTrainerUnit>;
}

function getStatusClass(level: SalesTrainerPathLevel): string {
    if (level.locked) {
        return "bg-slate-100 text-slate-500";
    }
    if (level.status === "completed") {
        return "bg-emerald-100 text-emerald-700";
    }
    return "bg-amber-100 text-amber-700";
}

export function PathLevelTimeline({ path, unitsById }: PathLevelTimelineProps) {
    return (
        <div className="grid gap-3">
            {path.levels.map((level, index) => {
                const isCurrent = isCurrentFocusLevel(path, level);
                const { href, label } = getLevelAction(level);
                const studyHref = getLearnerChapterLink(unitsById?.get(level.unit_id));

                return (
                    <div
                        key={level.unit_id}
                        className={`rounded-lg border bg-white p-4 ${
                            isCurrent ? "border-slate-900 ring-1 ring-slate-900/10" : "border-slate-100"
                        }`}
                    >
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                            <div className="flex items-start gap-3">
                                <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                                    isCurrent ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                                }`}
                                >
                                    {index + 1}
                                </span>
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="font-bold text-slate-900">{level.level_title}</h3>
                                        <Badge className={getStatusClass(level)}>{getLevelStatusLabel(level)}</Badge>
                                        {isCurrent ? (
                                            <Badge className="bg-blue-100 text-blue-700">当前关卡</Badge>
                                        ) : null}
                                    </div>
                                    <p className="mt-1 text-sm text-slate-500">
                                        {level.level_description || level.description || "完成本关后继续下一关。"}
                                    </p>
                                    {level.latest_result ? (
                                        <p className="mt-2 text-xs text-slate-500">
                                            最近结果：{level.latest_result.score ?? "--"}
                                            {level.latest_result.max_score ? `/${level.latest_result.max_score}` : ""}
                                            {level.latest_result.passed === true ? " · 已通过" : level.latest_result.passed === false ? " · 未通过" : ""}
                                        </p>
                                    ) : null}
                                    {level.lock_reason ? (
                                        <p className="mt-2 text-xs text-slate-500">{level.lock_reason}</p>
                                    ) : null}
                                </div>
                            </div>
                            {level.locked ? (
                                <Button variant="outline" className="rounded-full" disabled>待解锁</Button>
                            ) : (
                                <div className="flex flex-wrap items-center gap-2">
                                    {studyHref ? (
                                        <Button asChild variant="outline" className="rounded-full">
                                            <Link
                                                href={studyHref}
                                                onClick={() => persistLearnReturn("/sales-trainer")}
                                            >
                                                阅读本章
                                            </Link>
                                        </Button>
                                    ) : null}
                                    <Button asChild variant="outline" className="rounded-full">
                                        <Link href={href}>{label}</Link>
                                    </Button>
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
