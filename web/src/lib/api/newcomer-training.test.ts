import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("api.newcomerTraining facade", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("loads module article through the newcomer path facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    module_key: "business_skills",
                    learning_content_id: "article-1",
                    title: "见客户前商务礼仪",
                    summary: "阅读文章后进入考卷。",
                    owner: "新人训练路径",
                    source: "admin_learning_content",
                    chapters: [],
                },
            }),
        });

        const result = await api.newcomerTraining.getModuleArticle("business_skills");

        expect(result.title).toBe("见客户前商务礼仪");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/newcomer-training/modules/business_skills/article"),
            expect.any(Object),
        );
    });

    it("loads and submits newcomer papers through the typed facade", async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    paper_id: "paper-1",
                    paper_key: "business-paper",
                    title: "商务礼仪入门考卷",
                    description: null,
                    module_key: "business_skills",
                    unit_id: "unit-1",
                    pass_threshold: 10,
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    questions: [],
                },
            }),
        }).mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    attempt_id: "attempt-1",
                    paper_id: "paper-1",
                    paper_title: "商务礼仪入门考卷",
                    paper_revision_id: "paper-revision-1",
                    unit_id: "unit-1",
                    user_id: "user-1",
                    total_score: 10,
                    max_score: 10,
                    passed: true,
                    status: "scored",
                    submitted_at: "2026-06-02T00:00:00Z",
                    answers: [],
                },
            }),
        });

        await api.newcomerTraining.getPaper("paper-1");
        await api.newcomerTraining.submitPaperAttempt({
            paper_id: "paper-1",
            answers: [{ question_id: "question-1", answer_payload: "A" }],
        });

        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/newcomer-training/papers/paper-1"),
            expect.any(Object),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/newcomer-training/paper-attempts"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    paper_id: "paper-1",
                    answers: [{ question_id: "question-1", answer_payload: "A" }],
                }),
            }),
        );
    });

    it("exposes paper revision id on submitted paper attempts", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    attempt_id: "attempt-1",
                    paper_id: "paper-1",
                    paper_title: "商务礼仪入门考卷",
                    paper_revision_id: "paper-revision-1",
                    unit_id: "unit-1",
                    user_id: "user-1",
                    total_score: 10,
                    max_score: 10,
                    passed: true,
                    status: "scored",
                    submitted_at: "2026-06-02T00:00:00Z",
                    answers: [],
                },
            }),
        });

        const result = await api.newcomerTraining.submitPaperAttempt({
            paper_id: "paper-1",
            answers: [{ question_id: "question-1", answer_payload: "A" }],
        });

        expect(result.paper_revision_id).toBe("paper-revision-1");
    });
});

