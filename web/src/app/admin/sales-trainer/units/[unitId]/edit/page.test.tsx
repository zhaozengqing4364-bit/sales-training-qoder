import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import EditSalesTrainerUnitPage from "./page";

const {
    getAdminCapabilitiesMock,
    listMaterialsMock,
    listQuestionsMock,
    listScorePromptsMock,
    listUnitsMock,
    routerRefreshMock,
    toastErrorMock,
    updateUnitMock,
} = vi.hoisted(() => ({
    getAdminCapabilitiesMock: vi.fn(),
    listMaterialsMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    listScorePromptsMock: vi.fn(),
    listUnitsMock: vi.fn(),
    routerRefreshMock: vi.fn(),
    toastErrorMock: vi.fn(),
    updateUnitMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ unitId: "unit-1" }),
    usePathname: () => "/admin/sales-trainer/units/unit-1/edit",
    useRouter: () => ({ refresh: routerRefreshMock }),
}));

vi.mock("@/components/admin/sales-trainer/unit-form", () => ({
    SalesTrainerUnitForm: ({
        availableMaterials,
        availablePrompts,
        availableQuestions,
        initialUnit,
    }: {
        availableMaterials: unknown[];
        availablePrompts: unknown[];
        availableQuestions: unknown[];
        initialUnit: { name: string } | null;
    }) => (
        <div data-testid="unit-form">
            编辑表单：{initialUnit?.name}/{availableQuestions.length}/{availablePrompts.length}/{availableMaterials.length}
        </div>
    ),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: vi.fn(),
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
                    listUnits: listUnitsMock,
                    updateUnit: updateUnitMock,
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

function grantModuleManagement() {
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
}

describe("EditSalesTrainerUnitPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        grantModuleManagement();
        listUnitsMock.mockResolvedValue({
            items: [{
                unit_id: "unit-1",
                name: "做题训练",
                description: "列表页项目",
                unit_type: "quiz",
                config: {
                    path: {
                        path_key: "newcomer_training_path_v1",
                        module_key: "business_skills",
                    },
                },
                status: "draft",
                created_by: "admin-1",
                updated_by: "admin-1",
                created_at: "2026-05-28T00:00:00Z",
                updated_at: "2026-05-28T00:00:00Z",
                questions: [],
            }],
            total: 1,
        });
        listQuestionsMock.mockResolvedValue({ items: [{ question_id: "question-1" }] });
        listScorePromptsMock.mockResolvedValue({ items: [{ prompt_id: "prompt-1" }] });
        listMaterialsMock.mockResolvedValue({ items: [{ material_id: "material-1" }] });
        updateUnitMock.mockResolvedValue({});
    });

    it("renders the edit form after all dependencies are loaded", async () => {
        render(<EditSalesTrainerUnitPage />);

        expect((await screen.findByTestId("unit-form")).textContent).toContain("编辑表单：做题训练/1/1/1");
        expect(listUnitsMock).toHaveBeenCalledWith({ include_archived: true, limit: 100 });
        expect(listQuestionsMock).toHaveBeenCalledWith({
            status: "published",
            tag: NEWCOMER_QUESTION_TAG,
        });
        expect(listScorePromptsMock).toHaveBeenCalledWith({ include_archived: true });
        expect(listMaterialsMock).toHaveBeenCalledWith({ include_archived: true, limit: 100 });
    });

    it("fails closed before loading edit dependencies without module management permission", async () => {
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

        render(<EditSalesTrainerUnitPage />);

        expect(await screen.findByText("模块单元权限不足")).toBeTruthy();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(listQuestionsMock).not.toHaveBeenCalled();
        expect(listScorePromptsMock).not.toHaveBeenCalled();
        expect(listMaterialsMock).not.toHaveBeenCalled();
        expect(updateUnitMock).not.toHaveBeenCalled();
        expect(screen.queryByTestId("unit-form")).toBeNull();
    });
});
