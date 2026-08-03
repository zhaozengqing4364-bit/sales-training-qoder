import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import type { ReadinessReviewQueueV1 } from "@/lib/api/types/newcomer-training";
import { ReadinessReviewQueueWorkspace } from "./review-queue-workspace";

const { listReadinessReviews, push } = vi.hoisted(() => ({
    listReadinessReviews: vi.fn(),
    push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push }),
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api/client", () => {
    class MockApiRequestError extends Error {
        readonly status: number;

        constructor(payload: { status: number; message: string }) {
            super(payload.message);
            this.status = payload.status;
        }
    }
    return {
        ApiRequestError: MockApiRequestError,
        api: { admin: { newcomerTraining: { listReadinessReviews } } },
        getApiErrorMessage: (error: Error) => error.message,
    };
});

const queue: ReadinessReviewQueueV1 = {
    contract_version: "1",
    generated_at: "2026-07-18T00:00:00Z",
    data_freshness: "fresh",
    capabilities: ["readiness.queue.read"],
    items: [
        {
            object_id: "dossier-1",
            object_summary: {
                learner: {
                    learner_id: "learner-1",
                    name: "张三",
                    cohort_id: "cohort-1",
                    cohort_name: "七月新人班",
                },
                path: {
                    path_revision_id: "revision-1",
                    title: "新人销售基础训练",
                    revision_label: "首发版",
                },
                status: "ready_for_review",
            },
            queue_reason: "训练证据已满足前置条件，等待人工复核。",
            risk_band: "medium",
            evidence_gaps: ["customer_understanding"],
            reviewer_id: null,
            due_at: null,
            primary_action: {
                label: "复核训练档案",
                href: "/admin/newcomer-training/reviews/dossier-1",
            },
            capabilities: ["readiness.queue.read"],
            updated_at: "2026-07-18T00:00:00Z",
        },
    ],
    total: 1,
    limit: 20,
    offset: 0,
    applied_filters: {
        state: null,
        cohort_id: null,
        competency_key: null,
        reviewer_id: null,
        waiting_hours_gte: null,
    },
    sort: ["risk_desc", "waiting_time_desc"],
};

describe("readiness review queue workspace", () => {
    beforeEach(() => {
        listReadinessReviews.mockReset();
        push.mockReset();
    });

    it("renders the v2 queue with a single authoritative review link", async () => {
        listReadinessReviews.mockResolvedValue(queue);

        render(<ReadinessReviewQueueWorkspace />);

        expect(await screen.findByText("张三")).toBeTruthy();
        expect(screen.getByText("七月新人班 · 新人销售基础训练")).toBeTruthy();
        expect(screen.getByText("存在 1 项能力证据缺口")).toBeTruthy();
        expect(screen.queryByText("customer_understanding")).toBeNull();
        expect(screen.getByRole("link", { name: "复核训练档案" }).getAttribute("href"))
            .toBe("/admin/newcomer-training/reviews/dossier-1");
        expect(listReadinessReviews).toHaveBeenCalledWith({
            state: undefined,
            cohort_id: undefined,
            limit: 20,
            offset: 0,
        });
    });

    it("distinguishes permission denial from an empty queue", async () => {
        listReadinessReviews.mockRejectedValue(new ApiRequestError({
            status: 403,
            errorCode: "[READINESS_PERMISSION_DENIED]",
            message: "无权查看复核队列。",
        }));

        render(<ReadinessReviewQueueWorkspace />);

        expect(await screen.findByText("当前账号不能查看达标复核")).toBeTruthy();
        await waitFor(() => {
            expect(screen.queryByText("当前没有待复核档案")).toBeNull();
        });
    });
});
