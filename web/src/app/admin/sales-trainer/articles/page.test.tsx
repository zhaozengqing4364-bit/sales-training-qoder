import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    LearningContent,
    LearningContentRevisionState,
    NewcomerLearningTopicsConfigResponse,
} from "@/lib/api/types";

import LearningArticlesPage from "./page";

const {
    generateDraftMock,
    getCapabilitiesMock,
    getLearningTopicsConfigMock,
    listLearningContentsMock,
    publishLearningTopicsConfigMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    generateDraftMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
    getLearningTopicsConfigMock: vi.fn(),
    listLearningContentsMock: vi.fn(),
    publishLearningTopicsConfigMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/learning-topics",
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
            learningContents: {
                ...actual.api.learningContents,
                list: listLearningContentsMock,
            },
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    getLearningTopicsConfig: getLearningTopicsConfigMock,
                    generateBusinessEtiquetteLearningTopicDraft: generateDraftMock,
                    publishLearningTopicsConfig: publishLearningTopicsConfigMock,
                },
            },
        },
    };
});

function revisionState(overrides: Partial<LearningContentRevisionState> = {}): LearningContentRevisionState {
    return {
        active_revision_id: "content-revision-1",
        active_revision_no: 1,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
        edit_target: "working_revision",
        publish_label: "当前无待发布修订",
        save_result_copy: "已保存。",
        ...overrides,
    };
}

function learningContent(overrides: Partial<LearningContent> = {}): LearningContent {
    return {
        learning_content_id: "article-1",
        title: "见客户前商务礼仪",
        summary: "学习商务拜访前礼仪。",
        owner: "新人训练路径",
        source: "sales_trainer_business_etiquette",
        status: "published",
        safety_flagged: false,
        version: 1,
        content_hash: null,
        published_at: "2026-07-08T00:00:00Z",
        created_at: "2026-07-08T00:00:00Z",
        updated_at: "2026-07-08T00:00:00Z",
        revision_state: revisionState(),
        chapters: [],
        ...overrides,
    };
}

function learningTopicsConfig(
    overrides: Partial<NewcomerLearningTopicsConfigResponse> = {},
): NewcomerLearningTopicsConfigResponse {
    return {
        source: "active_revision",
        fallback_reason: null,
        legacy_snapshot_only: false,
        management_entry: "/admin/sales-trainer/learning-topics",
        permission: "sales_trainer.manage_modules",
        payload: {
            schema_version: "newcomer_learning_topics_v1",
            topics: [{
                topic_key: "business_etiquette",
                source_module_key: "business_skills",
                enabled: true,
                title: "商务礼仪规范",
                description: "商务场景礼仪学习。",
                order_index: 1,
                learning_content_id: "article-1",
                learning_units: [],
                ai_coach: null,
                required: false,
                blocks_next: false,
                score_display_policy: "quiz_attempt_score",
            }],
        },
        active_revision_id: "topic-revision-1",
        active_revision_no: 1,
        active_revision_snapshot: null,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
        diagnostics: [],
        ...overrides,
    };
}

function adminCapabilities(canManageContent = true) {
    return {
        role: canManageContent ? "admin" : "viewer",
        role_label: canManageContent ? "管理员" : "只读人员",
        capabilities: {
            admin_full_access: false,
            manage_content: canManageContent,
            manage_questions: false,
            manage_modules: false,
            manage_prompts: false,
            view_records: false,
            view_global_records: false,
            retry_jobs: false,
            regrade_history: false,
            view_logs: false,
            view_settings: false,
        },
        capability_keys: canManageContent ? ["manage_content"] : [],
    };
}

describe("LearningArticlesPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getCapabilitiesMock.mockResolvedValue(adminCapabilities());
        listLearningContentsMock.mockResolvedValue({
            items: [learningContent()],
            total: 1,
        });
        getLearningTopicsConfigMock.mockResolvedValue(learningTopicsConfig());
        generateDraftMock.mockResolvedValue(learningTopicsConfig());
        publishLearningTopicsConfigMock.mockResolvedValue(learningTopicsConfig());
    });

    it("shows configured learning topics and the bound article", async () => {
        render(<LearningArticlesPage />);

        expect(await screen.findByText("学习专题")).toBeTruthy();
        expect(await screen.findByText("商务礼仪规范")).toBeTruthy();
        expect(screen.getByText("当前文章：见客户前商务礼仪（已发布）")).toBeTruthy();
        expect(screen.getByRole("link", { name: /进入专题配置/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/learning-topics/business-etiquette",
        );
    });

    it("generates a draft when no learning topic is configured", async () => {
        getLearningTopicsConfigMock.mockResolvedValueOnce(
            learningTopicsConfig({
                source: "not_configured",
                fallback_reason: "active_revision_missing",
                active_revision_id: null,
                active_revision_no: null,
                payload: {
                    schema_version: "newcomer_learning_topics_v1",
                    topics: [],
                },
            }),
        );

        render(<LearningArticlesPage />);

        fireEvent.click(await screen.findByRole("button", { name: "生成商务礼仪规范草稿" }));

        await waitFor(() => {
            expect(generateDraftMock).toHaveBeenCalledWith({
                overwrite_working: false,
                reason: "生成商务礼仪规范学习专题草稿",
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("已生成商务礼仪规范草稿");
    });

    it("publishes an unpublished learning topic revision", async () => {
        getLearningTopicsConfigMock.mockResolvedValueOnce(
            learningTopicsConfig({
                working_revision_id: "topic-working-1",
                working_revision_no: 2,
                has_unpublished_revision: true,
            }),
        );

        render(<LearningArticlesPage />);

        fireEvent.click(await screen.findByRole("button", { name: "发布学习专题" }));

        await waitFor(() => {
            expect(publishLearningTopicsConfigMock).toHaveBeenCalledWith({
                reason: "发布学习专题配置",
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("学习专题已发布");
    });

    it("fails closed without content management capability", async () => {
        getCapabilitiesMock.mockResolvedValueOnce(adminCapabilities(false));

        render(<LearningArticlesPage />);

        expect(await screen.findByText("学习专题管理权限不足")).toBeTruthy();
        expect(listLearningContentsMock).not.toHaveBeenCalled();
        expect(getLearningTopicsConfigMock).not.toHaveBeenCalled();
        expect(generateDraftMock).not.toHaveBeenCalled();
        expect(publishLearningTopicsConfigMock).not.toHaveBeenCalled();
    });
});
