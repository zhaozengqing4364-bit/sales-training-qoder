"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    formatAdminRecordStatus,
    formatTrainingTaskDisplay,
    formatUnitTypeLabel,
} from "@/lib/sales-trainer/admin-display";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerTrainingRecord,
    TrainingJourneyAnalyticsResponse,
} from "@/lib/api/types";

const MODULE_FILTER_OPTIONS = [
    { value: "ppt_explanation", label: "PPT 讲解录音" },
    { value: "business_skills", label: "商务技巧" },
    { value: "ai_coach", label: "AI 教练" },
    { value: "elevator_pitch", label: "金字塔演讲" },
    { value: "realtime_roleplay", label: "实时对练" },
] as const;

const TRAINING_STAGE_FILTER_OPTIONS = [
    { value: "not_started", label: "未开始" },
    { value: "in_progress", label: "进行中" },
    { value: "waiting_upload", label: "待上传" },
    { value: "processing", label: "处理中" },
    { value: "scored", label: "已评分" },
    { value: "passed", label: "已通过" },
    { value: "failed", label: "未通过" },
    { value: "needs_remediation", label: "需补救" },
    { value: "manual_review", label: "待人工复核" },
    { value: "error_terminal", label: "终止错误" },
    { value: "error_transient", label: "暂态错误" },
] as const;

const RECORD_STATUS_FILTER_OPTIONS = [
    { value: "submitted", label: "已提交" },
    { value: "uploaded", label: "已上传" },
    { value: "transcribing", label: "转写中" },
    { value: "transcribed", label: "转写完成" },
    { value: "scoring", label: "评分中" },
    { value: "scored", label: "已评分" },
    { value: "completed", label: "已完成" },
    { value: "in_progress", label: "进行中" },
    { value: "failed", label: "失败" },
    { value: "transcription_failed", label: "转写失败" },
    { value: "scoring_failed", label: "评分失败" },
] as const;

type TrainingRecordFilters = {
    user_id?: string;
    unit_id?: string;
    material_version_id?: string;
    module_key?: string;
    training_stage?: string;
    learner_level?: string;
    role_level?: string;
    status?: string;
};

type SearchParamReader = Pick<URLSearchParams, "get">;
type FilterOption = {
    value: string;
    label: string;
};

function queryValue(searchParams: SearchParamReader, key: string): string {
    return searchParams.get(key)?.trim() ?? "";
}

function filtersFromSearchParams(searchParams: SearchParamReader): TrainingRecordFilters {
    return {
        user_id: queryValue(searchParams, "user_id") || undefined,
        unit_id: queryValue(searchParams, "unit_id") || undefined,
        material_version_id: queryValue(searchParams, "material_version_id") || undefined,
        module_key: queryValue(searchParams, "module_key") || undefined,
        training_stage: queryValue(searchParams, "training_stage") || undefined,
        learner_level: queryValue(searchParams, "learner_level") || undefined,
        role_level: queryValue(searchParams, "role_level") || undefined,
        status: queryValue(searchParams, "status") || undefined,
    };
}

function compactFilters(filters: TrainingRecordFilters): TrainingRecordFilters {
    return Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value && value.trim()),
    ) as TrainingRecordFilters;
}

function queryStringFromFilters(filters: TrainingRecordFilters): string {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(compactFilters(filters))) {
        params.set(key, value);
    }
    return params.toString();
}

function formatLearner(record: SalesTrainerTrainingRecord): string {
    const primary = record.user_name || record.user_email || record.user_id;
    const secondary =
        record.user_department ||
        (record.user_email && record.user_email !== primary ? record.user_email : null);
    return secondary ? `${primary} · ${secondary}` : primary;
}

function formatScore(record: SalesTrainerTrainingRecord): string {
    if (record.score == null) {
        return "--";
    }
    if (record.max_score == null) {
        return String(record.score);
    }
    return `${record.score} / ${record.max_score}`;
}

