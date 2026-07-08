import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    NewcomerPathConfigResponse,
    SalesTrainerAudioScorePromptListResponse,
    SalesTrainerMaterialListResponse,
} from "@/lib/api/types";

import SalesTrainerPathsPage from "./page";
import {
    defaultPathConfigDiagnostics,
    defaultLearningContentsResponse,
    defaultPapersResponse,
    defaultPathRevisionsResponse,
    defaultSettingsResponse,
    defaultUnitsResponse,
} from "./page.test-data";

const {
    getCapabilitiesMock,
    getPathConfigMock,
    getSettingsMock,
    listLearningContentsMock,
    listMaterialsMock,
    listPapersMock,
    listPathConfigRevisionsMock,
    listScorePromptsMock,
    listUnitsMock,
    savePathConfigMock,
    searchParamsMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    getPathConfigMock: vi.fn(),
    getSettingsMock: vi.fn(),
    listLearningContentsMock: vi.fn(),
    listMaterialsMock: vi.fn(),
    listPapersMock: vi.fn(),
    listPathConfigRevisionsMock: vi.fn(),
    listScorePromptsMock: vi.fn(),
    listUnitsMock: vi.fn(),
    savePathConfigMock: vi.fn(),
    searchParamsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/paths",
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: searchParamsMock,
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
                    getSettings: getSettingsMock,
                    listMaterials: listMaterialsMock,
                    listScorePrompts: listScorePromptsMock,
                    listUnits: listUnitsMock,
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    getPathConfig: getPathConfigMock,
                    listPathConfigRevisions: listPathConfigRevisionsMock,
                    listPapers: listPapersMock,
                    publishPathConfig: vi.fn(),
                    rollbackPathConfig: vi.fn(),
                    savePathConfig: savePathConfigMock,
                },
            },
            learningContents: {
                ...actual.api.learningContents,
                list: listLearningContentsMock,
            },
        },
    };
});

describe("SalesTrainerPathsPage audio bindings", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: true,
                manage_content: true,
                manage_questions: true,
                manage_modules: true,
                manage_prompts: true,
                view_records: true,
                view_global_records: true,
                retry_jobs: true,
                regrade_history: true,
                view_logs: true,
                view_settings: true,
                enter_realtime: true,
            },
        });
        listUnitsMock.mockResolvedValue(defaultUnitsResponse());
        getPathConfigMock.mockResolvedValue(pathConfigWithPptModule());
        listPathConfigRevisionsMock.mockResolvedValue(defaultPathRevisionsResponse());
        listLearningContentsMock.mockResolvedValue(defaultLearningContentsResponse());
        listPapersMock.mockResolvedValue(defaultPapersResponse());
        listMaterialsMock.mockResolvedValue(publishedMaterials());
        listScorePromptsMock.mockResolvedValue(publishedScorePrompts());
        getSettingsMock.mockResolvedValue(defaultSettingsResponse());
        savePathConfigMock.mockResolvedValue(pathConfigWithPptModule());
        searchParamsMock.mockReturnValue(new URLSearchParams("module=ppt_explanation"));
    });

    it("saves selected material and scoring standard into the path working revision", async () => {
        render(<SalesTrainerPathsPage />);

        expect(await screen.findByText("优先绑定已有发布资源")).toBeTruthy();
        expect(screen.getByRole("link", { name: "管理评分标准" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/audio/score-standards?module=ppt_explanation&purpose=ppt_pitch",
        );
        expect(screen.getByRole("link", { name: "管理材料库" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/audio/materials?module=ppt_explanation&purpose=ppt_pitch",
        );

        fireEvent.change(await screen.findByLabelText("主材料（PPT 讲解录音）"), {
            target: { value: "material-ppt" },
        });
        fireEvent.change(screen.getByLabelText("录音评分标准（PPT 讲解录音）"), {
            target: { value: "prompt-ppt" },
        });
        fireEvent.change(screen.getByLabelText("本次变更说明"), {
            target: { value: "更新 PPT 讲解材料和评分标准" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存当前配置为新修订" }));

        await waitFor(() => {
            expect(savePathConfigMock).toHaveBeenCalled();
        });
        const request = savePathConfigMock.mock.calls[0]?.[0];
        expect(request?.reason).toBe("更新 PPT 讲解材料和评分标准");
        expect(request?.modules).toContainEqual(expect.objectContaining({
            module_key: "ppt_explanation",
            material_id: "material-ppt",
            material_version_id: "material-version-ppt-2",
            scoring_prompt_id: "prompt-ppt",
        }));
    });
});

function pathConfigWithPptModule(): NewcomerPathConfigResponse {
    return {
        source: "active_revision",
        fallback_reason: null,
        legacy_snapshot_only: false,
        management_entry: "/admin/newcomer-training/path-config",
        permission: "sales_trainer.manage_modules",
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
                target_unit_id: "ppt-unit",
                learning_content_id: null,
                exam_paper_id: null,
                disabled_reason: null,
                unlock_after_unit_ids: [],
                completion_rule: "scored",
                primary_action_label: "上传录音",
                retry_action_label: null,
                review_action_label: null,
                guidance_templates: {},
            }],
        },
        active_revision_id: "path-revision-2",
        active_revision_no: 2,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
        diagnostics: defaultPathConfigDiagnostics(),
    };
}

function publishedMaterials(): SalesTrainerMaterialListResponse {
    return {
        items: [{
            material_id: "material-ppt",
            material_key: "ppt-material",
            name: "新人训练路径 PPT",
            material_type: "ppt_deck",
            description: null,
            purpose: "ppt_pitch",
            status: "published",
            current_version_id: "material-version-ppt-2",
            current_version: {
                version_id: "material-version-ppt-2",
                material_id: "material-ppt",
                version_label: "v2",
                title: "新人训练路径 PPT v2",
                file_name: "ppt-v2.pdf",
                content_type: "application/pdf",
                file_size_bytes: 1024,
                storage_key: "materials/ppt-v2.pdf",
                file_hash: "sha256:ppt-v2",
                release_notes: null,
                status: "published",
                published_at: "2026-06-01T00:00:00Z",
                published_by: "admin-1",
                created_by: "admin-1",
                created_at: "2026-06-01T00:00:00Z",
                updated_at: "2026-06-01T00:00:00Z",
            },
            versions: [],
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
        }],
        total: 1,
    };
}

function publishedScorePrompts(): SalesTrainerAudioScorePromptListResponse {
    return {
        items: [{
            prompt_id: "prompt-ppt",
            name: "PPT 讲解评分标准",
            purpose: "ppt_pitch",
            system_prompt: "评分",
            scoring_template: "请评分",
            output_schema: {},
            learner_rubric: {},
            version: 3,
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
        }],
        total: 1,
    };
}
