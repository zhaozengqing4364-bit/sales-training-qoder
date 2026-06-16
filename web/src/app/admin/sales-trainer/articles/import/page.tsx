"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, RefreshCcw, UploadCloud } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    BusinessEtiquetteImportedChapter,
    BusinessEtiquetteImportResponse,
    BusinessEtiquetteReleaseImpactResponse,
    BusinessEtiquetteReleaseStrategy,
} from "@/lib/api/types";
import {
    BUSINESS_ETIQUETTE_IMPORT_COPY,
    BUSINESS_ETIQUETTE_IMPORT_DEFAULTS,
    BUSINESS_ETIQUETTE_RELEASE_COPY,
    BUSINESS_ETIQUETTE_RELEASE_STRATEGY_LABELS,
} from "@/lib/sales-trainer/business-etiquette-import-config";

function countKnowledgePoints(chapter: BusinessEtiquetteImportedChapter): number {
    return chapter.micro_chapters.reduce(
        (total, microChapter) => total + microChapter.knowledge_points.length,
        0,
    );
}

function formatFileSize(size: number): string {
    if (size < 1024) {
        return `${size} B`;
    }
    if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
    }
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function parseUserIds(raw: string): string[] {
    return Array.from(new Set(raw.split(/[\s,，;；]+/).map((item) => item.trim()).filter(Boolean)));
}

function changeTypeLabel(value: "added" | "removed" | "changed"): string {
    return BUSINESS_ETIQUETTE_RELEASE_COPY.changeTypeLabels[value];
}

