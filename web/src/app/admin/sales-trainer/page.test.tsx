import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import SalesTrainerWorkbenchPage from "./page";

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer",
}));

vi.mock("@/components/admin/admin-layout-shells", () => ({
    AdminIndexShell: ({ children, header }: { children: ReactNode; header: ReactNode }) => (
        <div>
            {header}
            {children}
        </div>
    ),
    AdminPageHeader: ({ title, description, secondaryActions }: {
        title: string;
        description: string;
        secondaryActions?: ReactNode;
    }) => (
        <header>
            <h1>{title}</h1>
            <p>{description}</p>
            {secondaryActions}
        </header>
    ),
}));

vi.mock("@/components/admin/sales-trainer/module-nav", () => ({
    SalesTrainerAdminModuleNav: () => <nav aria-label="新人训练路径导航" />,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("SalesTrainerWorkbenchPage", () => {
    it("shows the AI coach config workbench entry", () => {
        render(<SalesTrainerWorkbenchPage />);

        expect(screen.getByRole("heading", { name: "新人训练路径工作台" })).toBeTruthy();
        expect(screen.getByRole("link", { name: /AI 教练配置/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/ai-coach",
        );
    });
});
