import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EditSalesTrainerScoreStandardPage from "./page";

const {
    getCapabilitiesMock,
    listScorePromptsMock,
    publishScorePromptMock,
    toastApiMock,
    toastSuccessMock,
    updateScorePromptMock,
} = vi.hoisted(() => {
    const toastError = vi.fn();
    const toastSuccess = vi.fn();
    return {
        getCapabilitiesMock: vi.fn(),
        listScorePromptsMock: vi.fn(),
        publishScorePromptMock: vi.fn(),
        toastApiMock: {
            error: toastError,
            success: toastSuccess,
        },
        toastSuccessMock: toastSuccess,
        updateScorePromptMock: vi.fn(),
    };
});

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "prompt-1" }),
    usePathname: () => "/admin/sales-trainer/score-standards/prompt-1/edit",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => toastApiMock,
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
                    publishScorePrompt: publishScorePromptMock,
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
        getCapabilitiesMock.mockReset();
        listScorePromptsMock.mockReset();
        publishScorePromptMock.mockReset();
        updateScorePromptMock.mockReset();
        grantContentManagement();
        listScorePromptsMock.mockResolvedValue({
            items: [{
                prompt_id: "prompt-1",
                name: "PPT 录音评分标准",
                purpose: "ppt_pitch",
                system_prompt: "你是严格的企业产品培训考官。",
                scoring_template: "评分：{transcript}",
                output_schema: {},
                learner_rubric: {
                    visible_to_learner: true,
                    pass_threshold: 80,
                    criteria: [],
                    common_mistakes: [],
                },
                status: "published",
                version: 1,
                created_by: null,
                updated_by: null,
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            }],
            total: 1,
        });
        updateScorePromptMock.mockResolvedValue({});
        publishScorePromptMock.mockResolvedValue({
            prompt_id: "prompt-1",
            name: "PPT 录音评分标准",
            purpose: "ppt_pitch",
            system_prompt: "严格评分",
            scoring_template: "评分：{transcript}",
            output_schema: {},
            learner_rubric: {},
            status: "published",
            version: 2,
            created_by: null,
            updated_by: null,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
        });
    });

    it("renders the edit form after content management permission is confirmed", async () => {
        render(<EditSalesTrainerScoreStandardPage />);

        expect((await screen.findByLabelText("评分标准名称") as HTMLInputElement).value).toBe("PPT 录音评分标准");
        expect(screen.getByRole("button", { name: "保存并发布" })).toBeTruthy();
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
        expect(screen.queryByRole("button", { name: "保存并发布" })).toBeNull();
    });

    it("saves the revision and publishes it before reporting success", async () => {
        render(<EditSalesTrainerScoreStandardPage />);

        const submitButton = await screen.findByRole("button", { name: "保存并发布" });
        fireEvent.submit(submitButton.closest("form") as HTMLFormElement);

        await waitFor(() => {
            expect(updateScorePromptMock).toHaveBeenCalledWith(
                "prompt-1",
                expect.objectContaining({ scoring_template: "评分：{transcript}" }),
            );
            expect(publishScorePromptMock).toHaveBeenCalledWith("prompt-1");
        });
        expect(updateScorePromptMock.mock.invocationCallOrder[0]).toBeLessThan(
            publishScorePromptMock.mock.invocationCallOrder[0],
        );
        expect(screen.getByRole("status").textContent).toContain("后续录音评分将使用本修订");
        expect(toastSuccessMock).toHaveBeenCalledWith("录音评分标准已保存并发布");
    });

    it("keeps the saved revision recoverable when publishing fails", async () => {
        publishScorePromptMock.mockRejectedValueOnce(new Error("发布服务暂不可用"));
        render(<EditSalesTrainerScoreStandardPage />);

        const submitButton = await screen.findByRole("button", { name: "保存并发布" });
        fireEvent.submit(submitButton.closest("form") as HTMLFormElement);

        const alert = await screen.findByRole("alert");
        expect(alert.textContent).toContain("修订已保存，但发布未完成");
        expect(alert.textContent).toContain("当前评分仍使用上一已发布版本");
        expect(updateScorePromptMock).toHaveBeenCalledTimes(1);
        expect(publishScorePromptMock).toHaveBeenCalledTimes(1);
    });
});
