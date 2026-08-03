import type {
    EvidenceDossierV1,
    FoundationActivityStatus,
    FoundationActivityType,
    FoundationActivityWorkspace,
    FoundationJourneyProjection,
    FoundationNotificationPage,
    FoundationTaskStatusPage,
} from "@/lib/api/types/newcomer-training";
import type {
    FoundationSourceContentKind,
    FoundationSourceProcessingState,
} from "@/lib/api/types/foundation-admin";
import {
    missionFromFoundationJourney,
    type LearnerMissionViewModel,
} from "./learner-mission";

export interface JourneyActivityViewModel {
    id: string;
    type: FoundationActivityType;
    title: string;
    objective: string;
    status: FoundationActivityStatus;
    statusLabel: string;
    estimatedMinutes: number;
    blockedReason: string | null;
    href: string | null;
}

export interface FoundationSourceRevisionViewModel {
    revisionId: string;
    contentKind: FoundationSourceContentKind;
    contentKindLabel: string;
    processingState: FoundationSourceProcessingState;
    processingLabel: string;
    isProcessing: boolean;
    canRetry: boolean;
    canPreview: boolean;
    failureMessage: string | null;
    originalFilename: string | null;
    fileSizeBytes: number | null;
    pageCount: number | null;
    durationMs: number | null;
    originalUrl: string | null;
    externalUrl: string | null;
    manualContent: string | null;
    playbackUrl: string | null;
    previewPageTemplate: string | null;
    pages: Array<{ page: number; status: "ready" | "failed"; text: string }>;
    sections: Array<{ index: number; text: string }>;
    missingPages: number[];
}

const SOURCE_KIND_LABELS: Record<FoundationSourceContentKind, string> = {
    document: "文档",
    slide_deck: "PPT 讲解材料",
    demo_video: "Demo 视频",
    external_demo: "受控 Demo 链接",
    script: "讲解稿",
    example_audio: "示范音频",
    attachment: "附件",
};

const SOURCE_PROCESSING_LABELS: Record<FoundationSourceProcessingState, string> = {
    pending: "等待处理",
    processing: "正在处理",
    partial: "部分完成",
    ready: "处理完成",
    failed: "处理失败",
    cancelled: "已取消",
};

export function toFoundationSourceRevisionViewModel(
    value: unknown,
): FoundationSourceRevisionViewModel | null {
    const revision = objectRecord(value);
    const draft = objectRecord(revision.working_revision);
    const preview = objectRecord(revision.preview);
    const access = objectRecord(revision.access);
    const revisionId = stringValue(revision.revision_id);
    const contentKind = stringValue(draft.content_kind) as FoundationSourceContentKind;
    const processingState = stringValue(draft.processing_state) as FoundationSourceProcessingState;
    if (
        !revisionId
        || !(contentKind in SOURCE_KIND_LABELS)
        || !(processingState in SOURCE_PROCESSING_LABELS)
    ) return null;
    const pages = Array.isArray(preview.pages)
        ? preview.pages.flatMap((item) => {
            const page = objectRecord(item);
            const pageNumber = numberValue(page.page);
            const status = stringValue(page.status);
            const safeStatus: "ready" | "failed" | null = status === "ready" || status === "failed"
                ? status
                : null;
            return pageNumber !== null && safeStatus !== null
                ? [{ page: pageNumber, status: safeStatus, text: stringValue(page.text) }]
                : [];
        })
        : [];
    const sections = Array.isArray(preview.sections)
        ? preview.sections.flatMap((item) => {
            const section = objectRecord(item);
            const index = numberValue(section.index);
            return index === null ? [] : [{ index, text: stringValue(section.text) }];
        })
        : [];
    const missingPages = Array.isArray(preview.missing_pages)
        ? preview.missing_pages.filter((item): item is number => typeof item === "number")
        : [];
    return {
        revisionId,
        contentKind,
        contentKindLabel: SOURCE_KIND_LABELS[contentKind],
        processingState,
        processingLabel: SOURCE_PROCESSING_LABELS[processingState],
        isProcessing: processingState === "pending" || processingState === "processing",
        canRetry: processingState === "failed" || processingState === "partial" || processingState === "cancelled",
        canPreview: processingState === "ready" || processingState === "partial",
        failureMessage: nullableString(draft.failure_message),
        originalFilename: nullableString(draft.original_filename),
        fileSizeBytes: numberValue(draft.file_size_bytes),
        pageCount: numberValue(draft.page_count),
        durationMs: numberValue(draft.duration_ms),
        originalUrl: nullableString(access.original),
        externalUrl: nullableString(draft.external_url),
        manualContent: nullableString(draft.manual_content),
        playbackUrl: nullableString(access.playback),
        previewPageTemplate: nullableString(access.preview_page_template),
        pages,
        sections,
        missingPages,
    };
}

