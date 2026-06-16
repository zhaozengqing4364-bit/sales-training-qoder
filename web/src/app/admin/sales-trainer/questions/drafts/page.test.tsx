import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    BusinessEtiquetteCapabilitySnapshotResponse,
    BusinessEtiquetteQuestionDraft,
    SalesTrainerQuestionCategoryListResponse,
} from "@/lib/api/types";

import BusinessEtiquetteQuestionDraftsPage from "./page";

const {
    approveDraftMock,
    generateDraftsMock,
    getCapabilitiesMock,
    listCategoriesMock,
    listDraftsMock,
    rejectDraftMock,
    toastApi,
    updateDraftMock,
} = vi.hoisted(() => {
    const toastError = vi.fn();
    const toastSuccess = vi.fn();
    return {
        approveDraftMock: vi.fn(),
        generateDraftsMock: vi.fn(),
        getCapabilitiesMock: vi.fn(),
        listCategoriesMock: vi.fn(),
        listDraftsMock: vi.fn(),
        rejectDraftMock: vi.fn(),
        toastApi: {
            error: toastError,
            success: toastSuccess,
        },
        updateDraftMock: vi.fn(),
    };
});

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/questions/drafts",
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => toastApi,
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
                    approveBusinessEtiquetteQuestionDraft: approveDraftMock,
                    generateBusinessEtiquetteQuestionDrafts: generateDraftsMock,
                    getBusinessEtiquetteCapabilities: getCapabilitiesMock,
                    listBusinessEtiquetteQuestionDrafts: listDraftsMock,
                    listQuestionCategories: listCategoriesMock,
                    rejectBusinessEtiquetteQuestionDraft: rejectDraftMock,
                    updateBusinessEtiquetteQuestionDraft: updateDraftMock,
                },
            },
        },
    };
});

function draft(
    overrides: Partial<BusinessEtiquetteQuestionDraft> = {},
): BusinessEtiquetteQuestionDraft {
    return {
        draft_id: "draft-1",
        batch_id: "batch-1",
        training_pack_key: "business_etiquette_v1",
        training_pack_revision_id: "revision-1",
        training_pack_revision_no: 2,
        learning_content_id: "content-1",
        chapter_id: "chapter-1",
        chapter_order: 1,
        chapter_title: "第 1 章",
        source_excerpt: "守时和尊重边界是商务礼仪基础。",
        question_type: "single_choice",
        title: "迟到处理",
        stem: "商务拜访即将迟到时，最合适的做法是什么？",
        options: [
            { value: "A", label: "提前说明并表达歉意" },
            { value: "B", label: "到场后再解释" },
        ],
        correct_answer: "A",
        correct_answers: [],
        reference_answer: null,
        explanation: "守时是商务礼仪基础。",
        difficulty: "medium",
        capability_keys: ["respect_boundaries"],
        status: "pending_review",
        prompt_template_id: "prompt-1",
        prompt_template_name: "商务礼仪题目生成",
        prompt_contract_hash: "contract-hash",
        prompt_contract_version: "v1",
        prompt_rendered_hash: "rendered-hash",
        model_config: {},
        raw_generation: {},
        review_notes: null,
        reviewed_by: null,
        reviewed_at: null,
        question_id: null,
        created_by: "admin",
        updated_by: "admin",
        created_at: "2026-06-14T00:00:00Z",
        updated_at: "2026-06-14T00:00:00Z",
        ...overrides,
    };
}

function categories(): SalesTrainerQuestionCategoryListResponse {
    return {
        total: 1,
        items: [{
            category_id: "category-1",
            parent_id: null,
            name: "商务礼仪",
            description: null,
            usage_scope: "sales_trainer",
            order_index: 1,
            created_at: "2026-06-14T00:00:00Z",
            updated_at: "2026-06-14T00:00:00Z",
        }],
    };
}

