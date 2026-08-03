import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FoundationQuestionReviewWorkspace } from "./question-review-workspace";

const listCandidatesV2 = vi.hoisted(() => vi.fn());
const getQuestionGenerationOptions = vi.hoisted(() => vi.fn());
const listQuestionGenerationBatches = vi.hoisted(() => vi.fn());
const listResourcesV2 = vi.hoisted(() => vi.fn());
const startQuestionGenerationV2 = vi.hoisted(() => vi.fn());
const previewCandidateBulkReview = vi.hoisted(() => vi.fn());
const confirmCandidateBulkReview = vi.hoisted(() => vi.fn());
const replaceMock = vi.hoisted(() => vi.fn());

vi.mock("@/components/admin/newcomer-training/workspace-nav", () => ({
    FoundationAdminCapabilityBoundary: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock("next/link", () => ({
    default: ({ href, children, prefetch, ...props }: { href: string; children: ReactNode; prefetch?: boolean }) => {
        void prefetch;
        return <a href={href} {...props}>{children}</a>;
    },
}));
vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/newcomer-training/questions",
    useRouter: () => ({ replace: replaceMock }),
    useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children, open }: { children: ReactNode; open: boolean }) => open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
}));
vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            newcomerTraining: {
                listCandidatesV2,
                getQuestionGenerationOptions,
                listQuestionGenerationBatches,
                listResourcesV2,
                startQuestionGenerationV2,
                previewCandidateBulkReview,
                confirmCandidateBulkReview,
            },
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

const candidates = [
    {
        candidate_id: "candidate-1",
        batch_id: "batch-1",
        status: "generated",
        version: 1,
        risk_level: "normal",
        content: {
            question_type: "single_choice",
            stem: "客户最关心的业务结果是什么？",
            options: [
                { option_id: "option-1", text: "业务连续性", is_correct: true },
                { option_id: "option-2", text: "产品颜色", is_correct: false },
            ],
            reference_answer: null,
            rubric: null,
            explanation: "应先确认客户业务目标。",
            difficulty: "easy",
            competency_keys: ["discovery"],
            source_anchor_ids: ["anchor-1"],
        },
        gate_status: "passed",
        gate_results: {},
        source_revision_id: "source-revision-1",
        learning_unit_revision_id: "unit-revision-1",
        reviewed_by: null,
        review_reason: null,
        created_at: "2026-07-17T08:00:00Z",
    },
    {
        candidate_id: "candidate-2",
        batch_id: "batch-1",
        status: "generated",
        version: 1,
        risk_level: "high",
        content: {
            question_type: "short_answer",
            stem: "如何确认客户决策链？",
            options: [],
            reference_answer: "识别决策人、影响人和使用人。",
            rubric: null,
            explanation: "答案必须覆盖三类角色。",
            difficulty: "medium",
            competency_keys: ["stakeholder_mapping"],
            source_anchor_ids: ["anchor-2"],
        },
        gate_status: "needs_review",
        gate_results: {},
        source_revision_id: "source-revision-1",
        learning_unit_revision_id: "unit-revision-1",
        reviewed_by: null,
        review_reason: null,
        created_at: "2026-07-17T08:05:00Z",
    },
] as const;

function renderWorkspace() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return render(
        <QueryClientProvider client={client}>
            <FoundationQuestionReviewWorkspace />
        </QueryClientProvider>,
    );
}

