import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EditSalesTrainerScoreStandardPage from "./page";

const {
    getCapabilitiesMock,
    listScorePromptsMock,
    toastErrorMock,
    toastSuccessMock,
    updateScorePromptMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    listScorePromptsMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
    updateScorePromptMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "prompt-1" }),
    usePathname: () => "/admin/sales-trainer/score-standards/prompt-1/edit",
}));

vi.mock("@/components/admin/sales-trainer/score-prompt-form", () => ({
    SalesTrainerScorePromptForm: ({ initialPrompt }: { initialPrompt: { name: string } | null }) => (
        <div data-testid="score-prompt-form">评分标准表单：{initialPrompt?.name}</div>
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
                    getCapabilities: getCapabilitiesMock,
                    listScorePrompts: listScorePromptsMock,
                    updateScorePrompt: updateScorePromptMock,
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

describe("EditSalesTrainerScoreStandardPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        grantContentManagement();
        listScorePromptsMock.mockResolvedValue({
            items: [{
                prompt_id: "prompt-1",
                name: "PPT 录音评分标准",
                purpose: "ppt_pitch",
                prompt_template: "请评分",
                status: "published",
                version: 1,
                content_hash: "hash",
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            }],
            total: 1,
        });
        updateScorePromptMock.mockResolvedValue({});
    });

    it("renders the edit form after content management permission is confirmed", async () => {
        render(<EditSalesTrainerScoreStandardPage />);

        expect((await screen.findByTestId("score-prompt-form")).textContent).toContain("评分标准表单：PPT 录音评分标准");
        expect(listScorePromptsMock).toHaveBeenCalledWith({ include_archived: true });
    });

    it("fails closed before loading prompts without content management permission", async () => {
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

        render(<EditSalesTrainerScoreStandardPage />);

        expect(await screen.findByText("评分标准管理权限不足")).toBeTruthy();
        expect(listScorePromptsMock).not.toHaveBeenCalled();
        expect(updateScorePromptMock).not.toHaveBeenCalled();
        expect(screen.queryByTestId("score-prompt-form")).toBeNull();
    });
});
