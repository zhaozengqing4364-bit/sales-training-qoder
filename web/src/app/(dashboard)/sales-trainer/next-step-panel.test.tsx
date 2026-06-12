import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SalesTrainerNextStepPanel } from "./next-step-panel";

const { listPathsMock } = vi.hoisted(() => ({
    listPathsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>{children}</button>
    ),
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
            },
        },
    };
});

function pathResponse(aiCoachAvailable: boolean) {
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
                ai_coach_availability: {
                    enabled: aiCoachAvailable,
                    configured: aiCoachAvailable,
                    available: aiCoachAvailable,
                    coach_path: aiCoachAvailable ? "/sales-trainer/business-skills/coach" : null,
                    disabled_reason: aiCoachAvailable ? null : "AI 教练未启用。",
                    allowed_interaction_types: aiCoachAvailable ? ["single_choice", "multiple_choice"] : [],
                },
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

describe("SalesTrainerNextStepPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("falls back to AI coach when current business skills level has no backend recommendation", async () => {
        listPathsMock.mockResolvedValue(pathResponse(true));

        render(<SalesTrainerNextStepPanel unitId="business-unit" />);

        expect(await screen.findByText("去 AI 教练练一轮")).toBeTruthy();
        expect(screen.getByRole("link", { name: /进入 AI 教练/ }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills/coach",
        );
    });

    it("falls back to the learner home when AI coach is unavailable", async () => {
        listPathsMock.mockResolvedValue(pathResponse(false));

        render(<SalesTrainerNextStepPanel unitId="business-unit" />);

        expect(await screen.findByText("回到新人训练路径首页")).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看训练路径" }).getAttribute("href")).toBe(
            "/sales-trainer",
        );
    });
});
