import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LearningPathPage from "./page";

const { getMineMock } = vi.hoisted(() => ({
    getMineMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
    }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
        <a href={href} className={className}>{children}</a>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            learningPath: {
                ...actual.api.learningPath,
                getMine: getMineMock,
            },
        },
    };
});

describe("LearningPathPage", () => {
    beforeEach(() => {
        getMineMock.mockReset();
        getMineMock.mockResolvedValue({
            user_id: "learner-1",
            path_type: "weakness_driven",
            recommended_template_ids: ["template-product"],
            recommendation_reasons: [
                {
                    dimension_name: "product_knowledge",
                    score: 51,
                    source_report_id: "report-1",
                    recommended_template_id: "template-product",
                },
            ],
            next_task: {
                title: "产品知识专项",
                state: "available",
                primary_cta: "开始专项练习",
                reason: "产品知识得分偏低，建议专项练习。",
                estimated_duration_minutes: 10,
                failure_reason: null,
                retry_action: null,
            },
            stages: [
                {
                    template_stage_key: "template_stage_product",
                    name: "产品证据表达",
                    state: "available",
                    prerequisites: [],
                    completion_policy: { min_score: 7 },
                    report_url: "/practice/session-1/report",
                    failure_reason: null,
                    retry_action: null,
                },
                {
                    template_stage_key: "template_stage_review",
                    name: "主管认证复核",
                    state: "pending_review",
                    prerequisites: [{ template_stage_key: "template_stage_product", required_result: "completed" }],
                    completion_policy: { min_score: 8 },
                    report_url: null,
                    failure_reason: null,
                    retry_action: null,
                },
            ],
            generated_at: "2026-05-13T00:00:00Z",
        });
    });

    it("renders full learning path stages with prerequisites", async () => {
        render(<LearningPathPage />);

        expect(await screen.findByText("我的学习路径")).toBeTruthy();
        expect(screen.getByText("产品证据表达")).toBeTruthy();
        expect(screen.getByText("主管认证复核")).toBeTruthy();
        expect(screen.getByText("前置条件：template_stage_product")).toBeTruthy();
        expect(screen.getByText("完成标准：最低 7 分")).toBeTruthy();
    });

    it("renders failure reason and retry action", async () => {
        getMineMock.mockResolvedValueOnce({
            user_id: "learner-1",
            path_type: "weakness_driven",
            recommended_template_ids: ["template-product"],
            recommendation_reasons: [],
            next_task: {
                title: "异议处理复训",
                state: "failed",
                primary_cta: "重新训练",
                reason: "异议处理得分偏低，建议专项练习。",
                estimated_duration_minutes: null,
                failure_reason: "未达到最低分",
                retry_action: "retry_current",
            },
            stages: [
                {
                    template_stage_key: "template_stage_objection",
                    name: "异议处理",
                    state: "failed",
                    prerequisites: [],
                    completion_policy: {},
                    report_url: null,
                    failure_reason: "未达到最低分",
                    retry_action: "retry_current",
                },
            ],
            generated_at: "2026-05-13T00:00:00Z",
        });

        render(<LearningPathPage />);

        expect(await screen.findByText("异议处理复训")).toBeTruthy();
        expect(screen.getAllByText("失败原因：未达到最低分").length).toBeGreaterThan(0);
        expect(screen.getAllByText("复训动作：retry_current").length).toBeGreaterThan(0);
        expect(screen.getByRole("link", { name: /重新训练/ }).getAttribute("href")).toBe("/training");
    });

    it("renders pending review placeholder for certification path", async () => {
        render(<LearningPathPage />);

        expect(await screen.findByText("认证路径已进入等待主管复核占位状态。")).toBeTruthy();
    });

    it("renders retraining required message for rejected certification path", async () => {
        getMineMock.mockResolvedValueOnce({
            user_id: "learner-1",
            path_type: "weakness_driven",
            recommended_template_ids: ["template-review"],
            recommendation_reasons: [],
            next_task: {
                title: "主管认证复训",
                state: "retraining_required",
                primary_cta: "开始复训",
                reason: "主管要求补强认证证据。",
                estimated_duration_minutes: 10,
                failure_reason: "认证未通过，需要复训价值逻辑。",
                retry_action: "retry_current",
            },
            stages: [
                {
                    template_stage_key: "template_stage_certification_review",
                    name: "主管认证复核",
                    state: "retraining_required",
                    prerequisites: [],
                    completion_policy: { min_score: 8 },
                    report_url: "/practice/session-cert/report",
                    failure_reason: "认证未通过，需要复训价值逻辑。",
                    retry_action: "retry_current",
                },
            ],
            generated_at: "2026-05-13T00:00:00Z",
        });

        render(<LearningPathPage />);

        expect(await screen.findByText("主管认证复训")).toBeTruthy();
        expect(screen.getByText("主管已要求复训，请完成复训后再回到认证路径。"))
            .toBeTruthy();
        expect(screen.getAllByText("复训动作：retry_current").length).toBeGreaterThan(0);
    });
});
