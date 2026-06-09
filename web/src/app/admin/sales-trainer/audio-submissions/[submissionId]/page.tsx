"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminDetailShell } from "@/components/admin/admin-layout-shells";
import { AudioSubmissionRegradePanel } from "@/components/admin/sales-trainer/audio-submission-regrade-panel";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { formatAdminRecordStatus, formatAudioSourceLabel } from "@/lib/sales-trainer/admin-display";
import type { SalesTrainerAudioSubmission } from "@/lib/api/types";

function formatSubmissionUser(submission: SalesTrainerAudioSubmission): string {
    const primary = submission.user_name || submission.user_email || submission.user_id;
    const secondary = submission.user_email && submission.user_email !== primary
        ? submission.user_email
        : submission.user_department;
    return secondary ? `${primary} · ${secondary}` : primary;
}

function getSnapshotItems(snapshot: Record<string, unknown> | null): Array<{
    name?: string;
    current_version?: { version_label?: string; title?: string; version_id?: string };
}> {
    const items = snapshot?.items;
    return Array.isArray(items) ? items as Array<{
        name?: string;
        current_version?: { version_label?: string; title?: string; version_id?: string };
    }> : [];
}

export default function SalesTrainerAudioSubmissionDetailPage() {
    const params = useParams<{ submissionId: string }>();
    const pathname = usePathname();
    const toast = useToast();
    const [submission, setSubmission] = useState<SalesTrainerAudioSubmission | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isOperating, setIsOperating] = useState(false);

    const loadSubmission = useCallback(async () => {
        setIsLoading(true);
        try {
            const result = await api.admin.salesTrainer.getAudioSubmission(params.submissionId);
            setSubmission(result);
        } catch (loadError) {
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [params.submissionId, toast]);

    useEffect(() => {
        void loadSubmission();
    }, [loadSubmission]);

    const fileUrl = useMemo(
        () => api.admin.salesTrainer.getAudioSubmissionFileUrl(params.submissionId),
        [params.submissionId],
    );

    async function retry(action: "transcription" | "scoring") {
        setIsOperating(true);
        try {
            if (action === "transcription") {
                await api.admin.salesTrainer.retryAudioTranscription(params.submissionId);
                toast.success("已触发重试转写");
            } else {
                await api.admin.salesTrainer.retryAudioScoring(params.submissionId);
                toast.success("已触发重试评分");
            }
            await loadSubmission();
        } catch (retryError) {
            toast.error(getApiErrorMessage(retryError));
            setIsOperating(false);
        }
    }

    return (
        <AdminDetailShell
            backHref="/admin/sales-trainer/audio-submissions"
            title={submission ? submission.original_filename : "录音详情"}
            description="提供授权文件访问、转写结果、评分结果，以及后台重试操作。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载录音详情...</div>
            ) : !submission ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    未找到录音详情。
                </div>
            ) : (
                <div className="space-y-6">
                    <GlassCard className="space-y-4 p-6">
                        <div className="flex flex-wrap items-center gap-2">
                            <Badge className="bg-slate-100 text-slate-700">{formatAdminRecordStatus(submission.status)}</Badge>
                            <a href={fileUrl} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm">授权播放</Button>
                            </a>
                            <a href={fileUrl} target="_blank" rel="noreferrer" download>
                                <Button variant="outline" size="sm">下载录音</Button>
                            </a>
                            <Button variant="outline" size="sm" disabled={isOperating} onClick={() => void retry("transcription")}>
                                重试转写
                            </Button>
                            <Button variant="outline" size="sm" disabled={isOperating} onClick={() => void retry("scoring")}>
                                重试评分
                            </Button>
                        </div>
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <p className="text-xs text-slate-500">用户</p>
                                <p className="mt-1 text-sm text-slate-900">{formatSubmissionUser(submission)}</p>
                                <p className="mt-1 text-xs text-slate-400">{submission.user_id}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">类型</p>
                                <p className="mt-1 text-sm text-slate-900">{submission.content_type}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">来源页面</p>
                                <p className="mt-1 text-sm text-slate-900">{formatAudioSourceLabel(submission.source_page)}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">上传时间</p>
                                <p className="mt-1 text-sm text-slate-900">{new Date(submission.created_at).toLocaleString()}</p>
                            </div>
                        </div>
                        {submission.error_message ? (
                            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                {submission.error_message}
                            </div>
                        ) : null}
                    </GlassCard>

                    {submission.material_snapshot || submission.score_scheme_snapshot || submission.task_brief_snapshot ? (
                        <GlassCard className="space-y-4 p-6">
                            <h2 className="text-lg font-bold text-slate-900">训练快照</h2>
                            {submission.task_brief_snapshot ? (
                                <div>
                                    <p className="text-xs text-slate-500">任务简报</p>
                                    <p className="mt-1 text-sm text-slate-900">
                                        {String(submission.task_brief_snapshot.title || submission.task_brief_snapshot.purpose || "--")}
                                    </p>
                                </div>
                            ) : null}
                            {getSnapshotItems(submission.material_snapshot).length ? (
                                <div>
                                    <p className="text-xs text-slate-500">材料版本</p>
                                    <div className="mt-2 space-y-2">
                                        {getSnapshotItems(submission.material_snapshot).map((item) => (
                                            <p key={`${item.name}-${item.current_version?.version_id}`} className="text-sm text-slate-900">
                                                {item.name || "训练材料"} · {item.current_version?.version_label || "--"} · {item.current_version?.title || "--"}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            ) : null}
                            {submission.score_scheme_snapshot ? (
                                <div>
                                    <p className="text-xs text-slate-500">评分方案</p>
                                    <p className="mt-1 text-sm text-slate-900">
                                        {String(submission.score_scheme_snapshot.name || "--")} · v{String(submission.score_scheme_snapshot.version || "--")}
                                    </p>
                                </div>
                            ) : null}
                        </GlassCard>
                    ) : null}

                    <GlassCard className="space-y-3 p-6">
                        <h2 className="text-lg font-bold text-slate-900">转写结果</h2>
                        <p className="text-sm text-slate-600">{submission.transcript?.transcript_text || "转写尚未完成。"}</p>
                    </GlassCard>

                    <GlassCard className="space-y-3 p-6">
                        <h2 className="text-lg font-bold text-slate-900">评分结果</h2>
                        {submission.score_result ? (
                            <>
                                <div className="grid gap-4 md:grid-cols-3">
                                    <div>
                                        <p className="text-xs text-slate-500">总分</p>
                                        <p className="mt-1 text-2xl font-black text-slate-900">{submission.score_result.total_score ?? "--"}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-slate-500">通过</p>
                                        <p className="mt-1 text-2xl font-black text-slate-900">{submission.score_result.passed ? "是" : "否"}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-slate-500">模型</p>
                                        <p className="mt-1 text-sm text-slate-900">{submission.score_result.deucate_model || "--"}</p>
                                    </div>
                                </div>
                                <p className="text-sm text-slate-600">{submission.score_result.summary || "暂无评分总结。"}</p>
                            </>
                        ) : (
                            <p className="text-sm text-slate-500">评分尚未完成。</p>
                        )}
                    </GlassCard>
                    {submission.score_result ? (
                        <AudioSubmissionRegradePanel submission={submission} />
                    ) : null}
                </div>
            )}
        </AdminDetailShell>
    );
}
