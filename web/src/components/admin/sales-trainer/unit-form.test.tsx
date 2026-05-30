import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SalesTrainerUnitForm } from "./unit-form";

describe("SalesTrainerUnitForm", () => {
    const onSubmit = vi.fn();

    beforeEach(() => {
        onSubmit.mockReset();
    });

    it("persists audio purpose in the unit config instead of relying on upload defaults", async () => {
        render(
            <SalesTrainerUnitForm
                mode="create"
                availableQuestions={[]}
                availablePrompts={[
                    {
                        prompt_id: "prompt-1",
                        name: "PPT 讲解评分",
                        purpose: "ppt_pitch",
                        system_prompt: "system",
                        scoring_template: "{transcript}",
                        output_schema: {},
                        version: 1,
                        status: "published",
                        created_by: "admin-1",
                        updated_by: "admin-1",
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                    },
                ]}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("训练单元名称"), {
            target: { value: "PPT 讲解录音" },
        });
        fireEvent.change(screen.getByLabelText("训练类型"), {
            target: { value: "audio_scoring" },
        });
        fireEvent.change(screen.getByLabelText("录音用途"), {
            target: { value: "ppt_pitch" },
        });
        fireEvent.change(screen.getByLabelText("录音评分标准"), {
            target: { value: "prompt-1" },
        });
        fireEvent.change(screen.getByLabelText("通过线（可选）"), {
            target: { value: "80" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建训练单元" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                name: "PPT 讲解录音",
                description: null,
                unit_type: "audio_scoring",
                config: {
                    audio: {
                        scoring_prompt_id: "prompt-1",
                        purpose: "ppt_pitch",
                        pass_threshold: 80,
                    },
                },
                questions: [],
            });
        });
    });

    it("omits blank audio pass threshold so backend scoring defaults apply", async () => {
        render(
            <SalesTrainerUnitForm
                mode="create"
                availableQuestions={[]}
                availablePrompts={[
                    {
                        prompt_id: "prompt-1",
                        name: "PPT 讲解评分",
                        purpose: "ppt_pitch",
                        system_prompt: "system",
                        scoring_template: "{transcript}",
                        output_schema: {},
                        version: 1,
                        status: "published",
                        created_by: "admin-1",
                        updated_by: "admin-1",
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                    },
                ]}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("训练单元名称"), {
            target: { value: "PPT 讲解录音" },
        });
        fireEvent.change(screen.getByLabelText("训练类型"), {
            target: { value: "audio_scoring" },
        });
        fireEvent.change(screen.getByLabelText("录音用途"), {
            target: { value: "ppt_pitch" },
        });
        fireEvent.change(screen.getByLabelText("录音评分标准"), {
            target: { value: "prompt-1" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建训练单元" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({
                name: "PPT 讲解录音",
                description: null,
                unit_type: "audio_scoring",
                config: {
                    audio: {
                        scoring_prompt_id: "prompt-1",
                        purpose: "ppt_pitch",
                    },
                },
                questions: [],
            });
        });
    });

    it("rejects invalid audio pass threshold before submit", async () => {
        render(
            <SalesTrainerUnitForm
                mode="create"
                availableQuestions={[]}
                availablePrompts={[
                    {
                        prompt_id: "prompt-1",
                        name: "PPT 讲解评分",
                        purpose: "ppt_pitch",
                        system_prompt: "system",
                        scoring_template: "{transcript}",
                        output_schema: {},
                        version: 1,
                        status: "published",
                        created_by: "admin-1",
                        updated_by: "admin-1",
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                    },
                ]}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("训练单元名称"), {
            target: { value: "PPT 讲解录音" },
        });
        fireEvent.change(screen.getByLabelText("训练类型"), {
            target: { value: "audio_scoring" },
        });
        fireEvent.change(screen.getByLabelText("录音用途"), {
            target: { value: "ppt_pitch" },
        });
        fireEvent.change(screen.getByLabelText("录音评分标准"), {
            target: { value: "prompt-1" },
        });
        fireEvent.change(screen.getByLabelText("通过线（可选）"), {
            target: { value: "101" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建训练单元" }));

        expect(await screen.findByText("音频评分通过线不能大于 100。")).toBeTruthy();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it("persists path configuration for level-based training", async () => {
        render(
            <SalesTrainerUnitForm
                mode="create"
                availableQuestions={[
                    {
                        question_id: "question-1",
                        title: "产品定位",
                        stem: "石犀核心定位是什么？",
                        reference_answer: "A",
                        category_id: "category-1",
                        question_type: "single_choice",
                        difficulty: "easy",
                        status: "published",
                        tags: [],
                        scoring_dimensions: [],
                        scoring_criteria: {},
                        safety_flagged: false,
                        department: null,
                        usage_scope: "sales_trainer",
                        version: 1,
                        content_hash: null,
                        published_at: null,
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                        options: [],
                        correct_answer: "A",
                        correct_answers: [],
                        correct_bool: null,
                        explanation: null,
                        ai_scoring: null,
                    },
                ]}
                availablePrompts={[]}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("训练单元名称"), {
            target: { value: "第一关：产品定位" },
        });
        fireEvent.click(screen.getByLabelText("加入销售训练闯关路径"));
        fireEvent.change(screen.getByLabelText("路径标识"), {
            target: { value: "new_seller" },
        });
        fireEvent.change(screen.getByLabelText("路径名称"), {
            target: { value: "新人销售闯关" },
        });
        fireEvent.change(screen.getByLabelText("训练目标"), {
            target: { value: "掌握首次客户沟通" },
        });
        fireEvent.change(screen.getByLabelText("关卡名称"), {
            target: { value: "第一关：产品定位" },
        });
        fireEvent.change(screen.getByLabelText("关卡顺序"), {
            target: { value: "1" },
        });
        fireEvent.change(screen.getByLabelText("通关规则"), {
            target: { value: "passed" },
        });
        fireEvent.change(screen.getByLabelText("反馈文案模板"), {
            target: { value: "not_started: 先完成本关训练证据。" },
        });
        fireEvent.click(screen.getByLabelText(/产品定位/));
        fireEvent.click(screen.getByRole("button", { name: "创建训练单元" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
                name: "第一关：产品定位",
                unit_type: "quiz",
                config: {
                    path: {
                        enabled: true,
                        path_key: "new_seller",
                        path_title: "新人销售闯关",
                        goal_title: "掌握首次客户沟通",
                        level_title: "第一关：产品定位",
                        order_index: 1,
                        completion_rule: "passed",
                        guidance_templates: {
                            not_started: "先完成本关训练证据。",
                        },
                    },
                },
                questions: [
                    {
                        question_id: "question-1",
                        order_index: 1,
                        points: 10,
                    },
                ],
            }));
        });
    });

    it("omits path defaults so the backend path schema remains authoritative", async () => {
        render(
            <SalesTrainerUnitForm
                mode="create"
                availableQuestions={[
                    {
                        question_id: "question-1",
                        title: "产品定位",
                        stem: "石犀核心定位是什么？",
                        reference_answer: "A",
                        category_id: "category-1",
                        question_type: "single_choice",
                        difficulty: "easy",
                        status: "published",
                        tags: [],
                        scoring_dimensions: [],
                        scoring_criteria: {},
                        safety_flagged: false,
                        department: null,
                        usage_scope: "sales_trainer",
                        version: 1,
                        content_hash: null,
                        published_at: null,
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                        options: [],
                        correct_answer: "A",
                        correct_answers: [],
                        correct_bool: null,
                        explanation: null,
                        ai_scoring: null,
                    },
                ]}
                availablePrompts={[]}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("训练单元名称"), {
            target: { value: "第一关：产品定位" },
        });
        fireEvent.click(screen.getByLabelText("加入销售训练闯关路径"));
        fireEvent.click(screen.getByLabelText(/产品定位/));
        fireEvent.click(screen.getByRole("button", { name: "创建训练单元" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
                config: {
                    path: {
                        enabled: true,
                    },
                },
            }));
        });
    });
});
