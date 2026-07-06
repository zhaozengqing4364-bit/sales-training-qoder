import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NewSalesTrainerQuestionPage from "./page";

const {
    createQuestionMock,
    getCapabilitiesMock,
    listQuestionCategoriesMock,
    routerPushMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    createQuestionMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
    listQuestionCategoriesMock: vi.fn(),
    routerPushMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/questions/new",
    useRouter: () => ({ push: routerPushMock }),
}));

vi.mock("@/components/admin/sales-trainer/question-form", () => ({
    SalesTrainerQuestionForm: ({ categories }: { categories: unknown[] }) => (
        <div data-testid="question-form">题目表单：{categories.length}</div>
    ),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: toastSuccessMock,
        error: toastErrorMock,
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
                    createQuestion: createQuestionMock,
                    getCapabilities: getCapabilitiesMock,
                    listQuestionCategories: listQuestionCategoriesMock,
                },
            },
        },
    };
});

describe("NewSalesTrainerQuestionPage", () => {
    beforeEach(() => {
        createQuestionMock.mockReset();
        getCapabilitiesMock.mockReset();
        listQuestionCategoriesMock.mockReset();
        routerPushMock.mockReset();
        toastErrorMock.mockReset();
        toastSuccessMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "training_manager",
            role_label: "培训负责人",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: true,
                view_records: true,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });
        listQuestionCategoriesMock.mockResolvedValue({
            items: [{ category_id: "category-1", name: "销售基础" }],
        });
    });

    it("fails closed before loading categories without question management permission", async () => {
        getCapabilitiesMock.mockResolvedValue({
            role: "viewer",
            role_label: "只读成员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<NewSalesTrainerQuestionPage />);

        expect(await screen.findByText("题库管理权限不足")).toBeTruthy();
        expect(listQuestionCategoriesMock).not.toHaveBeenCalled();
        expect(createQuestionMock).not.toHaveBeenCalled();
        expect(screen.queryByTestId("question-form")).toBeNull();
    });

    it("renders the create form after categories are loaded", async () => {
        render(<NewSalesTrainerQuestionPage />);

        expect((await screen.findByTestId("question-form")).textContent).toContain("题目表单：1");
        expect(listQuestionCategoriesMock).toHaveBeenCalledTimes(1);
    });

    it("blocks the create form when categories fail to load and recovers on retry", async () => {
        listQuestionCategoriesMock
            .mockRejectedValueOnce(new Error("categories forbidden"))
            .mockResolvedValueOnce({
                items: [{ category_id: "category-2", name: "商务礼仪" }],
            });

        render(<NewSalesTrainerQuestionPage />);

        expect(await screen.findByText("分类加载失败")).toBeTruthy();
        expect(screen.getByText("categories forbidden")).toBeTruthy();
        expect(screen.queryByTestId("question-form")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载分类" }));

        expect((await screen.findByTestId("question-form")).textContent).toContain("题目表单：1");
        expect(screen.queryByText("分类加载失败")).toBeNull();
        await waitFor(() => {
            expect(listQuestionCategoriesMock).toHaveBeenCalledTimes(2);
        });
    });
});
