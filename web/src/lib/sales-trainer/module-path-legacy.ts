import type { SalesTrainerPath, SalesTrainerPathLevel, SalesTrainerUnit } from "@/lib/api/types";

import type { SalesTrainerModuleView } from "./module-path";

type LegacyLevel = {
    readonly level: SalesTrainerPathLevel;
    readonly unit: SalesTrainerUnit | undefined;
};

function moduleKeyFor(item: LegacyLevel): string | null {
    return item.unit?.config.path?.module_key ?? null;
}

function moduleTypeFor(item: LegacyLevel): string | null {
    return item.unit?.config.path?.module_type ?? null;
}

function hasModuleConfig(item: LegacyLevel | undefined): boolean {
    return Boolean(item && moduleKeyFor(item));
}

function durationLabelFromLevel(level: SalesTrainerPathLevel): string {
    const durationMatch = level.level_title.match(/(\d+)\s*分钟/);
    if (durationMatch?.[1]) {
        return `${durationMatch[1]} 分钟`;
    }
    return level.level_title;
}

export function buildLegacyModuleViews(
    path: SalesTrainerPath,
    unitsById: Map<string, SalesTrainerUnit>,
): SalesTrainerModuleView[] {
    const enrichedLevels = [...path.levels]
        .sort((a, b) => a.order_index - b.order_index)
        .map((level) => ({
            level,
            unit: unitsById.get(level.unit_id),
        }));
    const pptItem = enrichedLevels.find((item) => moduleKeyFor(item) === "ppt_explanation")
        ?? enrichedLevels.find((item) => item.level.order_index === 1);
    const hubItem = enrichedLevels.find((item) => moduleKeyFor(item) === "business_skills")
        ?? enrichedLevels.find((item) => item.level.order_index === 2);
    const audioLevels = enrichedLevels
        .filter((item) =>
            moduleKeyFor(item) === "elevator_pitch"
            || moduleTypeFor(item) === "audio_scoring_group"
            || (!moduleKeyFor(item) && item.level.order_index >= 3)
        )
        .map((item) => item.level);
    const realtimeItem = enrichedLevels.find((item) => moduleKeyFor(item) === "realtime_roleplay_placeholder");

    return [
        {
            key: "ppt",
            title: hasModuleConfig(pptItem) ? pptItem?.level.level_title ?? "PPT讲解录音" : "PPT讲解录音",
            description: pptItem?.level.level_description ?? "学习新人训练路径 PPT 讲解要点后上传录音，由 AI 转写并评分。",
            orderLabel: "模块 1",
            primaryActionLabel: "上传 PPT 讲解录音",
            pptUploadHref: pptItem?.level.target_path ?? null,
            learnHubHref: null,
            learnHref: null,
            hubUnitId: null,
            audioOptions: [],
            disabled: false,
            disabledReason: null,
        },
        {
            key: "business_skills",
            title: hasModuleConfig(hubItem) ? hubItem?.level.level_title ?? "商务技巧" : "商务技巧",
            description: hubItem?.level.level_description ?? "阅读见客户前商务礼仪文章，并完成商务技巧考卷。",
            orderLabel: "模块 2",
            primaryActionLabel: "开始学习",
            pptUploadHref: null,
            learnHubHref: "/sales-trainer/business-skills",
            learnHref: hubItem?.level.unit_id
                ? `/sales-trainer/business-skills?unitId=${encodeURIComponent(hubItem.level.unit_id)}`
                : "/sales-trainer/business-skills",
            hubUnitId: hubItem?.level.unit_id ?? null,
            audioOptions: [],
            disabled: false,
            disabledReason: null,
        },
        {
            key: "elevator_pitch",
            title: audioLevels.some((level) => moduleKeyFor({ level, unit: unitsById.get(level.unit_id) }))
                ? audioLevels[0]?.name ?? "电梯演讲"
                : "电梯演讲",
            description: audioLevels[0]?.level_description ?? "选择后台配置的时长上传 PPT 演讲录音，获取转写与评分反馈。",
            orderLabel: "模块 3",
            primaryActionLabel: "选择演讲时长",
            pptUploadHref: null,
            learnHubHref: null,
            learnHref: null,
            hubUnitId: null,
            audioOptions: audioLevels.map((level) => ({
                level,
                durationLabel: durationLabelFromLevel(level),
            })),
            disabled: false,
            disabledReason: null,
        },
        {
            key: "realtime_practice",
            title: hasModuleConfig(realtimeItem) ? realtimeItem?.level.level_title ?? "实时对练" : "实时对练",
            description: realtimeItem?.level.level_description ?? "调用现有机器人系统进行客户模拟对练，当前迭代仅展示占位，不启动实时会话。",
            orderLabel: "模块 4",
            primaryActionLabel: null,
            pptUploadHref: null,
            learnHubHref: null,
            learnHref: null,
            hubUnitId: null,
            audioOptions: [],
            disabled: true,
            disabledReason: realtimeItem?.unit?.config.path?.disabled_reason ?? "暂不开放",
        },
    ];
}