describe("api.admin.newcomerTraining facade", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("binds module article through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    module_key: "business_skills",
                    learning_content_id: "article-1",
                    path_key: "newcomer_training_path_v1",
                    active_revision_id: "path-revision-1",
                    active_revision_no: 1,
                    working_revision_id: "path-revision-2",
                    working_revision_no: 2,
                    has_unpublished_revision: true,
                    impact_scope: "future_learners_only",
                },
            }),
        });

        const result = await api.admin.newcomerTraining.bindModuleArticle("business_skills", {
            learning_content_id: "article-1",
            path_key: "newcomer_training_path_v1",
            reason: "更新商务技巧学习文章绑定",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/newcomer-training/modules/business_skills/article-binding"),
            expect.objectContaining({
                method: "PUT",
                body: JSON.stringify({
                    learning_content_id: "article-1",
                    path_key: "newcomer_training_path_v1",
                    reason: "更新商务技巧学习文章绑定",
                }),
            }),
        );
        expect(result.working_revision_id).toBe("path-revision-2");
        expect(result.impact_scope).toBe("future_learners_only");
    });

    it("creates and publishes papers through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    paper_id: "paper-1",
                    paper_key: "business-paper",
                    title: "商务礼仪入门考卷",
                    description: null,
                    module_key: "business_skills",
                    unit_id: "unit-1",
                    pass_threshold: 10,
                    status: "draft",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    questions: [],
                },
            }),
        });

        await api.admin.newcomerTraining.createPaper({
            paper_key: "business-paper",
            title: "商务礼仪入门考卷",
            questions: [{ question_id: "question-1", order_index: 1, points: 10 }],
        });
        await api.admin.newcomerTraining.publishPaper("paper-1");

        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/admin/newcomer-training/papers"),
            expect.objectContaining({ method: "POST" }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/admin/newcomer-training/papers/paper-1/publish"),
            expect.objectContaining({ method: "POST" }),
        );
    });

    it("rolls back papers through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    paper_id: "paper-1",
                    paper_key: "business-paper",
                    title: "商务礼仪入门考卷",
                    description: null,
                    module_key: "business_skills",
                    unit_id: "unit-1",
                    pass_threshold: 10,
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    questions: [],
                },
            }),
        });

        await api.admin.newcomerTraining.rollbackPaper("paper-1", {
            target_revision_id: "paper-revision-1",
            reason: "恢复第一版",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/newcomer-training/papers/paper-1/rollback"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    target_revision_id: "paper-revision-1",
                    reason: "恢复第一版",
                }),
            }),
        );
    });

    it("loads paper revision history through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [{
                        revision_id: "paper-revision-2",
                        revision_no: 2,
                        status: "working",
                        change_class: "scoring_high_risk",
                        title: "商务技巧待发布版",
                        question_count: 3,
                        is_active: false,
                        is_working: true,
                        source_revision_id: "paper-revision-1",
                        payload_hash: "hash-2",
                        reason: "save edited exam paper revision",
                        trace_id: null,
                        created_by: "admin-1",
                        published_by: null,
                        created_at: "2026-06-03T00:00:00Z",
                        published_at: null,
                    }],
                    total: 1,
                },
            }),
        });

        const result = await api.admin.newcomerTraining.listPaperRevisions("paper-1");

        expect(result.items[0]?.revision_no).toBe(2);
        expect(result.items[0]?.is_working).toBe(true);
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/newcomer-training/papers/paper-1/revisions"),
            expect.objectContaining({ method: "GET" }),
        );
    });

    it("manages newcomer path config revisions through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    source: "active_revision",
                    path: {
                        path_key: "newcomer_training_path_v1",
                        title: "新人训练路径",
                        goal_title: "完成新人训练",
                        description: null,
                        enabled: true,
                        modules: [],
                    },
                    active_revision_id: "path-revision-1",
                    active_revision_no: 1,
                    working_revision_id: null,
                    working_revision_no: null,
                    has_unpublished_revision: false,
                },
            }),
        });

        await api.admin.newcomerTraining.getPathConfig();
        await api.admin.newcomerTraining.savePathConfig({
            path_key: "newcomer_training_path_v1",
            title: "新人训练路径",
            goal_title: "完成新人训练",
            description: null,
            enabled: true,
            modules: [],
            reason: "保存路径配置修订",
        });
        await api.admin.newcomerTraining.publishPathConfig({ reason: "发布路径配置" });
        await api.admin.newcomerTraining.listPathConfigRevisions();
        await api.admin.newcomerTraining.rollbackPathConfig({
            revision_id: "path-revision-1",
            reason: "回滚路径配置",
        });

        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/admin/newcomer-training/path-config"),
            expect.any(Object),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/admin/newcomer-training/path-config"),
            expect.objectContaining({
                method: "PUT",
                body: JSON.stringify({
                    path_key: "newcomer_training_path_v1",
                    title: "新人训练路径",
                    goal_title: "完成新人训练",
                    description: null,
                    enabled: true,
                    modules: [],
                    reason: "保存路径配置修订",
                }),
            }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            3,
            expect.stringContaining("/admin/newcomer-training/path-config/publish"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({ reason: "发布路径配置" }),
            }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            4,
            expect.stringContaining("/admin/newcomer-training/path-config/revisions"),
            expect.objectContaining({ method: "GET" }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            5,
            expect.stringContaining("/admin/newcomer-training/path-config/rollback"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    revision_id: "path-revision-1",
                    reason: "回滚路径配置",
                }),
            }),
        );
    });
});
