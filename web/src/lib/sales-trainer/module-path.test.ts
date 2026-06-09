import { describe, expect, it } from "vitest";

import type { NewcomerTrainingModuleType, SalesTrainerPath, SalesTrainerPathLevel, SalesTrainerUnit } from "@/lib/api/types";

import {
    NEWCOMER_TRAINING_PATH_KEY,
    NEW_SELLER_MODULES_PATH_KEY,
    buildModuleViews,
    filterPathsForHome,
    isThreeModulePath,
} from "./module-path";

function level(overrides: Partial<SalesTrainerPathLevel>): SalesTrainerPathLevel {
    const orderIndex = overrides.order_index ?? 1;
    return {
        unit_id: overrides.unit_id ?? `unit-${orderIndex}`,
        name: overrides.name ?? `模块 ${orderIndex}`,
        description: overrides.description ?? null,
        unit_type: overrides.unit_type ?? "audio_scoring",
        order_index: orderIndex,
        level_title: overrides.level_title ?? `第 ${orderIndex} 关`,
        level_description: overrides.level_description ?? null,
        locked: overrides.locked ?? false,
        lock_reason: overrides.lock_reason ?? null,
        status: overrides.status ?? "available",
        completion_rule: overrides.completion_rule ?? "scored",
        primary_action_label: overrides.primary_action_label ?? "开始本关",
        retry_action_label: overrides.retry_action_label ?? "重练本关",
        review_action_label: overrides.review_action_label ?? "查看结果",
        target_path: overrides.target_path ?? `/sales-trainer/audio/unit-${orderIndex}`,
        latest_result: overrides.latest_result ?? null,
    };
}

function path(levels: SalesTrainerPathLevel[], pathKey = NEW_SELLER_MODULES_PATH_KEY): SalesTrainerPath {
    return {
        path_key: pathKey,
        title: "新人训练路径",
        goal_title: "按模块自选",
        total_levels: levels.length,
        completed_levels: 0,
        current_level_id: levels[0]?.unit_id ?? null,
        next_level_id: levels[0]?.unit_id ?? null,
        goal_context: {
            goal_title: "按模块自选",
            score_basis: "sales_trainer_path_projection_v1",
            evidence_items: [],
            weak_points: [],
            next_recommendation: null,
        },
        levels,
    };
}

function unitWithPath(
    unitId: string,
    moduleKey: string,
    moduleType: NewcomerTrainingModuleType,
    pathConfig: SalesTrainerUnit["config"]["path"] = {},
): SalesTrainerUnit {
    return {
        unit_id: unitId,
        name: unitId,
        description: null,
        unit_type: moduleType === "article_exam" || moduleType === "realtime_placeholder" ? "quiz" : "audio_scoring",
        config: { path: { module_key: moduleKey, module_type: moduleType, ...pathConfig } },
        status: "published",
        created_by: null,
        updated_by: null,
        created_at: "",
        updated_at: "",
        questions: [],
    };
}

