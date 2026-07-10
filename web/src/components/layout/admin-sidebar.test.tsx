import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminSidebarContent } from "./admin-sidebar";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";

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

function salesTrainerCapabilities(
    overrides: Partial<SalesTrainerAdminCapabilities["capabilities"]>,
    roleLabel = "培训负责人",
): SalesTrainerAdminCapabilities {
    const capabilities = {
        admin_full_access: false,
        manage_content: false,
        manage_questions: false,
        manage_modules: false,
        manage_prompts: false,
        review_readiness: false,
        view_records: false,
        view_global_records: false,
        retry_jobs: false,
        regrade_history: false,
        view_logs: false,
        view_settings: false,
        ...overrides,
    };
    return {
        role: "support",
        role_label: roleLabel,
        capabilities,
        capability_keys: Object.entries(capabilities)
            .filter(([, enabled]) => enabled)
            .map(([key]) => key as SalesTrainerAdminCapabilities["capability_keys"][number]),
    };
}

describe("AdminSidebarContent", () => {
    beforeEach(() => {
        usePathnameMock.mockReturnValue("/admin/sales-trainer/paths");
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
        expect(screen.queryByRole("link", { name: "录音管理" })).toBeNull();
        expect(screen.queryByRole("link", { name: "学习专题" })).toBeNull();

        fireEvent.click(sectionButton);

        expect(await screen.findByRole("link", { name: "录音管理" })).not.toBeNull();
        const workbenchLink = await screen.findByRole("link", { name: "工作台" });
        expect(workbenchLink.getAttribute("href")).toBe("/admin/sales-trainer");
        expect(screen.getByRole("link", { name: "学习专题" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "路径与达标" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/paths",
        );
        expect(screen.getByRole("link", { name: "系统治理" })).not.toBeNull();
    });

    it("highlights only the concrete newcomer training child route when expanded", async () => {
        usePathnameMock.mockReturnValue("/admin/sales-trainer/learning-topics/questions");

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
        const learningTopicsLink = await screen.findByRole("link", { name: "学习专题" });

        expect(workbenchLink.className).not.toContain("text-slate-900 bg-white shadow");
        expect(learningTopicsLink.className).toContain("text-slate-900 bg-white shadow");
    });

    it("limits training leads to learner record entries", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "support-1",
                    display_name: "培训负责人",
                    role: "support",
                }}
                salesTrainerCapabilities={salesTrainerCapabilities({
                    manage_questions: true,
                    view_records: true,
                    view_logs: true,
                    view_settings: true,
                })}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        expect(screen.queryByRole("link", { name: "工作台" })).toBeNull();
        expect(await screen.findByRole("link", { name: "学习专题" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "系统治理" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "操作记录" })).not.toBeNull();
        expect(await screen.findByRole("link", { name: "录音管理" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "达标验收" })).not.toBeNull();
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
                salesTrainerCapabilities={salesTrainerCapabilities(
                    {
                        manage_content: true,
                        manage_questions: true,
                        manage_modules: true,
                    },
                    "内容管理员",
                )}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        expect(await screen.findByRole("link", { name: "路径与达标" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "录音管理" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "学习专题" })).not.toBeNull();
        expect(screen.queryByRole("link", { name: "学员录音" })).toBeNull();
        expect(screen.queryByRole("link", { name: "系统治理" })).toBeNull();
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
                salesTrainerCapabilities={salesTrainerCapabilities(
                    {
                        view_records: true,
                        retry_jobs: true,
                        regrade_history: true,
                        view_logs: true,
                        view_settings: true,
                    },
                    "运维人员",
                )}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "新人训练路径" }));

        expect(await screen.findByRole("link", { name: "系统治理" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "操作记录" })).not.toBeNull();
        expect(screen.getByRole("link", { name: "录音管理" })).not.toBeNull();
        expect(screen.queryByRole("link", { name: "学习专题" })).toBeNull();
        expect(screen.queryByRole("link", { name: "材料库" })).toBeNull();
    });

    it("renames the global AI coach policy entry to avoid confusing it with module config", async () => {
        render(
            <AdminSidebarContent
                currentUser={{
                    id: "admin-1",
                    display_name: "管理员",
                    role: "admin",
                }}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: "策略中心" }));

        expect(await screen.findByRole("link", { name: "AI 教练触达规则" })).not.toBeNull();
        expect(screen.queryByRole("link", { name: "AI 教练规则" })).toBeNull();
    });
});
