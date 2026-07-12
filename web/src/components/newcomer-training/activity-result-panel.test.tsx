import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityResultPanel } from "./activity-result-panel";

describe("ActivityResultPanel", () => {
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
