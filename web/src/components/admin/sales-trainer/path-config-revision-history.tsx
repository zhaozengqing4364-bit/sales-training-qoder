"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type { NewcomerConfigCenterModel } from "@/lib/sales-trainer/config-center";

interface RevisionHistoryProps {
    readonly model: NewcomerConfigCenterModel;
    readonly isMutating: boolean;
    readonly onRollbackRevision?: (revisionId: string, reason: string) => void;
}

export function PathConfigRevisionHistory({
    model,
    isMutating,
    onRollbackRevision,
}: RevisionHistoryProps) {
    const [reasonByRevision, setReasonByRevision] = useState<Record<string, string>>({});

    function updateReason(revisionId: string, reason: string) {
        setReasonByRevision((current) => ({
            ...current,
            [revisionId]: reason,
        }));
    }

    return (
        <GlassCard className="p-5">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-bold uppercase text-slate-400">历史版本</p>
                    <h2 className="mt-1 text-lg font-black text-slate-900">路径配置版本记录</h2>
                </div>
                <Badge className="border-slate-200 bg-slate-100 text-slate-600">
                    {model.governance.sourceLabel}
                </Badge>
            </div>
            {model.governance.revisions.length ? (
                <div className="mt-4 divide-y divide-slate-100 rounded-2xl border border-slate-100">
                    {model.governance.revisions.map((revision) => {
                        const reason = reasonByRevision[revision.revision_id] ?? "";
                        const rollbackDisabled = isMutating
                            || revision.is_active
                            || !onRollbackRevision
                            || !reason.trim();
                        return (
                            <div
                                key={revision.revision_id}
                                className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between"
                            >
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-bold text-slate-900">版本 v{revision.revision_no}</p>
                                        {revision.is_active ? (
                                            <Badge className="border-emerald-100 bg-emerald-50 text-emerald-700">当前生效</Badge>
                                        ) : null}
                                        {revision.is_working ? (
                                            <Badge className="border-amber-100 bg-amber-50 text-amber-700">待发布</Badge>
                                        ) : null}
                                    </div>
                                    <p className="mt-1 text-sm text-slate-500">
                                        {revision.reason ?? "未填写发布说明"} · {revision.module_count} 个关卡
                                    </p>
                                </div>
                                <div className="flex flex-col gap-2 md:min-w-72">
                                    <label className="sr-only" htmlFor={`path-rollback-reason-${revision.revision_id}`}>
                                        回滚原因（版本 v{revision.revision_no}）
                                    </label>
                                    <Input
                                        id={`path-rollback-reason-${revision.revision_id}`}
                                        value={reason}
                                        placeholder={`回滚原因（版本 v${revision.revision_no}）`}
                                        disabled={isMutating || revision.is_active || !onRollbackRevision}
                                        onChange={(event) => updateReason(revision.revision_id, event.target.value)}
                                    />
                                    <Button
                                        variant="outline"
                                        className="rounded-full"
                                        onClick={() => onRollbackRevision?.(revision.revision_id, reason.trim())}
                                        disabled={rollbackDisabled}
                                    >
                                        回滚到此版本
                                    </Button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <p className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-500">
                    尚未形成路径级历史版本；保存当前配置后会生成待发布修订。
                </p>
            )}
        </GlassCard>
    );
}
