import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EvidenceDossierV1 } from "@/lib/api/types/newcomer-training";
import { ReadinessDossierWorkspace } from "./review-dossier-workspace";

const {
    getReadinessReview,
    rebuildReadinessReview,
    recordReadinessDecision,
} = vi.hoisted(() => ({
    getReadinessReview: vi.fn(),
    rebuildReadinessReview: vi.fn(),
    recordReadinessDecision: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ learnerId: "dossier-1" }),
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
        api: {
            admin: {
                newcomerTraining: {
                    getReadinessReview,
                    rebuildReadinessReview,
                    recordReadinessDecision,
                },
            },
        },
        getApiErrorMessage: (error: Error) => error.message,
    };
});

vi.mock("@/lib/sales-trainer/idempotency", () => ({
    generateClientToken: () => "idempotency-1",
}));

function dossier(eligible = true): EvidenceDossierV1 {
    return {
        contract_version: "1",
        generated_at: "2026-07-18T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["readiness.dossier.read", "readiness.review", "readiness.rebuild"],
        dossier_id: "dossier-1",
        dossier_version: 3,
        snapshot_id: "snapshot-1",
        snapshot_version: 2,
        snapshot_stale: false,
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
        status: eligible ? "ready_for_review" : "incomplete",
        status_label: eligible ? "等待人工复核" : "训练证据待补充",
        summary: {
            eligibility: {
                eligible,
                required_activities_complete: eligible,
                competencies_sufficient: eligible,
                no_blocking_tasks: true,
                no_unresolved_quality_conflicts: true,
                missing_activity_ids: eligible ? [] : ["activity-1"],
                competency_gaps: eligible ? [] : ["customer_understanding"],
                quality_conflict_evidence_ids: [],
                reasons: eligible ? [] : ["客户理解能力证据仍不完整。"],
            },
            completed_required_activities: eligible ? 5 : 4,
            total_required_activities: 5,
            evidence_count: 1,
            stale_reason: null,
            risk_band: eligible ? "low" : "medium",
            risk_reasons: [],
        },
        competencies: [
            {
                competency_key: "customer_understanding",
                title: "客户理解",
                description: "能够识别客户背景和目标。",
                status: eligible ? "sufficient" : "gap",
                latest_result: eligible ? "已覆盖" : "待补充",
                latest_score: null,
                latest_max_score: null,
                trend: "stable",
                source_coverage: ["audio_assessment"],
                evidence_count: 1,
                valid_evidence_count: eligible ? 1 : 0,
                evidence_ids: ["evidence-1"],
                gap_reason: eligible ? null : "缺少有效录音证据。",
                review_prerequisite_met: eligible,
            },
        ],
        evidence: [
            {
                evidence_id: "evidence-1",
                competency_key: "customer_understanding",
                competency_title: "客户理解",
                source_activity_id: "activity-1",
                outcome_id: "outcome-1",
                outcome_version: 1,
                evidence_type: "audio_assessment",
                observed_score: 85,
                observed_max_score: 100,
                observed_result: "已达到录音讲解要求",
                quality: "valid",
                validity: "active",
                observed_at: "2026-07-18T00:00:00Z",
            },
        ],
        activities: [],
        ai_assessment: {
            status: "completed",
            label: "辅助评估已生成",
            message: "表达结构清楚，仍需人工核验证据范围。",
            evidence_ids: ["evidence-1"],
        },
        human_decision: null,
        decision_history: [],
        retraining: [],
        appeals: [],
        next_actions: [{ label: "记录复核结论", command: "record_decision" }],
    };
}

describe("readiness dossier workspace", () => {
    beforeEach(() => {
        getReadinessReview.mockReset();
        rebuildReadinessReview.mockReset();
        recordReadinessDecision.mockReset();
    });

    it("separates deterministic rules, AI inference, evidence, and the human decision", async () => {
        getReadinessReview.mockResolvedValue(dossier(true));
        recordReadinessDecision.mockResolvedValue({ decision_id: "decision-1" });

        render(<ReadinessDossierWorkspace />);

        expect(await screen.findByText("规则校验")).toBeTruthy();
        expect(screen.getByText("AI 辅助评估")).toBeTruthy();
        expect(screen.getByText("该内容属于辅助推断，不会自动授予基础训练达标结论。")).toBeTruthy();
        expect(screen.getByText(/录音讲解 · 已达到录音讲解要求/)).toBeTruthy();

        fireEvent.change(screen.getByLabelText("复核原因"), {
            target: { value: "证据范围完整，人工复核通过。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存复核结论" }));

        await waitFor(() => expect(recordReadinessDecision).toHaveBeenCalledWith(
            "dossier-1",
            expect.objectContaining({
                decision_type: "approve_foundation_ready",
                expected_dossier_version: 3,
                snapshot_id: "snapshot-1",
                reason: "证据范围完整，人工复核通过。",
                competency_keys: ["customer_understanding"],
                evidence_ids: ["evidence-1"],
            }),
            "idempotency-1",
        ));
    });

    it("does not default to approval when deterministic prerequisites are incomplete", async () => {
        getReadinessReview.mockResolvedValue(dossier(false));

        render(<ReadinessDossierWorkspace />);

        const decision = await screen.findByLabelText("复核结论") as HTMLSelectElement;
        await waitFor(() => expect(decision.value).toBe("request_more_evidence"));
        const approveOption = screen.getByRole("option", {
            name: "确认基础训练达标（前置条件未满足）",
        }) as HTMLOptionElement;
        expect(approveOption.disabled).toBe(true);
        expect(screen.getByText("客户理解能力证据仍不完整。")).toBeTruthy();
    });
});
