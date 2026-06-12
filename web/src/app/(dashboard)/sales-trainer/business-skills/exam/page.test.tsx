import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BusinessSkillsExamPage from "./page";

const { getArticleMock, getArticleProgressMock, getPaperMock, listUnitsMock, pushMock, submitAttemptMock, useRouterMock, useSearchParamsMock } = vi.hoisted(() => ({
    getArticleMock: vi.fn(),
    getArticleProgressMock: vi.fn(),
    getPaperMock: vi.fn(),
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

describe("BusinessSkillsExamPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.localStorage.clear();
        useSearchParamsMock.mockReturnValue(new URLSearchParams("unitId=business-unit"));
        useRouterMock.mockReturnValue({ push: pushMock });
        listUnitsMock.mockResolvedValue({
            items: [{
                unit_id: "business-unit",
                config: { path: { learning_content_id: "article-1", exam_paper_id: "paper-1" } },
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

    it("loads and submits the business skills paper on the dedicated exam page", async () => {
        window.localStorage.setItem(
            "newcomer-business-skills:article-1:completed-chapters",
            JSON.stringify(["chapter-1", "chapter-2"]),
        );

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByRole("heading", { name: "商务技巧考试" })).toBeTruthy();
        expect(screen.getByText("商务技巧考卷")).toBeTruthy();
        expect(screen.getByLabelText("正确")).toBeTruthy();
        expect(screen.getByLabelText("错误")).toBeTruthy();

        fireEvent.click(screen.getByLabelText("A"));
        fireEvent.click(screen.getByLabelText("错误"));
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
            expect(pushMock).toHaveBeenCalledWith(
                "/sales-trainer/quiz/result/attempt-1",
            );
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
        listUnitsMock.mockResolvedValueOnce({
            items: [{ unit_id: "business-unit", config: { path: {} } }],
            total: 1,
        });

        render(<BusinessSkillsExamPage />);

        expect(await screen.findByText("暂未绑定商务技巧考卷")).toBeTruthy();
        expect(screen.getByText(/新人训练路径配置中心 → 商务技巧 → 考卷管理/)).toBeTruthy();
        expect(getPaperMock).not.toHaveBeenCalled();
    });
});