export interface JourneyStageViewModel {
    id: string;
    sequence: number;
    title: string;
    objective: string;
    status: "locked" | "current" | "completed";
    statusLabel: string;
    completedCount: number;
    totalCount: number;
    activities: JourneyActivityViewModel[];
}

export interface JourneyRecentProgressViewModel {
    id: string;
    title: string;
    resultLabel: string;
    scoreLabel: string | null;
    producedAt: string;
    href: string;
}

export interface JourneyPageViewModel {
    status: FoundationJourneyProjection["status"];
    statusLabel: string;
    statusReason: string | null;
    dataFreshness: FoundationJourneyProjection["data_freshness"];
    pathTitle: string;
    progressPercent: number;
    progressLabel: string;
    mission: LearnerMissionViewModel | null;
    missionHref: string | null;
    currentStageId: string | null;
    stages: JourneyStageViewModel[];
    recentProgress: JourneyRecentProgressViewModel[];
}

function safeActivityHref(href: string | null | undefined, activityId: string): string {
    if (href?.startsWith("/newcomer-training/activities/")) return href;
    return `/newcomer-training/activities/${encodeURIComponent(activityId)}`;
}

function resultLabel(passed: boolean | null): string {
    if (passed === true) return "已通过";
    if (passed === false) return "需要补练";
    return "结果已记录";
}

export function toJourneyPageViewModel(
    journey: FoundationJourneyProjection,
): JourneyPageViewModel {
    const mission = missionFromFoundationJourney(journey);
    const stages = journey.stages.map<JourneyStageViewModel>((stage) => ({
        id: stage.stage_id,
        sequence: stage.sequence,
        title: stage.title,
        objective: stage.objective,
        status: stage.status,
        statusLabel: stage.status === "completed" ? "已完成" : stage.status === "locked" ? "未解锁" : "当前",
        completedCount: stage.activities.filter((activity) => activity.status === "completed").length,
        totalCount: stage.activities.length,
        activities: stage.activities.map((activity) => ({
            id: activity.activity_id,
            type: activity.type,
            title: activity.title,
            objective: activity.objective,
            status: activity.status,
            statusLabel: activity.status_label,
            estimatedMinutes: activity.estimated_minutes,
            blockedReason: activity.blocked_reason,
            href: activity.status === "locked"
                ? null
                : safeActivityHref(null, activity.activity_id),
        })),
    }));
    return {
        status: journey.status,
        statusLabel: journey.status_label,
        statusReason: journey.status_reason,
        dataFreshness: journey.data_freshness,
        pathTitle: journey.path?.title ?? "新人销售基础训练",
        progressPercent: journey.progress.percentage,
        progressLabel: `${journey.progress.completed_required}/${journey.progress.total_required} 项必修已完成`,
        mission,
        missionHref: mission
            ? safeActivityHref(journey.primary_action?.href, mission.activityId)
            : null,
        currentStageId: stages.find((stage) => stage.status === "current")?.id ?? null,
        stages,
        recentProgress: journey.recent_outcomes.slice(0, 5).map((outcome) => ({
            id: outcome.outcome_id,
            title: outcome.activity_title,
            resultLabel: resultLabel(outcome.passed),
            scoreLabel: outcome.score === null
                ? null
                : outcome.max_score === null
                  ? `${outcome.score} 分`
                  : `${outcome.score}/${outcome.max_score} 分`,
            producedAt: outcome.produced_at,
            href: safeActivityHref(null, outcome.activity_id),
        })),
    };
}

const PROCESSING_STATUSES = new Set([
    "scoring_pending",
    "processing",
    "preparing",
    "evaluating",
]);

const RESULT_STATUSES = new Set([
    "scoring_pending",
    "needs_review",
    "scored",
    "completed",
]);

export interface FoundationActivityViewModel extends FoundationActivityWorkspace {
    view_model_version: "activity_workspace_vm_v1";
    display: {
        is_processing: boolean;
        has_result: boolean;
        result_only: boolean;
        keeps_runner_visible: boolean;
        task_state_label: string | null;
        task_result_path: string | null;
    };
}

const TASK_STATE_LABELS: Record<string, string> = {
    queued: "等待处理",
    running: "处理中",
    retry_wait: "等待重试",
    cancel_requested: "正在取消",
    cancelled: "已取消",
    succeeded: "已完成",
    dead_letter: "处理未完成",
};

export function toActivityViewModel(
    workspace: FoundationActivityWorkspace,
): FoundationActivityViewModel {
    const resultStatus = RESULT_STATUSES.has(workspace.runner.status);
    const keepsRunnerVisible = ["audio_assessment", "ai_coach", "assignment"].includes(
        workspace.activity.type,
    );
    return {
        ...workspace,
        view_model_version: "activity_workspace_vm_v1",
        display: {
            is_processing: workspace.task !== null || PROCESSING_STATUSES.has(workspace.runner.status),
            has_result: workspace.outcome !== null || workspace.task !== null || resultStatus,
            result_only: workspace.task !== null || resultStatus,
            keeps_runner_visible: keepsRunnerVisible,
            task_state_label: workspace.task
                ? TASK_STATE_LABELS[workspace.task.state] ?? "处理中"
                : null,
            task_result_path: workspace.task
                ? `/newcomer-training/activities/${encodeURIComponent(workspace.activity.id)}`
                : null,
        },
    };
}

