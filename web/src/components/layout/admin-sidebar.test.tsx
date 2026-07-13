import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";
import { AdminSidebarContent } from "./admin-sidebar";

const usePathnameMock = vi.hoisted(() => vi.fn());
vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));
vi.mock("next/navigation", () => ({ usePathname: () => usePathnameMock() }));
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
    TooltipProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
    Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipContent: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

function capabilities(enabled: Partial<SalesTrainerAdminCapabilities["capabilities"]>): SalesTrainerAdminCapabilities {
    const values = {
        admin_full_access: false,
        manage_content: false,
        manage_questions: false,
        manage_modules: false,
        manage_prompts: false,
        view_records: false,
        view_global_records: false,
        retry_jobs: false,
        regrade_history: false,
        view_logs: false,
        view_settings: false,
        ...enabled,
    };
    return {
        role: "support",
        role_label: "培训负责人",
        capabilities: values,
        capability_keys: Object.entries(values)
            .filter(([, value]) => value)
            .map(([key]) => key as SalesTrainerAdminCapabilities["capability_keys"][number]),
    };
}

describe("AdminSidebarContent", () => {
    beforeEach(() => usePathnameMock.mockReturnValue("/admin/newcomer-training/path"));

    it("keeps newcomer training shortcuts together in one clear dropdown", () => {
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);
        expect(screen.getByRole("button", { name: "新人训练" }).getAttribute("aria-expanded"))
            .toBe("true");
        const pathLink = screen.getByRole("link", { name: "训练内容与路径" });
        expect(pathLink.getAttribute("href")).toBe("/admin/newcomer-training/path");
        expect(screen.getByRole("link", { name: "学员进度" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "达标审核" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "训练记录" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "新人训练设置" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "操作记录" })).toBeTruthy();
        expect(screen.queryByRole("link", { name: "训练分析" })).toBeNull();
    });

    it("gives content managers the same focused editor", () => {
        render(
            <AdminSidebarContent
                currentUser={{ id: "content-1", display_name: "内容管理员", role: "support" }}
                salesTrainerCapabilities={capabilities({ manage_content: true })}
            />,
        );
        expect(screen.getByRole("link", { name: "训练内容与路径" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/path");
    });

    it("keeps record-only access free of path editing", () => {
        render(
            <AdminSidebarContent
                currentUser={{ id: "lead-1", display_name: "培训负责人", role: "support" }}
                salesTrainerCapabilities={capabilities({ view_records: true })}
            />,
        );
        fireEvent.click(screen.getByRole("button", { name: "新人训练" }));
        expect(screen.queryByRole("link", { name: "训练内容与路径" })).toBeNull();
        expect(screen.getByRole("link", { name: "学员进度" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "训练记录" })).toBeTruthy();
    });
});
