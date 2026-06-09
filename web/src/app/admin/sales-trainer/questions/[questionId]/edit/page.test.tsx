import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EditSalesTrainerQuestionPage from "./page";

const {
    getQuestionMock,
    listCategoriesMock,
    toastErrorMock,
    toastMock,
    toastSuccessMock,
    updateQuestionMock,
} = vi.hoisted(() => {
    const toastError = vi.fn();
    const toastSuccess = vi.fn();
    return {
        getQuestionMock: vi.fn(),
        listCategoriesMock: vi.fn(),
        toastErrorMock: toastError,
        toastMock: {
            error: toastError,
            success: toastSuccess,
        },
        toastSuccessMock: toastSuccess,
        updateQuestionMock: vi.fn(),
    };
});

vi.mock("next/navigation", () => ({
    useParams: () => ({ questionId: "question-1" }),
    usePathname: () => "/admin/sales-trainer/questions/question-1/edit",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => toastMock,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getQuestion: getQuestionMock,
                    listQuestionCategories: listCategoriesMock,
                    updateQuestion: updateQuestionMock,
                },
            },
        },
    };
});

describe("EditSalesTrainerQuestionPage", () => {
    beforeEach(() => {
        getQuestionMock.mockReset();
        listCategoriesMock.mockReset();
        toastErrorMock.mockReset();
        toastSuccessMock.mockReset();
        updateQuestionMock.mockReset();
        getQuestionMock.mockResolvedValue({
            question_id: "question-1",
            title: "商务礼仪",
            stem: "见客户前应做什么？",
            reference_answer: null,
            category_id: "category-1",
            question_type: "single_choice",
            difficulty: "medium",
            status: "published",
            tags: ["新人训练路径", "商务技巧"],
            scoring_dimensions: [],
            scoring_criteria: {},
            safety_flagged: false,
            department: null,
            usage_scope: "sales_trainer",
            version: 1,
            content_hash: null,
            published_at: "2026-06-02T00:00:00Z",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            options: [{ value: "A", label: "确认客户背景" }],
            correct_answer: "A",
            correct_answers: [],
            correct_bool: null,
            explanation: null,
            ai_scoring: null,
        });
        listCategoriesMock.mockResolvedValue({
            items: [{
                category_id: "category-1",
                parent_id: null,
                name: "商务礼仪",
                description: null,
                usage_scope: "sales_trainer",
                order_index: 1,
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            }],
            total: 1,
        });
        updateQuestionMock.mockResolvedValue({
            question_id: "question-1",
            title: "商务礼仪新修订",
        });
    });

    it("saves a published question as a future-only revision", async () => {
        render(<EditSalesTrainerQuestionPage />);

        await waitFor(() => {
            const titleInput = screen.getByLabelText("题目标题");
            expect(titleInput).toBeInstanceOf(HTMLInputElement);
            if (titleInput instanceof HTMLInputElement) {
                expect(titleInput.value).toBe("商务礼仪");
            }
        });
        expect(screen.getByText(/已发布题目也可以编辑/)).toBeTruthy();
        expect(screen.getByText(/编辑将生成题目新修订/)).toBeTruthy();
        expect(screen.queryByRole("button", { name: "复制为新草稿" })).toBeNull();

        fireEvent.change(screen.getByLabelText("题目标题"), {
            target: { value: "商务礼仪新修订" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存题目" }));

        await waitFor(() => {
            expect(updateQuestionMock).toHaveBeenCalledWith("question-1", expect.objectContaining({
                title: "商务礼仪新修订",
                stem: "见客户前应做什么？",
                question_type: "single_choice",
                correct_answer: "A",
            }));
        });
        expect(toastSuccessMock).toHaveBeenCalledWith(
            "题目修订已保存，发布后只影响后续组卷和学员作答",
        );
    });
});