describe("FoundationQuestionReviewWorkspace", () => {
    beforeEach(() => {
        listCandidatesV2.mockReset();
        getQuestionGenerationOptions.mockReset();
        listQuestionGenerationBatches.mockReset();
        listResourcesV2.mockReset();
        startQuestionGenerationV2.mockReset();
        previewCandidateBulkReview.mockReset();
        confirmCandidateBulkReview.mockReset();
        replaceMock.mockReset();
        listCandidatesV2.mockResolvedValue({ items: candidates, total: candidates.length });
        getQuestionGenerationOptions.mockResolvedValue({
            ready: true,
            empty_message: null,
            prompt_options: [{ template_id: "question-generation", revision_id: "prompt-v1", revision_no: 1, label: "题目生成模板 · 第 1 版" }],
            model_routing_options: [{ profile_id: "question-models", revision_id: "route-v1", revision_no: 1, label: "题目生成模型策略 · 第 1 版" }],
        });
        listQuestionGenerationBatches.mockResolvedValue({ items: [], limit: 30 });
        listResourcesV2.mockImplementation(({ resource_type }: { resource_type: string }) => Promise.resolve({
            items: resource_type === "source_document"
                ? [{ resource_id: "source-1", title: "销售基础材料", status: "active", published_revision_id: "source-revision-1", working_revision_id: null }]
                : [{ resource_id: "unit-1", title: "客户价值学习", status: "active", published_revision_id: "unit-revision-1", working_revision_id: null }],
            total: 1,
        }));
        startQuestionGenerationV2.mockResolvedValue({ batch_id: "batch-new", status: "queued", task_id: "task-new" });
        previewCandidateBulkReview.mockResolvedValue({
            review_id: "review-1",
            preview_token: "preview-token",
            impact_hash: "impact-hash",
            eligible_count: 2,
            failure_count: 0,
            expires_at: "2026-07-17T09:00:00Z",
            items: candidates.map((candidate) => ({
                candidate_id: candidate.candidate_id,
                status: "eligible",
                reason: null,
            })),
        });
        confirmCandidateBulkReview.mockResolvedValue({
            succeeded_count: 1,
            failure_count: 1,
            items: [
                { candidate_id: "candidate-1", status: "succeeded", message: "已批准并写入正式题库" },
                { candidate_id: "candidate-2", status: "failed", message: "来源锚点已变化，请重新核对" },
            ],
        });
    });

    it("requests a bounded server page for the review queue", async () => {
        renderWorkspace();

        await waitFor(() => expect(listCandidatesV2).toHaveBeenCalledWith({
            status: "generated",
            batch_id: undefined,
            search: undefined,
            page: 1,
            page_size: 20,
        }));
        expect(await screen.findByText(/共 2 题 · 第 1 页/)).toBeTruthy();
    });

    it("keeps a partial bulk result visible instead of reporting full success", async () => {
        renderWorkspace();

        fireEvent.click(await screen.findByLabelText("选择题目：客户最关心的业务结果是什么？"));
        fireEvent.click(screen.getByLabelText("选择题目：如何确认客户决策链？"));
        fireEvent.change(screen.getByLabelText("审核依据"), {
            target: { value: "已逐题核对答案、来源与能力映射" },
        });
        fireEvent.click(screen.getByRole("button", { name: "预览批准入库" }));

        expect(await screen.findByRole("heading", { name: "批量审核影响预览" })).toBeTruthy();
        expect(screen.getByText("2 题")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "确认批准入库" }));

        expect(await screen.findByText("批量审核部分完成")).toBeTruthy();
        expect(screen.getByRole("status").textContent).toContain("成功 1 题，未成功 1 题");
        expect(screen.getByText("来源锚点已变化，请重新核对")).toBeTruthy();
        expect(screen.getByRole("button", { name: "关闭" })).toBeTruthy();
        expect(confirmCandidateBulkReview).toHaveBeenCalledTimes(1);
    });

    it("starts a durable generation batch from safe published options", async () => {
        renderWorkspace();

        fireEvent.change(await screen.findByLabelText("已发布材料"), {
            target: { value: "source-revision-1" },
        });
        fireEvent.change(screen.getByLabelText("已发布学习单元"), {
            target: { value: "unit-revision-1" },
        });
        fireEvent.click(screen.getByRole("button", { name: "开始生成候选题" }));

        await waitFor(() => expect(startQuestionGenerationV2).toHaveBeenCalledTimes(1));
        expect(startQuestionGenerationV2.mock.calls[0]?.[0]).toEqual({
            source_revision_id: "source-revision-1",
            learning_unit_revision_id: "unit-revision-1",
            requested_count: 10,
            prompt_template_id: "question-generation",
            prompt_revision_id: "prompt-v1",
            model_routing_profile_id: "question-models",
            model_routing_revision_id: "route-v1",
        });
        expect((await screen.findByRole("status")).textContent).toContain("任务已提交");
        expect(screen.queryByText(/prompt-v1|route-v1/)).toBeNull();
    });
});
