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

    it("submits customer FAQ unit short answers through the typed facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    topic_key: "customer_faq",
                    learning_unit_key: "company_value",
                    learning_unit_title: "公司与核心价值",
                    total_score: 86,
                    max_score: 100,
                    passed: true,
                    pass_threshold: 80,
                    answers: [{
                        card_key: "customer_faq_q001",
                        question: "石犀科技公司是做什么的？",
                        answer_text: "石犀是做数据流动治理的平台。",
                        score: 86,
                        max_score: 100,
                        passed: true,
                        feedback: "回答覆盖核心口径。",
                        reason: "covered_core_answer",
                        scoring_source: "ai_llm",
                        scoring_provider: "fake",
                        scoring_model: "unit-test",
                        scoring_latency_ms: 12,
                    }],
                },
            }),
        });

        const result = await api.newcomerTraining.submitCustomerFaqShortAnswerAttempt(
            "company_value",
            {
                answers: [{
                    card_key: "customer_faq_q001",
                    answer_text: "石犀是做数据流动治理的平台。",
                }],
            },
        );

        expect(result.total_score).toBe(86);
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/newcomer-training/customer-faq/learning-units/company_value/short-answer-attempts"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    answers: [{
                        card_key: "customer_faq_q001",
                        answer_text: "石犀是做数据流动治理的平台。",
                    }],
                }),
            }),
        );
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

    it("previews business etiquette releases through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    summary: { changed_chapters: 2 },
                },
            }),
        });

        await api.admin.newcomerTraining.getBusinessEtiquetteReleaseImpact({
            training_pack_key: "business_etiquette_v1",
            target_revision_id: "revision-2",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining(
                "/admin/newcomer-training/business-etiquette/release-impact?training_pack_key=business_etiquette_v1&target_revision_id=revision-2",
            ),
            expect.any(Object),
        );
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

    it("loads learning content binding impact through the admin newcomer facade", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    learning_content_id: "article-1",
                    active_bindings: [{
                        source: "active_revision",
                        path_key: "newcomer_training_path_v1",
                        module_key: "business_skills",
                        module_title: "商务技巧",
                        revision_id: "path-revision-1",
                        revision_no: 1,
                        learner_effective: true,
                        learning_units: [{
                            unit_key: "trust-base",
                            title: "职业信任底座",
                            source_chapter_orders: [0],
                            ai_coach_remediation_chapter_orders: [1],
                            capability_keys: ["first_impression"],
                            require_quiz: true,
                            require_ai_coach: true,
                        }],
                        impacted_chapter_orders: [0, 1],
                    }],
                    working_bindings: [],
                    has_active_binding: true,
                    has_working_binding: false,
                    is_bound_to_business_skills: true,
                    can_archive: false,
                    archive_block_reason: "该文章正在被已发布或待发布新人训练路径引用。",
                    management_entries: {
                        article_binding: "/admin/sales-trainer/learning-topics",
                        path_config: "/admin/sales-trainer/paths",
                        question_drafts: "/admin/sales-trainer/questions/drafts",
                    },
                },
            }),
        });

        const result = await api.admin.newcomerTraining.getLearningContentBindingImpact("article-1");

        expect(result.can_archive).toBe(false);
        expect(result.active_bindings[0]?.learning_units[0]?.title).toBe("职业信任底座");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/newcomer-training/learning-contents/article-1/binding-impact"),
            expect.any(Object),
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
