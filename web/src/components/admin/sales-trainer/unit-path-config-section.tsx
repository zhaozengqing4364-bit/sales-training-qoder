"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";

export type SalesTrainerCompletionRule = "passed" | "scored" | "submitted";

interface UnitPathConfigSectionProps {
    readonly canEdit: boolean;
    readonly completionRule: SalesTrainerCompletionRule | "";
    readonly goalTitle: string;
    readonly guidanceTemplates: string;
    readonly isSubmitting: boolean;
    readonly levelDescription: string;
    readonly levelTitle: string;
    readonly name: string;
    readonly pathEnabled: boolean;
    readonly pathKey: string;
    readonly pathOrderIndex: string;
    readonly pathTitle: string;
    readonly primaryActionLabel: string;
    readonly retryActionLabel: string;
    readonly reviewActionLabel: string;
    readonly setCompletionRule: (value: SalesTrainerCompletionRule | "") => void;
    readonly setGoalTitle: (value: string) => void;
    readonly setGuidanceTemplates: (value: string) => void;
    readonly setLevelDescription: (value: string) => void;
    readonly setLevelTitle: (value: string) => void;
    readonly setPathEnabled: (value: boolean) => void;
    readonly setPathKey: (value: string) => void;
    readonly setPathOrderIndex: (value: string) => void;
    readonly setPathTitle: (value: string) => void;
    readonly setPrimaryActionLabel: (value: string) => void;
    readonly setRetryActionLabel: (value: string) => void;
    readonly setReviewActionLabel: (value: string) => void;
    readonly setUnlockAfterUnitIds: (value: string) => void;
    readonly unlockAfterUnitIds: string;
}

export function UnitPathConfigSection({
    canEdit,
    completionRule,
    goalTitle,
    guidanceTemplates,
    isSubmitting,
    levelDescription,
    levelTitle,
    name,
    pathEnabled,
    pathKey,
    pathOrderIndex,
    pathTitle,
    primaryActionLabel,
    retryActionLabel,
    reviewActionLabel,
    setCompletionRule,
    setGoalTitle,
    setGuidanceTemplates,
    setLevelDescription,
    setLevelTitle,
    setPathEnabled,
    setPathKey,
    setPathOrderIndex,
    setPathTitle,
    setPrimaryActionLabel,
    setRetryActionLabel,
    setReviewActionLabel,
    setUnlockAfterUnitIds,
    unlockAfterUnitIds,
}: UnitPathConfigSectionProps) {
    const [showAdvancedFields, setShowAdvancedFields] = useState(false);

    return (
        <GlassCard className="space-y-4 p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">闯关路径配置</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        路径结构请优先到“新人训练路径配置中心”维护；这里仅保留高级兼容配置。
                    </p>
                </div>
                <Link href="/admin/sales-trainer/paths" className="text-sm font-semibold text-slate-900 underline">
                    打开新人训练路径配置中心
                </Link>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                    type="checkbox"
                    checked={pathEnabled}
                    onChange={(event) => setPathEnabled(event.target.checked)}
                    disabled={isSubmitting || !canEdit}
                />
                加入新人训练路径
            </label>
            {pathEnabled ? (
                <div className="space-y-4">
                    <Button
                        type="button"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => setShowAdvancedFields((current) => !current)}
                    >
                        {showAdvancedFields ? "收起高级兼容字段" : "展开高级兼容字段"}
                    </Button>
                    {showAdvancedFields ? (
                        <PathAdvancedFields
                            canEdit={canEdit}
                            completionRule={completionRule}
                            goalTitle={goalTitle}
                            guidanceTemplates={guidanceTemplates}
                            isSubmitting={isSubmitting}
                            levelDescription={levelDescription}
                            levelTitle={levelTitle}
                            name={name}
                            pathKey={pathKey}
                            pathOrderIndex={pathOrderIndex}
                            pathTitle={pathTitle}
                            primaryActionLabel={primaryActionLabel}
                            retryActionLabel={retryActionLabel}
                            reviewActionLabel={reviewActionLabel}
                            setCompletionRule={setCompletionRule}
                            setGoalTitle={setGoalTitle}
                            setGuidanceTemplates={setGuidanceTemplates}
                            setLevelDescription={setLevelDescription}
                            setLevelTitle={setLevelTitle}
                            setPathKey={setPathKey}
                            setPathOrderIndex={setPathOrderIndex}
                            setPathTitle={setPathTitle}
                            setPrimaryActionLabel={setPrimaryActionLabel}
                            setRetryActionLabel={setRetryActionLabel}
                            setReviewActionLabel={setReviewActionLabel}
                            setUnlockAfterUnitIds={setUnlockAfterUnitIds}
                            unlockAfterUnitIds={unlockAfterUnitIds}
                        />
                    ) : null}
                </div>
            ) : null}
        </GlassCard>
    );
}