describe("module-path", () => {
    it("detects newcomer path keys", () => {
        expect(isThreeModulePath(path([]))).toBe(true);
        expect(isThreeModulePath(path([], NEWCOMER_TRAINING_PATH_KEY))).toBe(true);
    });

    it("prefers module path when legacy flag is off", () => {
        const filtered = filterPathsForHome([
            path([level({})]),
            path([level({})], "new_seller_goal_path"),
        ]);

        expect(filtered).toHaveLength(1);
        expect(filtered[0].path_key).toBe(NEW_SELLER_MODULES_PATH_KEY);
    });

    it("prefers the configured newcomer training path over the older module path", () => {
        const filtered = filterPathsForHome([
            path([level({})]),
            path([level({})], NEWCOMER_TRAINING_PATH_KEY),
        ]);

        expect(filtered).toHaveLength(1);
        expect(filtered[0].path_key).toBe(NEWCOMER_TRAINING_PATH_KEY);
    });

    it("keeps legacy order fallback only when no backend module keys exist", () => {
        const legacyPath = path([
            level({ unit_id: "u1", order_index: 1, level_title: "PPT", target_path: "/sales-trainer/audio/u1" }),
            level({ unit_id: "u2", unit_type: "quiz", order_index: 2, level_title: "商务", target_path: "/sales-trainer/business-skills" }),
            level({ unit_id: "u3", order_index: 3, level_title: "电梯演讲 · 5 分钟" }),
            level({ unit_id: "u4", order_index: 4, level_title: "电梯演讲 · 10 分钟" }),
        ]);

        const views = buildModuleViews(legacyPath, new Map<string, SalesTrainerUnit>());

        expect(views.map((view) => view.title)).toEqual(["PPT讲解录音", "商务技巧", "电梯演讲", "实时对练"]);
        expect(views[1].learnHref).toBe("/sales-trainer/business-skills?unitId=u2");
        expect(views[2].audioOptions.map((option) => option.durationLabel)).toEqual(["5 分钟", "10 分钟"]);
        expect(views[3].disabled).toBe(true);
    });

    it("does not render hardcoded modules for newcomer path without backend module keys", () => {
        const newcomerPath = path([
            level({ unit_id: "u1", order_index: 1, level_title: "PPT", target_path: "/sales-trainer/audio/u1" }),
            level({ unit_id: "u2", unit_type: "quiz", order_index: 2, level_title: "商务", target_path: "/sales-trainer/business-skills" }),
        ], NEWCOMER_TRAINING_PATH_KEY);

        const views = buildModuleViews(newcomerPath, new Map<string, SalesTrainerUnit>());

        expect(views).toEqual([]);
    });

    it("renders only modules provided by backend configuration", () => {
        const businessLevel = level({
            unit_id: "business-unit",
            unit_type: "quiz",
            order_index: 2,
            level_title: "第二关：客户拜访礼仪",
            level_description: "先学三节内容，再进入考试。",
            primary_action_label: "进入学习页",
            target_path: "/sales-trainer/business-skills",
        });
        const views = buildModuleViews(
            path([businessLevel], NEWCOMER_TRAINING_PATH_KEY),
            new Map([
                [
                    "business-unit",
                    unitWithPath("business-unit", "business_skills", "article_exam"),
                ],
            ]),
        );

        expect(views).toHaveLength(1);
        expect(views[0]).toMatchObject({
            key: "business_skills",
            title: "第二关：客户拜访礼仪",
            description: "先学三节内容，再进入考试。",
            primaryActionLabel: "进入学习页",
            learnHref: "/sales-trainer/business-skills?unitId=business-unit",
            disabled: false,
        });
    });

    it("prefers active path revision module identity over stale unit config", () => {
        const activeLevel = {
            ...level({
                unit_id: "active-business-unit",
                unit_type: "quiz",
                order_index: 1,
                level_title: "第二关：商务技巧新版",
                target_path: "/sales-trainer/business-skills",
            }),
            module_key: "business_skills" as const,
            module_type: "article_exam" as const,
        };
        const unitsById = new Map<string, SalesTrainerUnit>([
            [
                "active-business-unit",
                unitWithPath("active-business-unit", "ppt_explanation", "audio_scoring"),
            ],
        ]);

        const views = buildModuleViews(
            path([activeLevel], NEWCOMER_TRAINING_PATH_KEY),
            unitsById,
        );

        expect(views).toHaveLength(1);
        expect(views[0]).toMatchObject({
            key: "business_skills",
            title: "第二关：商务技巧新版",
            learnHref: "/sales-trainer/business-skills?unitId=active-business-unit",
        });
    });

    it("uses backend module keys and disabled realtime placeholder without order fallback", () => {
        const levels = [
            level({ unit_id: "business-unit", order_index: 10, level_title: "第二关：商务技巧", unit_type: "quiz" }),
            level({ unit_id: "ppt-unit", order_index: 20, level_title: "第一关：PPT 讲解录音", target_path: "/sales-trainer/audio/ppt-unit" }),
            level({ unit_id: "pitch-10", order_index: 30, level_title: "电梯演讲 · 10 分钟" }),
            level({ unit_id: "pitch-20", order_index: 40, level_title: "电梯演讲 · 20 分钟" }),
            level({ unit_id: "realtime", order_index: 50, level_title: "第四关：实时对练" }),
        ];
        const unitsById = new Map<string, SalesTrainerUnit>([
            ["ppt-unit", unitWithPath("ppt-unit", "ppt_explanation", "audio_scoring")],
            ["business-unit", unitWithPath("business-unit", "business_skills", "article_exam")],
            ["pitch-10", unitWithPath("pitch-10", "elevator_pitch", "audio_scoring_group")],
            ["pitch-20", unitWithPath("pitch-20", "elevator_pitch", "audio_scoring_group")],
            [
                "realtime",
                unitWithPath("realtime", "realtime_roleplay_placeholder", "realtime_placeholder", {
                    disabled_reason: "试运行阶段暂不开放",
                }),
            ],
        ]);

        const views = buildModuleViews(path(levels, NEWCOMER_TRAINING_PATH_KEY), unitsById);

        expect(views.map((view) => view.key)).toEqual(["business_skills", "ppt", "elevator_pitch", "realtime_practice"]);
        expect(views[0].hubUnitId).toBe("business-unit");
        expect(views[1].pptUploadHref).toBe("/sales-trainer/audio/ppt-unit");
        expect(views[2].audioOptions.map((option) => option.durationLabel)).toEqual(["10 分钟", "20 分钟"]);
        expect(views[3].disabledReason).toBe("试运行阶段暂不开放");
    });
});
