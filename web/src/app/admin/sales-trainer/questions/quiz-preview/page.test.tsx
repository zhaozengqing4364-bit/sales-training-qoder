import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    BusinessEtiquetteLearningUnit,
    BusinessEtiquetteLearningUnitsResponse,
    BusinessEtiquetteUnitQuiz,
} from "@/lib/api/types";

import BusinessEtiquetteQuizPreviewPage from "./page";

const {
    getLearningUnitsMock,
    getQuizPreviewMock,
    toastErrorMock,
} = vi.hoisted(() => ({
    getLearningUnitsMock: vi.fn(),
    getQuizPreviewMock: vi.fn(),
    toastErrorMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/questions/quiz-preview",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: toastErrorMock,
        success: vi.fn(),
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getBusinessEtiquetteLearningUnits: getLearningUnitsMock,
            },
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getBusinessEtiquetteUnitQuizPreview: getQuizPreviewMock,
                },
            },
        },
    };
});

function capability() {
    return {
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
            evidence_type: "quiz_question" as const,
            weight: 1,
            required: true,
            description: null,
        }],
        owner_scope: "business_etiquette_training_pack" as const,
        status: "published" as const,
    };
}

function learningUnit(): BusinessEtiquetteLearningUnit {
    return {
        unit_key: "trust_foundation",
        title: "职业信任底座",
        description: "尊重分寸、第一印象。",
        order_index: 1,
        enabled: true,
        source_chapter_orders: [1],
        capability_keys: ["respect_boundaries"],
        unlock_after_unit_keys: [],
        require_reading: true,
        require_quiz: true,
        require_ai_coach: true,
        ai_coach_required_capability_keys: ["respect_boundaries"],
        ai_coach_pass_mastery_level_key: "basic",
        ai_coach_ready_mastery_level_key: "field_ready",
        ai_coach_max_remediation_attempts: 3,
        ai_coach_manual_review_after_max_attempts: true,
        ai_coach_block_next_until_passed: true,
        ai_coach_remediation_chapter_orders: [1],
        quiz_question_count: 3,
        quiz_pass_threshold: null,
        quiz_allow_retake: true,
        quiz_max_attempts: null,
        quiz_question_type_weights: {},
        allow_skip_reading: false,
        block_next_until_complete: true,
        empty_state_message: null,
        capabilities: [capability()],
        chapters: [{
            chapter_id: "chapter-1",
            title: "第一章",
            order_index: 1,
            completed: false,
        }],
        progress: {
            completed_chapter_ids: [],
            total_chapters: 1,
            completed_chapters: 0,
            is_completed: false,
        },
    };
}

function learningUnitsResponse(): BusinessEtiquetteLearningUnitsResponse {
    return {
        module_key: "business_skills",
        learning_content_id: "content-1",
        path_revision_id: "path-revision-1",
        path_revision_no: 3,
        units: [learningUnit()],
    };
}

function quizPreview(): BusinessEtiquetteUnitQuiz {
    return {
        training_pack_key: "business_etiquette_v1",
        learning_unit_key: "trust_foundation",
        learning_unit_title: "职业信任底座",
        path_revision_id: "path-revision-1",
        path_revision_no: 3,
        training_pack_revision_id: "pack-revision-1",
        training_pack_revision_no: 2,
        question_count: 1,
        pass_threshold: null,
        allow_retake: true,
        max_attempts: null,
        capabilities: [capability()],
        questions: [{
            question_id: "question-1",
            title: "迟到处理",
            stem: "商务拜访即将迟到时，最合适的做法是什么？",
            question_type: "single_choice",
            points: 10,
            order_index: 1,
            options: [
                { value: "A", label: "提前说明并表达歉意" },
                { value: "B", label: "到场后再解释" },
            ],
            capability_keys: ["respect_boundaries"],
            chapter_orders: [1],
        }],
    };
}

describe("BusinessEtiquetteQuizPreviewPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getLearningUnitsMock.mockResolvedValue(learningUnitsResponse());
        getQuizPreviewMock.mockResolvedValue(quizPreview());
    });

    it("previews quiz questions through the admin preview API", async () => {
        render(<BusinessEtiquetteQuizPreviewPage />);

        expect(await screen.findByText("小测组卷预览")).toBeTruthy();

        await waitFor(() => {
            expect(getLearningUnitsMock).toHaveBeenCalled();
            expect(getQuizPreviewMock).toHaveBeenCalledWith("trust_foundation");
        });

        expect(screen.getByText("按学员端真实规则预览当前小单元会抽到哪些已发布题目；这里不保存、不提交、不占用学员作答次数。")).toBeTruthy();
        expect(screen.getByText("分类不会直接控制抽题；分类只帮助运营管理正式题目。")).toBeTruthy();
        expect(await screen.findByText("迟到处理")).toBeTruthy();
        expect(await screen.findByText("单选题")).toBeTruthy();
        expect(screen.getAllByText("第 1 章").length).toBeGreaterThan(0);
    });
});
