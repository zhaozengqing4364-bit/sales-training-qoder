import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { LearnerRouteLoadingState } from "./learner-route-loading-state";

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

describe("LearnerRouteLoadingState", () => {
    it("announces route loading state with accessible status semantics", () => {
        render(
            <LearnerRouteLoadingState label="正在加载训练页面">
                <div>shell body</div>
            </LearnerRouteLoadingState>,
        );

        const status = screen.getByRole("status");
        expect(status.getAttribute("aria-live")).toBe("polite");
        expect(status.getAttribute("aria-busy")).toBe("true");
        expect(screen.getByText("正在加载训练页面").className).toContain("sr-only");
        expect(screen.getByText("shell body")).toBeTruthy();
    });
});
