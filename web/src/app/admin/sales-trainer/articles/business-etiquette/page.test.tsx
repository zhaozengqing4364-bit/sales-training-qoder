import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    LearningContent,
    LearningContentRevisionState,
    NewcomerLearningTopicsConfigResponse,
    SalesTrainerQuestion,
} from "@/lib/api/types";
import { defaultBusinessEtiquetteLearningUnits } from "@/lib/sales-trainer/business-etiquette-units";

import BusinessEtiquetteLearningTopicPage from "./page";

const {
    addChapterMock,
    createContentMock,
    createPaperMock,
    getLearningTopicsConfigMock,
    getPathConfigMock,
    listContentsMock,
    listLearningTopicsRevisionsMock,
    listPapersMock,
    listQuestionsMock,
    publishContentMock,
    publishPaperMock,
    saveLearningTopicsConfigMock,
    savePathConfigMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    addChapterMock: vi.fn(),
    createContentMock: vi.fn(),
    createPaperMock: vi.fn(),
    getLearningTopicsConfigMock: vi.fn(),
    getPathConfigMock: vi.fn(),
    listContentsMock: vi.fn(),
    listLearningTopicsRevisionsMock: vi.fn(),
    listPapersMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    publishContentMock: vi.fn(),
    publishPaperMock: vi.fn(),
    saveLearningTopicsConfigMock: vi.fn(),
    savePathConfigMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: toastErrorMock,
        success: toastSuccessMock,
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
                addChapter: addChapterMock,
                create: createContentMock,
                list: listContentsMock,
                publish: publishContentMock,
            },
            admin: {
                ...actual.api.admin,
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    createPaper: createPaperMock,
                    getLearningTopicsConfig: getLearningTopicsConfigMock,
                    getPathConfig: getPathConfigMock,
                    listLearningTopicsRevisions: listLearningTopicsRevisionsMock,
                    listPapers: listPapersMock,
                    publishPaper: publishPaperMock,
                    saveLearningTopicsConfig: saveLearningTopicsConfigMock,
                    savePathConfig: savePathConfigMock,
                    generateBusinessEtiquetteLearningTopicDraft: vi.fn(),
                    previewLearningTopicsPublish: vi.fn(),
                    publishLearningTopicsConfig: vi.fn(),
                    previewLearningTopicsRollback: vi.fn(),
                    rollbackLearningTopicsConfig: vi.fn(),
                },
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    listQuestions: listQuestionsMock,
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
        learning_content_id: "content-1",
        title: "商务礼仪规范",
        summary: "商务礼仪学习文章。",
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
        chapters: [{
            chapter_id: "chapter-1",
            learning_content_id: "content-1",
            title: "导读",
            content: "正文",
            order_index: 1,
            created_at: "2026-07-08T00:00:00Z",
            updated_at: "2026-07-08T00:00:00Z",
        }],
        ...overrides,
    };
}

function learningTopicsConfig(boundContentId: string | null): NewcomerLearningTopicsConfigResponse {
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
                learning_content_id: boundContentId,
                learning_units: defaultBusinessEtiquetteLearningUnits().slice(0, 1),
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
    };
}

function pathConfig(boundPaperId: string | null = null) {
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
                module_key: "business_skills",
                module_type: "article_exam",
                enabled: true,
                order_index: 2,
                title: "商务礼仪规范",
                description: "专题学习",
                target_unit_id: null,
                learning_content_id: "content-1",
                exam_paper_id: boundPaperId,
                disabled_reason: null,
                unlock_after_unit_ids: [],
                completion_rule: "passed",
                primary_action_label: "开始学习",
                retry_action_label: null,
                review_action_label: null,
                guidance_templates: {},
            }],
        },
        active_revision_id: "path-revision-1",
        active_revision_no: 1,
        active_revision_snapshot: null,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
        diagnostics: {},
    };
}

function question(overrides: Partial<SalesTrainerQuestion> = {}): SalesTrainerQuestion {
    return {
        question_id: "question-1",
        title: "见客户前应该准备什么？",
        question_type: "single_choice",
        difficulty: "easy",
        category_id: null,
        tags: ["newcomer_training"],
        stem: "见客户前应该准备什么？",
        options: [],
        answer: {},
        analysis: null,
        status: "published",
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: "2026-07-08T00:00:00Z",
        updated_at: "2026-07-08T00:00:00Z",
        ...overrides,
    } as SalesTrainerQuestion;
}

describe("BusinessEtiquetteLearningTopicPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listContentsMock.mockResolvedValue({ items: [learningContent()], total: 1 });
        getLearningTopicsConfigMock.mockResolvedValue(learningTopicsConfig("content-1"));
        getPathConfigMock.mockResolvedValue(pathConfig());
        listPapersMock.mockResolvedValue({ items: [], total: 0 });
        listQuestionsMock.mockResolvedValue({ items: [question()], total: 1 });
        listLearningTopicsRevisionsMock.mockResolvedValue({ items: [], total: 0 });
        createContentMock.mockResolvedValue(learningContent({ learning_content_id: "content-new", status: "draft" }));
        addChapterMock.mockResolvedValue([]);
        publishContentMock.mockResolvedValue(learningContent({ learning_content_id: "content-new" }));
        saveLearningTopicsConfigMock.mockResolvedValue(learningTopicsConfig("content-new"));
        createPaperMock.mockResolvedValue({ paper_id: "paper-new" });
        publishPaperMock.mockResolvedValue({ paper_id: "paper-new" });
        savePathConfigMock.mockResolvedValue(pathConfig("paper-new"));
    });

    it("keeps topic resources together on the topic detail page", async () => {
        render(<BusinessEtiquetteLearningTopicPage />);

        expect(await screen.findByText("文章与章节")).toBeTruthy();
        expect(screen.getByText("小测/考卷")).toBeTruthy();
        expect(screen.getByText("AI 教练与得分展示")).toBeTruthy();
        expect(screen.getByRole("link", { name: "高级管理考卷" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/learning-topics/papers",
        );
        expect(screen.getByText("不阻塞后续关卡")).toBeTruthy();
    });

    it("creates an article with its first chapter and binds the published content in place", async () => {
        getLearningTopicsConfigMock.mockResolvedValue(learningTopicsConfig(null));
        listContentsMock.mockResolvedValue({ items: [], total: 0 });
        render(<BusinessEtiquetteLearningTopicPage />);

        fireEvent.change(await screen.findByLabelText("学习文章标题"), {
            target: { value: "商务礼仪规范" },
        });
        fireEvent.change(screen.getByLabelText("首章节标题"), {
            target: { value: "拜访前准备" },
        });
        fireEvent.change(screen.getByLabelText("首章节正文"), {
            target: { value: "确认客户背景、会议目标和沟通材料。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建、发布并绑定" }));

        await waitFor(() => {
            expect(createContentMock).toHaveBeenCalledWith(expect.objectContaining({
                title: "商务礼仪规范",
            }));
        });
        expect(addChapterMock).toHaveBeenCalledWith("content-new", {
            title: "拜访前准备",
            content: "确认客户背景、会议目标和沟通材料。",
        });
        expect(publishContentMock).toHaveBeenCalledWith("content-new");
        expect(saveLearningTopicsConfigMock).toHaveBeenCalledWith(expect.objectContaining({
            reason: "更新商务礼仪规范学习文章绑定",
        }));
    });

    it("creates and publishes a quiz paper from selected questions inside the topic", async () => {
        render(<BusinessEtiquetteLearningTopicPage />);

        fireEvent.click(await screen.findByLabelText(/见客户前应该准备什么/));
        fireEvent.click(screen.getByRole("button", { name: "创建并发布小测" }));

        await waitFor(() => {
            expect(createPaperMock).toHaveBeenCalledWith(expect.objectContaining({
                module_key: "business_skills",
                questions: [{ question_id: "question-1", order_index: 1, points: 10 }],
            }));
        });
        expect(publishPaperMock).toHaveBeenCalledWith("paper-new");
        expect(savePathConfigMock).toHaveBeenCalledWith(expect.objectContaining({
            reason: "更新商务礼仪规范小测绑定",
        }));
        expect(toastSuccessMock).toHaveBeenCalledWith("小测/考卷已创建、发布并保存为当前专题待发布配置");
    });
});
