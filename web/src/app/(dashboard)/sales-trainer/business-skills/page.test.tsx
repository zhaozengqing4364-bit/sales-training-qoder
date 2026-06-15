import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";

import BusinessSkillsPage from "./page";

const {
    completeChapterMock,
    getArticleMock,
    getBusinessUnitsMock,
    getUnitQuizMock,
    listPathsMock,
    listUnitsMock,
    submitUnitQuizAttemptMock,
    useSearchParamsMock,
} = vi.hoisted(() => ({
    completeChapterMock: vi.fn(),
    getArticleMock: vi.fn(),
    getBusinessUnitsMock: vi.fn(),
    getUnitQuizMock: vi.fn(),
    listPathsMock: vi.fn(),
    listUnitsMock: vi.fn(),
    submitUnitQuizAttemptMock: vi.fn(),
    useSearchParamsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useSearchParams: () => useSearchParamsMock(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                listPaths: listPathsMock,
                listUnits: listUnitsMock,
            },
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                completeModuleArticleChapter: completeChapterMock,
                getBusinessEtiquetteLearningUnits: getBusinessUnitsMock,
                getBusinessEtiquetteUnitQuiz: getUnitQuizMock,
                getModuleArticle: getArticleMock,
                submitBusinessEtiquetteUnitQuizAttempt: submitUnitQuizAttemptMock,
            },
        },
    };
});

function learningUnitsResponse(completedChapterIds: string[] = []) {
    const isCompleted = (chapterId: string) => completedChapterIds.includes(chapterId);
    return {
        module_key: "business_skills",
        learning_content_id: "article-1",
        path_revision_id: "path-revision-1",
        path_revision_no: 1,
        units: [
            learningUnit({
                unitKey: "trust_foundation",
                title: "职业信任底座",
                orderIndex: 1,
                chapterId: "chapter-1",
                chapterTitle: "准备动作",
                completed: isCompleted("chapter-1"),
                unlockAfter: [],
            }),
            learningUnit({
                unitKey: "meeting_social",
                title: "初次见面社交",
                orderIndex: 2,
                chapterId: "chapter-2",
                chapterTitle: "到场礼仪",
                completed: isCompleted("chapter-2"),
                unlockAfter: ["trust_foundation"],
            }),
        ],
    };
}

function learningUnit({
    chapterId,
    chapterTitle,
    completed,
    orderIndex,
    title,
    unitKey,
    unlockAfter,
}: {
    chapterId: string;
    chapterTitle: string;
    completed: boolean;
    orderIndex: number;
    title: string;
    unitKey: string;
    unlockAfter: string[];
}) {
    return {
        unit_key: unitKey,
        title,
        description: `${title}训练说明。`,
        order_index: orderIndex,
        enabled: true,
        source_chapter_orders: [orderIndex],
        capability_keys: [`capability_${orderIndex}`],
        unlock_after_unit_keys: unlockAfter,
        require_reading: true,
        require_quiz: true,
        require_ai_coach: true,
        quiz_question_count: 5,
        quiz_pass_threshold: null,
        quiz_allow_retake: true,
        quiz_max_attempts: null,
        quiz_question_type_weights: {},
        allow_skip_reading: false,
        block_next_until_complete: true,
        empty_state_message: null,
        capabilities: [{
            capability_key: `capability_${orderIndex}`,
            display_name: `能力点 ${orderIndex}`,
            description: `${title}能力点说明。`,
            mastery_levels: [{
                level_key: "basic_mastery",
                display_name: "基本掌握",
                min_score: 70,
                description: "默认达标线。",
            }],
            default_threshold: 70,
            evidence_rules: [{
                evidence_type: "quiz_question",
                weight: 1,
                required: true,
                description: "小测命中该能力点。",
            }],
            owner_scope: "business_etiquette_training_pack",
            status: "published",
        }],
        chapters: [{
            chapter_id: chapterId,
            title: chapterTitle,
            order_index: orderIndex,
            completed,
        }],
        progress: {
            completed_chapter_ids: completed ? [chapterId] : [],
            total_chapters: 1,
            completed_chapters: completed ? 1 : 0,
            is_completed: completed,
        },
    };
}

