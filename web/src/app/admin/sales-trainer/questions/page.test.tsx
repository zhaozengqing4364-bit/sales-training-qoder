import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuestionsPage from "./page";
import { ApiRequestError } from "@/lib/api/client";

const {
    archiveQuestionMock,
    getCapabilitiesMock,
    listCategoriesMock,
    listQuestionsMock,
    publishQuestionMock,
    pushMock,
    toastErrorMock,
} = vi.hoisted(() => ({
    archiveQuestionMock: vi.fn(),
    getCapabilitiesMock: vi.fn(),
    listCategoriesMock: vi.fn(),
    listQuestionsMock: vi.fn(),
    publishQuestionMock: vi.fn(),
    pushMock: vi.fn(),
    toastErrorMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/questions",
    useRouter: () => ({ push: pushMock }),
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
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    archiveQuestion: archiveQuestionMock,
                    getCapabilities: getCapabilitiesMock,
                    listQuestionCategories: listCategoriesMock,
                    listQuestions: listQuestionsMock,
                    publishQuestion: publishQuestionMock,
                },
            },
        },
    };
});

describe("SalesTrainerQuestionsPage", () => {
    beforeEach(() => {
        archiveQuestionMock.mockReset();
        getCapabilitiesMock.mockReset();
        listCategoriesMock.mockReset();
        listQuestionsMock.mockReset();
        publishQuestionMock.mockReset();
        pushMock.mockReset();
        toastErrorMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
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
        listCategoriesMock.mockResolvedValue({
            items: [
                {
                    category_id: "category-1",
                    parent_id: null,
                    name: "商务礼仪",
                    description: null,
                    usage_scope: "sales_trainer",
                    order_index: 1,
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                },
                {
                    category_id: "category-coo",
                    parent_id: null,
                    name: "COO谈市场配套题库",
                    description: null,
                    usage_scope: "sales_trainer",
                    order_index: 2,
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                },
            ],
            total: 1,
        });
        listQuestionsMock.mockResolvedValue({
            items: [{
                question_id: "question-1",
                title: "报价沟通原则",
                stem: "当客户催促报价但需求尚未澄清时，你如何回应？",
                reference_answer: "先确认客户目标和约束，再给出报价路径。",
                category_id: "category-1",
                question_type: "short_answer",
                difficulty: "medium",
                status: "published",
                tags: ["新人训练路径", "business_skills", "报价"],
                scoring_dimensions: ["business_skills"],
                scoring_criteria: {},
                safety_flagged: false,
                department: null,
                usage_scope: "sales_trainer",
                version: 1,
                content_hash: null,
                published_at: "2026-06-02T00:00:00Z",
                created_at: "2026-06-02T00:00:00Z",
                updated_at: "2026-06-02T00:00:00Z",
                options: [],
                correct_answer: null,
                correct_answers: [],
                correct_bool: null,
                explanation: null,
                ai_scoring: { enabled: true },
            }],
            total: 1,
        });
    });

    it("renders a calmer question governance workspace", async () => {
        render(<SalesTrainerQuestionsPage />);

        await waitFor(() => {
            expect(listQuestionsMock).toHaveBeenCalledWith({
                category_id: undefined,
                difficulty: undefined,
                status: undefined,
                tag: "新人训练路径",
            });
        });

        expect(await screen.findByText("正式题目概览")).toBeTruthy();
        expect(screen.getByText("AI 草稿审核后会进入这里；只有发布后的题目才会被学员端小测抽取。")).toBeTruthy();
        expect(screen.queryByText(/sales_trainer/)).toBeNull();
        expect(screen.getAllByText("正式题目库").length).toBeGreaterThan(0);
        expect(screen.getByText("正式题目清单")).toBeTruthy();
        expect(screen.getByText("小测按已发布状态和能力点抽题；分类只用于运营管理和筛选。")).toBeTruthy();
        expect(screen.getByText("筛选题目")).toBeTruthy();
        expect(screen.getByText("报价沟通原则")).toBeTruthy();
        expect(screen.getAllByText("商务礼仪").length).toBeGreaterThan(0);
        expect(screen.queryByRole("option", { name: "COO谈市场配套题库" })).toBeNull();
        expect(screen.getByText("#商务技巧")).toBeTruthy();
        expect(screen.queryByText("#business_skills")).toBeNull();
        expect(screen.getByText("简答题")).toBeTruthy();
        expect(screen.getAllByText("已发布").length).toBeGreaterThan(0);
        expect(screen.queryByText("published")).toBeNull();
        expect(screen.getByRole("button", { name: "编辑" })).toBeTruthy();
        expect(screen.queryByRole("button", { name: /复制草稿/ })).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "AI 出题审核" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/questions/drafts");

        fireEvent.click(screen.getByRole("button", { name: "小测预览" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/questions/quiz-preview");

        fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/questions/new");
    });

    it("keeps load failures visible instead of falling back to an empty list", async () => {
        listQuestionsMock
            .mockRejectedValueOnce(
                new ApiRequestError({
                    status: 403,
                    errorCode: "[ROLE_REQUIRED]",
                    message: "权限不足",
                    traceId: "trace-question-403",
                    details: null,
                }),
            )
            .mockResolvedValueOnce({
                items: [],
                total: 0,
            });

        render(<SalesTrainerQuestionsPage />);

        await waitFor(() => {
            expect(screen.getByText("题目加载失败")).toBeTruthy();
        });
        expect(screen.getByText(/权限不足/)).toBeTruthy();
        expect(screen.queryByText("暂无题目")).toBeNull();
        expect(toastErrorMock).toHaveBeenCalledWith(expect.stringContaining("权限不足"));

        fireEvent.click(screen.getByRole("button", { name: "重新加载题目" }));

        await waitFor(() => {
            expect(listQuestionsMock).toHaveBeenCalledTimes(2);
        });
    });

    it("fails closed before loading questions when capability loading fails", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(
            new ApiRequestError({
                status: 403,
                errorCode: "[ROLE_REQUIRED]",
                message: "权限不足",
                traceId: "trace-capability-403",
                details: null,
            }),
        );

        render(<SalesTrainerQuestionsPage />);

        expect(await screen.findByText("题库管理权限不足")).toBeTruthy();
        expect(screen.getByText(/trace-capability-403/)).toBeTruthy();
        expect(listQuestionsMock).not.toHaveBeenCalled();
        expect(listCategoriesMock).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "新建题目" })).toBeNull();
        expect(screen.queryByRole("button", { name: "AI 出题审核" })).toBeNull();
    });

    it("does not expose question write actions without manage_questions", async () => {
        getCapabilitiesMock.mockResolvedValueOnce({
            role: "viewer",
            role_label: "只读人员",
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

        render(<SalesTrainerQuestionsPage />);

        expect(await screen.findByText("题库管理权限不足")).toBeTruthy();
        expect(listQuestionsMock).not.toHaveBeenCalled();
        expect(listCategoriesMock).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: "新建题目" })).toBeNull();
        expect(screen.queryByRole("button", { name: "发布" })).toBeNull();
        expect(screen.queryByRole("button", { name: "归档" })).toBeNull();
    });
});
