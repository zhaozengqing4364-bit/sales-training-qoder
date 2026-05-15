import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StudyPage from "./page";

const { getContentMock, completeChapterMock } = vi.hoisted(() => ({
    getContentMock: vi.fn(),
    completeChapterMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ learningContentId: "content-1" }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            learnerStudy: {
                getContent: getContentMock,
                completeChapter: completeChapterMock,
            },
        },
    };
});

function makeChapter(id: string, order: number, title: string, content: string) {
    return {
        chapter_id: id,
        learning_content_id: "content-1",
        title,
        content,
        order_index: order,
        created_at: "2026-05-15T00:00:00Z",
        updated_at: "2026-05-15T00:00:00Z",
    };
}

function makeContent() {
    return {
        learning_content_id: "content-1",
        title: "销售异议处理",
        summary: "学习如何处理常见异议",
        owner: "curriculum-team",
        source: "manual",
        chapters: [
            makeChapter("chapter-1", 0, "开场技巧", "先确认客户背景。"),
            makeChapter("chapter-2", 1, "异议识别", "识别常见的四种异议类型。"),
        ],
        progress: {
            completed_chapter_ids: [],
            completed_count: 0,
            total_chapters: 2,
            is_completed: false,
            state: "not_started" as const,
            primary_cta: "开始学习",
        },
    };
}

describe("StudyPage", () => {
    beforeEach(() => {
        getContentMock.mockReset();
        completeChapterMock.mockReset();
    });

    it("renders loading state", async () => {
        getContentMock.mockReturnValue(new Promise(() => {}));
        render(<StudyPage />);
        expect(screen.getByText("加载讲义中...")).toBeTruthy();
    });

    it("renders error state and retry button", async () => {
        getContentMock.mockRejectedValue(new Error("加载失败"));
        render(<StudyPage />);
        expect(await screen.findByRole("heading", { name: "加载失败" })).toBeTruthy();
        expect(screen.getByRole("button", { name: /重试/ })).toBeTruthy();
    });

    it("renders study content with chapters and progress", async () => {
        getContentMock.mockResolvedValue(makeContent());
        render(<StudyPage />);

        expect(await screen.findByRole("heading", { name: "销售异议处理" })).toBeTruthy();
        expect(screen.getByText("学习如何处理常见异议")).toBeTruthy();
        expect(screen.getByText("阅读进度 0/2")).toBeTruthy();
        expect(screen.getByText("先确认客户背景。")).toBeTruthy();
        expect(screen.getByRole("button", { name: /标记完成/ })).toBeTruthy();
    });

    it("switches chapters and marks one complete", async () => {
        getContentMock.mockResolvedValue(makeContent());
        completeChapterMock.mockResolvedValue({
            chapter_id: "chapter-1",
            already_completed: false,
            progress: {
                completed_chapter_ids: ["chapter-1"],
                completed_count: 1,
                total_chapters: 2,
                is_completed: false,
                state: "in_progress",
                primary_cta: "继续学习",
            },
        });

        render(<StudyPage />);

        await screen.findByRole("button", { name: /标记完成/ });
        const completeButton = screen.getByRole("button", { name: /标记完成/ });
        fireEvent.click(completeButton);

        expect(completeChapterMock).toHaveBeenCalledWith("content-1", "chapter-1");
        expect(await screen.findByText("阅读进度 1/2")).toBeTruthy();
        expect(screen.getByText("本章已完成")).toBeTruthy();
    });

    it("renders mobile chapter selector with select element", async () => {
        getContentMock.mockResolvedValue(makeContent());
        render(<StudyPage />);

        await screen.findByRole("heading", { name: "销售异议处理" });
        const chapterSelect = screen.getByLabelText("选择章节");
        expect(chapterSelect.tagName).toBe("SELECT");
        const options = within(chapterSelect).getAllByRole("option");
        expect(options).toHaveLength(2);
    });

    it("shows completed state with completion CTA disabled", async () => {
        const completedContent = {
            ...makeContent(),
            progress: {
                completed_chapter_ids: ["chapter-1", "chapter-2"],
                completed_count: 2,
                total_chapters: 2,
                is_completed: true,
                state: "completed" as const,
                primary_cta: "参加考试",
            },
        };
        getContentMock.mockResolvedValue(completedContent);
        render(<StudyPage />);

        expect(await screen.findByText("学习完成")).toBeTruthy();
        expect(screen.getByText("你已阅读完所有章节。考试功能即将上线，敬请期待。")).toBeTruthy();
        expect(screen.getByRole("button", { name: /即将上线/ })).toBeTruthy();
    });

    it("renders empty state when content has no chapters", async () => {
        const emptyContent = {
            ...makeContent(),
            chapters: [],
            progress: { ...makeContent().progress, total_chapters: 0 },
        };
        getContentMock.mockResolvedValue(emptyContent);
        render(<StudyPage />);

        expect(await screen.findByText("暂无章节")).toBeTruthy();
    });

    it("handles already completed chapter idempotently", async () => {
        const partialContent = {
            ...makeContent(),
            progress: {
                completed_chapter_ids: ["chapter-1"],
                completed_count: 1,
                total_chapters: 2,
                is_completed: false,
                state: "in_progress" as const,
                primary_cta: "继续学习",
            },
        };
        getContentMock.mockResolvedValue(partialContent);

        render(<StudyPage />);

        await screen.findByText("阅读进度 1/2");
        expect(screen.getByText("本章已完成")).toBeTruthy();
    });
});
