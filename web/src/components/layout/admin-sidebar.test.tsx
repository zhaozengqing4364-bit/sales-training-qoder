import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminSidebarContent } from "./admin-sidebar";

const { usePathnameMock } = vi.hoisted(() => ({
    usePathnameMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => <a href={href} {...props}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    usePathname: () => usePathnameMock(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/glass-tooltip", () => ({
    TooltipProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    Tooltip: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    TooltipTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    TooltipContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return actual;
});

describe("AdminSidebarContent", () => {
    beforeEach(() => {
        usePathnameMock.mockReturnValue("/admin/sales-trainer/units");
    });

    it("exposes the sales-trainer admin entry in the shared sidebar", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "admin-1",
                    display_name: "管理员",
                    role: "admin",
                }}
            />,
        );

        expect(await screen.findByRole("button", { name: "销售训练" })).not.toBeNull();
        const workbenchLink = await screen.findByRole("link", { name: "工作台" });
        expect(workbenchLink.getAttribute("href")).toBe("/admin/sales-trainer");
        expect(screen.getByRole("link", { name: "训练路径" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "销售题库" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "录音评分标准" })).not.toBeNull();
    });

    it("limits support users to the sales-trainer admin entry", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "support-1",
                    display_name: "培训负责人",
                    role: "support",
                }}
            />,
        );

        expect(await screen.findByRole("button", { name: "销售训练" })).not.toBeNull();
        const workbenchLink = await screen.findByRole("link", { name: "工作台" });
        expect(workbenchLink.getAttribute("href")).toBe("/admin/sales-trainer");
        expect(screen.queryByRole("link", { name: "用户管理" })).toBeNull();
        expect(screen.queryByRole("link", { name: "智能体管理" })).toBeNull();
    });
});
