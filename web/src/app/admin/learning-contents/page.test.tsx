import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminLearningContentsPage from "./page";
import type { LearningContent } from "@/lib/api/types";

const {
    listMock,
} = vi.hoisted(() => ({
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
});