function formatEffectiveScore(record: SalesTrainerTrainingRecord): string {
    const score = record.effective_score?.score;
    const maxScore = record.effective_score?.max_score;
    if (score == null) {
        return "--";
    }
    if (maxScore == null) {
        return String(score);
    }
    return `${score} / ${maxScore}`;
}

function formatScoreDelta(record: SalesTrainerTrainingRecord): string | null {
    const delta = record.effective_score?.score_delta;
    if (typeof delta !== "number" || delta === 0) {
        return null;
    }
    return `${delta > 0 ? "+" : ""}${delta}`;
}

function detailPath(record: SalesTrainerTrainingRecord): string {
    return `/admin/sales-trainer/training-records/${record.record_type}/${record.record_id}`;
}

function formatJourneyLevel(
    record: SalesTrainerTrainingRecord,
    key: "learner_level" | "role_level",
): string {
    const level = record[key];
    if (!level) {
        return "--";
    }
    return level.label || level.level_key;
}

function formatTrainingStage(record: SalesTrainerTrainingRecord): string {
    const stage = record.training_stage;
    if (!stage) {
        return "--";
    }
    return TRAINING_STAGE_FILTER_OPTIONS.find((option) => option.value === stage)?.label ?? stage;
}

function mergeFilterOptions(
    baseOptions: readonly FilterOption[],
    dynamicOptions: readonly FilterOption[],
    selectedValue: string,
): FilterOption[] {
    const merged = new Map<string, FilterOption>();
    for (const option of [...baseOptions, ...dynamicOptions]) {
        const value = option.value.trim();
        if (value && !merged.has(value)) {
            merged.set(value, { value, label: option.label || value });
        }
    }
    const selected = selectedValue.trim();
    if (selected && !merged.has(selected)) {
        merged.set(selected, { value: selected, label: selected });
    }
    return [...merged.values()];
}

export default function SalesTrainerTrainingRecordsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const initialFilters = filtersFromSearchParams(searchParams);
    const [items, setItems] = useState<SalesTrainerTrainingRecord[]>([]);
    const [userId, setUserId] = useState(initialFilters.user_id ?? "");
    const [unitId, setUnitId] = useState(initialFilters.unit_id ?? "");
    const [materialVersionId, setMaterialVersionId] = useState(
        initialFilters.material_version_id ?? "",
    );
    const [moduleKey, setModuleKey] = useState(initialFilters.module_key ?? "");
    const [trainingStage, setTrainingStage] = useState(initialFilters.training_stage ?? "");
    const [learnerLevel, setLearnerLevel] = useState(initialFilters.learner_level ?? "");
    const [roleLevel, setRoleLevel] = useState(initialFilters.role_level ?? "");
    const [recordStatus, setRecordStatus] = useState(initialFilters.status ?? "");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] =
        useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const [filterMetadata, setFilterMetadata] = useState<TrainingJourneyAnalyticsResponse | null>(
        null,
    );
    const [filterMetadataError, setFilterMetadataError] = useState<string | null>(null);
    const canAccessRecords = isSalesTrainerAdminPathAllowedForCapabilities(
        pathname,
        adminCapabilities,
    );

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

    const currentFilters = useCallback(
        (): TrainingRecordFilters =>
            compactFilters({
                user_id: userId.trim(),
                unit_id: unitId.trim(),
                material_version_id: materialVersionId.trim(),
                module_key: moduleKey,
                training_stage: trainingStage,
                learner_level: learnerLevel.trim(),
                role_level: roleLevel.trim(),
                status: recordStatus,
            }),
        [
            learnerLevel,
            materialVersionId,
            moduleKey,
            recordStatus,
            roleLevel,
            trainingStage,
            unitId,
            userId,
        ],
    );

    const syncUrl = useCallback(
        (filters: TrainingRecordFilters) => {
            const query = queryStringFromFilters(filters);
            router.push(query ? `${pathname}?${query}` : pathname);
        },
        [pathname, router],
    );

    const loadRecords = useCallback(
        async (filters?: TrainingRecordFilters) => {
            if (!canAccessRecords) {
                return;
            }
            setIsLoading(true);
            setError(null);
            try {
                const result = await api.admin.salesTrainer.listTrainingRecords({
                    ...filters,
                    limit: 100,
                });
                setItems(result.items);
            } catch (loadError) {
                setItems([]);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        },
        [canAccessRecords],
    );

    const loadFilterMetadata = useCallback(async () => {
        if (!canAccessRecords) {
            return;
        }
        setFilterMetadataError(null);
        try {
            setFilterMetadata(await api.admin.salesTrainer.getJourneyAnalytics({ limit: 500 }));
        } catch (loadError) {
            setFilterMetadata(null);
            setFilterMetadataError(getApiErrorMessage(loadError));
        }
    }, [canAccessRecords]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessRecords) {
            setItems([]);
            setError(null);
            setIsLoading(false);
            return;
        }
        void loadRecords(currentFilters());
        void loadFilterMetadata();
    }, [canAccessRecords, currentFilters, isCapabilityLoading, loadFilterMetadata, loadRecords]);

    const moduleOptions = useMemo(() => {
        const analyticsOptions = (filterMetadata?.module_summaries ?? []).map((summary) => ({
            value: summary.module_key,
            label: summary.title || summary.module_key,
        }));
        const recordOptions = items
            .filter((record) => Boolean(record.module_key))
            .map((record) => ({
                value: String(record.module_key),
                label: record.unit_name || String(record.module_key),
            }));
        return mergeFilterOptions(
            MODULE_FILTER_OPTIONS,
            [...analyticsOptions, ...recordOptions],
            moduleKey,
        );
    }, [filterMetadata?.module_summaries, items, moduleKey]);

    const learnerLevelOptions = useMemo(() => {
        const analyticsOptions = (filterMetadata?.learner_level_summaries ?? []).map((summary) => ({
            value: summary.key,
            label: summary.label || summary.key,
        }));
        const recordOptions = items
            .map((record) => record.learner_level)
            .filter((level): level is NonNullable<SalesTrainerTrainingRecord["learner_level"]> =>
                Boolean(level),
            )
            .map((level) => ({
                value: level.level_key,
                label: level.label || level.level_key,
            }));
        return mergeFilterOptions([], [...analyticsOptions, ...recordOptions], learnerLevel);
    }, [filterMetadata?.learner_level_summaries, items, learnerLevel]);

    const roleLevelOptions = useMemo(() => {
        const analyticsOptions = (filterMetadata?.role_level_summaries ?? []).map((summary) => ({
            value: summary.key,
            label: summary.label || summary.key,
        }));
        const recordOptions = items
            .map((record) => record.role_level)
            .filter((level): level is NonNullable<SalesTrainerTrainingRecord["role_level"]> =>
                Boolean(level),
            )
            .map((level) => ({
                value: level.level_key,
                label: level.label || level.level_key,
            }));
        return mergeFilterOptions([], [...analyticsOptions, ...recordOptions], roleLevel);
    }, [filterMetadata?.role_level_summaries, items, roleLevel]);

    function submitFilters() {
        const filters = currentFilters();
        syncUrl(filters);
        void loadRecords(filters);
    }

    function applyFilters(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        submitFilters();
    }

    function resetFilters() {
        setUserId("");
        setUnitId("");
        setMaterialVersionId("");
        setModuleKey("");
        setTrainingStage("");
        setLearnerLevel("");
        setRoleLevel("");
        setRecordStatus("");
        syncUrl({});
        void loadRecords();
    }

    const content = (() => {
        if (isCapabilityLoading) {
            return (
                <div className="py-12 text-center text-sm text-slate-500">
                    正在校验训练记录权限...
                </div>
            );
        }
        if (capabilityError || !canAccessRecords) {
            return (
                <AdminLoadErrorCard
                    title="训练记录权限不足"
                    description="当前页不会在权限未确认时加载训练记录，避免把权限异常伪装为空记录。请联系管理员开通训练记录查看权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            );
        }
        if (error) {
            return (
                <AdminLoadErrorCard
                    title="训练记录加载失败"
                    description="当前页不会在训练记录读取失败时渲染空状态。请检查权限、筛选条件或后端接口后重试。"
                    message={error}
                    retryLabel="重新加载训练记录"
                    onRetry={() => void loadRecords(currentFilters())}
                />
            );
        }
        return (
            <GlassCard className="overflow-hidden p-0">
                <div aria-label="训练记录明细表格" className="overflow-x-auto" role="region">
                    <table className="min-w-[1120px] w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 text-left text-slate-500">
                                <th className="px-6 py-4">学员</th>
                                <th className="px-6 py-4">阶段/等级</th>
                                <th className="px-6 py-4">任务</th>
                                <th className="px-6 py-4">类型</th>
                                <th className="px-6 py-4">材料版本</th>
                                <th className="px-6 py-4">得分</th>
                                <th className="px-6 py-4">补救</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">提交时间</th>
                                <th className="px-6 py-4">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td
                                        colSpan={10}
                                        className="px-6 py-10 text-center text-slate-500"
                                    >
                                        正在加载训练记录...
                                    </td>
                                </tr>
                            ) : items.length === 0 ? (
                                <tr>
                                    <td
                                        colSpan={10}
                                        className="px-6 py-10 text-center text-slate-500"
                                    >
                                        暂无训练记录
                                    </td>
                                </tr>
                            ) : (
                                items.map((item) => {
                                    const snapshot = item.material_snapshot;
                                    const taskDisplay = formatTrainingTaskDisplay(
                                        item.unit_name,
                                        item.unit_id,
                                    );
                                    const snapshotItems = Array.isArray(snapshot?.items)
                                        ? snapshot.items
                                        : [];
                                    const firstMaterial = snapshotItems[0] as
                                        | { current_version?: { version_label?: string } }
                                        | undefined;
                                    return (
                                        <tr
                                            key={`${item.record_type}-${item.record_id}`}
                                            className="border-b border-slate-100 last:border-b-0"
                                        >
                                            <td className="px-6 py-4">
                                                <p className="font-medium text-slate-900">
                                                    {formatLearner(item)}
                                                </p>
                                                <p className="mt-1 text-xs text-slate-400">
                                                    {item.user_id}
                                                </p>
                                            </td>
                                            <td className="px-6 py-4">
                                                <Badge className="bg-blue-50 text-blue-700">
                                                    {formatTrainingStage(item)}
                                                </Badge>
                                                <p className="mt-2 text-xs text-slate-500">
                                                    学员：
                                                    {formatJourneyLevel(item, "learner_level")}
                                                </p>
                                                <p className="mt-1 text-xs text-slate-500">
                                                    角色：{formatJourneyLevel(item, "role_level")}
                                                </p>
                                            </td>
                                            <td className="px-6 py-4">
                                                <p>{taskDisplay.title}</p>
                                                {taskDisplay.detail ? (
                                                    <p className="mt-1 text-xs text-slate-400">
                                                        {taskDisplay.detail}
                                                    </p>
                                                ) : null}
                                            </td>
                                            <td className="px-6 py-4">
                                                {formatUnitTypeLabel(item.unit_type)}
                                            </td>
                                            <td className="px-6 py-4">
                                                {firstMaterial?.current_version?.version_label ??
                                                    "--"}
                                            </td>
                                            <td className="px-6 py-4">
                                                <p className="font-semibold text-slate-900">
                                                    {formatEffectiveScore(item)}
                                                </p>
                                                <p className="mt-1 text-xs text-slate-500">
                                                    原始分 {formatScore(item)}
                                                </p>
                                                {item.latest_regrade ? (
                                                    <p className="mt-1 text-xs text-emerald-700">
                                                        当前有效分 · 重评{" "}
                                                        {formatScoreDelta(item) ?? "无变化"}
                                                    </p>
                                                ) : null}
                                            </td>
                                            <td className="px-6 py-4">
                                                {item.remediation?.needed ? (
                                                    <Badge className="bg-amber-50 text-amber-700">
                                                        {item.remediation.action_label}
                                                    </Badge>
                                                ) : (
                                                    <span className="text-slate-400">--</span>
                                                )}
                                            </td>
                                            <td className="px-6 py-4">
                                                <Badge className="bg-slate-100 text-slate-700">
                                                    {formatAdminRecordStatus(item.status)}
                                                </Badge>
                                            </td>
                                            <td className="px-6 py-4">
                                                {item.submitted_at
                                                    ? new Date(item.submitted_at).toLocaleString()
                                                    : "--"}
                                            </td>
                                            <td className="px-6 py-4">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => router.push(detailPath(item))}
                                                >
                                                    查看详情
                                                </Button>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </GlassCard>
        );
    })();

    return (
        <AdminIndexShell
            header={
                <AdminPageHeader
                    title="学员训练记录"
                    description="统一查看材料版本、录音、转写、评分、做题和操作记录，替代单独追录音与评分结果。"
                    secondaryActions={
                        <SalesTrainerAdminModuleNav
                            currentPath={pathname}
                            capabilities={adminCapabilities}
                        />
                    }
                />
            }
        >
            <GlassCard className="p-6">
                <form className="grid gap-4 md:grid-cols-2 xl:grid-cols-5" onSubmit={applyFilters}>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-user-id"
                        >
                            学员编号
                        </label>
                        <Input
                            id="records-user-id"
                            value={userId}
                            onChange={(event) => setUserId(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-unit-id"
                        >
                            训练任务编号
                        </label>
                        <Input
                            id="records-unit-id"
                            value={unitId}
                            onChange={(event) => setUnitId(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-material-version-id"
                        >
                            材料版本编号
                        </label>
                        <Input
                            id="records-material-version-id"
                            value={materialVersionId}
                            onChange={(event) => setMaterialVersionId(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-module-key"
                        >
                            训练模块
                        </label>
                        <select
                            id="records-module-key"
                            className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                            value={moduleKey}
                            onChange={(event) => setModuleKey(event.target.value)}
                        >
                            <option value="">全部模块</option>
                            {moduleOptions.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-training-stage"
                        >
                            训练阶段
                        </label>
                        <select
                            id="records-training-stage"
                            className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                            value={trainingStage}
                            onChange={(event) => setTrainingStage(event.target.value)}
                        >
                            <option value="">全部阶段</option>
                            {TRAINING_STAGE_FILTER_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-status"
                        >
                            记录状态
                        </label>
                        <select
                            id="records-status"
                            className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                            value={recordStatus}
                            onChange={(event) => setRecordStatus(event.target.value)}
                        >
                            <option value="">全部状态</option>
                            {RECORD_STATUS_FILTER_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-learner-level"
                        >
                            学员等级
                        </label>
                        <select
                            id="records-learner-level"
                            className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                            value={learnerLevel}
                            onChange={(event) => setLearnerLevel(event.target.value)}
                        >
                            <option value="">全部学员等级</option>
                            {learnerLevelOptions.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label
                            className="text-sm font-medium text-slate-700"
                            htmlFor="records-role-level"
                        >
                            角色等级
                        </label>
                        <select
                            id="records-role-level"
                            className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                            value={roleLevel}
                            onChange={(event) => setRoleLevel(event.target.value)}
                        >
                            <option value="">全部角色等级</option>
                            {roleLevelOptions.map((option) => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="flex items-end xl:col-start-4">
                        <Button
                            type="button"
                            className="w-full rounded-full bg-slate-900 text-white"
                            onClick={submitFilters}
                        >
                            查询
                        </Button>
                    </div>
                    <div className="flex items-end">
                        <Button
                            type="button"
                            variant="outline"
                            className="w-full rounded-full"
                            onClick={resetFilters}
                        >
                            重置
                        </Button>
                    </div>
                    {filterMetadataError ? (
                        <div
                            role="alert"
                            className="md:col-span-2 xl:col-span-5 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                        >
                            筛选项元数据加载失败：{filterMetadataError}
                        </div>
                    ) : null}
                </form>
            </GlassCard>

            {content}
        </AdminIndexShell>
    );
}
