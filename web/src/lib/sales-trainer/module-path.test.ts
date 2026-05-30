import { describe, expect, it } from "vitest";

import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";

import {
    NEW_SELLER_MODULES_PATH_KEY,
    buildModuleViews,
    filterPathsForHome,
    isThreeModulePath,
} from "./module-path";

const modulePath = (): SalesTrainerPath => ({
    path_key: NEW_SELLER_MODULES_PATH_KEY,
    title: "新人销售三模块训练",
    goal_title: "按模块自选",
    total_levels: 5,
    completed_levels: 0,
    current_level_id: "u1",
    next_level_id: "u1",
    goal_context: {
        goal_title: "按模块自选",
        score_basis: "sales_trainer_path_projection_v1",
        evidence_items: [],
        weak_points: [],
        next_recommendation: null,
    },
    levels: [
        {
            unit_id: "u1",
            name: "模块一",
            description: null,
            unit_type: "audio_scoring",
            order_index: 1,
            level_title: "PPT",
            level_description: "上传主胶片讲解录音",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/u1",
            latest_result: null,
        },
        {
            unit_id: "u2",
            name: "模块二",
            description: null,
            unit_type: "quiz",
            order_index: 2,
            level_title: "商务",
            level_description: "拜访前",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "submitted",
            primary_action_label: "学习",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/learn/hub",
            latest_result: null,
        },
        {
            unit_id: "u3",
            name: "5分钟",
            description: null,
            unit_type: "audio_scoring",
            order_index: 3,
            level_title: "金字塔演讲 · 5 分钟",
            level_description: "5m",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/u3",
            latest_result: null,
        },
        {
            unit_id: "u4",
            name: "10分钟",
            description: null,
            unit_type: "audio_scoring",
            order_index: 4,
            level_title: "金字塔演讲 · 10 分钟",
            level_description: "10m",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/u4",
            latest_result: null,
        },
        {
            unit_id: "u5",
            name: "15分钟",
            description: null,
            unit_type: "audio_scoring",
            order_index: 5,
            level_title: "金字塔演讲 · 15 分钟",
            level_description: "15m",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/u5",
            latest_result: null,
        },
    ],
});

describe("module-path", () => {
    it("detects three-module path key", () => {
        expect(isThreeModulePath(modulePath())).toBe(true);
    });

    it("prefers module path when legacy flag is off", () => {
        const paths = [
            modulePath(),
            { ...modulePath(), path_key: "new_seller_goal_path", total_levels: 17 },
        ];
        const filtered = filterPathsForHome(paths);
        expect(filtered).toHaveLength(1);
        expect(filtered[0].path_key).toBe(NEW_SELLER_MODULES_PATH_KEY);
    });

    it("builds three module cards with ppt upload and audio options", () => {
        const views = buildModuleViews(modulePath(), new Map<string, SalesTrainerUnit>());
        expect(views).toHaveLength(3);
        expect(views[0].pptUploadHref).toBe("/sales-trainer/audio/u1");
        expect(views[1].learnHubHref).toBe("/sales-trainer/learn/hub");
        expect(views[2].audioOptions).toHaveLength(3);
        expect(views[2].audioOptions[0].durationLabel).toBe("5 分钟");
    });
});
