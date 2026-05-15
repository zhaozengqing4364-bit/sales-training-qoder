import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TestBankPage from "./page";

const {
    listCategoriesMock,
    importQuestionsMock,
    getImportJobMock,
} = vi.hoisted(() => ({
    listCategoriesMock: vi.fn(),
    importQuestionsMock: vi.fn(),
    getImportJobMock: vi.fn(),
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
    ConfirmDialog: () => null,
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
    X: () => <span>x</span>,
    Upload: () => <span>upload</span>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            testBank: {
                listCategories: listCategoriesMock,
                createCategory: vi.fn(),
                updateCategory: vi.fn(),
                deleteCategory: vi.fn(),
                listQuestions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
                createQuestion: vi.fn(),
                getQuestion: vi.fn(),
                updateQuestion: vi.fn(),
                publishQuestion: vi.fn(),
                archiveQuestion: vi.fn(),
                importQuestions: importQuestionsMock,
                getImportJob: getImportJobMock,
            },
        },
    };
});

describe("TestBankPage import section", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listCategoriesMock.mockResolvedValue({
            items: [{ category_id: "cat-1", name: "销售技巧", description: "desc", parent_id: null, order_index: 0 }],
            total: 1,
        });
    });

    function createFile(name: string, content: string, type = "text/csv"): File {
        return new File([content], name, { type });
    }

    it("displays imported count and failed count after successful upload", async () => {
        importQuestionsMock.mockResolvedValue({
            task_id: "import-abc",
            status: "completed",
            result: {
                imported: 5,
                failed: 2,
                errors: [
                    { row: 3, field: "title", message: "标题不能为空" },
                    { row: 7, field: "difficulty", message: "无效的难度值" },
                ],
            },
        });

        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const fileInput = screen.getByTestId("import-file-input");
        const file = createFile("test.csv", "title,stem,category_id\ntest,stem,cat-1", "text/csv");

        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(importQuestionsMock).toHaveBeenCalled();
        });

        await waitFor(() => {
            expect(screen.getByText("导入完成")).toBeTruthy();
        });

        expect(screen.getByText("5")).toBeTruthy();
        expect(screen.getByText("2")).toBeTruthy();
    });

    it("shows error table after failed rows", async () => {
        importQuestionsMock.mockResolvedValue({
            task_id: "import-abc",
            status: "completed",
            result: {
                imported: 3,
                failed: 2,
                errors: [
                    { row: 2, field: "title", message: "标题不能为空" },
                    { row: 4, field: "stem", message: "题干不能为空" },
                ],
            },
        });

        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const fileInput = screen.getByTestId("import-file-input");
        const file = createFile("test.csv", "title,stem\ntest,stem", "text/csv");

        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText("标题不能为空")).toBeTruthy();
        });

        const rowCells = screen.getAllByText("2");
        expect(rowCells.length).toBeGreaterThanOrEqual(1);

        const row4 = screen.getByText("4");
        expect(row4).toBeTruthy();
        expect(screen.getByText("title")).toBeTruthy();
        expect(screen.getByText("stem")).toBeTruthy();
        expect(screen.getByText("题干不能为空")).toBeTruthy();
    });

    it("rejects invalid file extension", async () => {
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const fileInput = screen.getByTestId("import-file-input");
        const file = createFile("test.pdf", "content", "application/pdf");

        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/仅支持.*csv.*jsonl/)).toBeTruthy();
        });

        expect(importQuestionsMock).not.toHaveBeenCalled();
    });

    it("rejects oversize file (>10MB)", async () => {
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const fileInput = screen.getByTestId("import-file-input");

        // Create a mock File with >10MB size
        const largeContent = "x".repeat(1024); // 1KB
        const largeFile = new File([largeContent], "large.csv", { type: "text/csv" });
        // Override size to simulate >10MB
        Object.defineProperty(largeFile, "size", { value: 11 * 1024 * 1024 });

        fireEvent.change(fileInput, { target: { files: [largeFile] } });

        await waitFor(() => {
            expect(screen.getByText(/文件大小不能超过.*10MB/)).toBeTruthy();
        });

        expect(importQuestionsMock).not.toHaveBeenCalled();
    });

    it("rejects empty file", async () => {
        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const fileInput = screen.getByTestId("import-file-input");
        const file = createFile("empty.csv", "", "text/csv");

        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/文件为空/)).toBeTruthy();
        });

        expect(importQuestionsMock).not.toHaveBeenCalled();
    });

    it("calls importQuestions with File from input", async () => {
        importQuestionsMock.mockResolvedValue({
            task_id: "import-xyz",
            status: "completed",
            result: { imported: 1, failed: 0, errors: [] },
        });

        render(<TestBankPage />);
        await waitFor(() => {
            expect(listCategoriesMock).toHaveBeenCalled();
        });

        const fileInput = screen.getByTestId("import-file-input");
        const file = createFile("questions.jsonl", '{"title":"test"}\n', "application/jsonl");

        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(importQuestionsMock).toHaveBeenCalledWith(
                expect.objectContaining({ name: "questions.jsonl" }),
            );
        });
    });
});
