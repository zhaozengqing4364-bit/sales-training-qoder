import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SalesTrainerNextStepPanel } from "./next-step-panel";

const { getJourneyMock, listPathsMock } = vi.hoisted(() => ({
    getJourneyMock: vi.fn(),
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
                getJourney: getJourneyMock,
                listPaths: listPathsMock,
            },
        },
    };
});

function journeyResponse(nextAction: null | {
    label: string;
    target_path: string;
}) {
    return {
        journey_id: "journey-user-1",
        learner_id: "user-1",
        learner_name: "新人",
        department: "销售一部",
        path_key: "newcomer_training_path_v1",
        path_revision_id: "revision-1",
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
            enabled: true,
            status: "in_progress",
            stage: "in_progress",
            passed: null,
            score: null,
            max_score: null,
            required: true,
            completion_satisfied: false,
            locked: false,
            block_reason: null,
            completion_rule: "passed",
            source: {
                path_revision_id: "revision-1",
                path_revision_no: 1,
            },
            learner_level_required: null,
            unmet_reasons: [],
            diagnostics: [],
            next_action: nextAction
                ? {
                    action_key: "continue_business_skills",
                    label: nextAction.label,
                    target_path: nextAction.target_path,
                    disabled: false,
                    disabled_reason: null,
                }
                : null,
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
    };
}

describe("SalesTrainerNextStepPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("uses the backend TrainingJourney next action", async () => {
        getJourneyMock.mockResolvedValue(journeyResponse({
            label: "继续训练",
            target_path: "/sales-trainer/business-skills",
        }));

        render(<SalesTrainerNextStepPanel unitId="business-unit" />);

        expect(await screen.findByText("商务技巧")).toBeTruthy();
        expect(screen.getByRole("link", { name: /继续训练/ }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills",
        );
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("does not synthesize an AI coach fallback when Journey has no next action", async () => {
        getJourneyMock.mockResolvedValue(journeyResponse(null));

        render(<SalesTrainerNextStepPanel unitId="business-unit" />);

        expect(await screen.findByText("回到新人训练路径首页")).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看训练路径" }).getAttribute("href")).toBe(
            "/sales-trainer",
        );
        expect(screen.queryByText("去 AI 教练练一轮")).toBeNull();
        expect(listPathsMock).not.toHaveBeenCalled();
    });
});
