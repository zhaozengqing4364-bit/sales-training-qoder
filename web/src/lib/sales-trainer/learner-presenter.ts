import type {
    SalesTrainerAudioSubmissionStatus,
    SalesTrainerPath,
    SalesTrainerPathLevel,
    SalesTrainerUnit,
    SalesTrainerUnitConfig,
    SalesTrainerUnitType,
} from "@/lib/api/types";

export interface SalesTrainerLearnerConfig {
    learning_content_id?: string;
    chapter_order_index?: number;
    presentation_entry?: string;
    hub?: boolean;
}

export function readLearnerConfig(
    config: SalesTrainerUnitConfig | undefined,
): SalesTrainerLearnerConfig | null {
    const learner = config?.learner;
    if (!learner || typeof learner !== "object") {
        return null;
    }
    return learner as SalesTrainerLearnerConfig;
}

const DEFAULT_AUDIO_PASS_THRESHOLD = 70;

const INTERNAL_UNIT_NAME_PATTERN = /E2E|Goal验收|测试|test/i;

const SUBMISSION_STATUS_LABELS: Record<SalesTrainerAudioSubmissionStatus, string> = {
    uploaded: "已上传",
    transcribing: "正在转写",
    transcribed: "转写完成",
    transcription_failed: "转写失败",
    scoring: "正在评分",
    scored: "评分完成",
    scoring_failed: "评分失败",
};

export function getUnitTypeLabel(unitType: SalesTrainerUnitType): string {
    return unitType === "quiz" ? "做题训练" : "语音作业（上传）";
}

export function getSubmissionStatusLabel(status: SalesTrainerAudioSubmissionStatus): string {
    return SUBMISSION_STATUS_LABELS[status] ?? "处理中";
}

export function isTerminalSubmissionStatus(status: SalesTrainerAudioSubmissionStatus): boolean {
    return status === "scored" || status === "transcription_failed" || status === "scoring_failed";
}

export function collectPathUnitIds(paths: SalesTrainerPath[]): Set<string> {
    const unitIds = new Set<string>();
    for (const path of paths) {
        for (const level of path.levels) {
            unitIds.add(level.unit_id);
        }
    }
    return unitIds;
}

export function isLikelyInternalUnit(unit: SalesTrainerUnit): boolean {
    return INTERNAL_UNIT_NAME_PATTERN.test(unit.name);
}

export function partitionUnits(
    units: SalesTrainerUnit[],
    pathUnitIds: Set<string>,
): { pathUnits: SalesTrainerUnit[]; extraUnits: SalesTrainerUnit[] } {
    const pathUnits: SalesTrainerUnit[] = [];
    const extraUnits: SalesTrainerUnit[] = [];

    for (const unit of units) {
        if (pathUnitIds.has(unit.unit_id)) {
            pathUnits.push(unit);
        } else {
            extraUnits.push(unit);
        }
    }

    return { pathUnits, extraUnits };
}

export function sortExtraUnits(units: SalesTrainerUnit[]): SalesTrainerUnit[] {
    return [...units].sort((left, right) => {
        const leftInternal = isLikelyInternalUnit(left);
        const rightInternal = isLikelyInternalUnit(right);
        if (leftInternal !== rightInternal) {
            return leftInternal ? 1 : -1;
        }
        return left.name.localeCompare(right.name, "zh-CN");
    });
}

export function getAudioPassThreshold(unit: SalesTrainerUnit | null | undefined): number {
    const threshold = unit?.config.audio?.pass_threshold;
    return typeof threshold === "number" && Number.isFinite(threshold) ? threshold : DEFAULT_AUDIO_PASS_THRESHOLD;
}

export function findFocusLevel(path: SalesTrainerPath): SalesTrainerPathLevel | undefined {
    const recommendationUnitId = path.goal_context.next_recommendation?.unit_id;
    return path.levels.find((level) => level.unit_id === recommendationUnitId)
        ?? path.levels.find((level) => level.unit_id === path.next_level_id)
        ?? path.levels.find((level) => level.unit_id === path.current_level_id)
        ?? path.levels.find((level) => level.status !== "completed")
        ?? path.levels[path.levels.length - 1];
}

export function findLevelForUnit(
    paths: SalesTrainerPath[],
    unitId: string,
): { path: SalesTrainerPath; level: SalesTrainerPathLevel } | null {
    for (const path of paths) {
        const level = path.levels.find((candidate) => candidate.unit_id === unitId);
        if (level) {
            return { path, level };
        }
    }
    return null;
}

export interface PrimaryAction {
    title: string;
    reason: string;
    actionLabel: string;
    targetPath: string;
    levelTitle: string | null;
}

export function resolvePrimaryAction(path: SalesTrainerPath): PrimaryAction | null {
    const recommendation = path.goal_context.next_recommendation;
    if (recommendation) {
        return {
            title: recommendation.title,
            reason: recommendation.reason,
            actionLabel: recommendation.action_label,
            targetPath: recommendation.target_path,
            levelTitle: recommendation.level_title,
        };
    }

    const focusLevel = findFocusLevel(path);
    if (!focusLevel || focusLevel.locked) {
        return null;
    }

    const actionLabel = focusLevel.status === "completed"
        ? focusLevel.review_action_label
        : focusLevel.status === "in_progress"
            ? focusLevel.retry_action_label
            : focusLevel.primary_action_label;
    const targetPath = focusLevel.status === "completed" && focusLevel.latest_result?.target_path
        ? focusLevel.latest_result.target_path
        : focusLevel.target_path;

    return {
        title: focusLevel.level_title,
        reason: focusLevel.level_description || focusLevel.description || "继续完成本关训练。",
        actionLabel,
        targetPath,
        levelTitle: focusLevel.level_title,
    };
}

export function getLevelStatusLabel(level: SalesTrainerPathLevel): string {
    if (level.locked) {
        return "未解锁";
    }
    if (level.status === "completed") {
        return "已通关";
    }
    if (level.status === "in_progress") {
        return "待重练";
    }
    return "当前可练";
}

export function isCurrentFocusLevel(path: SalesTrainerPath, level: SalesTrainerPathLevel): boolean {
    const focusLevel = findFocusLevel(path);
    return focusLevel?.unit_id === level.unit_id;
}

export function getLevelAction(level: SalesTrainerPathLevel): { href: string; label: string } {
    const href = level.status === "completed" && level.latest_result?.target_path
        ? level.latest_result.target_path
        : level.target_path;
    const label = level.status === "completed"
        ? "查看结果"
        : level.status === "in_progress"
            ? level.retry_action_label
            : level.primary_action_label;

    return { href, label };
}

export function formatPassThresholdLine(threshold: number): string {
    return `本关需达到 ${threshold} 分通过，可多次上传，以最新一次为准`;
}

export function getLearnerChapterLink(
    unit: SalesTrainerUnit | null | undefined,
): string | null {
    const learner = readLearnerConfig(unit?.config);
    const chapterOrderIndex = learner?.chapter_order_index;
    if (!unit?.unit_id || typeof chapterOrderIndex !== "number" || chapterOrderIndex < 1) {
        return null;
    }
    return `/sales-trainer/learn/${unit.unit_id}`;
}

export function getLearnerChapterHint(
    unit: SalesTrainerUnit | null | undefined,
): string | null {
    const learner = readLearnerConfig(unit?.config);
    const chapterOrderIndex = learner?.chapter_order_index;
    if (typeof chapterOrderIndex !== "number" || chapterOrderIndex < 1) {
        return null;
    }
    return `建议先阅读第 ${chapterOrderIndex} 章，再开始本章测验。`;
}
