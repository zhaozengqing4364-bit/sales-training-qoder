import type { SalesTrainerUnit } from "@/lib/api/types";

import { readLearnerConfig } from "./learner-presenter";

export interface HubChapterEntry {
    unitId: string;
    chapterOrderIndex: number;
    levelTitle: string;
    unitName: string;
}

export function buildHubChapterEntries(units: SalesTrainerUnit[]): HubChapterEntry[] {
    const entries: HubChapterEntry[] = [];
    for (const unit of units) {
        const learner = readLearnerConfig(unit.config);
        const chapterOrderIndex = learner?.chapter_order_index;
        if (typeof chapterOrderIndex !== "number" || chapterOrderIndex < 1) {
            continue;
        }
        entries.push({
            unitId: unit.unit_id,
            chapterOrderIndex,
            levelTitle: `第 ${chapterOrderIndex} 章`,
            unitName: unit.name,
        });
    }
    return entries.sort((left, right) => left.chapterOrderIndex - right.chapterOrderIndex);
}

export function buildHubLearnHref(unitId: string): string {
    return `/sales-trainer/learn/${unitId}?hub=1`;
}
