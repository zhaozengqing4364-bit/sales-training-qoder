import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StudyPage from "./page";

const { getContentMock, completeChapterMock, startExamMock, pushMock } = vi.hoisted(() => ({
    getContentMock: vi.fn(),
    completeChapterMock: vi.fn(),
    startExamMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ learningContentId: "content-1" }),
    useRouter: () => ({ push: pushMock }),
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
                startExam: startExamMock,
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
        startExamMock.mockReset();
        pushMock.mockReset();
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
        expect(screen.getByText(/阅读进度 0\/2/)).toBeTruthy();
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
        expect(await screen.findByText(/阅读进度 1\/2/)).toBeTruthy();
        expect(screen.getByText("本章已完成")).toBeTruthy();
    });

    it("shows completion errors without changing progress", async () => {
        getContentMock.mockResolvedValue(makeContent());
        completeChapterMock.mockRejectedValue(new Error("backend unavailable"));

        render(<StudyPage />);

        await screen.findByRole("button", { name: /标记完成/ });
        fireEvent.click(screen.getByRole("button", { name: /标记完成/ }));

        expect((await screen.findByRole("alert")).textContent).toMatch(/标记完成失败/);
        expect(screen.getByText(/阅读进度 0\/2/)).toBeTruthy();
        expect(screen.queryByText("本章已完成")).toBeNull();
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

    it("starts an AI exam when learning is completed", async () => {
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
        startExamMock.mockResolvedValue({ session_id: "exam-session-1", examiner_agent_id: "examiner-1" });
        render(<StudyPage />);

        expect(await screen.findByText("学习完成")).toBeTruthy();
        expect(screen.getByText("你已阅读完所有章节。现在可以进入 AI 考官考核。")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: /开始 AI 考核/ }));

        expect(startExamMock).toHaveBeenCalledWith("content-1");
        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/exam/exam-session-1");
        });
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

        await screen.findByText(/阅读进度 1\/2/);
        expect(screen.getByText("本章已完成")).toBeTruthy();
    });

    it("displays progress bar with percentage", async () => {
        getContentMock.mockResolvedValue(makeContent());
        render(<StudyPage />);

        await screen.findByText(/阅读进度 0\/2/);
        const progressBar = screen.getByRole("progressbar", { name: /学习进度/ });
        expect(progressBar).toBeTruthy();
        expect(progressBar.getAttribute("aria-valuenow")).toBe("0");
        expect(progressBar.getAttribute("aria-valuemax")).toBe("100");
    });

    it("shows next-chapter button and switches content on click", async () => {
        getContentMock.mockResolvedValue(makeContent());
        render(<StudyPage />);

        await screen.findByText("先确认客户背景。");
        const nextButton = screen.getByRole("button", { name: /下一章/ });
        expect(nextButton).toBeTruthy();

        fireEvent.click(nextButton);

        expect(await screen.findByText("识别常见的四种异议类型。")).toBeTruthy();
        expect(screen.queryByRole("button", { name: /下一章/ })).toBeNull();
    });
});
