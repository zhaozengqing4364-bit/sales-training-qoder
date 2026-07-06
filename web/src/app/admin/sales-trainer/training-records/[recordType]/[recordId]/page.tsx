"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminDetailShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { RoleplayObservationPanel } from "@/app/admin/sales-trainer/training-records/roleplay-observation-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    formatAdminRecordStatus,
    formatTrainingTaskDisplay,
    formatUnitTypeLabel,
} from "@/lib/sales-trainer/admin-display";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerMaterialSnapshot,
    SalesTrainerOperationLog,
    SalesTrainerScoreSchemeSnapshot,
    SalesTrainerTaskBriefSnapshot,
    SalesTrainerTrainingRecord,
    SalesTrainerTrainingRecordType,
    TrainingJourneyLearnerLevel,
} from "@/lib/api/types";

const RECORD_TYPES = new Set<string>([
    "audio_submission",
    "quiz_attempt",
    "ai_coach_session",
    "business_etiquette_quiz_attempt",
    "realtime_roleplay_session",
]);

function isRecordType(value: string): value is SalesTrainerTrainingRecordType {
    return RECORD_TYPES.has(value);
}

function formatScore(score: number | null | undefined, maxScore: number | null | undefined): string {
    if (score == null) {
        return "--";
    }
    return maxScore == null ? String(score) : `${score} / ${maxScore}`;
}

function fieldText(item: Record<string, unknown>, keys: string[], fallback = "--"): string {
    for (const key of keys) {
        const value = item[key];
        if (typeof value === "string" && value.trim()) {
            return value;
        }
        if (typeof value === "number" || typeof value === "boolean") {
            return String(value);
        }
    }
    return fallback;
}

function objectValue(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return null;
    }
    return value as Record<string, unknown>;
}

function formatMasteryState(value: unknown): string {
    if (value === "mastered") {
        return "已掌握";
    }
    if (value === "not_mastered") {
        return "未达标";
    }
    return value == null ? "未完成" : String(value);
}

function formatDelta(record: SalesTrainerTrainingRecord): string {
    const delta = record.effective_score?.score_delta;
    if (typeof delta !== "number" || delta === 0) {
        return "无变化";
    }
    return `${delta > 0 ? "+" : ""}${delta}`;
}

function learnerText(record: SalesTrainerTrainingRecord): string {
    const primary = record.user_name || record.user_email || record.user_id;
    const secondary = record.user_department || (
        record.user_email && record.user_email !== primary ? record.user_email : null
    );
    return secondary ? `${primary} · ${secondary}` : primary;
}

function RawPayload({ value }: { value: unknown }) {
    if (!value) {
        return <p className="text-sm text-slate-500">暂无原始数据。</p>;
    }
    return (
        <pre className="max-h-80 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
            {JSON.stringify(value, null, 2)}
        </pre>
    );
}

function formatLevelContext(level: TrainingJourneyLearnerLevel | null | undefined): string {
    if (!level) {
        return "--";
    }
    return level.label || level.level_key || "--";
}

function operationLogContextLines(log: SalesTrainerOperationLog): string[] {
    const context = log.training_context;
    if (!context) {
        return [];
    }
    return [
        `路径版本：${context.path_revision_no ? `v${context.path_revision_no}` : "--"}`,
        `训练阶段：${context.training_stage ?? "--"}`,
        `学员等级：${formatLevelContext(context.learner_level)}`,
        `角色等级：${formatLevelContext(context.role_level)}`,
    ];
}

function legacySnapshot<T extends Record<string, unknown>>(value: unknown): T | null {
    return objectValue(value) as T | null;
}

