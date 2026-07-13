import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

import { GlassSheet } from "./glass-sheet";

describe("GlassSheet", () => {
    it("uses compositor-safe transform strings and a non-blurred backdrop", () => {
        const source = readFileSync(path.join(process.cwd(), "src/components/ui/glass-sheet.tsx"), "utf8");
        expect(source).toContain("useReducedMotion");
        expect(source).toContain('translate3d(-100%,0,0)');
        expect(source).toContain('translate3d(100%,0,0)');
        expect(source).toContain('translate3d(0,100%,0)');
        expect(source).not.toMatch(/\n\s+[xy]:/);
        expect(source).not.toContain("backdrop-blur-sm");
        expect(source).toContain('{ type: "spring", duration: 0.5, bounce: 0.2 }');
    });

    it.each([
        ["left", "left-0"],
        ["right", "right-0"],
        ["bottom", "bottom-0"],
    ] as const)("marks the %s sheet as spatial motion", (side, positionClass) => {
        render(<GlassSheet isOpen onClose={vi.fn()} side={side}><p>{side} 面板</p></GlassSheet>);

        const dialog = screen.getByRole("dialog");
        expect(dialog.getAttribute("data-motion-kind")).toBe("spatial");
        expect(dialog.className).toContain(positionClass);
    });

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