export default function BusinessEtiquetteImportPage() {
    const pathname = usePathname();
    const toast = useToast();
    const [trainingPackKey, setTrainingPackKey] = useState<string>(
        BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.trainingPackKey,
    );
    const [allowOverwriteDraft, setAllowOverwriteDraft] = useState<boolean>(
        BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.allowOverwriteDraft,
    );
    const [reason, setReason] = useState<string>(
        BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.importReason,
    );
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [result, setResult] = useState<BusinessEtiquetteImportResponse | null>(null);
    const [releaseImpact, setReleaseImpact] = useState<BusinessEtiquetteReleaseImpactResponse | null>(null);
    const [releaseImpactError, setReleaseImpactError] = useState<string | null>(null);
    const [isLoadingImpact, setIsLoadingImpact] = useState(false);
    const [releaseStrategy, setReleaseStrategy] = useState<BusinessEtiquetteReleaseStrategy>("future_learners_only");
    const [assignedUserIdsText, setAssignedUserIdsText] = useState("");
    const [releaseReason, setReleaseReason] = useState<string>(
        BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.releaseReason,
    );
    const [isPublishingRelease, setIsPublishingRelease] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const selectedFileLabel = useMemo(() => {
        if (!selectedFile) {
            return BUSINESS_ETIQUETTE_IMPORT_COPY.emptyFileLabel;
        }
        return `${selectedFile.name} · ${formatFileSize(selectedFile.size)}`;
    }, [selectedFile]);

    const loadReleaseImpact = useCallback(async (trainingPackKey: string) => {
        setIsLoadingImpact(true);
        setReleaseImpactError(null);
        try {
            const impact = await api.admin.salesTrainer.getBusinessEtiquetteReleaseImpact({
                training_pack_key: trainingPackKey,
            });
            setReleaseImpact(impact);
            setReleaseStrategy(impact.config.default_strategy);
        } catch (error) {
            setReleaseImpact(null);
            setReleaseImpactError(getApiErrorMessage(error));
        } finally {
            setIsLoadingImpact(false);
        }
    }, []);

    async function submitImport(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selectedFile) {
            toast.error(BUSINESS_ETIQUETTE_IMPORT_COPY.fileRequired);
            return;
        }
        setIsSubmitting(true);
        try {
            const imported = await api.admin.salesTrainer.importBusinessEtiquetteMarkdown({
                file: selectedFile,
                training_pack_key: trainingPackKey,
                allow_overwrite_draft: allowOverwriteDraft,
                reason,
            });
            setResult(imported);
            void loadReleaseImpact(imported.training_pack_key);
            toast.success(BUSINESS_ETIQUETTE_IMPORT_COPY.submitSuccess);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsSubmitting(false);
        }
    }

    function resetDraft() {
        setSelectedFile(null);
        setResult(null);
        setReleaseImpact(null);
        setReleaseImpactError(null);
        setReason(BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.importReason);
        setTrainingPackKey(BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.trainingPackKey);
        setAllowOverwriteDraft(BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.allowOverwriteDraft);
        setReleaseStrategy("future_learners_only");
        setAssignedUserIdsText("");
        setReleaseReason(BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.releaseReason);
    }

    async function publishRelease() {
        if (!result) {
            return;
        }
        const assignedUserIds = parseUserIds(assignedUserIdsText);
        if (releaseStrategy === "assign_retraining" && assignedUserIds.length === 0) {
            toast.error(BUSINESS_ETIQUETTE_RELEASE_COPY.assignedUsersRequired);
            return;
        }
        setIsPublishingRelease(true);
        try {
            const published = await api.admin.salesTrainer.publishBusinessEtiquetteRelease({
                training_pack_key: result.training_pack_key,
                strategy: releaseStrategy,
                assigned_user_ids: assignedUserIds,
                reason: releaseReason,
            });
            toast.success(
                `${BUSINESS_ETIQUETTE_RELEASE_COPY.publishSuccessPrefix}${published.active_revision_no}`,
            );
            await loadReleaseImpact(result.training_pack_key);
        } catch (error) {
            toast.error(getApiErrorMessage(error));
        } finally {
            setIsPublishingRelease(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title={BUSINESS_ETIQUETTE_IMPORT_COPY.pageTitle}
                    description={BUSINESS_ETIQUETTE_IMPORT_COPY.pageDescription}
                    secondaryActions={(
                        <div className="flex flex-wrap gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                className="rounded-full"
                                onClick={resetDraft}
                                disabled={isSubmitting}
                            >
                                <RefreshCcw className="mr-2 h-4 w-4" />
                                重置
                            </Button>
                            <SalesTrainerAdminModuleNav currentPath={pathname} />
                        </div>
                    )}
                />
            )}
        >
            <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
                <GlassCard className="p-6">
                    <form className="space-y-5" onSubmit={(event) => void submitImport(event)}>
                        <div>
                            <label
                                className="text-sm font-semibold text-slate-900"
                                htmlFor="business-etiquette-file"
                            >
                                Markdown 文件
                            </label>
                            <input
                                id="business-etiquette-file"
                                className="mt-2 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
                                type="file"
                                accept={BUSINESS_ETIQUETTE_IMPORT_DEFAULTS.acceptedFileTypes}
                                onChange={(event) => {
                                    setSelectedFile(event.target.files?.[0] ?? null);
                                    setResult(null);
                                    setReleaseImpact(null);
                                    setReleaseImpactError(null);
                                }}
                            />
                            <p className="mt-2 text-xs font-medium text-slate-500">
                                {selectedFileLabel}
                            </p>
                        </div>

                        <div>
                            <label
                                className="text-sm font-semibold text-slate-900"
                                htmlFor="business-etiquette-pack-key"
                            >
                                训练包 key
                            </label>
                            <input
                                id="business-etiquette-pack-key"
                                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                                value={trainingPackKey}
                                onChange={(event) => setTrainingPackKey(event.target.value)}
                            />
                        </div>

                        <div>
                            <label
                                className="text-sm font-semibold text-slate-900"
                                htmlFor="business-etiquette-reason"
                            >
                                操作原因
                            </label>
                            <textarea
                                id="business-etiquette-reason"
                                className="mt-2 min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                                value={reason}
                                onChange={(event) => setReason(event.target.value)}
                            />
                        </div>

                        <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                            <input
                                aria-label="允许覆盖当前未发布草稿"
                                className="mt-1 h-4 w-4 rounded border-slate-300"
                                type="checkbox"
                                checked={allowOverwriteDraft}
                                onChange={(event) => setAllowOverwriteDraft(event.target.checked)}
                            />
                            <span>
                                <span className="block text-sm font-semibold text-slate-900">
                                    允许覆盖当前未发布草稿
                                </span>
                                <span className="mt-1 block text-xs text-slate-500">
                                    覆盖只会替换 working revision，不会改动已发布版本。
                                </span>
                            </span>
                        </label>

                        <Button
                            type="submit"
                            className="w-full rounded-full bg-slate-900 text-white"
                            disabled={isSubmitting}
                        >
                            <UploadCloud className="mr-2 h-4 w-4" />
                            {isSubmitting
                                ? BUSINESS_ETIQUETTE_IMPORT_COPY.importingLabel
                                : BUSINESS_ETIQUETTE_IMPORT_COPY.submitLabel}
                        </Button>
                    </form>
                </GlassCard>

                <div className="space-y-6">
                    {result ? (
                        <>
                            <ReleaseImpactPanel
                                assignedUserIdsText={assignedUserIdsText}
                                impact={releaseImpact}
                                impactError={releaseImpactError}
                                isLoading={isLoadingImpact}
                                isPublishing={isPublishingRelease}
                                onAssignedUserIdsTextChange={setAssignedUserIdsText}
                                onPublish={() => void publishRelease()}
                                onRefresh={() => void loadReleaseImpact(result.training_pack_key)}
                                onReleaseReasonChange={setReleaseReason}
                                onStrategyChange={setReleaseStrategy}
                                releaseReason={releaseReason}
                                strategy={releaseStrategy}
                            />
                            <ImportResultPreview result={result} />
                        </>
                    ) : (
                        <GlassCard className="p-8 text-center">
                            <FileText className="mx-auto h-10 w-10 text-slate-300" />
                            <h2 className="mt-4 text-lg font-bold text-slate-900">
                                等待导入结果
                            </h2>
                            <p className="mt-2 text-sm text-slate-500">
                                草稿生成后会显示原始章节、微章节和知识点解析结果。
                            </p>
                        </GlassCard>
                    )}
                </div>
            </div>
        </AdminIndexShell>
    );
}