function pathResponse(coachPath: string | null = null) {
    return {
        items: [{
            path_key: "newcomer_training_path_v1",
            title: "新人训练路径",
            goal_title: "掌握新人训练路径",
            total_levels: 1,
            completed_levels: 0,
            current_level_id: "business-unit",
            next_level_id: "business-unit",
            levels: [{
                unit_id: "business-unit",
                name: "商务技巧",
                description: null,
                unit_type: "quiz",
                module_key: "business_skills",
                module_type: "article_exam",
                order_index: 2,
                level_title: "第二关：商务技巧",
                level_description: null,
                locked: false,
                lock_reason: null,
                status: "available",
                completion_rule: "passed",
                primary_action_label: "开始学习",
                retry_action_label: "重练本关",
                review_action_label: "查看结果",
                target_path: "/sales-trainer/business-skills",
                ai_coach_availability: coachPath ? {
                    enabled: true,
                    configured: true,
                    available: true,
                    coach_path: coachPath,
                    disabled_reason: null,
                    allowed_interaction_types: ["single_choice", "multiple_choice"],
                } : null,
                latest_result: null,
            }],
            goal_context: {
                goal_title: "掌握新人训练路径",
                score_basis: "sales_trainer_path_projection_v1",
                evidence_items: [],
                weak_points: [],
                next_recommendation: null,
            },
        }],
        total: 1,
    };
}

function unitQuizResponse() {
    return {
        training_pack_key: "business_etiquette_training_pack_v1",
        learning_unit_key: "trust_foundation",
        learning_unit_title: "职业信任底座",
        path_revision_id: "path-revision-1",
        path_revision_no: 1,
        training_pack_revision_id: "pack-revision-1",
        training_pack_revision_no: 1,
        question_count: 1,
        pass_threshold: null,
        allow_retake: true,
        max_attempts: null,
        capabilities: [{
            capability_key: "capability_1",
            display_name: "能力点 1",
            description: "职业信任能力。",
            mastery_levels: [{
                level_key: "basic_mastery",
                display_name: "基本掌握",
                min_score: 70,
                description: "默认达标线。",
            }],
            default_threshold: 70,
            evidence_rules: [],
            owner_scope: "business_etiquette_training_pack",
            status: "published",
        }],
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
            capability_keys: ["capability_1"],
            chapter_orders: [1],
        }],
    };
}

function quizAttemptResponse() {
    return {
        attempt_id: "attempt-1",
        training_pack_key: "business_etiquette_training_pack_v1",
        learning_unit_key: "trust_foundation",
        learning_unit_title: "职业信任底座",
        user_id: "user-1",
        user_name: "张三",
        user_department: "销售部",
        path_revision_id: "path-revision-1",
        path_revision_no: 1,
        training_pack_revision_id: "pack-revision-1",
        training_pack_revision_no: 1,
        status: "scored",
        total_score: 10,
        max_score: 10,
        passed: true,
        capability_scores: [{
            capability_key: "capability_1",
            display_name: "能力点 1",
            score: 10,
            max_score: 10,
            normalized_score: 100,
            threshold: 70,
            mastered: true,
            mastery_level_key: "basic_mastery",
            mastery_level_name: "基本掌握",
        }],
        weak_capability_keys: [],
        recommended_chapter_orders: [1],
        answers: [],
        submitted_at: "2026-06-14T10:00:00Z",
    };
}

