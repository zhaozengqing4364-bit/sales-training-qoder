import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { LearnerHelpCard } from "./learner-help-card";

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild: _asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) => (
        <button type="button" {...props}>{children}</button>
    ),
}));

describe("LearnerHelpCard", () => {
    it("keeps dashboard help semantics while exposing context actions", () => {
        render(<LearnerHelpCard context="dashboard" />);

        expect(screen.getByText("需要帮助或反馈？")).toBeTruthy();
        expect(screen.getByText("统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。")).toBeTruthy();
        expect(screen.getByText("页面异常、入口缺失或结果不对时，请通过这个统一入口反馈当前页面路径或会话编号。")).toBeTruthy();
        expect(screen.getByRole("link", { name: /去训练大厅/ }).getAttribute("href")).toBe("/training");
    });

    it.each([
        ["history", "历史记录看不全时还能做什么？", "开始训练", "/training"],
        ["practice", "练习中遇到异常怎么办？", "返回训练大厅", "/training"],
        ["report", "报告看不懂或证据不足时怎么办？", "去训练大厅", "/training"],
    ] as const)("renders %s-specific guidance and primary action", (context, title, actionLabel, href) => {
        render(<LearnerHelpCard context={context} />);

        expect(screen.getByText(title)).toBeTruthy();
        expect(screen.getByRole("link", { name: new RegExp(actionLabel) }).getAttribute("href")).toBe(href);
    });
});