function ReleaseImpactPanel({
    assignedUserIdsText,
    impact,
    impactError,
    isLoading,
    isPublishing,
    onAssignedUserIdsTextChange,
    onPublish,
    onRefresh,
    onReleaseReasonChange,
    onStrategyChange,
    releaseReason,
    strategy,
}: {
    assignedUserIdsText: string;
    impact: BusinessEtiquetteReleaseImpactResponse | null;
    impactError: string | null;
    isLoading: boolean;
    isPublishing: boolean;
    onAssignedUserIdsTextChange: (value: string) => void;
    onPublish: () => void;
    onRefresh: () => void;
    onReleaseReasonChange: (value: string) => void;
    onStrategyChange: (value: BusinessEtiquetteReleaseStrategy) => void;
    releaseReason: string;
    strategy: BusinessEtiquetteReleaseStrategy;
}) {
    const assignedCount = parseUserIds(assignedUserIdsText).length;
    return (
        <GlassCard className="overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">
                            {BUSINESS_ETIQUETTE_RELEASE_COPY.panelEyebrow}
                        </p>
                        <h2 className="mt-1 text-xl font-bold text-slate-900">
                            {BUSINESS_ETIQUETTE_RELEASE_COPY.panelTitle}
                        </h2>
                        <p className="mt-2 text-sm text-slate-500">
                            {BUSINESS_ETIQUETTE_RELEASE_COPY.panelDescription}
                        </p>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        className="rounded-full"
                        onClick={onRefresh}
                        disabled={isLoading}
                    >
                        <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                        {BUSINESS_ETIQUETTE_RELEASE_COPY.refreshButton}
                    </Button>
                </div>
            </div>

            {impactError ? (
                <div className="px-6 py-4 text-sm font-medium text-red-700">
                    {impactError}
                </div>
            ) : null}

            {impact ? (
                <div className="space-y-5 px-6 py-5">
                    <dl className="grid gap-3 md:grid-cols-4">
                        <Metric
                            label={BUSINESS_ETIQUETTE_RELEASE_COPY.metrics.changedChapters}
                            value={`${impact.summary.changed_chapter_count} 个`}
                        />
                        <Metric
                            label={BUSINESS_ETIQUETTE_RELEASE_COPY.metrics.impactedLearningUnits}
                            value={`${impact.summary.impacted_learning_unit_count} 个`}
                        />
                        <Metric
                            label={BUSINESS_ETIQUETTE_RELEASE_COPY.metrics.activeLearners}
                            value={`${impact.summary.active_learner_count} 人`}
                        />
                        <Metric
                            label={BUSINESS_ETIQUETTE_RELEASE_COPY.metrics.recommendedRetraining}
                            value={`${impact.summary.recommended_retraining_user_count} 人`}
                        />
                    </dl>

                    <div className="grid gap-4 lg:grid-cols-2">
                        <ImpactList
                            empty={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.chapterEmpty}
                            items={impact.chapter_changes.map((chapter) => (
                                `${chapter.chapter_order}. ${chapter.title} · ${changeTypeLabel(chapter.change_type)}`
                            ))}
                            title={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.chapterTitle}
                        />
                        <ImpactList
                            empty={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.learningUnitEmpty}
                            items={impact.impacted_learning_units.map((unit) => (
                                `${unit.title} · 章节 ${unit.impacted_chapter_orders.join("、") || "--"}`
                            ))}
                            title={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.learningUnitTitle}
                        />
                        <ImpactList
                            empty={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.questionEmpty}
                            items={[
                                ...impact.impacted_questions.map((question) => (
                                    `${question.title} · 正式题 · 第 ${question.chapter_order} 章`
                                )),
                                ...impact.impacted_question_drafts.map((draft) => (
                                    `${draft.title} · 草稿/${draft.status} · 第 ${draft.chapter_order} 章`
                                )),
                            ]}
                            title={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.questionTitle}
                        />
                        <ImpactList
                            empty={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.capabilityEmpty}
                            items={impact.impacted_capabilities.map((capability) => (
                                `${capability.display_name} · ${changeTypeLabel(capability.change_type)}`
                            ))}
                            title={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.capabilityTitle}
                        />
                    </div>

                    <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-4">
                        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
                            <div>
                                <label className="text-sm font-semibold text-slate-900" htmlFor="business-etiquette-release-strategy">
                                    {BUSINESS_ETIQUETTE_RELEASE_COPY.strategyLabel}
                                </label>
                                <select
                                    id="business-etiquette-release-strategy"
                                    className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                                    value={strategy}
                                    onChange={(event) => onStrategyChange(event.target.value as BusinessEtiquetteReleaseStrategy)}
                                >
                                    {impact.strategy_options.map((option) => (
                                        <option key={option} value={option}>
                                            {BUSINESS_ETIQUETTE_RELEASE_STRATEGY_LABELS[option]}
                                        </option>
                                    ))}
                                </select>
                                <p className="mt-2 text-xs text-slate-500">
                                    {BUSINESS_ETIQUETTE_RELEASE_COPY.defaultStrategyPrefix}
                                    {BUSINESS_ETIQUETTE_RELEASE_STRATEGY_LABELS[impact.config.default_strategy]}。
                                </p>
                            </div>
                            <div>
                                <label className="text-sm font-semibold text-slate-900" htmlFor="business-etiquette-release-reason">
                                    {BUSINESS_ETIQUETTE_RELEASE_COPY.releaseReasonLabel}
                                </label>
                                <input
                                    id="business-etiquette-release-reason"
                                    className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                                    value={releaseReason}
                                    onChange={(event) => onReleaseReasonChange(event.target.value)}
                                />
                            </div>
                        </div>

                        {strategy === "assign_retraining" ? (
                            <div className="mt-4">
                                <label className="text-sm font-semibold text-slate-900" htmlFor="business-etiquette-assigned-users">
                                    {BUSINESS_ETIQUETTE_RELEASE_COPY.assignedUsersLabel}
                                </label>
                                <textarea
                                    id="business-etiquette-assigned-users"
                                    className="mt-2 min-h-24 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                                    placeholder={BUSINESS_ETIQUETTE_RELEASE_COPY.assignedUsersPlaceholder}
                                    value={assignedUserIdsText}
                                    onChange={(event) => onAssignedUserIdsTextChange(event.target.value)}
                                />
                                <p className="mt-2 text-xs text-slate-500">
                                    {BUSINESS_ETIQUETTE_RELEASE_COPY.assignedUsersCountPrefix}{" "}
                                    {assignedCount} 人，
                                    {BUSINESS_ETIQUETTE_RELEASE_COPY.assignedUsersLimitPrefix}{" "}
                                    {impact.config.max_assigned_retraining_users} 人。
                                </p>
                            </div>
                        ) : null}

                        <div className="mt-4 flex flex-wrap items-center gap-3">
                            <Button
                                type="button"
                                className="rounded-full bg-slate-900 text-white"
                                onClick={onPublish}
                                disabled={isPublishing || isLoading}
                            >
                                {isPublishing
                                    ? BUSINESS_ETIQUETTE_RELEASE_COPY.publishingLabel
                                    : BUSINESS_ETIQUETTE_RELEASE_COPY.publishButton}
                            </Button>
                            <span className="text-xs font-medium text-slate-500">
                                v{impact.target_revision_no}{" "}
                                {BUSINESS_ETIQUETTE_RELEASE_COPY.oldSnapshotNotice}
                            </span>
                        </div>
                    </div>

                    <ImpactList
                        empty={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.activeLearnerEmpty}
                        items={impact.active_learners.map((learner) => (
                            `${learner.user_name ?? learner.user_id} · ${learner.source_record_types.join(" + ")}`
                        ))}
                        title={BUSINESS_ETIQUETTE_RELEASE_COPY.lists.activeLearnerTitle}
                    />
                </div>
            ) : !impactError ? (
                <div className="px-6 py-4 text-sm text-slate-500">
                    {isLoading
                        ? BUSINESS_ETIQUETTE_RELEASE_COPY.loadingImpact
                        : BUSINESS_ETIQUETTE_RELEASE_COPY.noImpact}
                </div>
            ) : null}
        </GlassCard>
    );
}

