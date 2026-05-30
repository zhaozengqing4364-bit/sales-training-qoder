import { describe, expect, it } from "vitest";

import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";

import {
    collectPathUnitIds,
    findFocusLevel,
    getAudioPassThreshold,
    getLearnerChapterHint,
    getLearnerChapterLink,
    getSubmissionStatusLabel,
    getUnitTypeLabel,
    isLikelyInternalUnit,
    partitionUnits,
    resolvePrimaryAction,
    sortExtraUnits,
} from "./learner-presenter";

const baseUnit = (overrides: Partial<SalesTrainerUnit>): SalesTrainerUnit => ({
    unit_id: "unit-1",
    name: "正式单元",
    description: "说明",
    unit_type: "quiz",
    config: {},
    status: "published",
    created_by: "admin",
    updated_by: "admin",
    created_at: "2026-05-28T00:00:00Z",
    updated_at: "2026-05-28T00:00:00Z",
    questions: [],
    ...overrides,
});

const basePath = (overrides: Partial<SalesTrainerPath> = {}): SalesTrainerPath => ({
    path_key: "new_seller",
    title: "新人闯关",
    goal_title: "目标",
    total_levels: 2,
    completed_levels: 0,
    current_level_id: "quiz-unit",
    next_level_id: "quiz-unit",
    goal_context: {
        goal_title: "目标",
        score_basis: "sales_trainer_path_projection_v1",
        evidence_items: [],
        weak_points: [],
        next_recommendation: null,
    },
    levels: [
        {
            unit_id: "quiz-unit",
            name: "做题单元",
            description: "题目",
            unit_type: "quiz",
            order_index: 1,
            level_title: "第一关",
            level_description: "先做题",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "passed",
            primary_action_label: "开始做题",
            retry_action_label: "重练本关",
            review_action_label: "查看结果",
            target_path: "/sales-trainer/quiz/quiz-unit",
            latest_result: null,
        },
        {
            unit_id: "audio-unit",
            name: "语音单元",
            description: "语音",
            unit_type: "audio_scoring",
            order_index: 2,
            level_title: "第二关",
            level_description: "上传语音",
            locked: true,
            lock_reason: "先完成第一关",
            status: "locked",
            completion_rule: "passed",
            primary_action_label: "上传语音",
            retry_action_label: "重练本关",
            review_action_label: "查看结果",
            target_path: "/sales-trainer/audio/audio-unit",
            latest_result: null,
        },
    ],
    ...overrides,
});

describe("learner-presenter", () => {
    it("maps unit types and submission statuses to learner-facing Chinese labels", () => {
        expect(getUnitTypeLabel("quiz")).toBe("做题训练");
        expect(getUnitTypeLabel("audio_scoring")).toBe("语音作业（上传）");
        expect(getSubmissionStatusLabel("transcribing")).toBe("正在转写");
        expect(getSubmissionStatusLabel("scored")).toBe("评分完成");
    });

    it("collects path unit ids and partitions orphan units", () => {
        const paths = [basePath()];
        const pathUnitIds = collectPathUnitIds(paths);
        const units = [
            baseUnit({ unit_id: "quiz-unit" }),
            baseUnit({ unit_id: "audio-unit", unit_type: "audio_scoring" }),
            baseUnit({ unit_id: "extra-unit", name: "额外练习" }),
        ];

        const { extraUnits } = partitionUnits(units, pathUnitIds);
        expect(extraUnits.map((unit) => unit.unit_id)).toEqual(["extra-unit"]);
    });

    it("detects likely internal units and sorts them after regular units", () => {
        expect(isLikelyInternalUnit(baseUnit({ name: "E2E 冒烟" }))).toBe(true);
        expect(isLikelyInternalUnit(baseUnit({ name: "正式销售话术" }))).toBe(false);

        const sorted = sortExtraUnits([
            baseUnit({ unit_id: "internal", name: "Goal验收脚本" }),
            baseUnit({ unit_id: "regular", name: "客户异议" }),
        ]);
        expect(sorted.map((unit) => unit.unit_id)).toEqual(["regular", "internal"]);
    });

    it("reads audio pass threshold with default fallback", () => {
        expect(getAudioPassThreshold(baseUnit({ config: {} }))).toBe(70);
        expect(getAudioPassThreshold(baseUnit({
            unit_type: "audio_scoring",
            config: { audio: { pass_threshold: 80 } },
        }))).toBe(80);
    });

    it("resolves primary action from recommendation or focus level", () => {
        const withRecommendation = basePath({
            goal_context: {
                goal_title: "目标",
                score_basis: "sales_trainer_path_projection_v1",
                evidence_items: [],
                weak_points: [],
                next_recommendation: {
                    title: "下一关",
                    reason: "继续训练",
                    action_label: "开始本关",
                    target_path: "/sales-trainer/quiz/quiz-unit",
                    unit_id: "quiz-unit",
                    level_title: "第一关",
                    recommendation_kind: "start_level",
                },
            },
        });

        expect(resolvePrimaryAction(withRecommendation)?.targetPath).toBe("/sales-trainer/quiz/quiz-unit");

        const withoutRecommendation = basePath();
        expect(findFocusLevel(withoutRecommendation)?.unit_id).toBe("quiz-unit");
        expect(resolvePrimaryAction(withoutRecommendation)?.actionLabel).toBe("开始做题");
    });

    it("builds learner chapter links from unit config", () => {
        const linkedUnit = baseUnit({
            unit_id: "coo-quiz-1",
            config: {
                learner: {
                    learning_content_id: "lc-coo",
                    chapter_order_index: 3,
                },
            },
        });

        expect(getLearnerChapterLink(linkedUnit)).toBe("/sales-trainer/learn/coo-quiz-1");
        expect(getLearnerChapterHint(linkedUnit)).toBe("建议先阅读第 3 章，再开始本章测验。");
        expect(getLearnerChapterLink(baseUnit({ config: {} }))).toBeNull();
    });
});
