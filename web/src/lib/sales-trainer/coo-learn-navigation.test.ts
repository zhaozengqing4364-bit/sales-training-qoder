import { describe, expect, it } from "vitest";

import type { LearningChapter, SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";

import {
    buildLearnHref,
    buildPathChapterEntries,
    decodeReturnTo,
    findAdjacentLearnUnits,
    resolveChapterByOrderIndex,
    validateCooChapterAccess,
} from "./coo-learn-navigation";

function baseUnit(overrides: Partial<SalesTrainerUnit> = {}): SalesTrainerUnit {
    return {
        unit_id: "unit-1",
        name: "Unit 1",
        description: null,
        unit_type: "quiz",
        config: {
            learner: { chapter_order_index: 1 },
        },
        status: "published",
        created_by: null,
        updated_by: null,
        created_at: "2026-05-28T00:00:00Z",
        updated_at: "2026-05-28T00:00:00Z",
        questions: [],
        ...overrides,
    };
}

function basePath(): SalesTrainerPath {
    return {
        path_key: "coo",
        title: "COO 路径",
        goal_title: "目标",
        total_levels: 2,
        completed_levels: 0,
        current_level_id: "unit-1",
        next_level_id: "unit-2",
        goal_context: {
            goal_title: "目标",
            score_basis: "sales_trainer_path_projection_v1",
            evidence_items: [],
            weak_points: [],
            next_recommendation: null,
        },
        levels: [
            {
                unit_id: "unit-1",
                name: "U1",
                description: null,
                unit_type: "quiz",
                order_index: 1,
                level_title: "第 1 关",
                level_description: null,
                locked: false,
                lock_reason: null,
                status: "available",
                completion_rule: "passed",
                primary_action_label: "开始",
                retry_action_label: "重练",
                review_action_label: "查看",
                target_path: "/sales-trainer/quiz/unit-1",
                latest_result: null,
            },
            {
                unit_id: "unit-2",
                name: "U2",
                description: null,
                unit_type: "quiz",
                order_index: 2,
                level_title: "第 2 关",
                level_description: null,
                locked: false,
                lock_reason: null,
                status: "available",
                completion_rule: "passed",
                primary_action_label: "开始",
                retry_action_label: "重练",
                review_action_label: "查看",
                target_path: "/sales-trainer/quiz/unit-2",
                latest_result: null,
            },
        ],
    };
}

describe("coo-learn-navigation", () => {
    it("builds path chapter entries from learner config", () => {
        const units = new Map<string, SalesTrainerUnit>([
            ["unit-1", baseUnit({ unit_id: "unit-1", config: { learner: { chapter_order_index: 1 } } })],
            ["unit-2", baseUnit({ unit_id: "unit-2", config: { learner: { chapter_order_index: 2 } } })],
        ]);
        const entries = buildPathChapterEntries(basePath(), units);
        expect(entries).toHaveLength(2);
        expect(entries[0].unitId).toBe("unit-1");
        expect(entries[1].chapterOrderIndex).toBe(2);
    });

    it("resolves adjacent learn units on the path", () => {
        const entries = [
            { unitId: "unit-1", chapterOrderIndex: 1, levelTitle: "L1", pathOrderIndex: 1 },
            { unitId: "unit-2", chapterOrderIndex: 2, levelTitle: "L2", pathOrderIndex: 2 },
        ];
        expect(findAdjacentLearnUnits(entries, "unit-2")).toEqual({
            prevUnitId: "unit-1",
            nextUnitId: null,
            chapterIndex: 2,
            totalChapters: 2,
        });
    });

    it("resolves chapter by order_index", () => {
        const chapters: LearningChapter[] = [
            {
                chapter_id: "c1",
                learning_content_id: "lc",
                title: "第一章",
                content: "body",
                order_index: 1,
                created_at: "",
                updated_at: "",
            },
            {
                chapter_id: "c2",
                learning_content_id: "lc",
                title: "第二章",
                content: "body",
                order_index: 2,
                created_at: "",
                updated_at: "",
            },
        ];
        expect(resolveChapterByOrderIndex(chapters, 2)?.chapter_id).toBe("c2");
    });

    it("rejects access when unit is not on path", () => {
        const chapter: LearningChapter = {
            chapter_id: "c1",
            learning_content_id: "lc",
            title: "T",
            content: "",
            order_index: 1,
            created_at: "",
            updated_at: "",
        };
        expect(
            validateCooChapterAccess({
                pathContext: null,
                chapter,
                expectedChapterOrderIndex: 1,
            }),
        ).toContain("销售训练路径");
    });

    it("builds learn href and decodes return path", () => {
        expect(buildLearnHref("unit-1")).toBe("/sales-trainer/learn/unit-1");
        expect(buildLearnHref("unit-1", "/sales-trainer")).toBe("/sales-trainer/learn/unit-1");
        expect(buildLearnHref("unit-1", "/sales-trainer?tab=path")).toContain("returnTo=");
        expect(decodeReturnTo(encodeURIComponent("/sales-trainer"))).toBe("/sales-trainer");
        expect(decodeReturnTo("https://evil.com")).toBe("/sales-trainer");
    });
});
