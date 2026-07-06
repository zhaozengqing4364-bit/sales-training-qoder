import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BusinessSkillsExamPage from "./page";

const {
    getArticleMock,
    getArticleProgressMock,
    getJourneyMock,
    getPaperMock,
    listPathsMock,
    listUnitsMock,
    pushMock,
    submitAttemptMock,
    useRouterMock,
    useSearchParamsMock,
} = vi.hoisted(() => ({
    getArticleMock: vi.fn(),
    getArticleProgressMock: vi.fn(),
    getJourneyMock: vi.fn(),
    getPaperMock: vi.fn(),
    listPathsMock: vi.fn(),
    listUnitsMock: vi.fn(),
    pushMock: vi.fn(),
    submitAttemptMock: vi.fn(),
    useRouterMock: vi.fn(),
    useSearchParamsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useRouter: () => useRouterMock(),
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
                getJourney: getJourneyMock,
                listPaths: listPathsMock,
                listUnits: listUnitsMock,
            },
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getModuleArticle: getArticleMock,
                getModuleArticleProgress: getArticleProgressMock,
                getPaper: getPaperMock,
                submitPaperAttempt: submitAttemptMock,
            },
        },
    };
});

function journeyResponse(
    unitId: string | null = "business-unit",
    overrides: { learningContentId?: string | null; examPaperId?: string | null } = {},
) {
    const learningContentId = overrides.learningContentId === undefined ? "article-1" : overrides.learningContentId;
    const examPaperId = overrides.examPaperId === undefined ? "paper-1" : overrides.examPaperId;
    return {
        journey_id: "journey-user-1",
        learner_id: "user-1",
        learner_name: "新人",
        department: "销售部",
        path_key: "newcomer_training_path_v1",
        path_revision_id: "path-revision-1",
        path_revision_no: 1,
        source: "active_revision",
        legacy_snapshot_only: false,
        role_capabilities: [],
        learner_level: {
            level_key: "unassigned",
            label: "未分配",
            source: "training_projection",
            rank: 0,
        },
        role_level: {
            level_key: "learner",
            label: "学员",
            source: "training_projection",
            rank: 0,
        },
        training_stage: "in_progress",
        modules: [{
            module_key: "business_skills",
            title: "商务技巧",
            kind: "quiz_attempt",
            module_type: "article_exam",
            display_name: "商务技巧",
            order_index: 2,
            target_unit_id: unitId,
            target_unit_ids: unitId ? [unitId] : [],
            learning_content_id: learningContentId,
            exam_paper_id: examPaperId,
            enabled: true,
            status: "not_started",
            stage: "not_started",
            passed: null,
            score: null,
            max_score: null,
            required: true,
            completion_satisfied: false,
            locked: false,
            block_reason: null,
            completion_rule: "passed",
            source: {
                path_revision_id: "path-revision-1",
                path_revision_no: 1,
            },
            learner_level_required: null,
            unmet_reasons: [],
            diagnostics: [],
            next_action: null,
            latest_outcome: null,
            outcome_history: [],
        }],
        overall_progress: {
            total_modules: 1,
            completed_modules: 0,
            passed_modules: 0,
            failed_modules: 0,
            needs_remediation_modules: 0,
        },
        diagnostics: [],
        generated_at: "2026-06-29T00:00:00Z",
    };
}

