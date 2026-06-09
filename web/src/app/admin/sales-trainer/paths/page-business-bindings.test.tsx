import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    LearningContentListResponse,
    NewcomerExamPaperListResponse,
} from "@/lib/api/types";

import SalesTrainerPathsPage from "./page";
import {
    defaultMaterialsResponse,
    defaultModuleArticle,
    defaultPathConfigResponse,
    defaultPathRevisionsResponse,
    defaultScorePromptsResponse,
    defaultSettingsResponse,
    defaultUnitsResponse,
} from "./page.test-data";

const {
    getModuleArticleMock,
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
    getModuleArticleMock: vi.fn(),
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
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getModuleArticle: getModuleArticleMock,
            },
        },
    };
});

describe("SalesTrainerPathsPage business skill bindings", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listUnitsMock.mockResolvedValue(defaultUnitsResponse());
        getPathConfigMock.mockResolvedValue(defaultPathConfigResponse());
        listPathConfigRevisionsMock.mockResolvedValue(defaultPathRevisionsResponse());
        listLearningContentsMock.mockResolvedValue(learningContents());
        getModuleArticleMock.mockResolvedValue(defaultModuleArticle());
        listPapersMock.mockResolvedValue(papers());
        listMaterialsMock.mockResolvedValue(defaultMaterialsResponse());
        listScorePromptsMock.mockResolvedValue(defaultScorePromptsResponse());
        getSettingsMock.mockResolvedValue(defaultSettingsResponse());
        savePathConfigMock.mockResolvedValue(defaultPathConfigResponse());
        searchParamsMock.mockReturnValue(new URLSearchParams("module=business_skills"));
    });

    it("saves selected learning content and paper into the path working revision", async () => {
        render(<SalesTrainerPathsPage />);

        fireEvent.change(await screen.findByLabelText("学习文章（商务技巧新修订）"), {
            target: { value: "content-2" },
        });
        fireEvent.change(screen.getByLabelText("考试考卷（商务技巧新修订）"), {
            target: { value: "paper-2" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存当前配置为新修订" }));

        await waitFor(() => {
            expect(savePathConfigMock).toHaveBeenCalled();
        });
        const request = savePathConfigMock.mock.calls[0]?.[0];
        expect(request?.modules).toContainEqual(expect.objectContaining({
            module_key: "business_skills",
            learning_content_id: "content-2",
            exam_paper_id: "paper-2",
        }));
    });
});

function learningContents(): LearningContentListResponse {
    return {
        items: [
            contentItem("content-1", "见客户前商务礼仪"),
            contentItem("content-2", "客户拜访前准备"),
        ],
        total: 2,
    };
}

function contentItem(learningContentId: string, title: string): LearningContentListResponse["items"][number] {
    return {
        learning_content_id: learningContentId,
        title,
        summary: null,
        owner: "新人训练路径",
        source: "sales_trainer_business_skills",
        status: "published",
        safety_flagged: false,
        version: 1,
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
        chapters: [{
            chapter_id: `${learningContentId}-chapter-1`,
            learning_content_id: learningContentId,
            title: "第一节",
            content: "正文",
            order_index: 1,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
        }],
    };
}

function papers(): NewcomerExamPaperListResponse {
    return {
        items: [
            paperItem("paper-1", "商务技巧考卷"),
            paperItem("paper-2", "客户拜访准备考卷"),
        ],
        total: 2,
    };
}

function paperItem(paperId: string, title: string): NewcomerExamPaperListResponse["items"][number] {
    return {
        paper_id: paperId,
        paper_key: paperId,
        title,
        description: null,
        module_key: "business_skills",
        unit_id: "paper-unit",
        pass_threshold: 70,
        status: "published",
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: "2026-06-01T00:00:00Z",
        updated_at: "2026-06-01T00:00:00Z",
        questions: [],
    };
}
