import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
        fireEvent.change(screen.getByLabelText("模型配置 ID"), {
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
});
