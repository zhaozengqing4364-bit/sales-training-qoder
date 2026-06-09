import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SalesTrainerScorePromptForm } from "./score-prompt-form";

describe("SalesTrainerScorePromptForm", () => {
    it("prefills the scoring purpose when opened from configuration diagnostics", () => {
        render(
            <SalesTrainerScorePromptForm
                mode="create"
                initialPurpose="ppt_pitch"
                isSubmitting={false}
                onSubmit={vi.fn()}
            />,
        );

        const purposeSelect = screen.getByLabelText("适用用途");
        expect(purposeSelect).toBeInstanceOf(HTMLSelectElement);
        if (!(purposeSelect instanceof HTMLSelectElement)) {
            throw new Error("适用用途字段应该是业务用途下拉。");
        }
        expect(purposeSelect.value).toBe("ppt_pitch");
        expect(screen.getByText("PPT 讲解录音")).toBeTruthy();
    });

    it("allows editing published scoring standards as future-only revisions", () => {
        const onSubmit = vi.fn();

        render(
            <SalesTrainerScorePromptForm
                mode="edit"
                initialPrompt={{
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
                    created_at: "2026-06-01T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                }}
                isSubmitting={false}
                onSubmit={onSubmit}
            />,
        );

        expect(screen.getByText("编辑将生成新修订")).toBeTruthy();
        expect(screen.getByText(/只影响后续学员/)).toBeTruthy();
        expect(screen.queryByRole("button", { name: "复制为新草稿" })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "保存评分标准" }));

        expect(onSubmit).toHaveBeenCalledWith({
            name: "PPT 讲解评分",
            purpose: "ppt_pitch",
            system_prompt: "system",
            scoring_template: "{transcript}",
            output_schema: {},
            learner_rubric: {},
        });
    });
});
