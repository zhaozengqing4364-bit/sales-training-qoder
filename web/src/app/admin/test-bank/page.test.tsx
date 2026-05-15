import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TestBankPage from "./page";

const {
    listCategoriesMock,
    createCategoryMock,
    deleteCategoryMock,
    listQuestionsMock,
    createQuestionMock,
    publishQuestionMock,
    archiveQuestionMock,
} = vi.hoisted(() => ({
    listCategoriesMock: vi.fn(),
    createCategoryMock: vi.fn(),
    deleteCategoryMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    createQuestionMock: vi.fn(),
    publishQuestionMock: vi.fn(),
    archiveQuestionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, onClick, disabled, ...props }: Record<string, unknown>) => (
        <button type="button" onClick={onClick as () => void} disabled={disabled as boolean} {...props}>
            {children as React.ReactNode}
        </button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, ...props }: Record<string, unknown>) => <div {...props}>{children as React.ReactNode}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, ...props }: Record<string, unknown>) => <span {...props}>{children as React.ReactNode}</span>,
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: ({ open, title, description, confirmText, onConfirm }: {
        open: boolean;
        title: string;
        description: string;
        confirmText?: string;
        onConfirm: () => void;
    }) => open ? (
        <div role="dialog">
            <div>{title}</div>
            <div>{description}</div>
            <button type="button" onClick={onConfirm}>{confirmText ?? "确认"}</button>
        </div>
    ) : null,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: vi.fn(),
        error: vi.fn(),
    }),
}));

vi.mock("@/components/ui/mobile-table-card", () => ({
    MobileTableCard: ({ title }: { title: React.ReactNode }) => <div>{title}</div>,
}));

vi.mock("lucide-react", () => ({
    RefreshCcw: () => <span>refresh</span>,
    Plus: () => <span>+</span>,
    Edit2: () => <span>edit</span>,
    Trash2: () => <span>delete</span>,
    Search: () => <span>search</span>,
    BookOpen: () => <span>book</span>,
    AlertCircle: () => <span>alert</span>,
    ChevronDown: () => <span>chevron</span>,
    FileText: () => <span>file</span>,
    Tag: () => <span>tag</span>,
    Filter: () => <span>filter</span>,
    Eye: () => <span>eye</span>,
    Archive: () => <span>archive</span>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            testBank: {
                listCategories: listCategoriesMock,
                createCategory: createCategoryMock,
                updateCategory: vi.fn(),
                deleteCategory: deleteCategoryMock,
                listQuestions: listQuestionsMock,
                createQuestion: createQuestionMock,
                getQuestion: vi.fn(),
                updateQuestion: vi.fn(),
                publishQuestion: publishQuestionMock,
                archiveQuestion: archiveQuestionMock,
            },
        },
    };
});

describe("TestBankPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listCategoriesMock.mockResolvedValue({
            items: [
                { category_id: "cat-1", name: "销售技巧", description: "desc", parent_id: null, order_index: 0 },
            ],
            total: 1,
        });
        listQuestionsMock.mockResolvedValue({
            items: [
                {
                    question_id: "q-1",
                    title: "如何应对客户异议",
                    stem: "stem",
                    reference_answer: null,
                    category_id: "cat-1",
                    difficulty: "medium",
                    status: "draft",
                    tags: ["异议处理"],
                    scoring_dimensions: ["逻辑性"],
                    scoring_criteria: {},
                    safety_flagged: false,
                    department: null,
                    version: 1,
                    content_hash: null,
                    published_at: null,
                    category_name: "销售技巧",
                },
            ],
            total: 1,
        });
    });

    it("loads and displays categories on mount", async () => {
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });
        const items = screen.getAllByText("销售技巧");
        expect(items.length).toBeGreaterThan(0);
    });

    it("loads and displays questions on mount", async () => {
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listQuestionsMock).toHaveBeenCalled();
        });
        expect(screen.getByText("如何应对客户异议")).toBeTruthy();
    });

    it("creates a category via form", async () => {
        createCategoryMock.mockResolvedValue({
            category_id: "cat-new",
            name: "新产品",
            description: null,
            parent_id: null,
            order_index: 1,
        });
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const input = screen.getByPlaceholderText("分类名称");
        fireEvent.change(input, { target: { value: "新产品" } });
        fireEvent.click(screen.getByRole("button", { name: /新建分类/ }));

        await waitFor(() => {
            expect(createCategoryMock).toHaveBeenCalledWith(
                expect.objectContaining({ name: "新产品" }),
            );
        });
    });

    it("shows delete error for protected category", async () => {
        deleteCategoryMock.mockRejectedValue(new Error("CATEGORY_HAS_CHILDREN"));
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const deleteButtons = screen.getAllByRole("button", { name: "delete" });
        fireEvent.click(deleteButtons[0]);

        await waitFor(() => {
            expect(screen.getByRole("dialog")).toBeTruthy();
        });

        fireEvent.click(screen.getByRole("button", { name: /删除/ }));

        await waitFor(() => {
            expect(screen.getByText(/CATEGORY_HAS_CHILDREN/)).toBeTruthy();
        });
    });

    it("filters questions by category and difficulty", async () => {
        render(<TestBankPage />);
        await screen.findByText("如何应对客户异议");

        const categorySelect = screen.getByRole("combobox", { name: /分类/ });
        fireEvent.change(categorySelect, { target: { value: "cat-1" } });

        await waitFor(() => {
            expect(listQuestionsMock).toHaveBeenCalledWith(
                expect.objectContaining({ category_id: "cat-1" }),
            );
        });
    });

    it("publishes a question", async () => {
        publishQuestionMock.mockResolvedValue({
            question_id: "q-1",
            title: "如何应对客户异议",
            status: "published",
        });
        render(<TestBankPage />);
        await screen.findByText("如何应对客户异议");

        fireEvent.click(screen.getByRole("button", { name: /发布/ }));

        await waitFor(() => {
            expect(publishQuestionMock).toHaveBeenCalledWith("q-1");
        });
    });

    it("archives a question", async () => {
        archiveQuestionMock.mockResolvedValue({
            question_id: "q-1",
            title: "如何应对客户异议",
            status: "archived",
        });
        render(<TestBankPage />);
        await screen.findByText("如何应对客户异议");

        fireEvent.click(screen.getByRole("button", { name: /归档/ }));

        await waitFor(() => {
            expect(archiveQuestionMock).toHaveBeenCalledWith("q-1");
        });
    });

    it("shows publish gate error", async () => {
        publishQuestionMock.mockRejectedValue(
            new Error("[QUESTION_ITEM_PUBLISH_GATE_FAILED]: 缺少参考答案"),
        );
        render(<TestBankPage />);
        await screen.findByText("如何应对客户异议");

        fireEvent.click(screen.getByRole("button", { name: /发布/ }));

        await waitFor(() => {
            expect(screen.getByText(/缺少参考答案/)).toBeTruthy();
        });
    });
});