export interface NotificationCenterItemViewModel {
    id: string;
    kind: "notification" | "task" | "decision" | "retraining";
    kindLabel: string;
    title: string;
    description: string;
    statusLabel: string;
    createdAt: string;
    href: string;
    actionLabel: string;
    unread: boolean;
    canCancel: boolean;
}

export interface NotificationCenterViewModel {
    items: NotificationCenterItemViewModel[];
    total: number;
    page: number;
    pageSize: number;
    hasMore: boolean;
    partialMessage: string | null;
}

export function toNotificationCenterViewModel(input: {
    notifications?: FoundationNotificationPage;
    tasks?: FoundationTaskStatusPage;
    dossier?: EvidenceDossierV1;
    page: number;
    pageSize: number;
    failedSources?: string[];
}): NotificationCenterViewModel {
    const notificationItems = (input.notifications?.items ?? []).map<NotificationCenterItemViewModel>((item) => ({
        id: `notification:${item.notification_id}`,
        kind: "notification",
        kindLabel: item.created_from,
        title: item.title,
        description: item.content,
        statusLabel: item.is_read ? "已读" : "未读",
        createdAt: item.created_at,
        href: item.action_path ?? "/newcomer-training",
        actionLabel: item.action_label ?? "返回当前训练",
        unread: !item.is_read,
        canCancel: false,
    }));
    const taskItems = (input.tasks?.items ?? []).map<NotificationCenterItemViewModel>((task) => ({
        id: `task:${task.task_id}`,
        kind: "task",
        kindLabel: "后台任务",
        title: task.title,
        description: task.error?.message
            ?? task.progress?.label
            ?? (task.state === "succeeded" ? "结果已经安全保存。" : "任务已接受，可以离开页面后再回来查看。"),
        statusLabel: task.state_label,
        createdAt: task.updated_at,
        href: task.result_path ?? `/newcomer-training/tasks/${encodeURIComponent(task.task_id)}`,
        actionLabel: task.result_path ? "查看业务结果" : "查看任务进度",
        unread: !["succeeded", "cancelled"].includes(task.state),
        canCancel: task.can_cancel,
    }));
    const decision = input.dossier?.human_decision;
    const decisionItem: NotificationCenterItemViewModel[] = decision ? [{
        id: `decision:${decision.decision_id}`,
        kind: "decision",
        kindLabel: "达标复核",
        title: decision.decision_label,
        description: decision.reason,
        statusLabel: decision.status === "active" ? "当前结论" : "历史结论",
        createdAt: decision.created_at,
        href: "/newcomer-training/dossier",
        actionLabel: "查看训练档案",
        unread: false,
        canCancel: false,
    }] : [];
    const retrainingItems = (input.dossier?.retraining ?? [])
        .filter((item) => !["completed", "cancelled"].includes(item.status))
        .map<NotificationCenterItemViewModel>((item) => ({
            id: `retraining:${item.assignment_id}`,
            kind: "retraining",
            kindLabel: "补练安排",
            title: item.activity_title,
            description: item.reason,
            statusLabel: "待完成",
            createdAt: item.assigned_at,
            href: item.next_action?.href?.startsWith("/newcomer-training")
                ? item.next_action.href
                : "/newcomer-training",
            actionLabel: item.next_action?.label ?? "查看当前训练",
            unread: true,
            canCancel: false,
        }));
    const deduped = new Map<string, NotificationCenterItemViewModel>();
    [...notificationItems, ...taskItems, ...decisionItem, ...retrainingItems]
        .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))
        .forEach((item) => {
            const resultKey = ["notification", "task"].includes(item.kind)
                && item.href !== "/newcomer-training"
                ? `result:${item.href}`
                : item.id;
            if (!deduped.has(resultKey)) deduped.set(resultKey, item);
        });
    const failedSources = input.failedSources ?? [];
    return {
        items: [...deduped.values()],
        total: Math.max(input.notifications?.total ?? 0, input.tasks?.total ?? 0, deduped.size),
        page: input.page,
        pageSize: input.pageSize,
        hasMore: Boolean(input.notifications?.has_more || input.tasks?.has_more),
        partialMessage: failedSources.length > 0
            ? `${failedSources.join("、")}暂时无法更新，已保留其余可用结果。`
            : null,
    };
}

function objectRecord(value: unknown): Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value)
        ? value as Record<string, unknown>
        : {};
}

function stringValue(value: unknown): string {
    return typeof value === "string" ? value : "";
}

function nullableString(value: unknown): string | null {
    return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: unknown): number | null {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}
