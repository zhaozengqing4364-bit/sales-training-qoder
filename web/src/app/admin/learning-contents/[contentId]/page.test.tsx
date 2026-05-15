import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LearningChapter, LearningContent } from "@/lib/api/types";

const {
    getMock,
    updateMock,
    addChapterMock,
    updateChapterMock,
    deleteChapterMock,
    reorderChaptersMock,
    publishMock,
    archiveMock,
} = vi.hoisted(() => ({
    getMock: vi.fn(),
    updateMock: vi.fn(),
    addChapterMock: vi.fn(),
    updateChapterMock: vi.fn(),
    deleteChapterMock: vi.fn(),
    reorderChaptersMock: vi.fn(),
    publishMock: vi.fn(),
    archiveMock: vi.fn(),
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

vi.mock("@/components/ui/status-indicator", () => ({
    StatusIndicator: ({ status, message }: { status: string; message?: string }) => (
        <span data-testid={`status-${status}`}>{message || status}</span>
    ),
}));

vi.mock("@/components/ui/empty-state", () => ({
    EmptyState: ({ title, description }: { title: string; description: string }) => (
        <div data-testid="empty-state">
            <span>{title}</span>
            <span>{description}</span>
        </div>
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
                list: vi.fn(),
                create: vi.fn(),
                get: getMock,
                update: updateMock,
                addChapter: addChapterMock,
                updateChapter: updateChapterMock,
                deleteChapter: deleteChapterMock,
                reorderChapters: reorderChaptersMock,
                publish: publishMock,
                archive: archiveMock,
            },
        },
    };
});

const MOCK_CONTENT_ID = "content-1";

vi.mock("next/navigation", () => ({
    useParams: () => ({ contentId: MOCK_CONTENT_ID }),
    useRouter: () => ({ back: vi.fn() }),
}));

function makeChapter(overrides: Partial<LearningChapter> = {}): LearningChapter {
    return {
        chapter_id: "chapter-1",
        learning_content_id: MOCK_CONTENT_ID,
        title: "第一章",
        content: "第一章内容",
        order_index: 0,
        created_at: "2026-05-15T00:00:00Z",
        updated_at: "2026-05-15T00:00:00Z",
        ...overrides,
    };
}

function makeContent(overrides: Partial<LearningContent> = {}): LearningContent {
    return {
        learning_content_id: MOCK_CONTENT_ID,
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
        chapters: [
            makeChapter(),
            makeChapter({ chapter_id: "chapter-2", title: "第二章", content: "第二章内容", order_index: 1 }),
        ],
        ...overrides,
    };
}

describe("AdminLearningContentDetailPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getMock.mockResolvedValue(makeContent());
    });

    it("renders loading state initially", async () => {
        getMock.mockImplementation(() => new Promise(() => {}));
        render(<AdminLearningContentDetailPage />);
        expect(screen.getByText(/加载中/)).toBeTruthy();
    });

    it("renders error state when get fails", async () => {
        getMock.mockRejectedValueOnce(new Error("network error"));
        render(<AdminLearningContentDetailPage />);
        await waitFor(() => {
            expect(screen.getByText(/加载失败/)).toBeTruthy();
        });
    });

    it("renders detail metadata, status, version, owner, source, and safety flag", async () => {
        getMock.mockResolvedValue(
            makeContent({
                title: "销售异议处理",
                summary: "学习如何处理常见异议",
                owner: "curriculum-team",
                source: "manual",
                status: "draft",
                safety_flagged: false,
                version: 1,
            }),
        );
        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByDisplayValue("销售异议处理")).toBeTruthy();
            expect(screen.getByDisplayValue("学习如何处理常见异议")).toBeTruthy();
            expect(screen.getByDisplayValue("curriculum-team")).toBeTruthy();
            expect(screen.getByDisplayValue("manual")).toBeTruthy();
        });

        expect(screen.getByText(/草稿/)).toBeTruthy();
        expect(screen.getByText(/v1/)).toBeTruthy();
    });

    it("renders chapters list", async () => {
        getMock.mockResolvedValue(
            makeContent({
                chapters: [
                    makeChapter({ chapter_id: "c1", title: "第一章", order_index: 0 }),
                    makeChapter({ chapter_id: "c2", title: "第二章", order_index: 1 }),
                ],
            }),
        );
        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("第一章")).toBeTruthy();
            expect(screen.getByText("第二章")).toBeTruthy();
        });
    });

    it("shows empty state when no chapters", async () => {
        getMock.mockResolvedValue(makeContent({ chapters: [] }));
        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText(/暂无章节/)).toBeTruthy();
        });
    });

    it("updates metadata and refreshes state", async () => {
        const content = makeContent();
        const updatedContent = makeContent({
            title: "新标题",
            summary: "新摘要",
            owner: "new-team",
            source: "imported",
            safety_flagged: true,
        });
        updateMock.mockResolvedValue(updatedContent);
        getMock.mockResolvedValueOnce(content).mockResolvedValueOnce(updatedContent);

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByDisplayValue("销售异议处理")).toBeTruthy();
        });

        fireEvent.change(screen.getByDisplayValue("销售异议处理"), { target: { value: "新标题" } });
        fireEvent.change(screen.getByDisplayValue("学习如何处理常见异议"), { target: { value: "新摘要" } });
        fireEvent.change(screen.getByDisplayValue("curriculum-team"), { target: { value: "new-team" } });
        fireEvent.change(screen.getByDisplayValue("manual"), { target: { value: "imported" } });
        fireEvent.click(screen.getByRole("checkbox", { name: /安全标记/ }));
        fireEvent.click(screen.getByText(/保存元数据/));

        await waitFor(() => {
            expect(updateMock).toHaveBeenCalledWith(MOCK_CONTENT_ID, {
                title: "新标题",
                summary: "新摘要",
                owner: "new-team",
                source: "imported",
                safety_flagged: true,
            });
        });

        await waitFor(() => {
            expect(screen.getByDisplayValue("新标题")).toBeTruthy();
        });
    });

    it("shows metadata update error", async () => {
        getMock.mockResolvedValue(makeContent());
        updateMock.mockRejectedValueOnce(new Error("update failed"));

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByDisplayValue("销售异议处理")).toBeTruthy();
        });

        fireEvent.click(screen.getByText(/保存元数据/));

        await waitFor(() => {
            expect(screen.getByText(/update failed/)).toBeTruthy();
        });
    });

    it("adds a chapter", async () => {
        const content = makeContent({ chapters: [] });
        const newChapter = makeChapter({ chapter_id: "c-new", title: "新章节", order_index: 0 });
        addChapterMock.mockResolvedValue(newChapter);
        getMock.mockResolvedValueOnce(content).mockResolvedValueOnce({
            ...content,
            chapters: [newChapter],
        });

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByPlaceholderText(/章节标题/)).toBeTruthy();
        });

        fireEvent.change(screen.getByPlaceholderText(/章节标题/), { target: { value: "新章节" } });
        fireEvent.change(screen.getByPlaceholderText(/章节内容/), { target: { value: "新章节内容" } });
        fireEvent.click(screen.getByRole("button", { name: /添加章节/ }));

        await waitFor(() => {
            expect(addChapterMock).toHaveBeenCalledWith(MOCK_CONTENT_ID, {
                title: "新章节",
                content: "新章节内容",
            });
        });

        await waitFor(() => {
            expect(screen.getByText("新章节")).toBeTruthy();
        });
    });

    it("edits a chapter", async () => {
        const chapter = makeChapter({ chapter_id: "c1", title: "第一章", order_index: 0 });
        getMock.mockResolvedValue(makeContent({ chapters: [chapter] }));
        updateChapterMock.mockResolvedValue({ ...chapter, title: "修改后的章节" });
        getMock
            .mockResolvedValueOnce(makeContent({ chapters: [chapter] }))
            .mockResolvedValueOnce(makeContent({ chapters: [{ ...chapter, title: "修改后的章节" }] }));

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("第一章")).toBeTruthy();
        });

        fireEvent.click(screen.getAllByTitle("编辑")[0]);

        await waitFor(() => {
            expect(screen.getByDisplayValue("第一章")).toBeTruthy();
        });

        fireEvent.change(screen.getByDisplayValue("第一章"), { target: { value: "修改后的章节" } });

        // Find inline save button: it's the button whose textContent is exactly "保存"
        const allBtns = screen.getAllByRole("button");
        const saveBtn = allBtns.find((b) => b.textContent?.trim() === "保存");
        expect(saveBtn).toBeTruthy();
        fireEvent.click(saveBtn!);

        await waitFor(
            () => {
                expect(updateChapterMock).toHaveBeenCalled();
            },
            { timeout: 3000 },
        );
    });

    it("deletes a chapter", async () => {
        const chapter = makeChapter({ chapter_id: "c1", title: "第一章", order_index: 0 });
        getMock
            .mockResolvedValueOnce(makeContent({ chapters: [chapter] }))
            .mockResolvedValueOnce(makeContent({ chapters: [] }));

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("第一章")).toBeTruthy();
        });

        fireEvent.click(screen.getAllByTitle("删除")[0]);

        await waitFor(() => {
            expect(deleteChapterMock).toHaveBeenCalledWith(MOCK_CONTENT_ID, "c1");
        });

        await waitFor(() => {
            expect(screen.getByText(/暂无章节/)).toBeTruthy();
        });
    });

    it("reorders chapters - move up", async () => {
        const c1 = makeChapter({ chapter_id: "c1", title: "第一章", order_index: 0 });
        const c2 = makeChapter({ chapter_id: "c2", title: "第二章", order_index: 1 });
        getMock
            .mockResolvedValueOnce(makeContent({ chapters: [c1, c2] }))
            .mockResolvedValueOnce(makeContent({ chapters: [c2, c1] }));

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("第一章")).toBeTruthy();
            expect(screen.getByText("第二章")).toBeTruthy();
        });

        fireEvent.click(screen.getAllByTitle("上移")[1]);

        await waitFor(() => {
            expect(reorderChaptersMock).toHaveBeenCalledWith(MOCK_CONTENT_ID, ["c2", "c1"]);
        });
    });

    it("reorders chapters - move down", async () => {
        const c1 = makeChapter({ chapter_id: "c1", title: "第一章", order_index: 0 });
        const c2 = makeChapter({ chapter_id: "c2", title: "第二章", order_index: 1 });
        getMock
            .mockResolvedValueOnce(makeContent({ chapters: [c1, c2] }))
            .mockResolvedValueOnce(makeContent({ chapters: [c2, c1] }));

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("第一章")).toBeTruthy();
        });

        fireEvent.click(screen.getAllByTitle("下移")[0]);

        await waitFor(() => {
            expect(reorderChaptersMock).toHaveBeenCalledWith(MOCK_CONTENT_ID, ["c2", "c1"]);
        });
    });

    it("displays publish gate failure reason codes", async () => {
        getMock.mockResolvedValue(makeContent());

        const gateError = Object.assign(new Error("发布门禁未通过"), {
            name: "ApiRequestError",
            status: 422,
            errorCode: "[PUBLISH_GATE_FAILED]",
            rawMessage: "发布门禁未通过",
            details: {
                gate_results: [
                    {
                        gate_name: "chapter_check",
                        status: "failed",
                        reason_code: "no_chapters",
                        message: "学习内容没有章节",
                    },
                    {
                        gate_name: "security_check",
                        status: "failed",
                        reason_code: "security_flagged_content",
                        message: "内容被安全标记",
                    },
                ],
            },
        });

        publishMock.mockRejectedValueOnce(gateError);

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByRole("button", { name: "发布" })).toBeTruthy();
        });

        fireEvent.click(screen.getByRole("button", { name: "发布" }));

        await waitFor(() => {
            expect(screen.getByText(/no_chapters/)).toBeTruthy();
            expect(screen.getByText(/security_flagged_content/)).toBeTruthy();
        });
    });

    it("publishes successfully", async () => {
        const content = makeContent({ status: "draft" });
        const publishedContent = makeContent({
            status: "published",
            published_at: "2026-05-15T12:00:00Z",
        });
        getMock.mockResolvedValueOnce(content).mockResolvedValueOnce(publishedContent);
        publishMock.mockResolvedValue(publishedContent);

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("发布")).toBeTruthy();
        });

        fireEvent.click(screen.getByRole("button", { name: "发布" }));

        await waitFor(() => {
            expect(publishMock).toHaveBeenCalledWith(MOCK_CONTENT_ID);
        });

        await waitFor(() => {
            expect(screen.getByText(/已发布/)).toBeTruthy();
        });
    });

    it("archives successfully", async () => {
        const content = makeContent({ status: "published" });
        const archivedContent = makeContent({ status: "archived" });
        getMock.mockResolvedValueOnce(content).mockResolvedValueOnce(archivedContent);
        archiveMock.mockResolvedValue(archivedContent);

        render(<AdminLearningContentDetailPage />);

        await waitFor(() => {
            expect(screen.getByRole("button", { name: "归档" })).toBeTruthy();
        });

        fireEvent.click(screen.getByRole("button", { name: "归档" }));

        await waitFor(() => {
            expect(archiveMock).toHaveBeenCalledWith(MOCK_CONTENT_ID);
        });

        await waitFor(() => {
            expect(screen.getByText(/已归档/)).toBeTruthy();
        });
    });
});

import AdminLearningContentDetailPage from "./page";
