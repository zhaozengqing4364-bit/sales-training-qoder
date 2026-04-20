import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { MobileQuickActions } from "./mobile-quick-actions";

vi.mock("next/link", () => ({
    default: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
        <a href={href} className={className}>{children}</a>
    ),
}));

vi.mock("@/components/layout/learner-help-entry", () => ({
    LearnerHelpEntry: ({ className }: { className?: string }) => (
        <button type="button" className={className}>帮助与反馈</button>
    ),
}));

describe("MobileQuickActions", () => {
    it("renders learner-safe mobile shortcuts without needing the drawer", () => {
        render(<MobileQuickActions primaryLabel="继续训练" />);

        expect(screen.getByRole("navigation", { name: "移动快捷入口" })).toBeTruthy();
        expect(screen.getByRole("link", { name: /继续训练/ }).getAttribute("href")).toBe("/training");
        expect(screen.getByRole("link", { name: /历史/ }).getAttribute("href")).toBe("/history");
        expect(screen.getByRole("button", { name: "帮助与反馈" })).toBeTruthy();
        expect(screen.getByText("手机端无需打开抽屉即可进入训练、历史和帮助与反馈。")).toBeTruthy();
    });
});
