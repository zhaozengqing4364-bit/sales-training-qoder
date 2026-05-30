import type { SalesTrainerPath, SalesTrainerPathLevel, SalesTrainerUnit } from "@/lib/api/types";


export const NEW_SELLER_MODULES_PATH_KEY = "new_seller_modules_v1";
export const LEGACY_GOAL_PATH_KEY = "new_seller_goal_path";

export const MODULE_SUGGESTED_ORDER_HINT =
    "建议顺序：PPT演练 → 拜访前商务 → 金字塔演讲（时长自选）。各模块可随时进入，无强制解锁。";

export function isLegacyPathEnabled(): boolean {
    return process.env.NEXT_PUBLIC_SALES_TRAINER_LEGACY_PATH === "1";
}

export function filterPathsForHome(paths: SalesTrainerPath[]): SalesTrainerPath[] {
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
    return path.path_key === NEW_SELLER_MODULES_PATH_KEY;
}

export interface ModuleAudioOption {
    level: SalesTrainerPathLevel;
    durationLabel: string;
}

export interface SalesTrainerModuleView {
    key: "ppt" | "visit_prep" | "pyramid";
    title: string;
    description: string;
    orderLabel: string;
    /** 模块一：上传 PPT 讲解录音 */
    pptUploadHref: string | null;
    learnHubHref: string | null;
    hubUnitId: string | null;
    audioOptions: ModuleAudioOption[];
}

function durationLabelFromLevel(level: SalesTrainerPathLevel): string {
    const title = level.level_title;
    if (title.includes("15")) {
        return "15 分钟";
    }
    if (title.includes("10")) {
        return "10 分钟";
    }
    if (title.includes("5")) {
        return "5 分钟";
    }
    return level.level_title;
}

export function buildModuleViews(
    path: SalesTrainerPath,
    _unitsById: Map<string, SalesTrainerUnit>,
): SalesTrainerModuleView[] {
    const sorted = [...path.levels].sort((a, b) => a.order_index - b.order_index);
    const pptLevel = sorted.find((level) => level.order_index === 1);
    const hubLevel = sorted.find((level) => level.order_index === 2);
    const audioLevels = sorted.filter((level) => level.order_index >= 3);

    return [
        {
            key: "ppt",
            title: "PPT演练",
            description: pptLevel?.level_description
                ?? "上传主胶片讲解录音，由 AI 转写并评分。",
            orderLabel: "模块 1",
            pptUploadHref: pptLevel?.target_path ?? null,
            learnHubHref: null,
            hubUnitId: null,
            audioOptions: [],
        },
        {
            key: "visit_prep",
            title: "拜访前商务",
            description: hubLevel?.level_description
                ?? "阅读 COO 谈市场十五讲，章节可任意顺序浏览。",
            orderLabel: "模块 2",
            pptUploadHref: null,
            learnHubHref: "/sales-trainer/learn/hub",
            hubUnitId: hubLevel?.unit_id ?? null,
            audioOptions: [],
        },
        {
            key: "pyramid",
            title: "金字塔演讲",
            description: "选择时长上传演讲录音，获取转写与评分反馈。",
            orderLabel: "模块 3",
            pptUploadHref: null,
            learnHubHref: null,
            hubUnitId: null,
            audioOptions: audioLevels.map((level) => ({
                level,
                durationLabel: durationLabelFromLevel(level),
            })),
        },
    ];
}
