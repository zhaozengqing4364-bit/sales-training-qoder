import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NewcomerPaperNewPage from "./page";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";

const {
    createPaperMock,
    getCapabilitiesMock,
    listQuestionsMock,
    pushMock,
    toastErrorMock,
    toastMock,
    toastSuccessMock,
} = vi.hoisted(() => {
    const toastError = vi.fn();
    const toastSuccess = vi.fn();
    return {
        createPaperMock: vi.fn(),
        getCapabilitiesMock: vi.fn(),
        listQuestionsMock: vi.fn(),
        pushMock: vi.fn(),
        toastErrorMock: toastError,
        toastMock: {
            error: toastError,
            success: toastSuccess,
        },
        toastSuccessMock: toastSuccess,
    };
});

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/learning-topics/papers/new",
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
                    createPaper: createPaperMock,
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

describe("NewcomerPaperNewPage", () => {
    beforeEach(() => {
        createPaperMock.mockReset();
        getCapabilitiesMock.mockReset();
        listQuestionsMock.mockReset();
        pushMock.mockReset();
        toastErrorMock.mockReset();
        toastSuccessMock.mockReset();
        createPaperMock.mockResolvedValue({ paper_id: "paper-1" });
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
        listQuestionsMock.mockResolvedValue({
            items: [{
                question_id: "question-1",
                title: "客户到访准备",
                stem: "见客户前应完成哪些商务礼仪准备？",
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
            }],
            total: 1,
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("fails closed before loading questions without content management permission", async () => {
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

        render(<NewcomerPaperNewPage />);

        expect(await screen.findByText("学习专题考卷权限不足")).toBeTruthy();
        expect(listQuestionsMock).not.toHaveBeenCalled();
        expect(createPaperMock).not.toHaveBeenCalled();
        expect(screen.queryByLabelText("考卷标题")).toBeNull();
        expect(screen.queryByRole("button", { name: "创建考卷" })).toBeNull();
    });

    it("creates a business skills paper from published newcomer questions without asking for internal ids", async () => {
        const paperKeyTime = new Date("2026-06-03T08:00:00Z").getTime();
        vi.spyOn(Date, "now").mockReturnValue(paperKeyTime);

        render(<NewcomerPaperNewPage />);

        await waitFor(() => {
            expect(listQuestionsMock).toHaveBeenCalledWith({
                status: "published",
                tag: NEWCOMER_QUESTION_TAG,
            });
        });
        await screen.findByText("客户到访准备");

        expect(screen.queryByText("考卷标识")).toBeNull();
        expect(screen.queryByText("题目编号")).toBeNull();

        fireEvent.change(screen.getByLabelText("考卷标题"), {
            target: { value: "商务技巧正式考卷" },
        });
        fireEvent.change(screen.getByLabelText("每题默认分值"), {
            target: { value: "15" },
        });
        fireEvent.change(screen.getByLabelText("考卷说明"), {
            target: { value: "用于第二关商务技巧考试。" },
        });
        fireEvent.click(screen.getByLabelText(/客户到访准备/));
        fireEvent.click(screen.getByRole("button", { name: "创建考卷" }));

        await waitFor(() => {
            expect(createPaperMock).toHaveBeenCalledWith({
                paper_key: `business_skills_paper_${paperKeyTime}`,
                title: "商务技巧正式考卷",
                description: "用于第二关商务技巧考试。",
                module_key: "business_skills",
                questions: [{
                    question_id: "question-1",
                    order_index: 1,
                    points: 15,
                }],
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("学习专题考卷已创建");
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/learning-topics/papers");
    });
});
