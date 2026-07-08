import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerTrainingTasksPage from "./page";

const { routeAccessMock } = vi.hoisted(() => ({
    routeAccessMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/training-tasks",
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

vi.mock("@/components/admin/sales-trainer/admin-load-error-card", () => ({
    AdminLoadErrorCard: ({ title, message }: { title: string; message: string }) => (
        <div role="alert">
            <h2>{title}</h2>
            <p>{message}</p>
        </div>
    ),
}));

vi.mock("@/components/admin/sales-trainer/module-nav", () => ({
    SalesTrainerAdminModuleNav: () => <nav aria-label="训练任务模块内导航" />,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <article>{children}</article>,
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => routeAccessMock(),
}));

describe("SalesTrainerTrainingTasksPage", () => {
    beforeEach(() => {
        routeAccessMock.mockReset();
        routeAccessMock.mockReturnValue({
            capabilities: null,
            canAccess: true,
            denialMessage: null,
            error: null,
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });
    });

    it("shows audio scenarios as task-level governance entries", () => {
        render(<SalesTrainerTrainingTasksPage />);

        expect(screen.getByRole("heading", { name: "训练任务" })).toBeTruthy();
        expect(screen.getByRole("link", { name: /PPT 讲解/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/training-tasks/ppt-explanation",
        );
        expect(screen.getByRole("link", { name: /公司产品 Demo/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/training-tasks/company-product-demo",
        );
        expect(screen.getByRole("link", { name: /金字塔演讲/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/training-tasks/elevator-pitch",
        );
        expect(screen.getByRole("link", { name: /商务礼仪专题/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/articles",
        );
        expect(screen.queryByText("ppt_pitch")).toBeNull();
        expect(screen.queryByText("module_key")).toBeNull();
    });

    it("fails closed when the current admin cannot manage training tasks", () => {
        routeAccessMock.mockReturnValueOnce({
            capabilities: null,
            canAccess: false,
            denialMessage: "当前账号无权访问该新人训练管理页面。",
            error: null,
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });

        render(<SalesTrainerTrainingTasksPage />);

        expect(screen.getByRole("alert").textContent).toContain("训练任务不可访问");
        expect(screen.queryByText("录音评测场景")).toBeNull();
        expect(screen.queryByRole("link", { name: /PPT 讲解/ })).toBeNull();
    });
});