function HistoricalReplaySnapshotCard({ record }: { record: SalesTrainerTrainingRecord }) {
    const audioSubmission = objectValue(record.audio_submission);
    const scoreSchemeSnapshot =
        record.score_scheme_snapshot ||
        legacySnapshot<SalesTrainerScoreSchemeSnapshot>(audioSubmission?.["score_scheme_snapshot"]);
    const promptSnapshot = scoreSchemeSnapshot?.prompt_snapshot || null;
    const materialSnapshot =
        record.material_snapshot ||
        legacySnapshot<SalesTrainerMaterialSnapshot>(audioSubmission?.["material_snapshot"]);
    const taskBriefSnapshot =
        record.task_brief_snapshot ||
        legacySnapshot<SalesTrainerTaskBriefSnapshot>(audioSubmission?.["task_brief_snapshot"]);

    if (!scoreSchemeSnapshot && !materialSnapshot && !taskBriefSnapshot) {
        return null;
    }

    const scoringTemplate = promptSnapshot?.scoring_template || "";
    const scoringTemplatePreview = scoringTemplate
        ? scoringTemplate.slice(0, 160)
        : "--";
    const confirmedMaterialVersion = materialSnapshot?.confirmed_material_version_id || "--";
    const taskTitle = taskBriefSnapshot?.title || "--";

    return (
        <GlassCard className="space-y-4 p-6">
            <h2 className="text-lg font-bold text-slate-900">历史回放快照</h2>
            <div className="grid gap-4 md:grid-cols-4">
                <div>
                    <p className="text-xs text-slate-500">Path Revision</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {record.path_revision_id || "--"} · v{record.path_revision_no ?? "--"}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">评分 Prompt 快照</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {promptSnapshot?.name || "--"}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">Prompt Version</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {promptSnapshot?.version ?? "--"}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">确认材料版本</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {confirmedMaterialVersion}
                    </p>
                </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">任务快照</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">{taskTitle}</p>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">评分模板摘要</p>
                    <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-700">
                        {scoringTemplatePreview}
                    </p>
                </div>
            </div>
        </GlassCard>
    );
}