function ImportResultPreview({ result }: { result: BusinessEtiquetteImportResponse }) {
    return (
        <GlassCard className="overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                            草稿未发布
                        </p>
                        <h2 className="mt-1 text-xl font-bold text-slate-900">
                            {result.book_title}
                        </h2>
                        <p className="mt-2 text-sm text-slate-500">
                            working revision v{result.working_revision_no} ·{" "}
                            {result.source_filename}
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Link
                            className="inline-flex items-center rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                            href={`/admin/learning-contents/${result.learning_content_id}`}
                        >
                            打开章节编辑
                        </Link>
                        <Link
                            className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
                            href="/admin/sales-trainer/articles"
                        >
                            返回文章绑定
                        </Link>
                    </div>
                </div>

                <dl className="mt-5 grid gap-3 sm:grid-cols-3">
                    <Metric label="原始章节" value={`${result.original_chapter_count} 个`} />
                    <Metric label="微章节" value={`${result.micro_chapter_count} 个`} />
                    <Metric label="知识点" value={`${result.knowledge_point_count} 个`} />
                </dl>
            </div>

            <div className="divide-y divide-slate-100">
                {result.chapters.map((chapter) => (
                    <details key={chapter.content_hash} className="group px-6 py-4" open>
                        <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
                            <div>
                                <p className="text-sm font-bold text-slate-900">
                                    {chapter.order_index}. {chapter.title}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    {chapter.micro_chapters.length} 个微章节 ·{" "}
                                    {countKnowledgePoints(chapter)} 个知识点
                                </p>
                            </div>
                            <span className="text-xs font-semibold text-slate-400 group-open:hidden">
                                展开
                            </span>
                            <span className="hidden text-xs font-semibold text-slate-400 group-open:inline">
                                收起
                            </span>
                        </summary>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                            {chapter.micro_chapters.map((microChapter) => (
                                <div
                                    key={`${chapter.order_index}-${microChapter.order_index}`}
                                    className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
                                >
                                    <p className="text-sm font-semibold text-slate-800">
                                        {microChapter.order_index}. {microChapter.title}
                                    </p>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        {microChapter.knowledge_points.length ? (
                                            microChapter.knowledge_points.map((point) => (
                                                <span
                                                    key={`${microChapter.order_index}-${point.order_index}-${point.line_number}`}
                                                    className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm"
                                                >
                                                    {point.title}
                                                </span>
                                            ))
                                        ) : (
                                            <span className="text-xs text-slate-400">
                                                无 H3 知识点
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </details>
                ))}
            </div>
        </GlassCard>
    );
}

function ImpactList({
    empty,
    items,
    title,
}: {
    empty: string;
    items: string[];
    title: string;
}) {
    return (
        <div className="rounded-xl border border-slate-100 bg-white px-4 py-4">
            <h3 className="text-sm font-bold text-slate-900">{title}</h3>
            {items.length ? (
                <ul className="mt-3 space-y-2 text-sm text-slate-600">
                    {items.slice(0, 8).map((item) => (
                        <li key={item} className="rounded-lg bg-slate-50 px-3 py-2">
                            {item}
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="mt-3 text-sm text-slate-400">{empty}</p>
            )}
            {items.length > 8 ? (
                <p className="mt-2 text-xs text-slate-400">还有 {items.length - 8} 项未展示。</p>
            ) : null}
        </div>
    );
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
            <dt className="text-xs font-medium text-slate-500">{label}</dt>
            <dd className="mt-1 text-lg font-bold text-slate-900">{value}</dd>
        </div>
    );
}
