import type { LearningChapter, SalesTrainerPath, SalesTrainerPathLevel, SalesTrainerUnit } from "@/lib/api/types";

import { readLearnerConfig, type SalesTrainerLearnerConfig } from "./learner-presenter";

export const SALES_TRAINER_LEARN_RETURN_KEY = "sales_trainer_learn_return";

export const DEFAULT_SALES_TRAINER_RETURN = "/sales-trainer";

export interface PathChapterEntry {
    unitId: string;
    chapterOrderIndex: number;
    levelTitle: string;
    pathOrderIndex: number;
}

export function getCooLearningContentId(): string | undefined {
    return process.env.NEXT_PUBLIC_COO_LEARNING_CONTENT_ID;
}

export function isCooLearningContentId(contentId: string): boolean {
    const cooId = getCooLearningContentId();
    return Boolean(cooId && contentId === cooId);
}

export function resolveLearnerContentId(
    learner: SalesTrainerLearnerConfig | null,
): string | undefined {
    return learner?.learning_content_id ?? getCooLearningContentId();
}

export function buildPathChapterEntries(
    path: SalesTrainerPath,
    unitsById: Map<string, SalesTrainerUnit>,
): PathChapterEntry[] {
    const sortedLevels = [...path.levels].sort((left, right) => left.order_index - right.order_index);
    const entries: PathChapterEntry[] = [];

    for (const level of sortedLevels) {
        const unit = unitsById.get(level.unit_id);
        const learner = readLearnerConfig(unit?.config);
        const chapterOrderIndex = learner?.chapter_order_index;
        if (typeof chapterOrderIndex !== "number" || chapterOrderIndex < 1) {
            continue;
        }
        entries.push({
            unitId: level.unit_id,
            chapterOrderIndex,
            levelTitle: level.level_title,
            pathOrderIndex: level.order_index,
        });
    }

    return entries;
}

export function findAdjacentLearnUnits(
    entries: PathChapterEntry[],
    currentUnitId: string,
): { prevUnitId: string | null; nextUnitId: string | null; chapterIndex: number; totalChapters: number } {
    const index = entries.findIndex((entry) => entry.unitId === currentUnitId);
    if (index < 0) {
        return {
            prevUnitId: null,
            nextUnitId: null,
            chapterIndex: 0,
            totalChapters: entries.length,
        };
    }
    return {
        prevUnitId: index > 0 ? entries[index - 1].unitId : null,
        nextUnitId: index < entries.length - 1 ? entries[index + 1].unitId : null,
        chapterIndex: index + 1,
        totalChapters: entries.length,
    };
}

export function resolveChapterByOrderIndex(
    chapters: LearningChapter[],
    chapterOrderIndex: number,
): LearningChapter | null {
    const sorted = [...chapters].sort((left, right) => left.order_index - right.order_index);
    const byOrderIndex = sorted.find((chapter) => chapter.order_index === chapterOrderIndex);
    if (byOrderIndex) {
        return byOrderIndex;
    }
    return sorted[chapterOrderIndex - 1] ?? null;
}

export function validateCooChapterAccess(params: {
    pathContext: { path: SalesTrainerPath; level: SalesTrainerPathLevel } | null;
    chapter: LearningChapter | null;
    expectedChapterOrderIndex: number;
    softHubNavigation?: boolean;
}): string | null {
    if (!params.pathContext && !params.softHubNavigation) {
        return "请从新人训练路径进入本章阅读。";
    }
    if (params.softHubNavigation) {
        if (!params.chapter) {
            return "未找到对应章节内容，请联系管理员检查配置。";
        }
        return null;
    }
    if (!params.chapter) {
        return "未找到对应章节内容，请联系管理员检查配置。";
    }
    if (params.chapter.order_index !== params.expectedChapterOrderIndex) {
        return "章节与训练关卡不匹配，请从新人训练路径重新进入。";
    }
    return null;
}

export function decodeReturnTo(value: string | null | undefined): string {
    if (!value) {
        return DEFAULT_SALES_TRAINER_RETURN;
    }
    try {
        const decoded = decodeURIComponent(value);
        if (decoded.startsWith("/") && !decoded.startsWith("//")) {
            return decoded;
        }
    } catch {
        return DEFAULT_SALES_TRAINER_RETURN;
    }
    return DEFAULT_SALES_TRAINER_RETURN;
}

export function buildLearnHref(unitId: string, returnTo = DEFAULT_SALES_TRAINER_RETURN): string {
    if (!returnTo || returnTo === DEFAULT_SALES_TRAINER_RETURN) {
        return `/sales-trainer/learn/${unitId}`;
    }
    const params = new URLSearchParams({ returnTo });
    return `/sales-trainer/learn/${unitId}?${params.toString()}`;
}

export function persistLearnReturn(returnTo: string): void {
    if (typeof sessionStorage === "undefined") {
        return;
    }
    sessionStorage.setItem(SALES_TRAINER_LEARN_RETURN_KEY, returnTo);
}

export function readLearnReturn(fallback: string): string {
    if (typeof sessionStorage === "undefined") {
        return fallback;
    }
    const stored = sessionStorage.getItem(SALES_TRAINER_LEARN_RETURN_KEY);
    if (stored?.startsWith("/") && !stored.startsWith("//")) {
        return stored;
    }
    return fallback;
}
