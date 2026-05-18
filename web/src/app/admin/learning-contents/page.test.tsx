import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminLearningContentsPage from "./page";
import type { LearningContent } from "@/lib/api/types";

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

const {
    createMock,
    deleteMock,
    listMock,
} = vi.hoisted(() => ({
    createMock: vi.fn(),
    deleteMock: vi.fn(),
    listMock: vi.fn(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
        <div {...props}>{children}</div>
    ),
}));



vi.mock("@/lib/debug", () => ({
    debug: {
        error: vi.fn(),
    },
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            learningContents: {
                create: createMock,
                delete: deleteMock,
                list: listMock,
            },
        },
    };
});

function makeLearningContent(overrides: Partial<LearningContent> = {}): LearningContent {
    return {
        learning_content_id: "content-1",
        title: "销售异议处理",
        summary: "学习如何处理常见异议",
        owner: "curriculum-team",
        source: "manual",
        status: "draft",
        safety_flagged: false,
        version: 1,
        content_hash: "hash-1",
        published_at: null,
        created_at: "2026-05-15T00:00:00Z",
        updated_at: "2026-05-15T00:00:00Z",
        chapters: [],
        ...overrides,
    };
}

describe("AdminLearningContentsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listMock.mockResolvedValue({ items: [], total: 0 });
        createMock.mockResolvedValue(makeLearningContent({ learning_content_id: "content-new", title: "新学习内容" }));
        deleteMock.mockResolvedValue(undefined);
    });

    it("renders loading state initially", () => {
        listMock.mockImplementation(() => new Promise(() => {}));
        render(<AdminLearningContentsPage />);
        expect(screen.getByText(/加载中/)).toBeTruthy();
    });

    it("renders empty state when no items", async () => {
        render(<AdminLearningContentsPage />);
        await waitFor(() => {
            expect(screen.getByText(/暂无学习内容/)).toBeTruthy();
        });
    });

    it("renders error state when list fails", async () => {
        listMock.mockRejectedValueOnce(new Error("network error"));
        render(<AdminLearningContentsPage />);
        await waitFor(() => {
            expect(screen.getByText(/加载失败/)).toBeTruthy();
        });
    });

    it("renders list items with status, owner, and source", async () => {
        listMock.mockResolvedValue({
            items: [
                makeLearningContent({
                    learning_content_id: "content-1",
                    title: "销售异议处理",
                    status: "draft",
                    owner: "curriculum-team",
                    source: "manual",
                }),
                makeLearningContent({
                    learning_content_id: "content-2",
                    title: "成交推进",
                    status: "published",
                    owner: "sales-team",
                    source: "imported",
                }),
            ],
            total: 2,
        });
        render(<AdminLearningContentsPage />);

        await waitFor(() => {
            expect(screen.getByText("销售异议处理")).toBeTruthy();
            expect(screen.getByText("成交推进")).toBeTruthy();
        });

        expect(screen.getByText(/草稿/)).toBeTruthy();
        expect(screen.getByText(/已发布/)).toBeTruthy();
        expect(screen.getByText(/curriculum-team/)).toBeTruthy();
        expect(screen.getByText(/sales-team/)).toBeTruthy();
        expect(screen.getByText(/manual/)).toBeTruthy();
        expect(screen.getByText(/imported/)).toBeTruthy();
    });

    it("renders title as link to detail page", async () => {
        listMock.mockResolvedValue({
            items: [
                makeLearningContent({
                    learning_content_id: "content-1",
                    title: "销售异议处理",
                    status: "draft",
                }),
            ],
            total: 1,
        });
        render(<AdminLearningContentsPage />);

        await waitFor(() => {
            expect(screen.getByText("销售异议处理")).toBeTruthy();
        });

        const link = screen.getByRole("link", { name: /销售异议处理/ });
        expect(link).toBeTruthy();
        expect(link.getAttribute("href")).toBe("/admin/learning-contents/content-1");
    });

    it("creates a draft learning content from the admin list page", async () => {
        render(<AdminLearningContentsPage />);
        await screen.findByText(/暂无学习内容/);

        fireEvent.change(screen.getByLabelText("标题"), { target: { value: "新学习内容" } });
        fireEvent.change(screen.getByLabelText("摘要"), { target: { value: "用于训练闭环" } });
        fireEvent.change(screen.getByLabelText("负责人"), { target: { value: "curriculum-team" } });
        fireEvent.click(screen.getByRole("button", { name: "创建内容" }));

        await waitFor(() => {
            expect(createMock).toHaveBeenCalledWith(
                expect.objectContaining({ title: "新学习内容", summary: "用于训练闭环", owner: "curriculum-team" }),
            );
        });
        expect(screen.getByText(/创建完成/)).toBeTruthy();
    });

    it("deletes a draft learning content from the admin list page", async () => {
        listMock.mockResolvedValue({ items: [makeLearningContent()], total: 1 });
        render(<AdminLearningContentsPage />);
        await screen.findByText("销售异议处理");

        fireEvent.click(screen.getByRole("button", { name: "删除" }));

        await waitFor(() => {
            expect(deleteMock).toHaveBeenCalledWith("content-1");
        });
        expect(screen.queryByText("销售异议处理")).toBeNull();
        expect(screen.getByText(/删除完成/)).toBeTruthy();
    });
});