type PathAdvancedFieldsProps = Omit<
    UnitPathConfigSectionProps,
    "pathEnabled" | "setPathEnabled"
>;

function PathAdvancedFields({
    canEdit,
    completionRule,
    goalTitle,
    guidanceTemplates,
    isSubmitting,
    levelDescription,
    levelTitle,
    name,
    pathKey,
    pathOrderIndex,
    pathTitle,
    primaryActionLabel,
    retryActionLabel,
    reviewActionLabel,
    setCompletionRule,
    setGoalTitle,
    setGuidanceTemplates,
    setLevelDescription,
    setLevelTitle,
    setPathKey,
    setPathOrderIndex,
    setPathTitle,
    setPrimaryActionLabel,
    setRetryActionLabel,
    setReviewActionLabel,
    setUnlockAfterUnitIds,
    unlockAfterUnitIds,
}: PathAdvancedFieldsProps) {
    return (
        <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-path-key">路径标识</label>
                <Input id="sales-trainer-path-key" value={pathKey} onChange={(event) => setPathKey(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认路径" />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-path-title">路径名称</label>
                <Input id="sales-trainer-path-title" value={pathTitle} onChange={(event) => setPathTitle(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="例如 新人训练路径" />
            </div>
            <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-goal-title">训练目标</label>
                <Input id="sales-trainer-goal-title" value={goalTitle} onChange={(event) => setGoalTitle(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="例如 掌握首次客户沟通" />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-level-title">关卡名称</label>
                <Input id="sales-trainer-level-title" value={levelTitle} onChange={(event) => setLevelTitle(event.target.value)} disabled={isSubmitting || !canEdit} placeholder={name || "例如 第一关：产品定位"} />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-path-order">关卡顺序</label>
                <Input id="sales-trainer-path-order" type="number" min={1} value={pathOrderIndex} onChange={(event) => setPathOrderIndex(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认顺序" />
            </div>
            <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-level-description">关卡说明</label>
                <textarea id="sales-trainer-level-description" value={levelDescription} onChange={(event) => setLevelDescription(event.target.value)} disabled={isSubmitting || !canEdit} rows={3} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm" />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-completion-rule">通关规则</label>
                <select
                    id="sales-trainer-completion-rule"
                    value={completionRule}
                    onChange={(event) => setCompletionRule(event.target.value ? toCompletionRule(event.target.value) : "")}
                    disabled={isSubmitting || !canEdit}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                >
                    <option value="">使用默认通关规则</option>
                    <option value="passed">必须通过</option>
                    <option value="scored">完成评分即可</option>
                    <option value="submitted">提交即可</option>
                </select>
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-unlock-after">前置关卡编号</label>
                <textarea id="sales-trainer-unlock-after" value={unlockAfterUnitIds} onChange={(event) => setUnlockAfterUnitIds(event.target.value)} disabled={isSubmitting || !canEdit} rows={3} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm" placeholder="每行一个训练任务编号；通常由配置中心维护" />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-primary-action">主按钮文案</label>
                <Input id="sales-trainer-primary-action" value={primaryActionLabel} onChange={(event) => setPrimaryActionLabel(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认文案" />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-retry-action">重练按钮文案</label>
                <Input id="sales-trainer-retry-action" value={retryActionLabel} onChange={(event) => setRetryActionLabel(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认文案" />
            </div>
            <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-review-action">查看结果按钮文案</label>
                <Input id="sales-trainer-review-action" value={reviewActionLabel} onChange={(event) => setReviewActionLabel(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="留空使用默认文案" />
            </div>
            <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-guidance-templates">反馈文案模板</label>
                <textarea id="sales-trainer-guidance-templates" value={guidanceTemplates} onChange={(event) => setGuidanceTemplates(event.target.value)} disabled={isSubmitting || !canEdit} rows={5} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm" placeholder="not_started: 本关还没有训练证据。" />
                <p className="text-xs text-slate-500">
                    可配置 locked、not_started、not_passed、not_scored、audio_improvement、start_level_reason、retry_level_reason、path_completed_reason。
                </p>
            </div>
        </div>
    );
}

export function toCompletionRule(value: string): SalesTrainerCompletionRule {
    return value === "scored" || value === "submitted" ? value : "passed";
}
