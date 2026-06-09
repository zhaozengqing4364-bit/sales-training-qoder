import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuestionsPage from "./page";

const {
    archiveQuestionMock,
    listCategoriesMock,
    listQuestionsMock,
    publishQuestionMock,
    pushMock,
    toastErrorMock,
} = vi.hoisted(() => ({
    archiveQuestionMock: vi.fn(),
    listCategoriesMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    publishQuestionMock: vi.fn(),
    pushMock: vi.fn(),
    toastErrorMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/questions",
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: toastErrorMock,
        success: vi.fn(),
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
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    archiveQuestion: archiveQuestionMock,
                    listQuestionCategories: listCategoriesMock,
                    listQuestions: listQuestionsMock,
                    publishQuestion: publishQuestionMock,
                },
            },
        },
    };
});

describe("SalesTrainerQuestionsPage", () => {
    beforeEach(() => {
        archiveQuestionMock.mockReset();
        listCategoriesMock.mockReset();
        listQuestionsMock.mockReset();
        publishQuestionMock.mockReset();
        pushMock.mockReset();
        toastErrorMock.mockReset();
        listCategoriesMock.mockResolvedValue({
            items: [
                {
                    category_id: "category-1",
                    parent_id: null,
                    name: "商务礼仪",
                    description: null,
                    usage_scope: "sales_trainer",
                    order_index: 1,
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                },
                {
                    category_id: "category-coo",
                    parent_id: null,
                    name: "COO谈市场配套题库",
                    description: null,
                    usage_scope: "sales_trainer",
                    order_index: 2,
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                },
            ],
            total: 1,
        });
        listQuestionsMock.mockResolvedValue({
            items: [{
                question_id: "question-1",
                title: "报价沟通原则",
                stem: "当客户催促报价但需求尚未澄清时，你如何回应？",
                reference_answer: "先确认客户目标和约束，再给出报价路径。",
                category_id: "category-1",
                question_type: "short_answer",
                difficulty: "medium",
                status: "published",
                tags: ["新人训练路径", "business_skills", "报价"],
                scoring_dimensions: ["business_skills"],
                scoring_criteria: {},
                safety_flagged: false,
                department: null,
                usage_scope: "sales_trainer",
                version: 1,
                content_hash: null,
                published_at: "2026-06-02T00:00:00Z",
                created_at: "2026-06-02T00:00:00Z",
                updated_at: "2026-06-02T00:00:00Z",
                options: [],
                correct_answer: null,
                correct_answers: [],
                correct_bool: null,
                explanation: null,
                ai_scoring: { enabled: true },
            }],
            total: 1,
        });
    });

    it("renders a calmer question governance workspace", async () => {
        render(<SalesTrainerQuestionsPage />);

        await waitFor(() => {
            expect(listQuestionsMock).toHaveBeenCalledWith({
                category_id: undefined,
                difficulty: undefined,
                status: undefined,
                tag: "新人训练路径",
            });
        });

        expect(await screen.findByText("题库治理面板")).toBeTruthy();
        expect(screen.getByText("新人训练路径专用题库，底层复用通用题库数据，管理员只维护本训练路径会用到的题目。")).toBeTruthy();
        expect(screen.queryByText(/sales_trainer/)).toBeNull();
        expect(screen.getAllByText("题目清单").length).toBeGreaterThan(0);
        expect(screen.getByText("筛选题目")).toBeTruthy();
        expect(screen.getByText("报价沟通原则")).toBeTruthy();
        expect(screen.getAllByText("商务礼仪").length).toBeGreaterThan(0);
        expect(screen.queryByRole("option", { name: "COO谈市场配套题库" })).toBeNull();
        expect(screen.getByText("#商务技巧")).toBeTruthy();
        expect(screen.queryByText("#business_skills")).toBeNull();
        expect(screen.getByText("简答题")).toBeTruthy();
        expect(screen.getAllByText("已发布").length).toBeGreaterThan(0);
        expect(screen.queryByText("published")).toBeNull();
        expect(screen.getByRole("button", { name: "编辑" })).toBeTruthy();
        expect(screen.queryByRole("button", { name: /复制草稿/ })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/questions/new");
    });
});
