import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SalesTrainerUnitForm } from "./unit-form";

describe("SalesTrainerUnitForm", () => {
    const onSubmit = vi.fn();
    const publishedMaterial = {
        material_id: "material-1",
        material_key: "company_master_deck",
        name: "公司主胶片",
        material_type: "ppt_deck" as const,
        description: null,
        purpose: "ppt_pitch",
        status: "published" as const,
        current_version_id: "version-1",
        current_version: {
            version_id: "version-1",
            material_id: "material-1",
            version_label: "v2026.06",
            title: "公司主胶片 2026-06",
            file_name: "deck.pptx",
            content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            file_size_bytes: 1024,
            storage_key: "cos://deck.pptx",
            file_hash: null,
            release_notes: null,
            status: "published" as const,
            published_at: "2026-06-01T00:00:00Z",
            published_by: "admin-1",
            created_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
        },
        versions: [],
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
    };

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
                        learner_rubric: {},
                        version: 1,
                        status: "published",
                        created_by: "admin-1",
                        updated_by: "admin-1",
                        created_at: "2026-05-28T00:00:00Z",
                        updated_at: "2026-05-28T00:00:00Z",
                    },
                ]}
                availableMaterials={[publishedMaterial]}
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
        fireEvent.change(screen.getByLabelText("主材料"), {
            target: { value: "material-1" },
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
                    task_brief: {
                        enabled: true,
                    },
                    materials: {
                        require_latest_confirmation: true,
                        bindings: [
                            {
                                material_id: "material-1",
                                required: true,
                                confirmation_required: true,
                                version_policy: "current_published",
                                display_order: 1,
                            },
                        ],
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
                        learner_rubric: {},
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
                        purpose: "general_audio_scoring",
                    },
                    task_brief: {
                        enabled: true,
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
                        learner_rubric: {},
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
        fireEvent.click(screen.getByLabelText("加入新人训练路径"));
        expect(screen.getByText("路径结构请优先到“新人训练路径配置中心”维护；这里仅保留高级兼容配置。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "打开新人训练路径配置中心" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/paths",
        );
        expect(screen.queryByLabelText("路径标识")).toBeNull();
        fireEvent.click(screen.getByText("展开高级兼容字段"));
        expect(screen.getByLabelText("前置关卡编号")).toBeTruthy();
        expect(screen.queryByText("前置关卡 ID")).toBeNull();
        fireEvent.change(screen.getByLabelText("路径标识"), {
            target: { value: "new_seller" },
        });
        fireEvent.change(screen.getByLabelText("路径名称"), {
            target: { value: "新人训练路径" },
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
                        path_title: "新人训练路径",
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
        fireEvent.click(screen.getByLabelText("加入新人训练路径"));
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

    it("allows editing published units as future-only revisions", async () => {
        render(
            <SalesTrainerUnitForm
                mode="edit"
                initialUnit={{
                    unit_id: "unit-1",
                    name: "商务技巧",
                    description: "见客户前准备",
                    unit_type: "quiz",
                    config: { path: { enabled: true } },
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-01T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    questions: [{
                        question_id: "question-1",
                        title: "礼仪",
                        stem: "见客户前应做什么？",
                        question_type: "single_choice",
                        points: 10,
                        order_index: 1,
                    }],
                }}
                availableQuestions={[]}
                availablePrompts={[]}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        expect(screen.getByText("编辑将生成新修订")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "复制为新草稿" })).toBeNull();
        fireEvent.change(screen.getByLabelText("训练单元名称"), {
            target: { value: "商务技巧新版" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存训练单元" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
                name: "商务技巧新版",
            }));
        });
    });
});
