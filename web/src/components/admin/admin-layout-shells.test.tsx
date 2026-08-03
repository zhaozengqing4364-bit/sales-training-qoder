import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
    AdminContextBar,
    AdminDetailShell,
    AdminFormShell,
    AdminIndexShell,
    AdminPageHeader,
    PolicyPageShell,
} from "./admin-layout-shells";

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

describe("Admin layout shells", () => {
    it("renders AdminPageHeader with title, description, and action slots", () => {
        render(
            <AdminPageHeader
                title="题库管理"
                description="管理试题分类与题目"
                primaryAction={<button type="button">新建</button>}
                secondaryActions={<button type="button">导入</button>}
            />,
        );

        expect(screen.getByRole("heading", { name: "题库管理" })).toBeTruthy();
        expect(screen.getByText("管理试题分类与题目")).toBeTruthy();
        expect(screen.getByRole("button", { name: "新建" })).toBeTruthy();
        expect(screen.getByRole("button", { name: "导入" })).toBeTruthy();
    });

    it("renders AdminIndexShell with header, context bar, and main content", () => {
        const view = render(
            <AdminIndexShell
                header={<div>Header</div>}
                contextBar={<AdminContextBar>Checklist</AdminContextBar>}
            >
                <div>Main table</div>
            </AdminIndexShell>,
        );

        expect(screen.getByText("Header")).toBeTruthy();
        expect(screen.getByText("Checklist")).toBeTruthy();
        expect(screen.getByText("Main table")).toBeTruthy();
        expect(view.container.firstElementChild?.className).not.toContain("duration-500");
        expect(view.container.firstElementChild?.className).not.toContain("slide-in-from-bottom");
    });

    it("renders AdminDetailShell with back link and active tab", () => {
        render(
            <AdminDetailShell
                backHref="/admin/knowledge"
                title="产品知识库"
                tabs={[
                    { label: "概览", href: "/admin/knowledge/kb-1", isActive: true },
                    { label: "文档", href: "/admin/knowledge/kb-1/documents" },
                ]}
            >
                <div>Hub content</div>
            </AdminDetailShell>,
        );

        expect(screen.getByRole("link", { name: "返回" }).getAttribute("href")).toBe("/admin/knowledge");
        expect(screen.getByRole("heading", { name: "产品知识库" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "概览" }).getAttribute("href")).toBe("/admin/knowledge/kb-1");
        expect(screen.getByText("Hub content")).toBeTruthy();
    });

    it("renders AdminFormShell with back link and action slot", () => {
        render(
            <AdminFormShell
                backHref="/admin/learning-contents"
                title="新建学习内容"
                actions={<button type="button">保存</button>}
            >
                <form aria-label="create-form">Form body</form>
            </AdminFormShell>,
        );

        expect(screen.getByRole("link", { name: "返回" }).getAttribute("href")).toBe("/admin/learning-contents");
        expect(screen.getByRole("heading", { name: "新建学习内容" })).toBeTruthy();
        expect(screen.getByRole("button", { name: "保存" })).toBeTruthy();
        expect(screen.getByRole("form", { name: "create-form" })).toBeTruthy();
    });

    it("renders PolicyPageShell with header, context bar, and content", () => {
        render(
            <PolicyPageShell
                header={<AdminPageHeader title="检索策略" description="全局检索配置" />}
                contextBar={<AdminContextBar>Scope banner</AdminContextBar>}
            >
                <div>Console body</div>
            </PolicyPageShell>,
        );

        expect(screen.getByRole("heading", { name: "检索策略" })).toBeTruthy();
        expect(screen.getByText("Scope banner")).toBeTruthy();
        expect(screen.getByText("Console body")).toBeTruthy();
    });
});
