import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    BusinessEtiquetteImportResponse,
    BusinessEtiquetteReleaseImpactResponse,
} from "@/lib/api/types";

import BusinessEtiquetteImportPage from "./page";

const {
    getBusinessEtiquetteReleaseImpactMock,
    getCapabilitiesMock,
    importBusinessEtiquetteMarkdownMock,
    publishBusinessEtiquetteReleaseMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    getBusinessEtiquetteReleaseImpactMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
    importBusinessEtiquetteMarkdownMock: vi.fn(),
    publishBusinessEtiquetteReleaseMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/articles/import",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: toastSuccessMock,
        error: toastErrorMock,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>(
        "@/lib/api/client",
    );
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                    getBusinessEtiquetteReleaseImpact:
                        getBusinessEtiquetteReleaseImpactMock,
                    importBusinessEtiquetteMarkdown:
                        importBusinessEtiquetteMarkdownMock,
                    publishBusinessEtiquetteRelease:
                        publishBusinessEtiquetteReleaseMock,
                },
            },
        },
    };
});

const importResult: BusinessEtiquetteImportResponse = {
    training_pack_key: "business_etiquette_v1",
    learning_content_id: "learning-content-1",
    learning_content_status: "draft",
    working_revision_id: "revision-2",
    working_revision_no: 2,
    active_revision_id: "revision-1",
    active_revision_no: 1,
    has_unpublished_revision: true,
    source_filename: "business-etiquette.md",
    content_type: "text/markdown",
    file_size_bytes: 2048,
    content_hash: "hash-1",
    imported_at: "2026-06-14T00:00:00Z",
    allow_overwrite_draft: true,
    ai_suggestions_enabled: false,
    book_title: "商务礼仪：新人的第一本职业素养手册",
    original_chapter_count: 8,
    micro_chapter_count: 56,
    knowledge_point_count: 120,
    chapters: [
        {
            title: "第一节：礼仪的底层逻辑",
            order_index: 1,
            line_number: 30,
            content_hash: "chapter-hash-1",
            micro_chapters: [
                {
                    title: "礼仪的文化根基",
                    order_index: 1,
                    line_number: 48,
                    knowledge_points: [
                        {
                            title: "核心知识点",
                            order_index: 1,
                            line_number: 52,
                        },
                    ],
                },
            ],
        },
    ],
};

const releaseImpact: BusinessEtiquetteReleaseImpactResponse = {
    training_pack_key: "business_etiquette_v1",
    active_revision_id: "revision-1",
    active_revision_no: 1,
    target_revision_id: "revision-2",
    target_revision_no: 2,
    target_revision_status: "working",
    strategy_options: [
        "future_learners_only",
        "allow_voluntary_switch",
        "assign_retraining",
    ],
    config: {
        default_strategy: "future_learners_only",
        allow_voluntary_switch: true,
        allow_assigned_retraining: true,
        max_assigned_retraining_users: 100,
        notification_template: "商务礼仪训练包已更新。",
        large_change_chapter_threshold: 2,
        management_entry: "/admin/sales-trainer/articles/import",
    },
    summary: {
        changed_chapter_count: 1,
        impacted_learning_unit_count: 1,
        impacted_question_count: 1,
        impacted_question_draft_count: 1,
        impacted_capability_count: 1,
        impacted_ai_coach_config_count: 1,
        active_learner_count: 2,
        recommended_retraining_user_count: 1,
        is_large_change: false,
    },
    chapter_changes: [{
        chapter_order: 1,
        title: "第一节：礼仪的底层逻辑",
        change_type: "changed",
        previous_content_hash: "old",
        target_content_hash: "new",
    }],
    impacted_learning_units: [{
        unit_key: "trust_foundation",
        title: "职业信任底座",
        source_chapter_orders: [1],
        capability_keys: ["respect_boundaries"],
        impacted_chapter_orders: [1],
        impacted_capability_keys: ["respect_boundaries"],
        require_quiz: true,
        require_ai_coach: true,
    }],
    impacted_questions: [{
        question_id: "question-1",
        draft_id: "draft-1",
        title: "尊重分寸题",
        question_type: "single_choice",
        chapter_order: 1,
        capability_keys: ["respect_boundaries"],
    }],
    impacted_question_drafts: [{
        draft_id: "draft-2",
        title: "复盘表达题",
        question_type: "short_answer",
        status: "pending_review",
        chapter_order: 1,
        capability_keys: ["respect_boundaries"],
    }],
    impacted_capabilities: [{
        capability_key: "respect_boundaries",
        display_name: "尊重与分寸感",
        change_type: "changed",
        previous_status: "published",
        target_status: "published",
    }],
    impacted_ai_coach_configs: [{
        unit_key: "trust_foundation",
        title: "职业信任底座",
        prompt_template_id: "prompt-1",
        scoring_prompt_template_id: null,
        allowed_training_card_types: ["scenario_judgment"],
        affected_reason: "小单元章节或能力点发生变化，需要复核训练卡与评分 prompt 是否仍匹配。",
    }],
    active_learners: [{
        user_id: "user-1",
        user_name: "张三",
        department: null,
        source_record_types: ["quiz_attempt", "ai_coach_session"],
        latest_path_revision_no: 1,
        latest_training_pack_revision_no: 1,
        has_active_ai_coach_session: true,
    }],
    recommended_retraining_user_ids: ["user-1"],
};