describe("BusinessSkillsExamPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.localStorage.clear();
        useSearchParamsMock.mockReturnValue(new URLSearchParams("unitId=business-unit"));
        useRouterMock.mockReturnValue({ push: pushMock });
        getJourneyMock.mockResolvedValue(journeyResponse());
        listUnitsMock.mockResolvedValue({
            items: [{
                unit_id: "business-unit",
                config: { path: { learning_content_id: "article-stale", exam_paper_id: "paper-stale" } },
            }],
            total: 1,
        });
        getArticleProgressMock.mockResolvedValue({
            module_key: "business_skills",
            learning_content_id: "article-1",
            completed_chapter_ids: [],
            total_chapters: 2,
            is_completed: true,
        });
        getArticleMock.mockResolvedValue({
            module_key: "business_skills",
            learning_content_id: "article-1",
            title: "见客户前商务礼仪",
            summary: null,
            owner: null,
            source: null,
            chapters: [
                { chapter_id: "chapter-1", title: "准备动作", content: "正文", order_index: 1 },
                { chapter_id: "chapter-2", title: "到场礼仪", content: "正文", order_index: 2 },
            ],
        });
        getPaperMock.mockResolvedValue({
            paper_id: "paper-1",
            paper_key: "business-basic",
            title: "商务技巧考卷",
            description: null,
            module_key: "business_skills",
            unit_id: "business-unit",
            pass_threshold: null,
            status: "published",
            created_by: null,
            updated_by: null,
            created_at: "2026-06-02T00:00:00Z",
            updated_at: "2026-06-02T00:00:00Z",
            questions: [{
                question_id: "q1",
                order_index: 1,
                points: 10,
                question_type: "single_choice",
                title: "着装",
                stem: "见客户前应如何着装？",
                options: [{ label: "A", value: "A" }],
            }, {
                question_id: "q2",
                order_index: 2,
                points: 10,
                question_type: "true_false",
                title: "礼仪判断",
                stem: "见客户时可以随意打断对方。",
                options: [],
            }],
        });
        submitAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            paper_id: "paper-1",
            paper_title: "商务技巧考卷",
            unit_id: "business-unit",
            user_id: "user-1",
            status: "scored",
            total_score: 10,
            max_score: 10,
            passed: true,
            submitted_at: "2026-06-02T00:00:00Z",
            answers: [],
        });
    });

    it("loads and submits the business skills paper from the active Journey module", async () => {
        render(<BusinessSkillsExamPage />);

        expect(await screen.findByRole("heading", { name: "商务技巧考试" })).toBeTruthy();
        expect(listPathsMock).not.toHaveBeenCalled();
        expect(screen.getByText("商务技巧考卷")).toBeTruthy();
        expect(screen.getByLabelText("正确")).toBeTruthy();
        expect(screen.getByLabelText("错误")).toBeTruthy();
        expect((screen.getByLabelText("A") as HTMLInputElement).checked).toBe(false);
        expect((screen.getByLabelText("错误") as HTMLInputElement).checked).toBe(false);
        expect((screen.getByRole("button", { name: "提交考卷" }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.getByText("所有题目完成后才能提交考卷。")).toBeTruthy();

        fireEvent.click(screen.getByLabelText("A"));
        fireEvent.click(screen.getByLabelText("错误"));
        expect((screen.getByRole("button", { name: "提交考卷" }) as HTMLButtonElement).disabled).toBe(false);
        fireEvent.click(screen.getByRole("button", { name: "提交考卷" }));

        await waitFor(() => {
            expect(submitAttemptMock).toHaveBeenCalledWith({
                paper_id: "paper-1",
                answers: [
                    { question_id: "q1", answer_payload: "A" },
                    { question_id: "q2", answer_payload: "false" },
                ],
            });
        });
        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/sales-trainer/quiz/result/attempt-1");
        });
    });

    it("requires completed learning chapters before loading the paper", async () => {
        getArticleProgressMock.mockResolvedValueOnce({
            module_key: "business_skills",
            learning_content_id: "article-1",
            completed_chapter_ids: [],
            total_chapters: 2,
            is_completed: false,
        });

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByText("请先完成商务技巧学习")).toBeTruthy();
        expect(screen.getByText(/完成全部章节后再进入考试/)).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回学习页" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills?unitId=business-unit",
        );
        expect(getPaperMock).not.toHaveBeenCalled();
        expect(submitAttemptMock).not.toHaveBeenCalled();
    });

    it("shows missing-paper configuration instead of fake success", async () => {
        getJourneyMock.mockResolvedValueOnce(journeyResponse("business-unit", { examPaperId: null }));

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByText("暂未绑定商务技巧考卷")).toBeTruthy();
        expect(screen.getByText(/新人训练路径配置中心 → 商务技巧 → 考卷管理/)).toBeTruthy();
        expect(getPaperMock).not.toHaveBeenCalled();
    });

    it("resolves missing unitId from the active Journey module", async () => {
        useSearchParamsMock.mockReturnValue(new URLSearchParams(""));

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByRole("heading", { name: "商务技巧考试" })).toBeTruthy();
        expect(screen.getByText("商务技巧考卷")).toBeTruthy();
        expect(getJourneyMock).toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
        expect(getPaperMock).toHaveBeenCalledWith("paper-1");
        expect(screen.getByRole("link", { name: "返回商务技巧学习" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills?unitId=business-unit",
        );
    });

    it("uses active Journey bindings instead of stale unit path config", async () => {
        render(<BusinessSkillsExamPage />);

        expect(await screen.findByRole("heading", { name: "商务技巧考试" })).toBeTruthy();
        expect(getArticleMock).toHaveBeenCalledWith("business_skills", {
            learning_content_id: "article-1",
        });
        expect(getPaperMock).toHaveBeenCalledWith("paper-1");
    });

    it("does not borrow another unit's paper when the requested unit has no paper binding", async () => {
        getJourneyMock.mockResolvedValueOnce(journeyResponse("business-unit", { examPaperId: null }));
        listUnitsMock.mockResolvedValueOnce({
            items: [
                {
                    unit_id: "business-unit",
                    config: {
                        path: {
                            learning_content_id: "article-1",
                            module_key: "business_skills",
                        },
                    },
                },
                {
                    unit_id: "other-unit",
                    config: {
                        path: {
                            learning_content_id: "article-2",
                            exam_paper_id: "paper-from-other-unit",
                            module_key: "business_skills",
                        },
                    },
                },
            ],
            total: 2,
        });

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByText("暂未绑定商务技巧考卷")).toBeTruthy();
        expect(getPaperMock).not.toHaveBeenCalled();
        expect(getArticleMock).not.toHaveBeenCalled();
        expect(getArticleProgressMock).not.toHaveBeenCalled();
    });

    it("does not infer the exam paper from stale unit path config when unitId is missing", async () => {
        useSearchParamsMock.mockReturnValue(new URLSearchParams(""));
        getJourneyMock.mockResolvedValueOnce(journeyResponse("business-unit"));
        listUnitsMock.mockResolvedValueOnce({
            items: [{
                unit_id: "legacy-business-unit",
                config: {
                    path: {
                        module_key: "business_skills",
                        learning_content_id: "article-legacy",
                        exam_paper_id: "paper-legacy",
                    },
                },
            }],
            total: 1,
        });

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByText(/active path revision 指向的商务技巧训练单元不存在/)).toBeTruthy();
        expect(getPaperMock).not.toHaveBeenCalled();
        expect(getArticleMock).not.toHaveBeenCalled();
        expect(getArticleProgressMock).not.toHaveBeenCalled();
    });
});
