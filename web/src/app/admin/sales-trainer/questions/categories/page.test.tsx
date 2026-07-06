import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuestionCategoriesPage from "./page";

const {
    createQuestionCategoryMock,
    getCapabilitiesMock,
    listQuestionCategoriesMock,
    toastErrorMock,
} = vi.hoisted(() => ({
    createQuestionCategoryMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
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
                    getCapabilities: getCapabilitiesMock,
                    listQuestionCategories: listQuestionCategoriesMock,
                    createQuestionCategory: createQuestionCategoryMock,
                },
            },
        },
    };
});

function capabilities(overrides: Record<string, boolean> = {}) {
    const values = {
        admin_full_access: false,
        manage_content: false,
        manage_questions: true,
        manage_modules: false,
        manage_prompts: false,
        view_records: false,
        view_global_records: false,
        retry_jobs: false,
        regrade_history: false,
        view_logs: false,
        view_settings: false,
        ...overrides,
    };
    return {
        role: "content_admin",
        role_label: "内容管理员",
        capabilities: values,
        capability_keys: Object.entries(values)
            .filter(([, enabled]) => enabled)
            .map(([key]) => key),
    };
}

describe("SalesTrainerQuestionCategoriesPage", () => {
    beforeEach(() => {
        createQuestionCategoryMock.mockReset();
        getCapabilitiesMock.mockReset();
        listQuestionCategoriesMock.mockReset();
        toastErrorMock.mockReset();
        getCapabilitiesMock.mockResolvedValue(capabilities());
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
        createQuestionCategoryMock.mockResolvedValue({
            category_id: "category-2",
            parent_id: null,
            name: "新分类",
            description: null,
            usage_scope: "sales_trainer",
            order_index: 2,
            created_at: "2026-06-02T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
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

    it("fails closed before loading categories without question management permission", async () => {
        getCapabilitiesMock.mockResolvedValue(capabilities({ manage_questions: false }));

        render(<SalesTrainerQuestionCategoriesPage />);

        expect(await screen.findByText("题目分类权限不足")).toBeTruthy();
        expect(listQuestionCategoriesMock).not.toHaveBeenCalled();
        expect(screen.queryByText("新建分类")).toBeNull();
        expect(screen.queryByText("正在加载分类...")).toBeNull();
    });

    it("keeps category load failures visible instead of rendering an empty list or create form", async () => {
        listQuestionCategoriesMock.mockRejectedValue(new Error("category forbidden"));

        render(<SalesTrainerQuestionCategoriesPage />);

        expect(await screen.findByText("分类加载失败")).toBeTruthy();
        expect(screen.getByText("category forbidden")).toBeTruthy();
        expect(screen.queryByText("暂无分类")).toBeNull();
        expect(screen.queryByText("新建分类")).toBeNull();
        expect(toastErrorMock).toHaveBeenCalledWith("category forbidden");
    });

    it("does not submit category creation when permission is denied", async () => {
        getCapabilitiesMock.mockResolvedValue(capabilities({ manage_questions: false }));

        render(<SalesTrainerQuestionCategoriesPage />);

        expect(await screen.findByText("题目分类权限不足")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "重新校验权限" }));

        await waitFor(() => {
            expect(getCapabilitiesMock).toHaveBeenCalledTimes(2);
        });
        expect(createQuestionCategoryMock).not.toHaveBeenCalled();
    });
});
