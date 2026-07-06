import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import NewSalesTrainerUnitPage from "./page";

const {
    createUnitMock,
    getAdminCapabilitiesMock,
    listMaterialsMock,
    listQuestionsMock,
    listScorePromptsMock,
    routerPushMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    createUnitMock: vi.fn(),
    getAdminCapabilitiesMock: vi.fn(),
    listMaterialsMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    listScorePromptsMock: vi.fn(),
    routerPushMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/units/new",
    useRouter: () => ({ push: routerPushMock }),
    useSearchParams: () => new URLSearchParams("module=ppt_explanation"),
}));

vi.mock("@/components/admin/sales-trainer/unit-form", () => ({
    SalesTrainerUnitForm: ({
        availableMaterials,
        availablePrompts,
        availableQuestions,
    }: {
        availableMaterials: unknown[];
        availablePrompts: unknown[];
        availableQuestions: unknown[];
    }) => (
        <div data-testid="unit-form">
            单元表单：{availableQuestions.length}/{availablePrompts.length}/{availableMaterials.length}
        </div>
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
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    createUnit: createUnitMock,
                },
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getAdminCapabilitiesMock,
                    listMaterials: listMaterialsMock,
                    listQuestions: listQuestionsMock,
                    listScorePrompts: listScorePromptsMock,
                },
            },
        },
    };
});

describe("NewSalesTrainerUnitPage", () => {
    beforeEach(() => {
        createUnitMock.mockReset();
        getAdminCapabilitiesMock.mockReset();
        listMaterialsMock.mockReset();
        listQuestionsMock.mockReset();
        listScorePromptsMock.mockReset();
        routerPushMock.mockReset();
        toastErrorMock.mockReset();
        toastSuccessMock.mockReset();
        getAdminCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: true,
                manage_prompts: false,
                manage_questions: false,
                view_records: false,
                view_settings: false,
                view_logs: false,
            },
        });
        listQuestionsMock.mockResolvedValue({ items: [{ question_id: "question-1" }] });
        listScorePromptsMock.mockResolvedValue({ items: [{ prompt_id: "prompt-1" }] });
        listMaterialsMock.mockResolvedValue({ items: [{ material_id: "material-1" }] });
    });

    it("fails closed before loading create dependencies without module management permission", async () => {
        getAdminCapabilitiesMock.mockResolvedValue({
            role: "viewer",
            role_label: "只读成员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<NewSalesTrainerUnitPage />);

        expect(await screen.findByText("模块单元权限不足")).toBeTruthy();
        expect(listQuestionsMock).not.toHaveBeenCalled();
        expect(listScorePromptsMock).not.toHaveBeenCalled();
        expect(listMaterialsMock).not.toHaveBeenCalled();
        expect(createUnitMock).not.toHaveBeenCalled();
        expect(screen.queryByTestId("unit-form")).toBeNull();
    });

    it("renders the create form after all dependencies are loaded", async () => {
        render(<NewSalesTrainerUnitPage />);

        expect((await screen.findByTestId("unit-form")).textContent).toContain("单元表单：1/1/1");
        expect(listQuestionsMock).toHaveBeenCalledWith({
            status: "published",
            tag: NEWCOMER_QUESTION_TAG,
        });
        expect(listScorePromptsMock).toHaveBeenCalledWith({ include_archived: false });
        expect(listMaterialsMock).toHaveBeenCalledWith({ include_archived: false, limit: 100 });
    });

    it("blocks the create form when dependencies fail to load and recovers on retry", async () => {
        listScorePromptsMock
            .mockRejectedValueOnce(new Error("prompts forbidden"))
            .mockResolvedValueOnce({ items: [{ prompt_id: "prompt-2" }] });

        render(<NewSalesTrainerUnitPage />);

        expect(await screen.findByText("表单依赖加载失败")).toBeTruthy();
        expect(screen.getByText("prompts forbidden")).toBeTruthy();
        expect(screen.queryByTestId("unit-form")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载表单依赖" }));

        expect((await screen.findByTestId("unit-form")).textContent).toContain("单元表单：1/1/1");
        expect(screen.queryByText("表单依赖加载失败")).toBeNull();
        await waitFor(() => {
            expect(listScorePromptsMock).toHaveBeenCalledTimes(2);
        });
    });
});
