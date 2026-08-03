import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FoundationAssessmentOperationsWorkspace } from "./assessment-operations-workspace";

const listAssessmentTasks = vi.hoisted(() => vi.fn());
const getAssessmentTaskDetail = vi.hoisted(() => vi.fn());
const redriveAssessmentTask = vi.hoisted(() => vi.fn());
const cancelAssessmentTask = vi.hoisted(() => vi.fn());
const previewAudioRegrade = vi.hoisted(() => vi.fn());
const confirmAudioRegrade = vi.hoisted(() => vi.fn());
const previewAudioInvalidation = vi.hoisted(() => vi.fn());
const confirmAudioInvalidation = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => <a href={href} {...props}>{children}</a>,
}));
vi.mock("@/components/admin/newcomer-training/workspace-nav", () => ({
    FoundationAdminCapabilityBoundary: ({ children }: { children: ReactNode }) => <>{children}</>,
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
                listAssessmentTasks,
                getAssessmentTaskDetail,
                redriveAssessmentTask,
                cancelAssessmentTask,
                previewAudioRegrade,
                confirmAudioRegrade,
                previewAudioInvalidation,
                confirmAudioInvalidation,
            },
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

function renderWorkspace() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return render(
        <QueryClientProvider client={client}>
            <FoundationAssessmentOperationsWorkspace />
        </QueryClientProvider>,
    );
}

describe("FoundationAssessmentOperationsWorkspace", () => {
    beforeEach(() => {
        listAssessmentTasks.mockReset();
        getAssessmentTaskDetail.mockReset();
        redriveAssessmentTask.mockReset();
        cancelAssessmentTask.mockReset();
        previewAudioRegrade.mockReset();
        confirmAudioRegrade.mockReset();
        previewAudioInvalidation.mockReset();
        confirmAudioInvalidation.mockReset();
        listAssessmentTasks.mockResolvedValue({
            items: [{
                task_id: "task-1",
                category: "录音评测",
                business_object: "王小明 · 异议处理录音",
                resource_type: "audio_submission",
                resource_id: "submission-1",
                state: "running",
                state_label: "处理中",
                attempt_count: 1,
                waiting_since: "2026-07-17T07:30:00Z",
                updated_at: "2026-07-17T07:35:00Z",
                failure: null,
                available_actions: ["查看详情", "申请取消"],
            }],
            total: 1,
            is_partial: false,
        });
        getAssessmentTaskDetail.mockResolvedValue({
            task_id: "task-1",
            organization_id: "organization-1",
            resource_type: "audio_submission",
            resource_id: "submission-1",
            state: "running",
            status_label: "处理中",
            current_step: "正在生成结构化评分",
            progress: { current: 2, total: 3, label: "评测进度" },
            can_cancel: true,
            can_redrive: false,
            result_kind: "partial_success",
            result_location: "/admin/newcomer-training/assessments/submission-1",
            partial_success_message: "转写结果已保存，结构化评分仍在处理。",
            error: null,
            attempt_count: 1,
            max_attempts: 3,
            updated_at: "2026-07-17T07:35:00Z",
            stale: true,
        });
        cancelAssessmentTask.mockResolvedValue({ task_id: "task-1", state: "cancel_requested" });
        redriveAssessmentTask.mockResolvedValue({ task_id: "task-2", state: "queued" });
        previewAudioRegrade.mockResolvedValue({
            preview_token: "regrade-preview",
            impact_hash: "a".repeat(64),
            expires_at: "2026-07-17T09:00:00Z",
            change_type: "regrade",
            summary: { affected_submission_count: 1, preserves_historical_result: true },
        });
        confirmAudioRegrade.mockResolvedValue({ submission_id: "submission-1", task_id: "task-2" });
        previewAudioInvalidation.mockResolvedValue({
            preview_token: "invalidate-preview",
            impact_hash: "b".repeat(64),
            expires_at: "2026-07-17T09:00:00Z",
            change_type: "invalidation",
            summary: { affected_submission_count: 1, preserves_historical_result: true },
        });
        confirmAudioInvalidation.mockResolvedValue({ submission_id: "submission-1", state: "invalidated" });
    });

    it("shows stale long-task state and requires a scoped reason before cancellation", async () => {
        renderWorkspace();

        fireEvent.click(await screen.findByRole("button", { name: /录音评测.*王小明/ }));

        expect(await screen.findByText("任务信息已超过 5 分钟未更新，执行操作前请先刷新。")).toBeTruthy();
        expect(screen.getByText("转写结果已保存，结构化评分仍在处理。")).toBeTruthy();
        expect(screen.getByText("2 / 3")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "预览取消" }));

        expect(screen.getByText("录音评测 · 王小明 · 异议处理录音 · 1 个业务对象")).toBeTruthy();
        fireEvent.change(screen.getByLabelText("操作原因"), {
            target: { value: "任务长时间未更新，需要在安全检查点停止" },
        });
        fireEvent.click(screen.getByRole("button", { name: "确认申请取消" }));

        expect(await screen.findByRole("status")).toBeTruthy();
        expect(screen.getByRole("status").textContent).toContain("取消申请已记录");
        expect(cancelAssessmentTask).toHaveBeenCalledWith(
            "task-1",
            "任务长时间未更新，需要在安全检查点停止",
            expect.any(String),
        );
    });

    it("uses server preview before appending a governed audio regrade", async () => {
        listAssessmentTasks.mockResolvedValue({
            items: [{
                task_id: "task-1",
                category: "录音评测",
                business_object: "王小明 · 异议处理录音",
                resource_type: "audio_submission",
                resource_id: "submission-1",
                state: "succeeded",
                state_label: "已完成",
                attempt_count: 1,
                waiting_since: "2026-07-17T07:30:00Z",
                updated_at: "2026-07-17T07:40:00Z",
                failure: null,
                available_actions: ["查看详情", "预览重评", "预览失效"],
            }],
            total: 1,
            is_partial: false,
        });
        getAssessmentTaskDetail.mockResolvedValue({
            task_id: "task-1",
            organization_id: "organization-1",
            resource_type: "audio_submission",
            resource_id: "submission-1",
            state: "succeeded",
            status_label: "已完成",
            current_step: "已完成",
            progress: null,
            can_cancel: false,
            can_redrive: false,
            result_kind: "success",
            result_location: "/admin/newcomer-training/assessments/submission-1",
            partial_success_message: null,
            error: null,
            attempt_count: 1,
            max_attempts: 3,
            updated_at: "2026-07-17T07:40:00Z",
            stale: false,
        });
        renderWorkspace();

        fireEvent.click(await screen.findByRole("button", { name: /录音评测.*王小明/ }));
        fireEvent.click(await screen.findByRole("button", { name: "预览重评" }));
        fireEvent.change(screen.getByLabelText("操作原因"), {
            target: { value: "评分标准修订后需要追加新评分版本" },
        });
        fireEvent.click(screen.getByRole("button", { name: "生成影响预览" }));

        expect(await screen.findByText("将追加一个新的评分版本，现有历史结果不会被覆盖。")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "确认重评当前录音" }));

        expect(await screen.findByRole("status")).toBeTruthy();
        expect(screen.getByRole("status").textContent).toContain("重评任务已创建");
        expect(previewAudioRegrade).toHaveBeenCalledWith(
            "submission-1",
            "评分标准修订后需要追加新评分版本",
        );
        expect(confirmAudioRegrade).toHaveBeenCalledWith(
            "submission-1",
            expect.objectContaining({ preview_token: "regrade-preview" }),
            expect.any(String),
        );
    });
});
