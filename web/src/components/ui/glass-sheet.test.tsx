import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GlassSheet } from "./glass-sheet";

describe("GlassSheet", () => {
    it("exposes dialog semantics and closes on Escape", async () => {
        const onClose = vi.fn();

        render(
            <GlassSheet isOpen={true} onClose={onClose} side="bottom">
                <p>实时分析面板</p>
            </GlassSheet>,
        );

        expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
        expect(screen.getByLabelText("关闭面板")).toBeTruthy();

        fireEvent.keyDown(document, { key: "Escape" });

        expect(onClose).toHaveBeenCalledTimes(1);
    });
});
