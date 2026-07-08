import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockGetModelConfigs = vi.fn();

vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            getModelConfigs: (...args: unknown[]) => mockGetModelConfigs(...args),
        },
    },
    getApiErrorMessage: (error: unknown) =>
        error instanceof Error ? error.message : String(error),
}));

import { SalesTrainerQuestionForm } from "./question-form";

describe("SalesTrainerQuestionForm", () => {
    const onSubmit = vi.fn();
    const categories = [
        {
            category_id: "category-1",
            parent_id: null,
            name: "销售基础",
            description: null,
            usage_scope: "sales_trainer",
            order_index: 1,
            created_at: "2026-05-28T00:00:00Z",
            updated_at: "2026-05-28T00:00:00Z",
        },
    ];

    beforeEach(() => {
        onSubmit.mockReset();
        mockGetModelConfigs.mockReset();
        mockGetModelConfigs.mockResolvedValue({
            llm: [
                {
                    id: "model-config-1",
                    name: "DeepSeek Flash",
                    model_type: "llm",
                    provider: "openai",
                    model_name: "deepseek-v4-flash",
                    is_default: true,
                    is_active: true,
                    last_test_status: "success",
                },
                {
                    id: "model-config-disabled",
                    name: "停用模型",
                    model_type: "llm",
                    provider: "openai",
                    model_name: "disabled-model",
                    is_default: false,
                    is_active: false,
                    last_test_status: null,
                },
            ],
            embedding: [],
            asr: [],
            tts: [],
            total: 2,
        });
    });

    it("submits answer explanation and short-answer AI scoring config", async () => {
        render(
            <SalesTrainerQuestionForm
                mode="create"
                categories={categories}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("题目标题"), {
            target: { value: "客户价值理解" },
        });
        fireEvent.change(screen.getByLabelText("题型"), {
            target: { value: "short_answer" },
        });
        expect(screen.getByPlaceholderText("留空使用新人训练路径默认简答评分角色")).toBeTruthy();
        expect(screen.queryByPlaceholderText("留空使用销售训练默认简答评分角色")).toBeNull();
        fireEvent.change(screen.getByLabelText("题干"), {
            target: { value: "请说明石犀如何帮助客户治理数据流动。" },
        });
        fireEvent.change(screen.getByLabelText("答案解析"), {
            target: { value: "优秀答案应说明客户场景、治理价值和下一步动作。" },
        });
        fireEvent.change(screen.getByLabelText("参考答案"), {
            target: { value: "石犀帮助客户建立可审计的数据流动治理体系。" },
        });
        fireEvent.change(screen.getByLabelText("评分维度"), {
            target: { value: "value_logic\ncustomer_context" },
        });
        fireEvent.change(screen.getByLabelText("简答通过线"), {
            target: { value: "75" },
        });
        await waitFor(() => {
            expect(screen.getByText("DeepSeek Flash · openai/deepseek-v4-flash · 默认")).toBeTruthy();
        });
        expect(screen.queryByText("停用模型 · openai/disabled-model")).toBeNull();
        fireEvent.change(screen.getByLabelText("LLM 模型配置"), {
            target: { value: "model-config-1" },
        });
        fireEvent.change(screen.getByLabelText("温度"), {
            target: { value: "0.2" },
        });
        fireEvent.change(screen.getByLabelText("超时秒数"), {
            target: { value: "20" },
        });
        fireEvent.change(screen.getByLabelText("重试次数"), {
            target: { value: "1" },
        });
        fireEvent.change(screen.getByLabelText("最大输出 tokens"), {
            target: { value: "500" },
        });
        fireEvent.change(screen.getByLabelText("系统提示词"), {
            target: { value: "你是销售训练简答评分员。" },
        });
        fireEvent.change(screen.getByLabelText("评分提示词模板"), {
            target: { value: "题干：{stem}\n参考答案：{reference_answer}\n答案：{answer}" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建题目" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
                title: "客户价值理解",
                question_type: "short_answer",
                explanation: "优秀答案应说明客户场景、治理价值和下一步动作。",
                reference_answer: "石犀帮助客户建立可审计的数据流动治理体系。",
                scoring_dimensions: ["value_logic", "customer_context"],
                ai_scoring: {
                    enabled: true,
                    pass_threshold: 75,
                    model_config_id: "model-config-1",
                    temperature: 0.2,
                    timeout: 20,
                    max_retries: 1,
                    max_tokens: 500,
                    system_prompt: "你是销售训练简答评分员。",
                    prompt_template: "题干：{stem}\n参考答案：{reference_answer}\n答案：{answer}",
                },
            }));
        });
    });

    it("omits blank short-answer pass threshold so the backend schema default applies", async () => {
        render(
            <SalesTrainerQuestionForm
                mode="create"
                categories={categories}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("题目标题"), {
            target: { value: "客户价值理解" },
        });
        fireEvent.change(screen.getByLabelText("题型"), {
            target: { value: "short_answer" },
        });
        fireEvent.change(screen.getByLabelText("题干"), {
            target: { value: "请说明石犀如何帮助客户治理数据流动。" },
        });
        fireEvent.change(screen.getByLabelText("参考答案"), {
            target: { value: "石犀帮助客户建立可审计的数据流动治理体系。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建题目" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
                ai_scoring: {
                    enabled: true,
                },
            }));
        });
    });

    it("rejects invalid short-answer AI numeric config before submit", async () => {
        render(
            <SalesTrainerQuestionForm
                mode="create"
                categories={categories}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("题目标题"), {
            target: { value: "客户价值理解" },
        });
        fireEvent.change(screen.getByLabelText("题型"), {
            target: { value: "short_answer" },
        });
        fireEvent.change(screen.getByLabelText("题干"), {
            target: { value: "请说明石犀如何帮助客户治理数据流动。" },
        });
        fireEvent.change(screen.getByLabelText("参考答案"), {
            target: { value: "石犀帮助客户建立可审计的数据流动治理体系。" },
        });
        fireEvent.change(screen.getByLabelText("简答通过线"), {
            target: { value: "101" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建题目" }));

        expect(await screen.findByText("简答通过线不能大于 100。")).toBeTruthy();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it("allows editing published questions as future-only revisions", () => {
        render(
            <SalesTrainerQuestionForm
                mode="edit"
                initialQuestion={{
                    question_id: "question-1",
                    title: "商务礼仪",
                    stem: "见客户前应做什么？",
                    reference_answer: null,
                    category_id: "category-1",
                    question_type: "single_choice",
                    difficulty: "medium",
                    status: "published",
                    tags: [],
                    scoring_dimensions: [],
                    scoring_criteria: {},
                    safety_flagged: false,
                    department: null,
                    usage_scope: "sales_trainer",
                    version: 1,
                    content_hash: null,
                    published_at: "2026-06-02T00:00:00Z",
                    created_at: "2026-06-01T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    options: [{ value: "A", label: "确认客户背景" }],
                    correct_answer: "A",
                    correct_answers: [],
                    correct_bool: null,
                    explanation: null,
                    ai_scoring: null,
                }}
                categories={categories}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        expect(screen.getByText("编辑将生成题目新修订")).toBeTruthy();
        expect(screen.getByText(/只影响后续组卷和后续学员作答/)).toBeTruthy();
        expect(screen.queryByRole("button", { name: "复制为新草稿" })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "保存题目" }));

        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
            title: "商务礼仪",
            stem: "见客户前应做什么？",
            question_type: "single_choice",
            correct_answer: "A",
        }));
    });
});
