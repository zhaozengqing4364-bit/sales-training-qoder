import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioTaskDetailPage from "./page";

const {
    createMaterialMock,
    createScorePromptMock,
    createUnitMock,
    loadMock,
    publishMaterialVersionMock,
    publishScorePromptMock,
    publishUnitMock,
    updateAudioScenarioMock,
    uploadMaterialVersionMock,
} = vi.hoisted(() => ({
    createMaterialMock: vi.fn(),
    createScorePromptMock: vi.fn(),
    createUnitMock: vi.fn(),
    loadMock: vi.fn(),
    publishMaterialVersionMock: vi.fn(),
    publishScorePromptMock: vi.fn(),
    publishUnitMock: vi.fn(),
    updateAudioScenarioMock: vi.fn(),
    uploadMaterialVersionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ scenarioSlug: "ppt-explanation" }),
    usePathname: () => "/admin/sales-trainer/audio/ppt-explanation",
    useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: vi.fn(),
        success: vi.fn(),
    }),
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => ({
        canAccess: true,
        capabilities: {
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: true,
                manage_content: true,
                manage_modules: true,
                manage_prompts: true,
                manage_questions: true,
                regrade_history: true,
                retry_jobs: true,
                view_global_records: true,
                view_logs: true,
                view_records: true,
                view_settings: true,
            },
            capability_keys: ["admin_full_access"],
        },
        denialMessage: null,
        isLoading: false,
        reloadCapabilities: vi.fn(),
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
                    publishUnit: publishUnitMock,
                },
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    createMaterial: createMaterialMock,
                    createScorePrompt: createScorePromptMock,
                    publishMaterialVersion: publishMaterialVersionMock,
                    publishScorePrompt: publishScorePromptMock,
                    uploadMaterialVersion: uploadMaterialVersionMock,
                },
            },
        },
    };
});

vi.mock("../../paths/use-path-config-center-workflow", () => ({
    usePathConfigCenterWorkflow: () => ({
        actionMessage: null,
        changeReason: "",
        data: {
            materials: [],
            pathConfig: {
                path: {
                    path_key: "newcomer_training_path_v1",
                    title: "新人训练路径",
                    goal_title: "完成新人训练",
                    description: null,
                    enabled: true,
                    modules: [{
                        module_key: "ppt_explanation",
                        module_type: "audio_scoring",
                        enabled: true,
                        order_index: 1,
                        title: "PPT 讲解录音",
                        description: "学习材料后上传录音",
                        target_unit_id: "",
                        learning_content_id: null,
                        exam_paper_id: null,
                        disabled_reason: null,
                        unlock_after_unit_ids: [],
                        completion_rule: "scored",
                        primary_action_label: "上传录音",
                        retry_action_label: null,
                        review_action_label: null,
                        guidance_templates: {},
                        material_id: "",
                        material_version_id: "",
                        scoring_prompt_id: "",
                    }],
                },
            },
            scorePrompts: [],
            units: [],
        },
        error: null,
        isLoading: false,
        isMutating: false,
        load: loadMock,
        model: {
            modules: [{
                moduleKey: "ppt_explanation",
                issues: [],
            }],
        },
        publishWorkingRevision: vi.fn(),
        saveCurrentRevision: vi.fn(),
        setChangeReason: vi.fn(),
        updateAudioScenario: updateAudioScenarioMock,
    }),
}));

describe("SalesTrainerAudioTaskDetailPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        createUnitMock.mockResolvedValue({ unit_id: "unit-new" });
        publishUnitMock.mockResolvedValue({ unit_id: "unit-new" });
        createMaterialMock.mockResolvedValue({ material_id: "material-new" });
        uploadMaterialVersionMock.mockResolvedValue({ version_id: "version-new" });
        publishMaterialVersionMock.mockResolvedValue({ version_id: "version-published" });
        createScorePromptMock.mockResolvedValue({ prompt_id: "prompt-new" });
        publishScorePromptMock.mockResolvedValue({ prompt_id: "prompt-published" });
        loadMock.mockResolvedValue(undefined);
    });

    it("creates, publishes, and binds a missing unit inside the audio task page", async () => {
        render(<SalesTrainerAudioTaskDetailPage />);

        fireEvent.click(await screen.findByRole("button", { name: "就地新建训练单元" }));
        fireEvent.click(await screen.findByRole("button", { name: "创建、发布并绑定" }));

        await waitFor(() => {
            expect(createUnitMock).toHaveBeenCalled();
        });
        expect(createUnitMock.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
            unit_type: "audio_scoring",
        }));
        expect(createUnitMock.mock.calls[0]?.[0]?.config.path.module_key).toBe("ppt_explanation");
        expect(publishUnitMock).toHaveBeenCalledWith("unit-new");
        expect(updateAudioScenarioMock).toHaveBeenCalledWith("ppt_explanation", expect.objectContaining({
            targetUnitId: "unit-new",
        }));
    });

    it("creates a material version and binds the published version without leaving the task", async () => {
        render(<SalesTrainerAudioTaskDetailPage />);

        fireEvent.click(await screen.findByRole("button", { name: "就地新建或上传材料" }));
        fireEvent.change(await screen.findByLabelText("材料文件"), {
            target: { files: [new File(["ppt"], "deck.pdf", { type: "application/pdf" })] },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建、发布并绑定" }));

        await waitFor(() => {
            expect(createMaterialMock).toHaveBeenCalledWith(expect.objectContaining({
                purpose: "ppt_pitch",
            }));
        });
        expect(uploadMaterialVersionMock).toHaveBeenCalledWith(
            "material-new",
            expect.objectContaining({ version_label: "v1" }),
        );
        expect(publishMaterialVersionMock).toHaveBeenCalledWith("version-new");
        expect(updateAudioScenarioMock).toHaveBeenCalledWith("ppt_explanation", expect.objectContaining({
            materialId: "material-new",
            materialVersionId: "version-published",
        }));
    });

    it("creates a structured score standard and binds the published prompt", async () => {
        render(<SalesTrainerAudioTaskDetailPage />);

        fireEvent.click(await screen.findByRole("button", { name: "就地新建评分标准" }));
        fireEvent.change(await screen.findByLabelText("评分标准名称"), {
            target: { value: "PPT 讲解评分" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建评分标准" }));

        await waitFor(() => {
            expect(createScorePromptMock).toHaveBeenCalledWith(expect.objectContaining({
                name: "PPT 讲解评分",
                purpose: "ppt_pitch",
            }));
        });
        expect(createScorePromptMock.mock.calls[0]?.[0]?.learner_rubric.criteria).toHaveLength(4);
        expect(publishScorePromptMock).toHaveBeenCalledWith("prompt-new");
        expect(updateAudioScenarioMock).toHaveBeenCalledWith("ppt_explanation", expect.objectContaining({
            scoringPromptId: "prompt-published",
        }));
    });
});
