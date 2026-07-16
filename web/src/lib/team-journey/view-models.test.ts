import { describe, expect, it } from "vitest";

import { toTeamJourneyRow } from "./view-models";

describe("toTeamJourneyRow", () => {
    it("maps summary DTO fields without requiring full journey phases", () => {
        const row = toTeamJourneyRow({
            learner_id: "learner-1",
            learner_name: " 张三 ",
            team: { team_id: "t1", code: "east", name: "华东" },
            summary: {
                path_revision_id: "rev-1",
                path_title: "新人训练",
                current_phase: { phase_id: "p1", title: "阶段一", status: "in_progress" },
                progress: { completed: false, completed_count: 2, total_required: 5, percent: 40 },
                primary_next_action: {
                    activity_id: "a1",
                    activity_type: "quiz",
                    action_key: "start_quiz",
                    label: "开始测验",
                },
                risk_labels: ["知识测验", "录音讲解"],
            },
        });
        expect(row).toEqual({
            learnerId: "learner-1",
            learnerName: "张三",
            currentPhase: "阶段一",
            progressPercent: 40,
            completedCount: 2,
            totalRequired: 5,
            riskLabels: ["知识测验", "录音讲解"],
        });
    });

    it("uses completed label when current phase is absent", () => {
        const row = toTeamJourneyRow({
            learner_id: "learner-2",
            learner_name: "",
            team: null,
            summary: {
                path_revision_id: "rev-1",
                path_title: "新人训练",
                current_phase: null,
                progress: { completed: true, completed_count: 3, total_required: 3, percent: 100 },
                primary_next_action: null,
                risk_labels: [],
            },
        });
        expect(row.learnerName).toBe("未命名学员");
        expect(row.currentPhase).toBe("已完成");
    });
});
