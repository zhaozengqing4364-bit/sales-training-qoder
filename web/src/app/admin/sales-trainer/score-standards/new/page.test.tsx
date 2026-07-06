import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NewSalesTrainerScoreStandardPage from "./page";

const {
    createScorePromptMock,
    getCapabilitiesMock,
    routerPushMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    createScorePromptMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
    routerPushMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/score-standards/new",
    useRouter: () => ({ push: routerPushMock }),
    useSearchParams: () => new URLSearchParams("purpose=ppt_pitch"),
}));

vi.mock("@/components/admin/sales-trainer/score-prompt-form", () => ({
    SalesTrainerScorePromptForm: ({ initialPurpose }: { initialPurpose: string | null }) => (
        <div data-testid="score-prompt-form">评分标准表单：{initialPurpose}</div>
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
                    createScorePrompt: createScorePromptMock,
                    getCapabilities: getCapabilitiesMock,
                },
            },
        },
    };
});

function grantContentManagement() {
    getCapabilitiesMock.mockResolvedValue({
        role: "content_admin",
        role_label: "内容管理员",
        capabilities: {
            admin_full_access: false,
            manage_content: true,
            manage_modules: false,
            manage_prompts: false,
            manage_questions: false,
            view_records: false,
            view_global_records: false,
            retry_jobs: false,
            regrade_history: false,
            view_settings: false,
            view_logs: false,
        },
    });
}

describe("NewSalesTrainerScoreStandardPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        grantContentManagement();
        createScorePromptMock.mockResolvedValue({ prompt_id: "prompt-1" });
    });

    it("renders the create form after content management permission is confirmed", async () => {
        render(<NewSalesTrainerScoreStandardPage />);

        expect((await screen.findByTestId("score-prompt-form")).textContent).toContain("评分标准表单：ppt_pitch");
        expect(getCapabilitiesMock).toHaveBeenCalledTimes(1);
    });

    it("fails closed before rendering the create form without content management permission", async () => {
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

        render(<NewSalesTrainerScoreStandardPage />);

        expect(await screen.findByText("评分标准管理权限不足")).toBeTruthy();
        expect(screen.queryByTestId("score-prompt-form")).toBeNull();
        expect(createScorePromptMock).not.toHaveBeenCalled();
    });
});
