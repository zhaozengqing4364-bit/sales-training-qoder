import type { SalesTrainerPath, SalesTrainerPathLevel, SalesTrainerUnit } from "@/lib/api/types";

import { buildLegacyModuleViews } from "./module-path-legacy";

export const NEW_SELLER_MODULES_PATH_KEY = "new_seller_modules_v1";
export const NEWCOMER_TRAINING_PATH_KEY = "newcomer_training_path_v1";
export const LEGACY_GOAL_PATH_KEY = "new_seller_goal_path";

export const MODULE_SUGGESTED_ORDER_HINT =
    "建议顺序：PPT讲解录音 → 商务技巧 → 电梯演讲（时长自选）。实时对练暂不开放。";

export function isLegacyPathEnabled(): boolean {
    return process.env.NEXT_PUBLIC_SALES_TRAINER_LEGACY_PATH === "1";
}

export function filterPathsForHome(paths: SalesTrainerPath[]): SalesTrainerPath[] {
    const newcomerPath = paths.find((path) => path.path_key === NEWCOMER_TRAINING_PATH_KEY);
    if (newcomerPath) {
        return [newcomerPath];
    }
    const modulePath = paths.find((path) => path.path_key === NEW_SELLER_MODULES_PATH_KEY);
    if (modulePath && !isLegacyPathEnabled()) {
        return [modulePath];
    }
    if (modulePath && isLegacyPathEnabled()) {
        const legacy = paths.filter((path) => path.path_key === LEGACY_GOAL_PATH_KEY);
        return [modulePath, ...legacy];
    }
    return paths;
}

export function isThreeModulePath(path: SalesTrainerPath): boolean {
    return path.path_key === NEWCOMER_TRAINING_PATH_KEY
        || path.path_key === NEW_SELLER_MODULES_PATH_KEY;
}

export interface ModuleAudioOption {
    level: SalesTrainerPathLevel;
    durationLabel: string;
}

export interface SalesTrainerModuleView {
    key: "ppt" | "business_skills" | "elevator_pitch" | "realtime_practice";
    title: string;
    description: string;
    orderLabel: string;
    primaryActionLabel: string | null;
    pptUploadHref: string | null;
    learnHubHref: string | null;
    learnHref: string | null;
    hubUnitId: string | null;
    audioOptions: ModuleAudioOption[];
    disabled: boolean;
    disabledReason: string | null;
}

type EnrichedLevel = {
    readonly level: SalesTrainerPathLevel;
    readonly unit: SalesTrainerUnit | undefined;
};

function moduleKeyFor(enriched: EnrichedLevel): string | null {
    return enriched.level.module_key ?? enriched.unit?.config.path?.module_key ?? null;
}

function hasLevelModuleConfig(enriched: EnrichedLevel): boolean {
    return Boolean(enriched.level.module_key);
}

function durationLabelFromLevel(level: SalesTrainerPathLevel): string {
    const title = level.level_title;
    const durationMatch = title.match(/(\d+)\s*分钟/);
    if (durationMatch?.[1]) {
        return `${durationMatch[1]} 分钟`;
    }
    return level.level_title;
}

function orderLabelFor(level: SalesTrainerPathLevel): string {
    return `第 ${level.order_index} 关`;
}

function isDisabled(enriched: EnrichedLevel, defaultValue: boolean): boolean {
    if (hasLevelModuleConfig(enriched)) {
        return defaultValue;
    }
    return defaultValue || enriched.unit?.config.path?.enabled === false;
}

function disabledReasonFor(enriched: EnrichedLevel, fallback: string): string | null {
    if (!isDisabled(enriched, false)) {
        return null;
    }
    return enriched.unit?.config.path?.disabled_reason ?? fallback;
}

function titleFor(enriched: EnrichedLevel, fallback: string): string {
    return enriched.level.level_title ?? enriched.unit?.config.path?.level_title ?? fallback;
}

function descriptionFor(enriched: EnrichedLevel, fallback: string): string {
    return enriched.level.level_description ?? enriched.unit?.config.path?.level_description ?? fallback;
}

function actionLabelFor(enriched: EnrichedLevel, fallback: string): string {
    return enriched.level.primary_action_label ?? enriched.unit?.config.path?.primary_action_label ?? fallback;
}

function businessSkillsHref(level: SalesTrainerPathLevel): string {
    const targetPath = level.target_path || "/sales-trainer/business-skills";
    if (targetPath.includes("unitId=")) {
        return targetPath;
    }
    const separator = targetPath.includes("?") ? "&" : "?";
    return `${targetPath}${separator}unitId=${encodeURIComponent(level.unit_id)}`;
}

function viewKeyFor(moduleKey: string | null): SalesTrainerModuleView["key"] | null {
    switch (moduleKey) {
        case "ppt_explanation":
            return "ppt";
        case "business_skills":
            return "business_skills";
        case "elevator_pitch":
            return "elevator_pitch";
        case "realtime_roleplay_placeholder":
        case "realtime_placeholder":
            return "realtime_practice";
        default:
            return null;
    }
}