describe("BusinessSkillsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useSearchParamsMock.mockReturnValue(new URLSearchParams("unitId=business-unit"));
        listUnitsMock.mockResolvedValue({
            items: [{
                unit_id: "business-unit",
                config: {
                    path: {
                        learning_content_id: "article-1",
                        exam_paper_id: "paper-1",
                    },
                },
            }],
            total: 1,
        });
        listPathsMock.mockResolvedValue(pathResponse());
        getBusinessUnitsMock.mockResolvedValue(learningUnitsResponse());
        getUnitQuizMock.mockResolvedValue(unitQuizResponse());
        submitUnitQuizAttemptMock.mockResolvedValue(quizAttemptResponse());
        completeChapterMock.mockImplementation(async (_moduleKey, chapterId) => {
            const completed = chapterId === "chapter-2"
                ? ["chapter-1", "chapter-2"]
                : ["chapter-1"];
            getBusinessUnitsMock.mockResolvedValueOnce(learningUnitsResponse(completed));
            return {
                module_key: "business_skills",
                learning_content_id: "article-1",
                completed_chapter_ids: completed,
                total_chapters: 2,
                is_completed: completed.length === 2,
            };
        });
        getArticleMock.mockResolvedValue({
            module_key: "business_skills",
            learning_content_id: "article-1",
            title: "见客户前商务礼仪",
            summary: "summary",
            owner: "新人训练路径",
            source: null,
            chapters: [
                {
                    chapter_id: "chapter-1",
                    title: "准备动作",
                    content: "![商务礼仪图](https://example.com/business.png)\n\n拜访前确认客户背景。",
                    order_index: 1,
                },
                {
                    chapter_id: "chapter-2",
                    title: "到场礼仪",
                    content: "提前到场并确认会议材料。",
                    order_index: 2,
                },
            ],
        });
    });

    it("renders configured learning units before chapter reading and unlocks exam after required reading", async () => {
        render(<BusinessSkillsPage />);

        expect(await screen.findByRole("heading", { name: "商务礼仪训练" })).toBeTruthy();
        expect(screen.getByRole("button", { name: /职业信任底座/ })).toBeTruthy();
        expect(screen.getByRole("button", { name: /初次见面社交/ })).toBeTruthy();
        expect(screen.getAllByText("能力点 1").length).toBeGreaterThan(0);
        expect(screen.getByText("见客户前商务礼仪")).toBeTruthy();
        expect(screen.getByRole("button", { name: /第一节 准备动作/ })).toBeTruthy();
        expect(screen.getByText("拜访前确认客户背景。")).toBeTruthy();
        expect(screen.getByRole("img", { name: "商务礼仪图" }).getAttribute("src")).toBe(
            "https://example.com/business.png",
        );
        expect(screen.queryByText("小单元测验")).toBeNull();
        expect(screen.queryByText("商务拜访即将迟到时，最合适的做法是什么？")).toBeNull();
        fireEvent.click(screen.getByRole("button", { name: "读完后小测" }));
        expect(getUnitQuizMock).not.toHaveBeenCalled();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "完成本节" }));
        await waitFor(() => {
            expect(completeChapterMock).toHaveBeenCalledWith(
                "business_skills",
                "chapter-1",
                { learning_content_id: "article-1" },
            );
        });
        fireEvent.click(screen.getByRole("button", { name: /初次见面社交/ }));
        expect(screen.getByRole("button", { name: /第一节 到场礼仪/ })).toBeTruthy();
        expect(screen.getByText("提前到场并确认会议材料。")).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "完成本节" }));
        await waitFor(() => {
            expect(screen.getByRole("link", { name: /进入考试/ }).getAttribute("href")).toBe(
                "/sales-trainer/business-skills/exam?unitId=business-unit",
            );
        });
        await waitFor(() => {
            expect(getArticleMock).toHaveBeenCalledWith("business_skills", {
                learning_content_id: "article-1",
            });
        });
    });

    it("does not trust stale article progress outside configured learning units", async () => {
        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        expect(screen.getByText((_, element) => element?.textContent === "0/1 已完成")).toBeTruthy();
        expect(screen.getByText("完成要求阅读的小单元后开放考试入口。")).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();
    });

    it("falls back to module article binding when selected unit has no article binding", async () => {
        listUnitsMock.mockResolvedValueOnce({
            items: [{
                unit_id: "business-unit",
                config: { path: { exam_paper_id: "paper-1" } },
            }],
            total: 1,
        });

        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        expect(getArticleMock).toHaveBeenCalledWith("business_skills", undefined);
    });

    it("shows the AI coach entry when path availability is enabled", async () => {
        listPathsMock.mockResolvedValueOnce(pathResponse("/sales-trainer/business-skills/coach"));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        expect(screen.getByRole("link", { name: "先去 AI 教练练一轮" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills/coach",
        );
    });

    it("loads, submits, and renders the configured unit quiz result", async () => {
        getBusinessUnitsMock.mockResolvedValueOnce(learningUnitsResponse(["chapter-1"]));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        expect(screen.queryByText("小单元测验")).toBeNull();
        expect(screen.queryByText("商务拜访即将迟到时，最合适的做法是什么？")).toBeNull();
        expect(getUnitQuizMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "开始小测" }));
        expect(await screen.findByText("小单元测验")).toBeTruthy();
        expect(screen.getByText("商务拜访即将迟到时，最合适的做法是什么？")).toBeTruthy();

        fireEvent.click(screen.getByLabelText("A. 提前说明并表达歉意"));
        fireEvent.click(screen.getByRole("button", { name: "提交小测" }));

        await waitFor(() => {
            expect(submitUnitQuizAttemptMock).toHaveBeenCalledWith(
                "trust_foundation",
                {
                    answers: [{
                        question_id: "question-1",
                        answer_payload: "A",
                    }],
                },
            );
        });
        expect(await screen.findByText("小测已达标")).toBeTruthy();
        expect(screen.getByText("100 分 · 基本掌握")).toBeTruthy();
    });

    it("keeps answers and shows a local error when unit quiz submission fails", async () => {
        getBusinessUnitsMock.mockResolvedValueOnce(learningUnitsResponse(["chapter-1"]));
        submitUnitQuizAttemptMock.mockRejectedValueOnce(new ApiRequestError({
            status: 500,
            errorCode: "[BUSINESS_ETIQUETTE_QUIZ_SUBMIT_FAILED]",
            message: "submit failed",
        }));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText("见客户前商务礼仪")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "开始小测" }));
        expect(await screen.findByText("商务拜访即将迟到时，最合适的做法是什么？")).toBeTruthy();

        const answer = screen.getByLabelText("A. 提前说明并表达歉意") as HTMLInputElement;
        fireEvent.click(answer);
        fireEvent.click(screen.getByRole("button", { name: "提交小测" }));

        expect(await screen.findByText("小测提交未完成")).toBeTruthy();
        expect(screen.getByText(/submit failed/)).toBeTruthy();
        expect(screen.getByText("商务拜访即将迟到时，最合适的做法是什么？")).toBeTruthy();
        expect(answer.checked).toBe(true);
        expect(screen.queryByText("小测已达标")).toBeNull();
        expect(screen.queryByText("商务礼仪训练内容暂不可用")).toBeNull();
    });

    it("shows an actionable remediation message when the article binding is missing", async () => {
        getArticleMock.mockRejectedValueOnce(new ApiRequestError({
            status: 404,
            errorCode: "[NEWCOMER_MODULE_BINDING_MISSING]",
            message: "article not bound",
        }));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText(/商务礼仪训练内容暂不可用/)).toBeTruthy();
        expect(screen.getByText(/新人训练路径配置中心 → 商务技巧 → 学习文章/)).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();
    });

    it("shows an actionable remediation message when learning unit config is missing", async () => {
        getBusinessUnitsMock.mockRejectedValueOnce(new ApiRequestError({
            status: 409,
            errorCode: "[BUSINESS_ETIQUETTE_LEARNING_UNITS_MISSING]",
            message: "missing units",
        }));

        render(<BusinessSkillsPage />);

        expect(await screen.findByText(/商务礼仪训练内容暂不可用/)).toBeTruthy();
        expect(screen.getByText(/商务礼仪小单元配置缺失/)).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入考试/ })).toBeNull();
    });
});
