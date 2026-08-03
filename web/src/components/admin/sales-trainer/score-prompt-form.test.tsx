import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SalesTrainerAudioScorePrompt } from "@/lib/api/types";
import { SalesTrainerScorePromptForm } from "./score-prompt-form";

function publishedPrompt(): SalesTrainerAudioScorePrompt {
    return {
        prompt_id: "prompt-long",
        name: "石犀 PPT 讲解评分标准",
        purpose: "ppt_pitch",
        system_prompt: "你是严格的企业产品培训考官。",
        scoring_template: "请评分：{transcript}",
        output_schema: {},
        learner_rubric: {
            visible_to_learner: true,
            pass_threshold: 80,
            criteria: [],
            common_mistakes: [],
        },
        version: 1,
        status: "published",
        created_by: null,
        updated_by: null,
        created_at: "2026-07-16T00:00:00Z",
        updated_at: "2026-07-16T00:00:00Z",
    };
}

describe("SalesTrainerScorePromptForm", () => {
    it("preserves a long scoring prompt and submits it for publication", async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn().mockResolvedValue(undefined);
        const longPrompt = [
            "# 石犀数据流动治理平台 PPT 讲解评估提示词",
            "产品定位、行业背景、资产与用户两端、平台加组件、产品能力与客户价值。".repeat(2_000),
            "你必须且只能输出合法 JSON，包含 total_score、summary、strengths、improvements、dimension_scores。",
            "{transcript}",
        ].join("\n");
        render(
            <SalesTrainerScorePromptForm
                mode="edit"
                initialPrompt={publishedPrompt()}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        fireEvent.change(screen.getByLabelText("评分说明"), {
            target: { value: longPrompt },
        });

        expect(screen.getByText(`当前 ${longPrompt.length.toLocaleString("zh-CN")} 字；`, { exact: false })).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "保存并发布" }));

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith(
                expect.objectContaining({
                    scoring_template: longPrompt,
                    system_prompt: "你是严格的企业产品培训考官。",
                }),
            );
        });
    });
});
