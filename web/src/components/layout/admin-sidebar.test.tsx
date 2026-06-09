import { fireEvent, render, screen } from "@testing-library/react";
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

    it("keeps newcomer training path submodules collapsed until explicitly opened", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "admin-1",
                    display_name: "管理员",
                    role: "admin",
                }}
            />,
        );

        const sectionButton = await screen.findByRole("button", { name: "新人训练路径" });
        expect(sectionButton).not.toBeNull();
        expect(screen.queryByRole("link", { name: "模块单元" })).toBeNull();
        expect(screen.queryByRole("link", { name: "题库管理" })).toBeNull();

        fireEvent.click(sectionButton);

        expect(await screen.findByRole("link", { name: "模块单元" })).not.toBeNull();
        const workbenchLink = await screen.findByRole("link", { name: "工作台" });
        expect(workbenchLink.getAttribute("href")).toBe("/admin/sales-trainer");
        expect(screen.getByRole("link", { name: "路径配置" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "题库管理" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "录音评分标准" })).not.toBeNull();
    });

    it("highlights only the concrete newcomer training child route when expanded", async () => {
        usePathnameMock.mockReturnValue("/admin/sales-trainer/questions");

        render(
            <AdminSidebarContent
                currentUser={{
                    id: "admin-1",
                    display_name: "管理员",
                    role: "admin",
                }}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        const workbenchLink = await screen.findByRole("link", { name: "工作台" });
        const questionLink = await screen.findByRole("link", { name: "题库管理" });

        expect(workbenchLink.className).not.toContain("text-slate-900 bg-white shadow");
        expect(questionLink.className).toContain("text-slate-900 bg-white shadow");
    });

    it("limits training leads to learner record entries", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "support-1",
                    display_name: "培训负责人",
                    role: "support",
                }}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        expect(screen.queryByRole("link", { name: "工作台" })).toBeNull();
        expect(screen.queryByRole("link", { name: "题库管理" })).toBeNull();
        expect(screen.queryByRole("link", { name: "配置" })).toBeNull();
        expect(screen.queryByRole("link", { name: "操作记录" })).toBeNull();
        expect(await screen.findByRole("link", { name: "学员录音" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "评分结果" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "训练记录" })).not.toBeNull();
        expect(screen.queryByRole("link", { name: "用户管理" })).toBeNull();
        expect(screen.queryByRole("link", { name: "智能体管理" })).toBeNull();
    });

    it("shows content configuration entries without ops diagnostics for content admins", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "content-1",
                    display_name: "内容管理员",
                    role: "content_admin",
                }}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        expect(await screen.findByRole("link", { name: "路径配置" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "商务技巧文章" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "考卷管理" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "材料库" })).not.toBeNull();
        expect(screen.queryByRole("link", { name: "学员录音" })).toBeNull();
        expect(screen.queryByRole("link", { name: "配置" })).toBeNull();
        expect(screen.queryByRole("link", { name: "操作记录" })).toBeNull();
        expect(screen.queryByRole("link", { name: "用户管理" })).toBeNull();
    });

    it("shows operations diagnostics without content mutation entries for operations", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "ops-1",
                    display_name: "运维人员",
                    role: "operations",
                }}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        expect(await screen.findByRole("link", { name: "配置" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "操作记录" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "学员录音" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "评分结果" })).not.toBeNull();
        expect(screen.queryByRole("link", { name: "题库管理" })).toBeNull();
        expect(screen.queryByRole("link", { name: "考卷管理" })).toBeNull();
        expect(screen.queryByRole("link", { name: "材料库" })).toBeNull();
    });
});
