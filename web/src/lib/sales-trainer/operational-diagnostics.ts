import type {
    NewcomerPathConfigResponse,
    NewcomerPathModuleConfig,
    NewcomerPathRevisionSummary,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
} from "@/lib/api/types";
import { readRealtimeProviderReadinessDiagnostics } from "@/lib/sales-trainer/realtime-provider-readiness";

const FAILED_AUDIO_STATUSES = new Set<string>([
    "transcription_failed",
    "scoring_failed",
]);
const RUNTIME_HEALTH_HREF = "/support/runtime";

export interface NewcomerFailedTask {
    readonly id: string;
    readonly source: "audio_submission" | "score_result";
    readonly title: string;
    readonly status: string;
    readonly errorCode: string;
    readonly errorMessage: string | null;
    readonly occurredAt: string;
    readonly href: string;
}

export interface NewcomerErrorCodeBucket {
    readonly code: string;
    readonly count: number;
}

export type NewcomerConfigurationDiagnosticStatus = "ready" | "missing" | "disabled";

export interface NewcomerModuleBindingDiagnostic {
    readonly title: string;
    readonly status: NewcomerConfigurationDiagnosticStatus;
    readonly detail: string;
    readonly href: string;
}

export interface NewcomerConfigurationDiagnostics {
    readonly sourceLabel: string;
    readonly activeRevisionLabel: string;
    readonly workingRevisionLabel: string;
    readonly latestReason: string | null;
    readonly revisionCount: number;
    readonly legacySnapshotOnlyCount: number;
    readonly moduleBindings: readonly NewcomerModuleBindingDiagnostic[];
}

export interface NewcomerOperationalDiagnostics {
    readonly failedCount: number;
    readonly failedTasks: readonly NewcomerFailedTask[];
    readonly errorCodeBuckets: readonly NewcomerErrorCodeBucket[];
    readonly configuration: NewcomerConfigurationDiagnostics | null;
}

export interface NewcomerOperationalDiagnosticsInput {
    readonly audioSubmissions: readonly SalesTrainerAudioSubmission[];
    readonly scoreResults: readonly SalesTrainerAudioScoreResult[];
    readonly pathConfig?: NewcomerPathConfigResponse | null;
    readonly pathRevisions?: readonly NewcomerPathRevisionSummary[];
}

export function buildNewcomerOperationalDiagnostics(
    input: NewcomerOperationalDiagnosticsInput,
): NewcomerOperationalDiagnostics {
    const failedTasks = [
        ...input.audioSubmissions.flatMap(audioFailureTask),
        ...input.scoreResults.flatMap(scoreFailureTask),
    ].sort((left, right) => Date.parse(right.occurredAt) - Date.parse(left.occurredAt));
    return {
        failedCount: failedTasks.length,
        failedTasks,
        errorCodeBuckets: buildErrorCodeBuckets(failedTasks),
        configuration: buildConfigurationDiagnostics(input),
    };
}

function audioFailureTask(submission: SalesTrainerAudioSubmission): NewcomerFailedTask[] {
    const errorCode = submission.error_code;
    if (!FAILED_AUDIO_STATUSES.has(submission.status) && !errorCode) {
        return [];
    }
    return [{
        id: submission.submission_id,
        source: "audio_submission",
        title: `${submission.user_name ?? submission.user_id} · ${submission.original_filename}`,
        status: submission.status,
        errorCode: errorCode ?? "[AUDIO_STATUS_FAILED]",
        errorMessage: submission.error_message,
        occurredAt: submission.updated_at,
        href: `/admin/sales-trainer/audio-submissions/${encodeURIComponent(submission.submission_id)}`,
    }];
}

function scoreFailureTask(score: SalesTrainerAudioScoreResult): NewcomerFailedTask[] {
    if (!score.error_code) {
        return [];
    }
    return [{
        id: score.score_id,
        source: "score_result",
        title: `评分结果 · ${score.submission_id}`,
        status: "scoring_failed",
        errorCode: score.error_code,
        errorMessage: score.error_message,
        occurredAt: score.created_at,
        href: "/admin/sales-trainer/score-results",
    }];
}

function buildErrorCodeBuckets(
    failedTasks: readonly NewcomerFailedTask[],
): NewcomerErrorCodeBucket[] {
    const buckets = new Map<string, number>();
    for (const task of failedTasks) {
        buckets.set(task.errorCode, (buckets.get(task.errorCode) ?? 0) + 1);
    }
    return [...buckets.entries()]
        .map(([code, count]) => ({ code, count }))
        .sort((left, right) => right.count - left.count);
}

function buildConfigurationDiagnostics(
    input: NewcomerOperationalDiagnosticsInput,
): NewcomerConfigurationDiagnostics | null {
    const pathConfig = input.pathConfig;
    if (!pathConfig) {
        return null;
    }
    const revisions = input.pathRevisions ?? [];
    return {
        sourceLabel: pathConfig.source === "active_revision" ? "路径级发布配置" : "兼容迁移视图",
        activeRevisionLabel: pathConfig.active_revision_no
            ? `当前生效版本 v${pathConfig.active_revision_no}`
            : "尚未发布路径级版本",
        workingRevisionLabel: pathConfig.working_revision_no
            ? `待发布修订 v${pathConfig.working_revision_no}`
            : "无待发布修订",
        latestReason: revisions[0]?.reason ?? null,
        revisionCount: revisions.length,
        legacySnapshotOnlyCount: legacySnapshotOnlyCount(input),
        moduleBindings: [...pathConfig.path.modules]
            .sort((left, right) => left.order_index - right.order_index)
            .map((module) => moduleBindingDiagnostic(module, pathConfig)),
    };
}

