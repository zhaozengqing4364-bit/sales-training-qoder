import { describe, expect, it } from "vitest";

import { toTeamJourneyRow } from "./view-models";

describe("toTeamJourneyRow", () => {
    it("maps the v2 admin learner projection without recomputing progress", () => {
        const row = toTeamJourneyRow({
            learner: { learner_id: "learner-1", name: " 张三 " },
            cohort: { cohort_id: "cohort-1", name: "华东新人班" },
            enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "rev-1", version: 1 },
            path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" },
            status: "active",
            status_label: "训练进行中",
            progress: { completed_required: 2, total_required: 5, percentage: 40 },
            current_activity: {
                activity_id: "a1",
                type: "quiz",
                title: "知识测验",
                objective: "验证知识掌握",
                status: "needs_remediation",
                status_label: "需要补练",
                estimated_minutes: 10,
                required: true,
                blocked_reason: null,
                latest_attempt_id: "attempt-1",
                latest_outcome_id: "outcome-1",
            },
            primary_action: null,
            updated_at: "2026-07-18T00:00:00Z",
        });
        expect(row).toEqual({
            learnerId: "learner-1",
            learnerName: "张三",
            currentPhase: "知识测验",
            progressPercent: 40,
            completedCount: 2,
            totalRequired: 5,
            riskLabels: ["知识测验"],
        });
    });

    it("uses completed label when current phase is absent", () => {
        const row = toTeamJourneyRow({
            learner: { learner_id: "learner-2", name: "" },
            cohort: { cohort_id: "cohort-1", name: "新人班" },
            enrollment: { enrollment_id: "enrollment-2", status: "active", revision_id: "rev-1", version: 1 },
            path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" },
            status: "completed",
            status_label: "训练已完成",
            progress: { completed_required: 3, total_required: 3, percentage: 100 },
            current_activity: null,
            primary_action: null,
            updated_at: "2026-07-18T00:00:00Z",
        });
        expect(row.learnerName).toBe("未命名学员");
        expect(row.currentPhase).toBe("训练已完成");
    });
});
