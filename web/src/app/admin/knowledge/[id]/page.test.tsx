import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import KnowledgeDetailPage from "./page";

const {
    backMock,
    getKnowledgeBaseMock,
    getKnowledgeBaseDocumentsMock,
    uploadDocumentMock,
    searchKnowledgeBaseMock,
    reprocessKnowledgeDocumentMock,
    successToastMock,
    errorToastMock,
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    getKnowledgeBaseMock: vi.fn(),
    getKnowledgeBaseDocumentsMock: vi.fn(),
    uploadDocumentMock: vi.fn(),
    searchKnowledgeBaseMock: vi.fn(),
    reprocessKnowledgeDocumentMock: vi.fn(),
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        back: backMock,
        push: vi.fn(),
    }),
    useParams: () => ({
        id: "kb-1",
    }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getKnowledgeBase: getKnowledgeBaseMock,
                getKnowledgeBaseDocuments: getKnowledgeBaseDocumentsMock,
                uploadDocument: uploadDocumentMock,
                searchKnowledgeBase: searchKnowledgeBaseMock,
                reprocessKnowledgeDocument: reprocessKnowledgeDocumentMock,
            },
        },
    };
});

describe("KnowledgeDetailPage", () => {
    beforeEach(() => {
        backMock.mockReset();
        getKnowledgeBaseMock.mockReset();
        getKnowledgeBaseDocumentsMock.mockReset();
        uploadDocumentMock.mockReset();
        searchKnowledgeBaseMock.mockReset();
        reprocessKnowledgeDocumentMock.mockReset();
        successToastMock.mockReset();
        errorToastMock.mockReset();

        getKnowledgeBaseMock.mockResolvedValue({
            id: "kb-1",
            name: "石犀产品资料库",
            description: "用于管理员诊断产品资料上传与检索状态。",
            category: "product",
            status: "active",
            document_count: 2,
            total_chunks: 6,
            created_at: "2026-03-23T00:00:00Z",
            updated_at: "2026-03-23T00:00:00Z",
        });

        getKnowledgeBaseDocumentsMock.mockResolvedValue([
            {
                id: "doc-ready",
                file_name: "石犀产品手册.txt",
                file_type: "txt",
                file_size: 1024,
                chunk_count: 6,
                status: "ready",
                created_at: "2026-03-23T00:00:00Z",
            },
            {
                id: "doc-failed",
                file_name: "签约案例.xlsx",
                file_type: "xlsx",
                file_size: 2048,
                chunk_count: 0,
                status: "failed",
                error_message: "Embedding failed",
                created_at: "2026-03-23T00:00:00Z",
            },
        ]);

        uploadDocumentMock.mockResolvedValue({
            id: "doc-uploaded",
            file_name: "新增资料.xlsx",
            file_type: "xlsx",
            file_size: 4096,
            chunk_count: 0,
            status: "pending",
            created_at: "2026-03-23T00:00:00Z",
        });

        searchKnowledgeBaseMock.mockResolvedValue({
            total: 1,
            results: [
                {
                    content: "标准版: ¥9,999/年",
                    score: 0.92,
                    metadata: {
                        document_id: "doc-ready",
                        document_title: "石犀产品手册.txt",
                        chunk_index: 0,
                    },
                },
            ],
        });

        reprocessKnowledgeDocumentMock.mockResolvedValue({
            message: "Document reprocessing started",
            document_id: "doc-failed",
        });
    });

    it("accepts xlsx/xls uploads and submits spreadsheet files to the admin API", async () => {
        const { container } = render(<KnowledgeDetailPage />);

        await screen.findByText("石犀产品资料库");

        const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
        expect(fileInput).toBeTruthy();
        expect(fileInput?.accept).toContain(".xlsx");
        expect(fileInput?.accept).toContain(".xls");

        const file = new File(["PK\u0003\u0004"], "新增资料.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        fireEvent.change(fileInput as HTMLInputElement, {
            target: { files: [file] },
        });

        await waitFor(() => {
            expect(uploadDocumentMock).toHaveBeenCalledTimes(1);
        });
        expect(uploadDocumentMock).toHaveBeenCalledWith("kb-1", expect.any(FormData));
    });

    it("shows an inline reprocess action for failed documents", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("签约案例.xlsx");

        const retryButton = await screen.findByRole("button", { name: /重试处理/i });
        fireEvent.click(retryButton);

        await waitFor(() => {
            expect(reprocessKnowledgeDocumentMock).toHaveBeenCalledWith("kb-1", "doc-failed");
        });
        expect(successToastMock).toHaveBeenCalled();
    });

    it("runs search diagnostics and renders matched knowledge evidence", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("石犀产品资料库");

        const queryInput = await screen.findByLabelText("知识库搜索诊断");
        fireEvent.change(queryInput, { target: { value: "产品价格" } });
        fireEvent.click(screen.getByRole("button", { name: /执行诊断/i }));

        await waitFor(() => {
            expect(searchKnowledgeBaseMock).toHaveBeenCalledWith("kb-1", "产品价格", 5, 0.7);
        });

        expect(await screen.findByText("标准版: ¥9,999/年")).toBeTruthy();
        expect(screen.getAllByText(/石犀产品手册\.txt/).length).toBeGreaterThan(0);
    });
});
