import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NewcomerPaperEditPage from "./page";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";

const {
    getCapabilitiesMock,
    listPapersMock,
    listQuestionsMock,
    pushMock,
    toastErrorMock,
    toastMock,
    toastSuccessMock,
    updatePaperMock,
} = vi.hoisted(() => {
    const toastError = vi.fn();
    const toastSuccess = vi.fn();
    return {
        getCapabilitiesMock: vi.fn(),
        listPapersMock: vi.fn(),
        listQuestionsMock: vi.fn(),
        pushMock: vi.fn(),
        toastErrorMock: toastError,
        toastMock: {
            error: toastError,
            success: toastSuccess,
        },
        toastSuccessMock: toastSuccess,
        updatePaperMock: vi.fn(),
    };
});

vi.mock("next/navigation", () => ({
    useParams: () => ({ paperId: "paper-1" }),
    usePathname: () => "/admin/sales-trainer/papers/paper-1/edit",
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => toastMock,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    listPapers: listPapersMock,
                    updatePaper: updatePaperMock,
                },
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                    listQuestions: listQuestionsMock,
                },
            },
        },
    };
});

describe("NewcomerPaperEditPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        listPapersMock.mockReset();
        listQuestionsMock.mockReset();
        pushMock.mockReset();
        toastErrorMock.mockReset();
        toastSuccessMock.mockReset();
        updatePaperMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "content_admin",
            role_label: "内容管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });
        listPapersMock.mockResolvedValue({
            items: [{
                paper_id: "paper-1",
                paper_key: "business-paper",
                title: "商务礼仪入门考卷",
                description: "原说明",
                module_key: "business_skills",
                unit_id: "unit-1",
                pass_threshold: 10,
                status: "draft",
                created_by: "admin-1",
                updated_by: "admin-1",
                created_at: "2026-06-02T00:00:00Z",
                updated_at: "2026-06-02T00:00:00Z",
                questions: [{
                    question_id: "question-1",
                    order_index: 1,
                    points: 10,
                    question_type: "multiple_choice",
                    title: "客户到访准备",
                    stem: "见客户前应完成哪些准备？",
                }],
            }],
            total: 1,
        });
        listQuestionsMock.mockResolvedValue({
            items: [
                questionFixture("question-1", "客户到访准备", "见客户前应完成哪些准备？"),
                questionFixture("question-2", "客户异议回应", "客户临时提出异议时如何回应？"),
            ],
            total: 2,
        });
        updatePaperMock.mockResolvedValue({ paper_id: "paper-1" });
    });

    it("fails closed before loading paper data without content management permission", async () => {
        getCapabilitiesMock.mockResolvedValue({
            role: "viewer",
            role_label: "只读成员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<NewcomerPaperEditPage />);

        expect(await screen.findByText("考卷管理权限不足")).toBeTruthy();
        expect(listPapersMock).not.toHaveBeenCalled();
        expect(listQuestionsMock).not.toHaveBeenCalled();
        expect(updatePaperMock).not.toHaveBeenCalled();
        expect(screen.queryByLabelText("考卷标题")).toBeNull();
        expect(screen.queryByRole("button", { name: "保存草稿" })).toBeNull();
    });

    it("updates a draft business skills paper without exposing internal identifiers", async () => {
        render(<NewcomerPaperEditPage />);

        await waitFor(() => {
            expect(listPapersMock).toHaveBeenCalledWith({ include_archived: true, limit: 100 });
        });
        expect(await screen.findByDisplayValue("商务礼仪入门考卷")).toBeTruthy();
        expect(screen.queryByText("考卷标识")).toBeNull();
        expect(screen.queryByText("题目编号")).toBeNull();
        expect(screen.queryByText("business-paper")).toBeNull();

        fireEvent.change(screen.getByLabelText("考卷标题"), {
            target: { value: "商务技巧草稿考卷" },
        });
        fireEvent.change(screen.getByLabelText("每题默认分值"), {
            target: { value: "12" },
        });
        fireEvent.click(screen.getByLabelText(/客户异议回应/));
        fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));

        await waitFor(() => {
            expect(updatePaperMock).toHaveBeenCalledWith("paper-1", {
                title: "商务技巧草稿考卷",
                description: "原说明",
                module_key: "business_skills",
                questions: [
                    { question_id: "question-1", order_index: 1, points: 12 },
                    { question_id: "question-2", order_index: 2, points: 12 },
                ],
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("考卷草稿已保存");
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/papers");
    });

    it("saves a published paper as a future revision instead of blocking editing", async () => {
        listPapersMock.mockResolvedValueOnce({
            items: [{
                paper_id: "paper-1",
                paper_key: "business-paper",
                title: "商务礼仪发布考卷",
                description: "原说明",
                module_key: "business_skills",
                unit_id: "unit-1",
                pass_threshold: 10,
                status: "published",
                created_by: "admin-1",
                updated_by: "admin-1",
                created_at: "2026-06-02T00:00:00Z",
                updated_at: "2026-06-02T00:00:00Z",
                questions: [{
                    question_id: "question-1",
                    order_index: 1,
                    points: 10,
                    question_type: "multiple_choice",
                    title: "客户到访准备",
                    stem: "见客户前应完成哪些准备？",
                }],
            }],
            total: 1,
        });

        render(<NewcomerPaperEditPage />);

        expect(await screen.findByDisplayValue("商务礼仪发布考卷")).toBeTruthy();
        expect(screen.getByText(/保存后生成新修订/)).toBeTruthy();
        expect(screen.queryByText("不可直接修改")).toBeNull();

        fireEvent.change(screen.getByLabelText("考卷标题"), {
            target: { value: "商务技巧新修订" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updatePaperMock).toHaveBeenCalledWith("paper-1", {
                title: "商务技巧新修订",
                description: "原说明",
                module_key: "business_skills",
                questions: [
                    { question_id: "question-1", order_index: 1, points: 10 },
                ],
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith(
            "已保存为新修订，发布并生效后只影响后续学员",
        );
    });
});

function questionFixture(questionId: string, title: string, stem: string) {
    return {
        question_id: questionId,
        title,
        stem,
        reference_answer: null,
        category_id: "category-1",
        question_type: "multiple_choice",
        difficulty: "medium",
        status: "published",
        tags: [NEWCOMER_QUESTION_TAG, "商务技巧"],
        scoring_dimensions: [],
        scoring_criteria: {},
        safety_flagged: false,
        department: null,
        usage_scope: "sales_trainer",
        version: 1,
        content_hash: null,
        published_at: "2026-06-03T00:00:00Z",
        created_at: "2026-06-03T00:00:00Z",
        updated_at: "2026-06-03T00:00:00Z",
        options: [],
        correct_answer: null,
        correct_answers: [],
        correct_bool: null,
        explanation: null,
        ai_scoring: null,
    };
}
