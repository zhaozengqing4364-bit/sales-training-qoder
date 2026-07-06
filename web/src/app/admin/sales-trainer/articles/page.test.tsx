import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    LearningContent,
    LearningContentRevisionState,
    NewcomerPathConfigDiagnostics,
    NewcomerPathConfigResponse,
} from "@/lib/api/types";

import NewcomerArticleBindingPage from "./page";

const {
    bindModuleArticleMock,
    createLearningContentMock,
    getCapabilitiesMock,
    getModuleArticleMock,
    getPathConfigMock,
    listLearningContentsMock,
    pushMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    bindModuleArticleMock: vi.fn(),
    createLearningContentMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
    getModuleArticleMock: vi.fn(),
    getPathConfigMock: vi.fn(),
    listLearningContentsMock: vi.fn(),
    pushMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/articles",
    useRouter: () => ({ push: pushMock }),
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
                create: createLearningContentMock,
            },
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getModuleArticle: getModuleArticleMock,
            },
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    getPathConfig: getPathConfigMock,
                    bindModuleArticle: bindModuleArticleMock,
                },
            },
        },
    };
});

function makeRevisionState(overrides: Partial<LearningContentRevisionState> = {}): LearningContentRevisionState {
    return {
        active_revision_id: "revision-1",
        active_revision_no: 1,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
        edit_target: "working_revision",
        publish_label: "当前无待发布修订",
        save_result_copy: "已保存为待发布修订，发布修订后才会影响学员端。",
        ...overrides,
    };
}

function makeLearningContent(overrides: Partial<LearningContent> = {}): LearningContent {
    return {
        learning_content_id: "article-1",
        title: "见客户前商务礼仪",
        summary: "学习商务拜访前礼仪。",
        owner: "新人训练路径",
        source: "sales_trainer_business_skills",
        status: "published",
        safety_flagged: false,
        version: 1,
        content_hash: null,
        published_at: "2026-06-02T00:00:00Z",
        created_at: "2026-06-02T00:00:00Z",
        updated_at: "2026-06-02T00:00:00Z",
        revision_state: makeRevisionState(),
        chapters: [{
            chapter_id: "chapter-1",
            learning_content_id: "article-1",
            title: "第一节",
            content: "![图](https://example.com/a.png)",
            order_index: 1,
            created_at: "2026-06-02T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
        }],
        ...overrides,
    };
}

function makePathConfig(boundContentId: string | null = "article-1"): NewcomerPathConfigResponse {
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
                title: "商务技巧",
                description: null,
                target_unit_id: "business-unit",
                learning_content_id: boundContentId,
                exam_paper_id: null,
                disabled_reason: null,
                unlock_after_unit_ids: [],
                completion_rule: "submitted",
                primary_action_label: null,
                retry_action_label: null,
                review_action_label: null,
                guidance_templates: {},
            }],
        },
        active_revision_id: "path-revision-1",
        active_revision_no: 1,
        working_revision_id: null,
        working_revision_no: null,
        has_unpublished_revision: false,
        diagnostics: pathConfigDiagnostics(),
    };
}

function pathConfigDiagnostics(): NewcomerPathConfigDiagnostics {
    return {
        surface_key: "newcomer_training_path_v1",
        resource_type: "newcomer_training_path",
        source: "active_revision",
        legacy_snapshot_only: false,
        fallback_applied: false,
        fallback_reason: null,
        realtime_provider_readiness: [],
        management_entry: "/admin/newcomer-training/path-config",
        permission_policy: {
            view: "sales_trainer.manage_modules",
            save: "sales_trainer.manage_modules",
            publish: "sales_trainer.manage_modules",
            rollback: "sales_trainer.manage_modules",
            high_risk_ai_coach: "sales_trainer.manage_prompts",
            regrade: "sales_trainer.regrade_history",
        },
        active_revision: null,
        working_revision: null,
        high_risk_actions: {
            publish: {
                requires_reason: true,
                requires_trace_id: true,
                audit_action: "newcomer_path_config.publish",
                impact_scope: "future_learners_only",
                preview_endpoint: "/api/v1/admin/newcomer-training/path-config/publish/preview",
            },
            rollback: {
                requires_reason: true,
                requires_trace_id: true,
                audit_action: "newcomer_path_config.rollback",
                impact_scope: "future_learners_only",
                preview_endpoint: "/api/v1/admin/newcomer-training/path-config/rollback/preview",
            },
            regrade: {
                requires_reason: true,
                requires_trace_id: true,
                audit_action: "historical_regrade.completed",
                impact_scope: "append_only_history",
                history_overwrite: false,
            },
        },
    };
}

