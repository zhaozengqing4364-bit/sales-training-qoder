import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UnitAudioScoringSection } from "./unit-audio-config-sections";

describe("UnitAudioScoringSection", () => {
    it("shows audio purpose in business language while preserving the configured value", () => {
        render(
            <UnitAudioScoringSection
                audioPurpose="ppt_pitch"
                availablePrompts={[]}
                canEdit
                isSubmitting={false}
                passThreshold=""
                promptId=""
                setAudioPurpose={vi.fn()}
                setPassThreshold={vi.fn()}
                setPromptId={vi.fn()}
            />,
        );

        const purposeSelect = screen.getByRole("combobox", { name: "录音用途" });
        expect(purposeSelect).toBeInstanceOf(HTMLSelectElement);
        if (!(purposeSelect instanceof HTMLSelectElement)) {
            throw new Error("录音用途应该使用业务下拉配置。");
        }
        expect(purposeSelect.value).toBe("ppt_pitch");
        expect(screen.getByText("PPT 讲解")).toBeTruthy();
    });
});
