import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";
import { SalesTrainerAdminModuleNav } from "./module-nav";

const prefetchMock = vi.hoisted(() => vi.fn());
vi.mock("next/link", () => ({
    default: ({ href, children, prefetch, ...props }: { href: string; children: ReactNode; prefetch?: boolean }) => (
        <a href={href} data-prefetch={String(prefetch)} {...props}>{children}</a>
    ),
}));
vi.mock("next/navigation", () => ({
    useRouter: () => ({ prefetch: prefetchMock }),
}));

const FULL_ACCESS: SalesTrainerAdminCapabilities = {
    role: "admin",
    role_label: "管理员",
    capability_keys: ["admin_full_access"],
    capabilities: {
        admin_full_access: true,
        manage_content: true,
        manage_questions: true,
        manage_modules: true,
        manage_prompts: true,
        view_records: true,
        view_global_records: true,
        retry_jobs: true,
        regrade_history: true,
        view_logs: true,
        view_settings: true,
    },
};

describe("SalesTrainerAdminModuleNav", () => {
    it("uses task-oriented newcomer training labels", () => {
        render(
            <SalesTrainerAdminModuleNav
                currentPath="/admin/newcomer-training/learners"
                capabilities={FULL_ACCESS}
            />,
        );

        expect(screen.getByRole("link", { name: /训练内容与路径/ })).toBeTruthy();
        expect(screen.getByRole("link", { name: /学员进度/ })).toBeTruthy();
        expect(screen.getByRole("link", { name: /达标审核/ })).toBeTruthy();
        expect(screen.getByRole("link", { name: /训练记录/ })).toBeTruthy();
        expect(screen.queryByRole("link", { name: /训练分析/ })).toBeNull();
        expect(screen.queryByRole("link", { name: /模块单元/ })).toBeNull();
        expect(screen.queryByText("路径与达标")).toBeNull();

        const pathLink = screen.getByRole("link", { name: /训练内容与路径/ });
        expect(pathLink.className).toContain("transition-colors");
        expect(pathLink.className).toContain("duration-[var(--duration-press)]");
        expect(pathLink.className).toContain("ease-[var(--ease-out)]");
    });

    it("keeps question navigation on existing routes without eager prefetch", () => {
        prefetchMock.mockReset();
        render(
            <SalesTrainerAdminModuleNav
                currentPath="/admin/sales-trainer/questions"
                capabilities={FULL_ACCESS}
            />,
        );

        const questionLink = screen.getByRole("link", { name: /题目列表/ });
        expect(questionLink.getAttribute("href")).toBe("/admin/sales-trainer/questions");
        expect(questionLink.getAttribute("data-prefetch")).toBe("false");
        expect(screen.getByRole("link", { name: /题目分类/ }).getAttribute("href"))
            .toBe("/admin/sales-trainer/questions/categories");
        expect(screen.queryByRole("link", { name: /资料导入/ })).toBeNull();
        expect(screen.queryByRole("link", { name: /能力点/ })).toBeNull();

        fireEvent.mouseEnter(questionLink);
        expect(prefetchMock).not.toHaveBeenCalled();
    });
});