function AiCoachSnapshotCard({ record }: { record: SalesTrainerTrainingRecord }) {
    const session = record.ai_coach_session;
    if (!session) {
        return null;
    }
    const articleSnapshot = session.article_snapshot;
    const configSnapshot = session.config_snapshot;
    const coachState = session.coach_state;
    const pathRevisionId = session.path_revision_id || record.path_revision_id || "--";
    const pathRevisionNo = String(session.path_revision_no ?? record.path_revision_no ?? "--");

    return (
        <GlassCard className="space-y-4 p-6">
            <h2 className="text-lg font-bold text-slate-900">AI Coach 快照</h2>
            <div className="grid gap-4 md:grid-cols-4">
                <div>
                    <p className="text-xs text-slate-500">掌握状态</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {formatMasteryState(session.mastery_state)}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">文章主题</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {articleSnapshot?.title || "--"}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">Prompt Revision</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {session.prompt_revision_id || "--"}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">Path Revision</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {pathRevisionId} · v{pathRevisionNo}
                    </p>
                </div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">掌握阈值</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {configSnapshot?.mastery_threshold ?? "--"}
                    </p>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">Trace ID</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {session.trace_id || "--"}
                    </p>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">Prompt Contract</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {session.prompt_contract_hash || "--"}
                    </p>
                </div>
            </div>
            {coachState ? (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-slate-900">Coach State</h3>
                    <div className="grid gap-2 md:grid-cols-2">
                        {Object.entries(coachState).map(([key, value]) => (
                            <div key={key} className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">
                                <p className="font-medium text-slate-900">{key}</p>
                                <p className="mt-1 break-all">{String(value)}</p>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}
        </GlassCard>
    );
}

function BusinessEtiquetteQuizSnapshotCard({ record }: { record: SalesTrainerTrainingRecord }) {
    const attempt = record.business_etiquette_quiz_attempt;
    if (!attempt) {
        return null;
    }
    const firstAnswer = attempt.answers[0];
    const capabilityNameByKey = new Map(
        attempt.capability_scores.map((capability) => [
            capability.capability_key,
            capability.display_name || capability.capability_key,
        ]),
    );
    const weakCapabilityText = attempt.weak_capability_keys.length
        ? attempt.weak_capability_keys
            .map((key) => capabilityNameByKey.get(key) || key)
            .join("、")
        : "无";

    return (
        <GlassCard className="space-y-4 p-6">
            <h2 className="text-lg font-bold text-slate-900">商务礼仪小测快照</h2>
            <div className="grid gap-4 md:grid-cols-4">
                <div>
                    <p className="text-xs text-slate-500">训练包</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {attempt.training_pack_key}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">学习单元</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {attempt.learning_unit_title || attempt.learning_unit_key}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">Path Revision</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {attempt.path_revision_id || record.path_revision_id || "--"} · v{attempt.path_revision_no ?? record.path_revision_no ?? "--"}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">训练包 Revision</p>
                    <p className="mt-1 break-all text-sm font-medium text-slate-900">
                        {attempt.training_pack_revision_id || "--"} · v{attempt.training_pack_revision_no ?? "--"}
                    </p>
                </div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">小测得分</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {formatScore(attempt.total_score, attempt.max_score)}
                    </p>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">弱项能力</p>
                    <p className="mt-1 break-words text-sm font-medium text-slate-900">
                        {weakCapabilityText}
                    </p>
                </div>
                <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-xs text-slate-500">推荐章节</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {attempt.recommended_chapter_orders.length
                            ? attempt.recommended_chapter_orders.join("、")
                            : "--"}
                    </p>
                </div>
            </div>
            {attempt.capability_scores.length ? (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-slate-900">能力得分</h3>
                    <div className="grid gap-2 md:grid-cols-2">
                        {attempt.capability_scores.map((capability) => (
                            <div key={capability.capability_key} className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">
                                <p className="font-medium text-slate-900">
                                    {capability.display_name || capability.capability_key}
                                </p>
                                <p className="mt-1">
                                    {formatScore(capability.score, capability.max_score)}
                                    {typeof capability.normalized_score === "number"
                                        ? ` · ${capability.normalized_score}%`
                                        : ""}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}
            {firstAnswer ? (
                <div className="rounded-lg border border-slate-100 p-4 text-sm text-slate-700">
                    <p className="font-medium text-slate-900">
                        题目 {firstAnswer.question_id || "--"} · {firstAnswer.question_type || "--"}
                    </p>
                    <p className="mt-1">
                        {formatScore(firstAnswer.score, firstAnswer.max_score)}
                    </p>
                    {firstAnswer.analysis ? (
                        <p className="mt-2 whitespace-pre-wrap break-words">
                            {firstAnswer.analysis}
                        </p>
                    ) : null}
                </div>
            ) : null}
        </GlassCard>
    );
}

export default function SalesTrainerTrainingRecordDetailPage() {
    const params = useParams<{ recordType: string; recordId: string }>();
    const pathname = usePathname();
    const [record, setRecord] = useState<SalesTrainerTrainingRecord | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const recordType = params.recordType;
    const canAccessRecord = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

    const loadCapabilities = useCallback(async () => {
        setIsCapabilityLoading(true);
        setCapabilityError(null);
        try {
            setAdminCapabilities(await api.admin.salesTrainer.getCapabilities());
        } catch (error) {
            setAdminCapabilities(null);
            setCapabilityError(getApiErrorMessage(error));
        } finally {
            setIsCapabilityLoading(false);
        }
    }, []);

    const loadRecord = useCallback(async () => {
        if (!isRecordType(recordType) || !canAccessRecord) {
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            setRecord(await api.admin.salesTrainer.getTrainingRecordDetail(
                recordType,
                params.recordId,
            ));
        } catch (loadError) {
            setRecord(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [canAccessRecord, params.recordId, recordType]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (!isRecordType(recordType)) {
            setRecord(null);
            setError("训练记录类型无效。");
            setIsLoading(false);
            return;
        }
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessRecord) {
            setRecord(null);
            setError(null);
            setIsLoading(false);
            return;
        }
        void loadRecord();
    }, [canAccessRecord, isCapabilityLoading, loadRecord, recordType]);

    const taskDisplay = record
        ? formatTrainingTaskDisplay(record.unit_name, record.unit_id)
        : null;
    const explanation = record?.score_explanation;
    const abilityProfile = record?.ability_profile;
    const rawPayload = record?.audio_submission
        ?? record?.quiz_attempt
        ?? record?.ai_coach_session
        ?? record?.business_etiquette_quiz_attempt
        ?? record?.realtime_roleplay_session
        ?? null;

    return (
        <AdminDetailShell
            backHref="/admin/sales-trainer/training-records"
            title="训练记录详情"
            description="统一查看当前有效分、原始分、重评、评分解释，以及实时对练 observation endpoint / legacy compliance fallback 的复盘信息。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {!isRecordType(recordType) ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    训练记录类型无效。
                </div>
            ) : isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验训练记录权限...</div>
            ) : capabilityError || !canAccessRecord ? (
                <AdminLoadErrorCard
                    title="训练记录权限不足"
                    description="当前页不会在权限未确认时加载训练记录详情，避免把权限异常伪装成未找到记录。请联系管理员开通训练记录查看权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载训练记录...</div>
            ) : error && !record ? (
                <AdminLoadErrorCard
                    title="训练记录加载失败"
                    description="当前页不会把接口异常伪装成未找到记录。请核对对象级权限、训练记录状态或后端服务状态后重试。"
                    message={error}
                    retryLabel="重新加载训练记录"
                    onRetry={() => void loadRecord()}
                />
            ) : !record ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    未找到训练记录。
                </div>
            ) : (
                <div className="space-y-6">
                    <GlassCard className="space-y-4 p-6">
                        <div className="flex flex-wrap items-center gap-2">
                            <Badge className="bg-slate-100 text-slate-700">
                                {formatUnitTypeLabel(record.unit_type)}
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700">
                                {formatAdminRecordStatus(record.status)}
                            </Badge>
                            {record.remediation?.needed ? (
                                <Badge className="bg-amber-50 text-amber-700">
                                    {record.remediation.action_label}
                                </Badge>
                            ) : null}
                        </div>
                        <div className="grid gap-4 md:grid-cols-4">
                            <div>
                                <p className="text-xs text-slate-500">学员</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">{learnerText(record)}</p>
                                <p className="mt-1 text-xs text-slate-400">{record.user_id}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">训练任务</p>
                                <p className="mt-1 text-sm text-slate-900">{taskDisplay?.title}</p>
                                {taskDisplay?.detail ? (
                                    <p className="mt-1 text-xs text-slate-400">{taskDisplay.detail}</p>
                                ) : null}
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">当前有效分</p>
                                <p className="mt-1 text-2xl font-black text-slate-900">
                                    {formatScore(record.effective_score?.score, record.effective_score?.max_score)}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    原始分 {formatScore(record.score, record.max_score)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">提交时间</p>
                                <p className="mt-1 text-sm text-slate-900">
                                    {record.submitted_at ? new Date(record.submitted_at).toLocaleString() : "--"}
                                </p>
                            </div>
                        </div>
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">重评与补救</h2>
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <p className="text-xs text-slate-500">有效分来源</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {record.effective_score?.source === "latest_regrade" ? "最近重评" : "原始记录"}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">重评分差</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">{formatDelta(record)}</p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">最近重评</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {record.latest_regrade?.["regrade_run_id"] ? String(record.latest_regrade["regrade_run_id"]) : "--"}
                                </p>
                            </div>
                        </div>
                        {record.remediation ? (
                            <div className="rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                                <p className="font-semibold">{record.remediation.action_label}</p>
                                <p className="mt-1">{record.remediation.reason}</p>
                                <Link href={record.remediation.target_path}>
                                    <Button className="mt-3 rounded-full bg-slate-900 text-white" size="sm">
                                        进入补救入口
                                    </Button>
                                </Link>
                            </div>
                        ) : null}
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">评分解释</h2>
                        <p className="text-sm text-slate-600">
                            {explanation?.summary || "暂无评分解释。"}
                        </p>
                        <div className="grid gap-3 md:grid-cols-3">
                            {(explanation?.dimensions || []).map((dimension, index) => (
                                <div key={`${fieldText(dimension, ["key"], String(index))}-${index}`} className="rounded-lg border border-slate-100 p-3">
                                    <p className="font-medium text-slate-900">
                                        {fieldText(dimension, ["label", "key"], "维度")}
                                    </p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        {fieldText(dimension, ["score"])} / {fieldText(dimension, ["max_score"])}
                                    </p>
                                    {dimension["is_weak"] === true ? (
                                        <Badge className="mt-2 bg-amber-50 text-amber-700">弱项</Badge>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                        {(explanation?.issues || []).length ? (
                            <div className="space-y-2">
                                <h3 className="text-sm font-semibold text-slate-900">问题</h3>
                                {explanation?.issues.map((issue, index) => (
                                    <div key={`${fieldText(issue, ["type"], String(index))}-${index}`} className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">
                                        {fieldText(issue, ["text", "feedback", "title", "type"])}
                                    </div>
                                ))}
                            </div>
                        ) : null}
                        {(explanation?.evidence || []).length ? (
                            <div className="space-y-2">
                                <h3 className="text-sm font-semibold text-slate-900">证据</h3>
                                {explanation?.evidence.map((evidence, index) => (
                                    <div key={`${fieldText(evidence, ["type"], String(index))}-${index}`} className="rounded-lg bg-white px-4 py-3 text-sm text-slate-700">
                                        {fieldText(evidence, ["text", "title", "question_id", "type"])}
                                    </div>
                                ))}
                            </div>
                        ) : null}
                    </GlassCard>

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">能力画像</h2>
                        <div className="grid gap-4 md:grid-cols-3">
                            <div>
                                <p className="text-xs text-slate-500">总体分</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {formatScore(abilityProfile?.overall_score, record.effective_score?.max_score)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">弱项数</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {abilityProfile?.weak_dimensions.length ?? 0}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500">证据数</p>
                                <p className="mt-1 text-sm font-medium text-slate-900">
                                    {abilityProfile?.evidence_count ?? 0}
                                </p>
                            </div>
                        </div>
                    </GlassCard>

                    {record.record_type === "ai_coach_session" ? (
                        <AiCoachSnapshotCard record={record} />
                    ) : null}
                    {record.record_type === "business_etiquette_quiz_attempt" ? (
                        <BusinessEtiquetteQuizSnapshotCard record={record} />
                    ) : null}
                    <HistoricalReplaySnapshotCard record={record} />
                    {record.record_type === "realtime_roleplay_session" ? (
                        <RoleplayObservationPanel record={record} />
                    ) : null}

                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">原始记录</h2>
                        <RawPayload value={rawPayload} />
                    </GlassCard>

                    {record.operation_logs.length ? (
                        <GlassCard className="space-y-4 p-6">
                            <h2 className="text-lg font-bold text-slate-900">操作日志</h2>
                            <div className="space-y-2">
                                {record.operation_logs.map((log) => (
                                    <div key={log.log_id} className="rounded-lg border border-slate-100 px-4 py-3 text-sm text-slate-700">
                                        <p className="font-medium text-slate-900">{log.action}</p>
                                        <p className="mt-1 text-xs text-slate-500">
                                            {new Date(log.created_at).toLocaleString()} · {log.actor_role || "--"}
                                        </p>
                                        {operationLogContextLines(log).length ? (
                                            <div className="mt-2 grid gap-1 text-xs text-slate-600 sm:grid-cols-2">
                                                {operationLogContextLines(log).map((line) => (
                                                    <span key={line}>{line}</span>
                                                ))}
                                            </div>
                                        ) : null}
                                    </div>
                                ))}
                            </div>
                        </GlassCard>
                    ) : null}
                </div>
            )}
        </AdminDetailShell>
    );
}
