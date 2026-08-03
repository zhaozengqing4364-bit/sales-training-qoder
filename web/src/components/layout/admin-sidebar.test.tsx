import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";
import type { FoundationAdminCapabilities } from "@/lib/api/types/foundation-admin";
import { AdminSidebarContent } from "./admin-sidebar";

const usePathnameMock = vi.hoisted(() => vi.fn());
const prefetchMock = vi.hoisted(() => vi.fn());
vi.mock("next/link", () => ({
    default: ({ href, children, prefetch, ...props }: { href: string; children: ReactNode; prefetch?: boolean }) => (
        <a href={href} data-prefetch={String(prefetch)} {...props}>{children}</a>
    ),
}));
vi.mock("next/navigation", () => ({
    usePathname: () => usePathnameMock(),
    useRouter: () => ({ prefetch: prefetchMock }),
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

function foundationCapabilities(): FoundationAdminCapabilities {
    return {
        capabilities: ["view_overview", "edit_content"],
        access: { view_overview: true, edit_content: true },
        permission_help: "请联系组织管理员申请权限。",
    };
}

describe("AdminSidebarContent", () => {
    beforeEach(() => {
        usePathnameMock.mockReturnValue("/admin/newcomer-training/resources");
        prefetchMock.mockReset();
    });

    it("keeps newcomer training shortcuts together in one clear dropdown", () => {
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);
        expect(screen.getByRole("button", { name: "新人训练" }).getAttribute("aria-expanded"))
            .toBe("true");
        expect(screen.getByRole("link", { name: "活动内容库" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/resources");
        expect(screen.getByRole("link", { name: "训练内容与路径" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/paths");
        expect(screen.queryByRole("link", { name: "实时对练" })).toBeNull();
        expect(screen.queryByRole("link", { name: "AI 教练" })).toBeNull();
        expect(screen.queryByRole("link", { name: "作业任务" })).toBeNull();
        expect(screen.getByRole("link", { name: "学员进度" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "达标审核" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "训练记录" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "新人训练设置" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "操作记录" })).toBeTruthy();
        expect(screen.queryByRole("link", { name: "训练分析" })).toBeNull();
    });

    it("switches the newcomer entry to the unified workspace from the backend projection", () => {
        usePathnameMock.mockReturnValue("/admin/newcomer-training");
        render(
            <AdminSidebarContent
                currentUser={{ id: "manager-1", display_name: "培训负责人", role: "support" }}
                salesTrainerCapabilities={capabilities({ manage_content: true })}
                foundationAdminCapabilities={foundationCapabilities()}
            />,
        );

        expect(screen.getByRole("link", { name: "新人训练工作台" }).getAttribute("href"))
            .toBe("/admin/newcomer-training");
        expect(screen.queryByRole("link", { name: "活动内容库" })).toBeNull();
        expect(screen.queryByRole("link", { name: "实时对练" })).toBeNull();
    });

    it("keeps the governed resource library inside the newcomer dropdown", () => {
        usePathnameMock.mockReturnValue("/admin/newcomer-training/resources");
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);

        expect(screen.getByRole("button", { name: "新人训练" }).getAttribute("aria-expanded"))
            .toBe("true");
        expect(screen.getByRole("button", { name: "内容与知识" }).getAttribute("aria-expanded"))
            .toBe("false");
        expect(screen.getByRole("link", { name: "活动内容库" })).toBeTruthy();
        expect(screen.queryByRole("link", { name: "实时对练" })).toBeNull();
    });

    it("provides a clear organization path for accounts and team relationships", () => {
        usePathnameMock.mockReturnValue("/admin/teams");
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);

        expect(screen.getByRole("button", { name: "组织与权限" }).getAttribute("aria-expanded")).toBe("true");
        const usersLink = screen.getByRole("link", { name: "用户管理" });
        const teamsLink = screen.getByRole("link", { name: "团队与成员" });
        expect(usersLink.getAttribute("href")).toBe("/admin/users");
        expect(usersLink.getAttribute("data-prefetch")).toBe("false");
        expect(teamsLink.getAttribute("href")).toBe("/admin/teams");
        expect(teamsLink.getAttribute("data-prefetch")).toBe("true");
    });

    it("keeps the priority organization entry ready on the admin overview", () => {
        usePathnameMock.mockReturnValue("/admin");
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);

        expect(screen.getByRole("button", { name: "组织与权限" }).getAttribute("aria-expanded"))
            .toBe("true");
        expect(screen.getByRole("link", { name: "团队与成员" }).getAttribute("data-prefetch"))
            .toBe("true");
    });

    it("prevents native full-page navigation until the admin shell is hydrated", () => {
        usePathnameMock.mockReturnValue("/admin");

        const markup = renderToStaticMarkup(
            <AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />,
        );
        const container = document.createElement("div");
        container.innerHTML = markup;
        const pendingTeamsLink = container.querySelector<HTMLElement>(
            '[data-admin-nav-href="/admin/teams"]',
        );

        expect(container.querySelector('a[href="/admin/teams"]')).toBeNull();
        expect(pendingTeamsLink?.tagName).toBe("SPAN");
        expect(pendingTeamsLink?.getAttribute("aria-disabled")).toBe("true");
        expect(pendingTeamsLink?.getAttribute("tabindex")).toBe("-1");
        expect(pendingTeamsLink?.className).toContain("pointer-events-none");
    });

    it("keeps high-frequency navigation feedback short and non-scaling", () => {
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);

        const section = screen.getByRole("button", { name: "新人训练" });
        const resourceLink = screen.getByRole("link", { name: "活动内容库" });
        for (const element of [section, resourceLink]) {
            expect(element.className).not.toContain("transition-all");
            expect(element.className).toContain("duration-[var(--duration-press)]");
            expect(element.className).toContain("ease-[var(--ease-out)]");
            expect(element.innerHTML).not.toContain("scale-110");
            expect(element.innerHTML).not.toContain("group-hover:scale-105");
        }
    });

    it("does not prefetch every visible or hovered route", () => {
        render(<AdminSidebarContent currentUser={{ id: "admin-1", display_name: "管理员", role: "admin" }} />);

        const resourceLink = screen.getByRole("link", { name: "活动内容库" });
        expect(resourceLink.getAttribute("data-prefetch")).toBe("false");
        expect(prefetchMock).not.toHaveBeenCalled();

        fireEvent.mouseEnter(resourceLink);
        expect(prefetchMock).not.toHaveBeenCalled();
    });

    it("gives content managers the governed resource entry", () => {
        render(
            <AdminSidebarContent
                currentUser={{ id: "content-1", display_name: "内容管理员", role: "support" }}
                salesTrainerCapabilities={capabilities({ manage_content: true })}
            />,
        );
        expect(screen.getByRole("link", { name: "活动内容库" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/resources");
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
        expect(screen.getByRole("link", { name: "录音管理" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/assessments");
        expect(screen.getByRole("link", { name: "达标审核" })).toBeTruthy();
    });
});