function buildPptView(enriched: EnrichedLevel): SalesTrainerModuleView {
    const disabled = isDisabled(enriched, false);
    return {
        key: "ppt",
        title: titleFor(enriched, "PPT讲解录音"),
        description: descriptionFor(enriched, "学习新人训练路径 PPT 讲解要点后上传录音，由 AI 转写并评分。"),
        orderLabel: orderLabelFor(enriched.level),
        primaryActionLabel: actionLabelFor(enriched, "上传 PPT 讲解录音"),
        pptUploadHref: disabled ? null : enriched.level.target_path,
        learnHubHref: null,
        learnHref: null,
        hubUnitId: null,
        audioOptions: [],
        disabled,
        disabledReason: disabledReasonFor(enriched, "当前模块已停用。"),
    };
}

function buildBusinessSkillsView(enriched: EnrichedLevel): SalesTrainerModuleView {
    const disabled = isDisabled(enriched, false);
    return {
        key: "business_skills",
        title: titleFor(enriched, "商务技巧"),
        description: descriptionFor(enriched, "阅读见客户前商务礼仪文章，并完成商务技巧考卷。"),
        orderLabel: orderLabelFor(enriched.level),
        primaryActionLabel: actionLabelFor(enriched, "开始学习"),
        pptUploadHref: null,
        learnHubHref: disabled ? null : "/sales-trainer/business-skills",
        learnHref: disabled ? null : businessSkillsHref(enriched.level),
        hubUnitId: enriched.level.unit_id,
        audioOptions: [],
        disabled,
        disabledReason: disabledReasonFor(enriched, "当前模块已停用。"),
    };
}

function buildElevatorPitchView(enrichedLevels: EnrichedLevel[]): SalesTrainerModuleView | null {
    const first = enrichedLevels[0];
    if (!first) {
        return null;
    }
    const disabled = isDisabled(first, false);
    return {
        key: "elevator_pitch",
        title: first.unit?.config.path?.level_title ?? first.unit?.name ?? "电梯演讲",
        description: descriptionFor(first, "选择后台配置的时长上传 PPT 演讲录音，获取转写与评分反馈。"),
        orderLabel: orderLabelFor(first.level),
        primaryActionLabel: actionLabelFor(first, "选择演讲时长"),
        pptUploadHref: null,
        learnHubHref: null,
        learnHref: null,
        hubUnitId: null,
        audioOptions: enrichedLevels
            .filter((item) => !isDisabled(item, false))
            .map((item) => ({
                level: item.level,
                durationLabel: durationLabelFromLevel(item.level),
            })),
        disabled,
        disabledReason: disabledReasonFor(first, "当前模块已停用。"),
    };
}

function buildRealtimePlaceholderView(enriched: EnrichedLevel): SalesTrainerModuleView {
    const disabledReason = enriched.unit?.config.path?.disabled_reason ?? "暂不开放";
    return {
        key: "realtime_practice",
        title: titleFor(enriched, "实时对练"),
        description: descriptionFor(enriched, "调用现有机器人系统进行客户模拟对练，当前迭代仅展示占位，不启动实时会话。"),
        orderLabel: orderLabelFor(enriched.level),
        primaryActionLabel: null,
        pptUploadHref: null,
        learnHubHref: null,
        learnHref: null,
        hubUnitId: null,
        audioOptions: [],
        disabled: true,
        disabledReason,
    };
}

function buildConfiguredModuleViews(enrichedLevels: EnrichedLevel[]): SalesTrainerModuleView[] {
    const views: SalesTrainerModuleView[] = [];
    const elevatorLevels = enrichedLevels.filter((item) => viewKeyFor(moduleKeyFor(item)) === "elevator_pitch");
    let didAddElevator = false;

    for (const item of enrichedLevels) {
        const viewKey = viewKeyFor(moduleKeyFor(item));
        switch (viewKey) {
            case "ppt":
                views.push(buildPptView(item));
                break;
            case "business_skills":
                views.push(buildBusinessSkillsView(item));
                break;
            case "elevator_pitch":
                if (!didAddElevator) {
                    const elevatorView = buildElevatorPitchView(elevatorLevels);
                    if (elevatorView) {
                        views.push(elevatorView);
                    }
                    didAddElevator = true;
                }
                break;
            case "realtime_practice":
                views.push(buildRealtimePlaceholderView(item));
                break;
            case null:
                break;
        }
    }

    return views;
}

export function buildModuleViews(
    path: SalesTrainerPath,
    unitsById: Map<string, SalesTrainerUnit>,
): SalesTrainerModuleView[] {
    const sorted = [...path.levels].sort((a, b) => a.order_index - b.order_index);
    const enrichedLevels = sorted.map((level) => ({
        level,
        unit: unitsById.get(level.unit_id),
    }));
    const hasConfiguredModules = enrichedLevels.some((item) => moduleKeyFor(item));
    if (hasConfiguredModules) {
        return buildConfiguredModuleViews(enrichedLevels);
    }
    if (path.path_key === NEWCOMER_TRAINING_PATH_KEY) {
        return [];
    }
    return buildLegacyModuleViews(path, unitsById);
}
