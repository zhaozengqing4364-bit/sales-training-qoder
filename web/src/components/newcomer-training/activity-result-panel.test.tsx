import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityResultPanel } from "./activity-result-panel";

describe("ActivityResultPanel", () => {
    it.each([
        ["in_progress", false, undefined, "已提交，正在处理"],
        ["failed", false, false, "这次还未通过"],
        ["completed", true, true, "活动已完成"],
    ] as const)("reveals the %s result once without changing its semantics", (status, completed, passed, title) => {
        render(<ActivityResultPanel status={status} completed={completed} passed={passed} moduleId="module-1" />);

        const panel = screen.getByText(title).closest("section");
        expect(panel?.className).toContain("motion-result-reveal");
        expect(panel?.getAttribute("data-motion-kind")).toBe("spatial");
        expect(panel?.getAttribute("aria-live")).toBe("polite");
    });

    it("explains processing without pretending the activity is complete", () => {
        render(<ActivityResultPanel status="in_progress" completed={false} moduleId="module-1" />);
        expect(screen.getByText("已提交，正在处理")).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回模块" })).toBeTruthy();
    });

    it("shows score and completion action", () => {
        render(<ActivityResultPanel status="completed" completed passed score={88} maxScore={100} moduleId="module-1" />);
        expect(screen.getByText("88 / 100")).toBeTruthy();
        expect(screen.getByText("活动已完成")).toBeTruthy();
    });
});
