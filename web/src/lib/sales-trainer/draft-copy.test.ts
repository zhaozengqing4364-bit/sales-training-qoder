import { afterEach, describe, expect, it, vi } from "vitest";

import {
    paperDraftCopyPayload,
    questionDraftCopyPayload,
    scorePromptDraftCopyPayload,
    unitDraftCopyPayload,
} from "./draft-copy";
import type {
    NewcomerExamPaper,
    SalesTrainerAudioScorePrompt,
    SalesTrainerQuestion,
    SalesTrainerUnit,
} from "@/lib/api/types";

describe("sales trainer draft copy payloads", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("copies a published question into a draft-create payload without lifecycle fields", () => {
        const question = {
            question_id: "question-1",
            title: "商务礼仪",
            stem: "见客户前应做什么？",
            reference_answer: null,
            category_id: "category-1",
            question_type: "single_choice",
            difficulty: "medium",
            status: "published",
            tags: ["礼仪"],
            scoring_dimensions: [],
            scoring_criteria: {},
            safety_flagged: false,
            department: null,
            usage_scope: "sales_trainer",
            version: 2,
            content_hash: "hash",
            published_at: "2026-06-02T00:00:00Z",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            options: [{ value: "A", label: "确认客户背景" }],
            correct_answer: "A",
            correct_answers: [],
            correct_bool: null,
            explanation: "出发前准备客户背景。",
            ai_scoring: null,
        } satisfies SalesTrainerQuestion;

        expect(questionDraftCopyPayload(question)).toEqual({
            title: "商务礼仪 (副本)",
            stem: "见客户前应做什么？",
            category_id: "category-1",
            question_type: "single_choice",
            difficulty: "medium",
            tags: ["礼仪"],
            department: null,
            safety_flagged: false,
            options: [{ value: "A", label: "确认客户背景" }],
            correct_answer: "A",
            correct_answers: [],
            correct_bool: null,
            reference_answer: null,
            scoring_dimensions: [],
            explanation: "出发前准备客户背景。",
            ai_scoring: null,
        });
    });

    it("copies published governed assets into create payloads", () => {
        vi.spyOn(Date, "now").mockReturnValue(1_780_000_000_000);
        const unit = {
            unit_id: "unit-1",
            name: "商务技巧",
            description: "见客户前准备",
            unit_type: "quiz",
            config: { path: { enabled: true, target_unit_id: "unit-1" } },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            questions: [{
                question_id: "question-1",
                title: "礼仪",
                stem: "题干",
                question_type: "single_choice",
                points: 10,
                order_index: 1,
            }],
        } satisfies SalesTrainerUnit;
        const prompt = {
            prompt_id: "prompt-1",
            name: "PPT 评分",
            purpose: "ppt_pitch",
            system_prompt: "system",
            scoring_template: "{transcript}",
            output_schema: {},
            learner_rubric: {},
            version: 1,
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
        } satisfies SalesTrainerAudioScorePrompt;
        const paper = {
            paper_id: "paper-1",
            paper_key: "business_skills",
            title: "商务技巧考卷",
            description: null,
            module_key: "business_skills",
            unit_id: "unit-1",
            pass_threshold: 70,
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            questions: [{
                question_id: "question-1",
                order_index: 1,
                points: 10,
                question_type: "single_choice",
                title: "礼仪",
                stem: "题干",
            }],
        } satisfies NewcomerExamPaper;

        expect(unitDraftCopyPayload(unit)).toMatchObject({
            name: "商务技巧 (副本)",
            config: { path: { enabled: true } },
            questions: [{ question_id: "question-1", order_index: 1, points: 10 }],
        });
        expect(scorePromptDraftCopyPayload(prompt)).toMatchObject({
            name: "PPT 评分 (副本)",
            scoring_template: "{transcript}",
        });
        expect(paperDraftCopyPayload(paper)).toMatchObject({
            paper_key: "business_skills_copy_mppy1i4g",
            title: "商务技巧考卷 (副本)",
            questions: [{ question_id: "question-1", order_index: 1, points: 10 }],
        });
    });
});