function capabilities(): BusinessEtiquetteCapabilitySnapshotResponse {
    return {
        training_pack_key: "business_etiquette_v1",
        source: "working_revision",
        working_revision_id: "revision-1",
        working_revision_no: 2,
        active_revision_id: null,
        active_revision_no: null,
        has_unpublished_revision: true,
        schema_version: 1,
        capabilities: [{
            capability_key: "respect_boundaries",
            display_name: "尊重与分寸感",
            description: "能识别商务边界。",
            mastery_levels: [{
                level_key: "basic",
                display_name: "基本掌握",
                min_score: 70,
                description: null,
            }],
            default_threshold: 70,
            evidence_rules: [{
                evidence_type: "quiz_question",
                weight: 1,
                required: true,
                description: null,
            }],
            owner_scope: "business_etiquette_training_pack",
            status: "draft",
        }],
        chapter_bindings: [{
            chapter_order: 1,
            capability_keys: ["respect_boundaries"],
        }],
        original_chapter_count: 1,
        needs_save: false,
        management_entry: "/admin/sales-trainer/articles/capabilities",
        permission: "sales_trainer.manage_modules",
        effective_timing: "training_pack_revision_publish_time",
    };
}

describe("BusinessEtiquetteQuestionDraftsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listDraftsMock.mockResolvedValue({
            items: [draft()],
            total: 1,
        });
        listCategoriesMock.mockResolvedValue(categories());
        getCapabilitiesMock.mockResolvedValue(capabilities());
        generateDraftsMock.mockResolvedValue({
            batch_id: "batch-2",
            items: [draft({ draft_id: "draft-2", batch_id: "batch-2" })],
            total: 1,
        });
        approveDraftMock.mockResolvedValue(draft({
            status: "converted",
            question_id: "question-1",
        }));
        updateDraftMock.mockResolvedValue(draft());
        rejectDraftMock.mockResolvedValue(draft({ status: "rejected" }));
    });

    it("loads drafts and approves a selected draft into question bank", async () => {
        render(<BusinessEtiquetteQuestionDraftsPage />);

        expect(await screen.findByText("迟到处理")).toBeTruthy();
        expect(screen.getAllByText("AI 出题审核").length).toBeGreaterThan(0);
        expect(screen.getByText("按章节生成商务礼仪题目草稿，人工审核后只会转为正式题目草稿；发布仍在正式题目库完成。")).toBeTruthy();
        expect(screen.getByText("发布题目")).toBeTruthy();
        expect(screen.getByText("小测抽题")).toBeTruthy();
        expect(screen.getByText("Prompt 合约 contract-hash · 修订 2")).toBeTruthy();

        fireEvent.change(screen.getByLabelText(/^题目分类/), {
            target: { value: "category-1" },
        });
        fireEvent.change(screen.getByLabelText("审核备注"), {
            target: { value: "审核通过" },
        });
        fireEvent.click(screen.getByRole("button", { name: "转为正式题目草稿" }));

        await waitFor(() => {
            expect(approveDraftMock).toHaveBeenCalledWith("draft-1", {
                category_id: "category-1",
                review_notes: "审核通过",
            });
        });
    });

    it("generates drafts through the governed prompt endpoint", async () => {
        render(<BusinessEtiquetteQuestionDraftsPage />);

        await screen.findByText("迟到处理");
        fireEvent.change(screen.getByLabelText("Prompt 模板 ID（高级）"), {
            target: { value: "prompt-template-id" },
        });
        fireEvent.change(screen.getAllByLabelText("能力点 key")[0], {
            target: { value: "respect_boundaries" },
        });
        fireEvent.click(screen.getByRole("button", { name: "生成草稿" }));

        await waitFor(() => {
            expect(generateDraftsMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    chapter_order: 1,
                    prompt_template_id: "prompt-template-id",
                    question_types: ["single_choice", "multiple_choice", "short_answer"],
                    capability_keys: ["respect_boundaries"],
                    model_config: {},
                }),
            );
        });
    });
});