function legacySnapshotOnlyCount(input: NewcomerOperationalDiagnosticsInput): number {
    return [
        ...input.audioSubmissions.filter((submission) => submission.legacy_snapshot_only),
        ...input.scoreResults.filter((result) => result.legacy_snapshot_only),
    ].length;
}

function moduleBindingDiagnostic(
    module: NewcomerPathModuleConfig,
    pathConfig: NewcomerPathConfigResponse,
): NewcomerModuleBindingDiagnostic {
    if (!module.enabled) {
        return moduleDiagnostic(module, "disabled", module.disabled_reason ?? "当前关卡已关闭。");
    }
    switch (module.module_type) {
        case "article_exam":
            return articleExamDiagnostic(module);
        case "audio_scoring":
        case "audio_scoring_group":
            return audioScoringDiagnostic(module);
        case "realtime_roleplay":
            return realtimeRoleplayDiagnostic(module, pathConfig);
        case "realtime_placeholder":
            return moduleDiagnostic(module, "disabled", "当前占位关闭，不创建实时对练。");
        default:
            return moduleDiagnostic(module, "missing", "关卡类型无法识别，请到配置中心检查。");
    }
}

function articleExamDiagnostic(
    module: NewcomerPathModuleConfig,
): NewcomerModuleBindingDiagnostic {
    const hasArticle = Boolean(module.learning_content_id);
    const hasPaper = Boolean(module.exam_paper_id);
    if (hasArticle && hasPaper) {
        return moduleDiagnostic(module, "ready", "学习文章和考卷已绑定。");
    }
    if (!hasArticle && !hasPaper) {
        return moduleDiagnostic(module, "missing", "缺少学习文章和考卷绑定。");
    }
    if (!hasArticle) {
        return moduleDiagnostic(module, "missing", "缺少学习文章绑定。");
    }
    return moduleDiagnostic(module, "missing", "缺少考卷绑定。");
}

function audioScoringDiagnostic(
    module: NewcomerPathModuleConfig,
): NewcomerModuleBindingDiagnostic {
    const hasMaterial = Boolean(module.material_id && module.material_version_id);
    const hasPrompt = Boolean(module.scoring_prompt_id);
    if (hasMaterial && hasPrompt) {
        return moduleDiagnostic(module, "ready", "材料版本和录音评分标准已绑定。");
    }
    if (!hasMaterial && !hasPrompt) {
        return moduleDiagnostic(module, "missing", "缺少材料版本和录音评分标准。");
    }
    if (!hasMaterial) {
        return moduleDiagnostic(module, "missing", "缺少材料版本。");
    }
    return moduleDiagnostic(module, "missing", "材料已绑定，缺少录音评分标准。");
}

function realtimeRoleplayDiagnostic(
    module: NewcomerPathModuleConfig,
    pathConfig: NewcomerPathConfigResponse,
): NewcomerModuleBindingDiagnostic {
    const projectedReadiness = realtimeProjectedReadiness(pathConfig, module.module_key);
    if (projectedReadiness) {
        if (!projectedReadiness.ready) {
            return moduleDiagnostic(
                module,
                "missing",
                `provider readiness 未通过：${projectedReadiness.failureReason}`,
                RUNTIME_HEALTH_HREF,
            );
        }
        return moduleDiagnostic(
            module,
            "ready",
            `运行时 ${projectedReadiness.runtimeDescriptorId} 与 provider readiness 已就绪。`,
            RUNTIME_HEALTH_HREF,
        );
    }
    const binding = module.runtime_binding;
    if (!binding) {
        return moduleDiagnostic(module, "missing", "缺少实时对练运行时绑定。");
    }
    const readiness = binding.provider_readiness_snapshot;
    if (!readiness.ready) {
        return moduleDiagnostic(
            module,
            "missing",
            `provider readiness 未通过：${readiness.failure_message ?? readiness.failure_code ?? "provider 未就绪"}`,
            RUNTIME_HEALTH_HREF,
        );
    }
    return moduleDiagnostic(
        module,
        "ready",
        `运行时 ${binding.runtime_descriptor_id} 与 provider readiness 已就绪。`,
        RUNTIME_HEALTH_HREF,
    );
}

function realtimeProjectedReadiness(
    pathConfig: NewcomerPathConfigResponse,
    moduleKey: string,
): {
    readonly ready: boolean;
    readonly runtimeDescriptorId: string;
    readonly failureReason: string;
} | null {
    return readRealtimeProviderReadinessDiagnostics(pathConfig.diagnostics)
        ?.find((record) => record.moduleKey === moduleKey) ?? null;
}

function moduleDiagnostic(
    module: NewcomerPathModuleConfig,
    status: NewcomerConfigurationDiagnosticStatus,
    detail: string,
    href = `/admin/sales-trainer/paths?module=${encodeURIComponent(module.module_key)}`,
): NewcomerModuleBindingDiagnostic {
    return {
        title: module.title,
        status,
        detail,
        href,
    };
}