describe("NewcomerArticleBindingPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
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
            capability_keys: ["manage_content"],
        });
        listLearningContentsMock.mockResolvedValue({
            items: [
                makeLearningContent(),
                makeLearningContent({
                    learning_content_id: "draft-article",
                    title: "商务技巧草稿",
                    status: "draft",
                    published_at: null,
                    chapters: [],
                }),
                makeLearningContent({
                    learning_content_id: "article-2",
                    title: "拜访前准备清单",
                    status: "published",
                    chapters: [{
                        chapter_id: "chapter-2",
                        learning_content_id: "article-2",
                        title: "第二节",
                        content: "客户背景与材料准备。",
                        order_index: 1,
                        created_at: "2026-06-02T00:00:00Z",
                        updated_at: "2026-06-02T00:00:00Z",
                    }],
                }),
                makeLearningContent({
                    learning_content_id: "content-other",
                    title: "课程训练其他文章",
                    owner: "课程训练",
                    source: "manual",
                }),
            ],
            total: 4,
        });
        getModuleArticleMock.mockResolvedValue({});
        getPathConfigMock.mockResolvedValue(makePathConfig());
        bindModuleArticleMock.mockResolvedValue({
            module_key: "business_skills",
            learning_content_id: "article-2",
            path_key: "newcomer_training_path_v1",
            active_revision_id: "path-revision-1",
            active_revision_no: 1,
            working_revision_id: "path-revision-2",
            working_revision_no: 2,
            has_unpublished_revision: true,
            impact_scope: "future_learners_only",
        });
        createLearningContentMock.mockResolvedValue(makeLearningContent({
            learning_content_id: "new-article",
            status: "draft",
        }));
    });

    it("shows the bound article and chapter management entry", async () => {
        render(<NewcomerArticleBindingPage />);

        expect(await screen.findByText("当前生效学习页绑定")).toBeTruthy();
        expect(getPathConfigMock).toHaveBeenCalledTimes(1);
        expect(getModuleArticleMock).not.toHaveBeenCalled();
        expect(screen.getAllByText("见客户前商务礼仪").length).toBeGreaterThan(0);
        expect(screen.getAllByText("1 节").length).toBeGreaterThan(0);
        expect(screen.getAllByRole("link", { name: /编辑章节/ })[0].getAttribute("href")).toBe(
            "/admin/learning-contents/article-1",
        );
        expect(screen.getAllByRole("link", { name: /编辑章节/ })[0].querySelector("button")).toBeNull();
        expect(screen.getByRole("link", { name: "预览学习页" }).querySelector("button")).toBeNull();
    });

    it("creates a draft article and opens the chapter editor", async () => {
        render(<NewcomerArticleBindingPage />);

        fireEvent.click(await screen.findByRole("button", { name: "新建商务技巧文章" }));

        await waitFor(() => {
            expect(createLearningContentMock).toHaveBeenCalledWith({
                title: "见客户前商务礼仪",
                summary: "新人训练路径商务技巧模块学习文章。",
                owner: "新人训练路径",
                source: "sales_trainer_business_skills",
                safety_flagged: false,
            });
        });
        expect(pushMock).toHaveBeenCalledWith("/admin/learning-contents/new-article");
    });

    it("saves a published learning content as an unpublished path revision", async () => {
        render(<NewcomerArticleBindingPage />);

        const nextArticle = await screen.findByText("拜访前准备清单");
        const row = nextArticle.closest("div.flex.flex-col.gap-4");
        if (!(row instanceof HTMLElement)) {
            throw new Error("Expected article row to be rendered.");
        }
        fireEvent.click(within(row).getByRole("button", { name: "保存为待发布绑定" }));

        await waitFor(() => {
            expect(bindModuleArticleMock).toHaveBeenCalledWith("business_skills", {
                learning_content_id: "article-2",
                path_key: "newcomer_training_path_v1",
                reason: "更新商务技巧学习文章绑定",
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("已保存为待发布路径修订");
        expect(screen.getByText("待发布路径修订已保存")).toBeTruthy();
        expect(screen.getAllByText("拜访前准备清单").length).toBeGreaterThan(0);
        expect(screen.getByText("路径配置 v2 发布后，对后续学员生效；已开始学习或考试的记录继续使用当时快照。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "去路径配置中心发布" }).getAttribute("href")).toBe("/admin/sales-trainer/paths");
        expect(screen.getByRole("button", { name: "待发布路径修订" }).hasAttribute("disabled")).toBe(true);
    });

    it("does not bind draft content or show unrelated learning contents", async () => {
        render(<NewcomerArticleBindingPage />);

        const draftArticle = await screen.findByText("商务技巧草稿");
        const draftRow = draftArticle.closest("div.flex.flex-col.gap-4");
        if (!(draftRow instanceof HTMLElement)) {
            throw new Error("Expected draft article row to be rendered.");
        }
        expect(within(draftRow).getByRole("button", { name: "保存为待发布绑定" }).hasAttribute("disabled")).toBe(true);
        expect(screen.queryByText("课程训练其他文章")).toBeNull();
        expect(screen.getAllByRole("link", { name: /编辑章节/ })[1].querySelector("button")).toBeNull();
    });

    it("shows an unbound state from admin path config without calling learner article API", async () => {
        getPathConfigMock.mockResolvedValueOnce(makePathConfig(null));

        render(<NewcomerArticleBindingPage />);

        expect(await screen.findByText("可绑定学习内容")).toBeTruthy();
        expect(screen.queryByText("当前生效学习页绑定")).toBeNull();
        expect(getPathConfigMock).toHaveBeenCalledTimes(1);
        expect(getModuleArticleMock).not.toHaveBeenCalled();
    });

    it("surfaces admin path config failures instead of treating them as learner empty bindings", async () => {
        getPathConfigMock.mockRejectedValueOnce(new Error("path config unavailable"));

        render(<NewcomerArticleBindingPage />);

        expect(await screen.findByText("path config unavailable")).toBeTruthy();
        expect(screen.queryByText("当前生效学习页绑定")).toBeNull();
        expect(getModuleArticleMock).not.toHaveBeenCalled();
    });

    it("fails closed without content management capability", async () => {
        getCapabilitiesMock.mockResolvedValueOnce({
            role: "viewer",
            role_label: "只读人员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: true,
                manage_modules: false,
                manage_prompts: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["manage_questions"],
        });

        render(<NewcomerArticleBindingPage />);

        expect(await screen.findByText("文章管理权限不足")).toBeTruthy();
        expect(listLearningContentsMock).not.toHaveBeenCalled();
        expect(getPathConfigMock).not.toHaveBeenCalled();
        expect(getModuleArticleMock).not.toHaveBeenCalled();
        expect(createLearningContentMock).not.toHaveBeenCalled();
        expect(bindModuleArticleMock).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "新建商务技巧文章" })).toBeNull();
        expect(screen.queryByRole("button", { name: "保存为待发布绑定" })).toBeNull();
        expect(screen.queryByRole("link", { name: /编辑章节/ })).toBeNull();
    });
});