function markdownFile(): File {
    return new File(["# 商务礼仪"], "business-etiquette.md", {
        type: "text/markdown",
    });
}

describe("BusinessEtiquetteImportPage", () => {
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
        importBusinessEtiquetteMarkdownMock.mockResolvedValue(importResult);
        getBusinessEtiquetteReleaseImpactMock.mockResolvedValue(releaseImpact);
        publishBusinessEtiquetteReleaseMock.mockResolvedValue({
            training_pack_key: "business_etiquette_v1",
            active_revision_id: "revision-2",
            active_revision_no: 2,
            previous_revision_id: "revision-1",
            strategy: "future_learners_only",
            impact_summary: releaseImpact.summary,
            created_session_ids: [],
        });
    });

    it("uploads a markdown file and renders the parsed preview", async () => {
        render(<BusinessEtiquetteImportPage />);

        const file = markdownFile();
        fireEvent.change(await screen.findByLabelText("Markdown 文件"), {
            target: { files: [file] },
        });
        fireEvent.change(screen.getByLabelText("操作原因"), {
            target: { value: "重新导入商务礼仪资料" },
        });
        fireEvent.click(await screen.findByRole("button", { name: "生成草稿版本" }));

        await waitFor(() => {
            expect(importBusinessEtiquetteMarkdownMock).toHaveBeenCalledWith({
                file,
                training_pack_key: "business_etiquette_v1",
                allow_overwrite_draft: true,
                reason: "重新导入商务礼仪资料",
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("商务礼仪资料草稿已生成");
        expect(screen.getByText("商务礼仪：新人的第一本职业素养手册")).toBeTruthy();
        expect(screen.getByText("8 个")).toBeTruthy();
        expect(screen.getByText("56 个")).toBeTruthy();
        expect(screen.getByText("120 个")).toBeTruthy();
        expect(screen.getAllByText(/第一节：礼仪的底层逻辑/).length).toBeGreaterThan(0);
        expect(screen.getByText("核心知识点")).toBeTruthy();
        expect(await screen.findByText("发布影响分析")).toBeTruthy();
        expect(await screen.findByText("章节 diff")).toBeTruthy();
        expect(await screen.findByText("职业信任底座 · 章节 1")).toBeTruthy();
        expect(screen.getByRole("link", { name: "打开章节编辑" }).getAttribute("href")).toBe(
            "/admin/learning-contents/learning-content-1",
        );
    });

    it("publishes the working revision with the selected release strategy", async () => {
        render(<BusinessEtiquetteImportPage />);

        const file = markdownFile();
        fireEvent.change(await screen.findByLabelText("Markdown 文件"), {
            target: { files: [file] },
        });
        fireEvent.click(await screen.findByRole("button", { name: "生成草稿版本" }));

        await screen.findByText("发布影响分析");
        fireEvent.change(await screen.findByLabelText("发布影响范围"), {
            target: { value: "assign_retraining" },
        });
        fireEvent.change(screen.getByLabelText("指定重练用户 ID"), {
            target: { value: "user-1\nuser-2" },
        });
        fireEvent.change(screen.getByLabelText("发布原因"), {
            target: { value: "月度更新重练" },
        });
        fireEvent.click(screen.getByRole("button", { name: "确认发布新版" }));

        await waitFor(() => {
            expect(publishBusinessEtiquetteReleaseMock).toHaveBeenCalledWith({
                training_pack_key: "business_etiquette_v1",
                strategy: "assign_retraining",
                assigned_user_ids: ["user-1", "user-2"],
                reason: "月度更新重练",
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("已发布训练包 v2");
    });

    it("does not submit without a markdown file", async () => {
        render(<BusinessEtiquetteImportPage />);

        fireEvent.click(await screen.findByRole("button", { name: "生成草稿版本" }));

        expect(importBusinessEtiquetteMarkdownMock).not.toHaveBeenCalled();
        expect(toastErrorMock).toHaveBeenCalledWith("请先选择 Markdown 文件。");
    });

    it("passes overwrite setting from the checkbox", async () => {
        render(<BusinessEtiquetteImportPage />);

        const file = markdownFile();
        fireEvent.change(await screen.findByLabelText("Markdown 文件"), {
            target: { files: [file] },
        });
        fireEvent.click(screen.getByRole("checkbox", { name: "允许覆盖当前未发布草稿" }));
        fireEvent.click(screen.getByRole("button", { name: "生成草稿版本" }));

        await waitFor(() => {
            expect(importBusinessEtiquetteMarkdownMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    allow_overwrite_draft: false,
                    file,
                }),
            );
        });
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

        render(<BusinessEtiquetteImportPage />);

        expect(await screen.findByText("资料导入权限不足")).toBeTruthy();
        expect(importBusinessEtiquetteMarkdownMock).not.toHaveBeenCalled();
        expect(getBusinessEtiquetteReleaseImpactMock).not.toHaveBeenCalled();
        expect(publishBusinessEtiquetteReleaseMock).not.toHaveBeenCalled();
        expect(screen.queryByLabelText("Markdown 文件")).toBeNull();
        expect(screen.queryByRole("button", { name: "生成草稿版本" })).toBeNull();
        expect(screen.queryByRole("button", { name: "确认发布新版" })).toBeNull();
    });
});
