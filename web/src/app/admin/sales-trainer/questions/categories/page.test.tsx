import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuestionCategoriesPage from "./page";

const {
    listQuestionCategoriesMock,
    toastErrorMock,
} = vi.hoisted(() => ({
    listQuestionCategoriesMock: vi.fn(),
    toastErrorMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/questions/categories",
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
                    listQuestionCategories: listQuestionCategoriesMock,
                    createQuestionCategory: vi.fn(),
                },
            },
        },
    };
});

describe("SalesTrainerQuestionCategoriesPage", () => {
    beforeEach(() => {
        listQuestionCategoriesMock.mockReset();
        toastErrorMock.mockReset();
        listQuestionCategoriesMock.mockResolvedValue({
            items: [{
                category_id: "category-1",
                parent_id: null,
                name: "商务礼仪",
                description: "见客户前准备",
                usage_scope: "sales_trainer",
                order_index: 1,
                created_at: "2026-06-02T00:00:00Z",
                updated_at: "2026-06-02T00:00:00Z",
            }],
            total: 1,
        });
    });

    it("describes category scope without exposing technical usage_scope names", async () => {
        render(<SalesTrainerQuestionCategoriesPage />);

        await waitFor(() => {
            expect(listQuestionCategoriesMock).toHaveBeenCalled();
        });

        expect(screen.getByRole("heading", { name: "题目分类" })).toBeTruthy();
        expect(screen.getByText("分类只是正式题目的管理维度；学员小测按已发布题目和能力点抽题，不按分类抽题。")).toBeTruthy();
        expect(screen.getByText("分类用于运营筛选、审核入库和后续维护，不是学员端的组卷规则。要检查小测会抽到哪些题，请使用“小测预览”。")).toBeTruthy();
        expect(screen.getByText("新人训练路径")).toBeTruthy();
        expect(screen.queryByText("sales_trainer")).toBeNull();
    });
});
