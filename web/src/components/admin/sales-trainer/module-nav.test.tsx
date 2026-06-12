import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SalesTrainerAdminModuleNav } from "./module-nav";

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

describe("SalesTrainerAdminModuleNav", () => {
    it("does not render a duplicate local nav for unit pages without subresources", () => {
        const { container } = render(<SalesTrainerAdminModuleNav currentPath="/admin/sales-trainer/units" />);

        expect(container.childElementCount).toBe(0);
        expect(screen.queryByRole("link", { name: "文章" })).toBeNull();
        expect(screen.queryByRole("link", { name: "考卷" })).toBeNull();
        expect(screen.queryByRole("link", { name: "题库" })).toBeNull();
    });

    it("shows question-bank options on question pages", () => {
        render(<SalesTrainerAdminModuleNav currentPath="/admin/sales-trainer/questions/categories" />);

        expect(screen.getByRole("link", { name: "题目清单" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/questions",
        );
        expect(screen.getByRole("link", { name: "分类管理" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/questions/categories",
        );
        expect(screen.queryByRole("link", { name: "新建题目" })).toBeNull();
        expect(screen.queryByRole("link", { name: "模块" })).toBeNull();
        expect(screen.queryByRole("link", { name: "录音" })).toBeNull();
    });

    it("groups path config and AI coach config together", () => {
        render(<SalesTrainerAdminModuleNav currentPath="/admin/sales-trainer/ai-coach" />);

        expect(screen.getByRole("link", { name: "路径配置" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/paths",
        );
        expect(screen.getByRole("link", { name: "AI 教练配置" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/ai-coach",
        );
    });
});
