import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    EvidenceDossierV1,
    ReadinessCompetencyProjection,
} from "@/lib/api/types/newcomer-training";

import { ReadinessDossierView } from "./readiness-dossier-view";

const { submitAppealMock } = vi.hoisted(() => ({
    submitAppealMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                submitAppeal: submitAppealMock,
            },
        },
    };
});

const COMPETENCIES: Array<[string, string]> = [
    ["product_knowledge", "产品知识"],
    ["customer_understanding", "客户理解"],
    ["needs_discovery", "需求发现"],
    ["value_expression", "价值表达"],
    ["objection_handling", "异议处理"],
    ["process_compliance", "流程与合规"],
    ["communication_structure", "沟通结构"],
];

function competency([competencyKey, title]: [string, string]): ReadinessCompetencyProjection {
    return {
        competency_key: competencyKey,
        title,
        description: `${title}训练说明`,
        status: competencyKey === "value_expression" ? "gap" : "sufficient",
        latest_result: "passed",
        latest_score: competencyKey === "value_expression" ? 68 : 90,
        latest_max_score: 100,
        trend: "stable",
        source_coverage: ["lesson"],
        evidence_count: 1,
        valid_evidence_count: 1,
        evidence_ids: [`evidence-${competencyKey}`],
        gap_reason: competencyKey === "value_expression" ? "完成价值表达补充录音" : null,
        review_prerequisite_met: competencyKey !== "value_expression",
    };
}

function dossierFixture(): EvidenceDossierV1 {
    return {
        contract_version: "1",
        generated_at: "2026-07-17T10:00:00Z",
        data_freshness: "fresh",
        capabilities: ["submit_appeal"],
        dossier_id: "dossier-1",
        dossier_version: 4,
        snapshot_id: "snapshot-1",
        snapshot_version: 2,
        snapshot_stale: false,
        learner: {
            learner_id: "learner-1",
            name: "新人小周",
            cohort_id: "cohort-1",
            cohort_name: "七月新人班",
        },
        path: {
            path_revision_id: "revision-1",
            title: "新人销售基础训练",
            revision_label: "首发版",
        },
        status: "retraining_assigned",
        status_label: "需要补充训练",
        summary: {
            eligibility: {
                eligible: false,
                required_activities_complete: true,
                competencies_sufficient: false,
                no_blocking_tasks: true,
                no_unresolved_quality_conflicts: true,
                missing_activity_ids: [],
                competency_gaps: ["value_expression"],
                quality_conflict_evidence_ids: [],
                reasons: ["价值表达仍需补充训练"],
            },
            completed_required_activities: 4,
            total_required_activities: 4,
            evidence_count: 7,
            stale_reason: null,
            risk_band: "high",
            risk_reasons: ["PRIVATE_RISK_REASON"],
        },
        competencies: COMPETENCIES.map(competency),
        evidence: [
            {
                evidence_id: "evidence-value_expression",
                competency_key: "value_expression",
                competency_title: "价值表达",
                source_activity_id: "audio-pitch",
                outcome_id: "outcome-1",
                outcome_version: 1,
                evidence_type: "录音讲解",
                observed_score: 68,
                observed_max_score: 100,
                observed_result: "not_passed",
                quality: "verified",
                validity: "valid",
                observed_at: "2026-07-17T09:00:00Z",
            },
        ],
        activities: [],
        ai_assessment: {
            status: "completed",
            label: "辅助摘要已生成",
            message: "可供培训负责人参考",
            draft: { raw_prompt: "PRIVATE_RAW_AI_DRAFT" },
            evidence_ids: ["evidence-value_expression"],
        },
        human_decision: {
            decision_id: "decision-1",
            snapshot_id: "snapshot-1",
            decision_type: "request_retraining",
            decision_label: "需要补充训练",
            status: "active",
            reviewer_id: "reviewer-1",
            competency_keys: ["value_expression"],
            evidence_ids: ["evidence-value_expression"],
            reason: "请补充一次价值表达录音。",
            notes: "PRIVATE_REVIEWER_NOTE",
            created_at: "2026-07-17T09:30:00Z",
            supersedes_decision_id: null,
        },
        decision_history: [],
        retraining: [
            {
                assignment_id: "assignment-1",
                activity_source: "existing_published",
                activity_id: "audio-pitch",
                activity_title: "价值表达补充录音",
                target_competency_keys: ["value_expression"],
                source_evidence_ids: ["evidence-value_expression"],
                reason: "用客户语言重新说明核心价值。",
                due_at: null,
                status: "assigned",
                version: 1,
                assigned_at: "2026-07-17T09:30:00Z",
                completed_at: null,
                next_action: {
                    label: "开始补充录音",
                    href: "/newcomer-training/activities/audio-pitch",
                },
            },
        ],
        appeals: [],
        next_actions: [
            {
                label: "开始补充录音",
                href: "/newcomer-training/activities/audio-pitch",
            },
        ],
    };
}

describe("ReadinessDossierView", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        submitAppealMock.mockResolvedValue({ appeal_id: "appeal-1", status: "submitted" });
    });

    it("shows the seven governed competencies, human result and in-flow retraining without private fields", () => {
        render(<ReadinessDossierView dossier={dossierFixture()} />);

        for (const [, title] of COMPETENCIES) {
            expect(screen.getByRole("heading", { name: title })).toBeTruthy();
        }
        expect(screen.getByText("请补充一次价值表达录音。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "开始补充录音" }).getAttribute("href")).toBe(
            "/newcomer-training/activities/audio-pitch",
        );
        expect(screen.queryByText("PRIVATE_RISK_REASON")).toBeNull();
        expect(screen.queryByText("PRIVATE_REVIEWER_NOTE")).toBeNull();
        expect(screen.queryByText("PRIVATE_RAW_AI_DRAFT")).toBeNull();
    });

    it("submits an appeal against the human decision and keeps the statement on failure", async () => {
        submitAppealMock.mockRejectedValueOnce(new Error("暂时无法提交"));
        render(<ReadinessDossierView dossier={dossierFixture()} />);

        fireEvent.change(screen.getByLabelText("情况说明"), {
            target: { value: "复核结论引用了错误事实。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交申诉" }));

        await waitFor(() => {
            expect(submitAppealMock).toHaveBeenCalledWith(
                {
                    target_type: "decision",
                    target_id: "decision-1",
                    dossier_version: 4,
                    reason_category: "fact_error",
                    statement: "复核结论引用了错误事实。",
                },
                expect.any(String),
            );
        });
        expect(screen.getByDisplayValue("复核结论引用了错误事实。")).toBeTruthy();
        expect((await screen.findByRole("alert")).textContent).toContain("暂时无法提交");
    });
});
