import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { previewMock, confirmMock } = vi.hoisted(() => ({
    previewMock: vi.fn(),
    confirmMock: vi.fn(),
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
    debug: { error: vi.fn() },
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            testBank: {
                ...actual.api.testBank,
                previewQuestionGeneration: previewMock,
                confirmQuestionGeneration: confirmMock,
            },
        },
    };
});

import { QuestionGenerationPanel } from "./question-generation-panel";

function makeDraft(overrides: Partial<Record<string, unknown>> = {}) {
    return {
        title: "异议处理测试",
        stem: "当客户提出价格异议时，你应该怎么做？",
        reference_answer: "先认同客户观点，再逐步引导。",
        scoring_criteria: { logic_weight: 0.6, persuasion_weight: 0.4 },
        scoring_dimensions: ["逻辑性", "说服力"],
        tags: ["异议处理"],
        difficulty: "medium",
        source_learning_content_id: "content-1",
        source_chapter_id: "chapter-1",
        ...overrides,
    };
}

const MOCK_CATEGORIES = [
    { category_id: "cat-1", name: "销售技巧", description: null, parent_id: null, order_index: 0, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    { category_id: "cat-2", name: "产品知识", description: null, parent_id: null, order_index: 1, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
];

describe("QuestionGenerationPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        previewMock.mockResolvedValue({ drafts: [] });
    });

    it("renders trigger button for a chapter", () => {
        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        expect(screen.getByText("AI 生成考题")).toBeTruthy();
    });

    it("calls preview API when trigger button is clicked", async () => {
        previewMock.mockResolvedValue({
            drafts: [makeDraft()],
        });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(previewMock).toHaveBeenCalledWith({
                learning_content_id: "content-1",
                chapter_id: "chapter-1",
            });
        });
    });

    it("shows loading state during preview generation", async () => {
        previewMock.mockImplementation(() => new Promise(() => {}));

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByText(/生成中/)).toBeTruthy();
        });
    });

    it("shows draft cards after preview succeeds", async () => {
        previewMock.mockResolvedValue({
            drafts: [
                makeDraft({ title: "第一题" }),
                makeDraft({ title: "第二题", difficulty: "hard" }),
            ],
        });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByDisplayValue("第一题")).toBeTruthy();
            expect(screen.getByDisplayValue("第二题")).toBeTruthy();
        });
    });

    it("shows preview error as inline message", async () => {
        previewMock.mockRejectedValue(new Error("[QUESTION_GENERATION_UNSAFE_CONTENT]"));

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByText(/疑似注入指令/)).toBeTruthy();
        });
    });

    it("allows editing draft fields", async () => {
        previewMock.mockResolvedValue({
            drafts: [makeDraft({ title: "原始标题" })],
        });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByDisplayValue("原始标题")).toBeTruthy();
        });

        fireEvent.change(screen.getByDisplayValue("原始标题"), {
            target: { value: "修改后的标题" },
        });

        expect(screen.getByDisplayValue("修改后的标题")).toBeTruthy();
    });

    it("displays category selector before confirm", async () => {
        previewMock.mockResolvedValue({
            drafts: [makeDraft()],
        });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByText("销售技巧")).toBeTruthy();
            expect(screen.getByText("产品知识")).toBeTruthy();
        });
    });

    it("calls confirm API with category_id and edited drafts", async () => {
        previewMock.mockResolvedValue({
            drafts: [makeDraft({ title: "最终标题", difficulty: "easy" })],
        });
        confirmMock.mockResolvedValue({
            items: [
                {
                    question_id: "q-saved",
                    title: "最终标题",
                    stem: "当客户提出价格异议时，你应该怎么做？",
                    reference_answer: "先认同客户观点，再逐步引导。",
                    category_id: "cat-1",
                    difficulty: "easy",
                    status: "draft",
                    tags: ["异议处理"],
                    scoring_dimensions: ["逻辑性", "说服力"],
                    scoring_criteria: { logic_weight: 0.6, persuasion_weight: 0.4 },
                    safety_flagged: false,
                    department: null,
                    version: 1,
                    content_hash: null,
                    published_at: null,
                    created_at: "2026-05-16T00:00:00Z",
                    updated_at: "2026-05-16T00:00:00Z",
                },
            ],
            total: 1,
        });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByDisplayValue("最终标题")).toBeTruthy();
        });

        const categorySelect = screen.getAllByRole("combobox")[1];
        fireEvent.change(categorySelect, { target: { value: "cat-1" } });

        fireEvent.click(screen.getByText("确认保存到试题库"));

        await waitFor(() => {
            expect(confirmMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    category_id: "cat-1",
                    drafts: expect.arrayContaining([
                        expect.objectContaining({
                            title: "最终标题",
                            difficulty: "easy",
                            source_learning_content_id: "content-1",
                            source_chapter_id: "chapter-1",
                        }),
                    ]),
                }),
            );
        });
    });

    it("shows success message after confirm save", async () => {
        previewMock.mockResolvedValue({ drafts: [makeDraft()] });
        confirmMock.mockResolvedValue({
            items: [
                {
                    question_id: "q-saved",
                    title: "已保存",
                    stem: "...",
                    reference_answer: "...",
                    category_id: "cat-1",
                    difficulty: "medium",
                    status: "draft",
                    tags: [],
                    scoring_dimensions: [],
                    scoring_criteria: {},
                    safety_flagged: false,
                    department: null,
                    version: 1,
                    content_hash: null,
                    published_at: null,
                    created_at: "2026-05-16T00:00:00Z",
                    updated_at: "2026-05-16T00:00:00Z",
                },
            ],
            total: 1,
        });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByDisplayValue("异议处理测试")).toBeTruthy();
        });

        const categorySelect = screen.getAllByRole("combobox")[1];
        fireEvent.change(categorySelect, { target: { value: "cat-1" } });
        fireEvent.click(screen.getByText("确认保存到试题库"));

        await waitFor(() => {
            expect(screen.getByText(/已保存 1 道题目/)).toBeTruthy();
        });
    });

    it("shows confirm save error as inline message", async () => {
        previewMock.mockResolvedValue({ drafts: [makeDraft()] });
        confirmMock.mockRejectedValue(new Error("保存失败: [QUESTION_GENERATION_FAILED]"));

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByDisplayValue("异议处理测试")).toBeTruthy();
        });

        const categorySelect = screen.getAllByRole("combobox")[1];
        fireEvent.change(categorySelect, { target: { value: "cat-1" } });
        fireEvent.click(screen.getByText("确认保存到试题库"));

        await waitFor(() => {
            expect(screen.getByText(/保存失败/)).toBeTruthy();
        });
    });

    it("shows empty state when no drafts returned", async () => {
        previewMock.mockResolvedValue({ drafts: [] });

        render(
            <QuestionGenerationPanel
                learningContentId="content-1"
                chapterId="chapter-1"
                categories={MOCK_CATEGORIES}
            />,
        );

        fireEvent.click(screen.getByText("AI 生成考题"));

        await waitFor(() => {
            expect(screen.getByText(/未生成/)).toBeTruthy();
        });
    });
});
