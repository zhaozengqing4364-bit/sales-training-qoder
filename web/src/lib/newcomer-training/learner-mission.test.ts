import { describe, expect, it } from "vitest";

import type { FoundationJourneyProjection } from "@/lib/api/types/newcomer-training";
import { missionFromFoundationJourney } from "./learner-mission";

function journey(): FoundationJourneyProjection {
    return {
        contract_version: "journey_projection_v1",
        generated_at: "2026-07-18T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["newcomer.journey.read"],
        status: "active",
        status_label: "训练进行中",
        status_reason: null,
        enrollment: {
            enrollment_id: "enrollment-1",
            status: "active",
            revision_id: "revision-1",
            version: 1,
        },
        path: {
            path_id: "path-1",
            title: "新人销售基础训练",
            revision_label: "首发版",
        },
        progress: { completed_required: 0, total_required: 5, percentage: 0 },
        stages: [
            {
                stage_id: "stage-1",
                sequence: 1,
                title: "建立基础",
                objective: "掌握产品与客户基础",
                status: "current",
                activities: [
                    {
                        activity_id: "lesson-1",
                        type: "lesson",
                        title: "学习产品知识",
                        objective: "准确说明产品价值",
                        status: "available",
                        status_label: "可以开始",
                        estimated_minutes: 20,
                        required: true,
                        blocked_reason: null,
                        latest_attempt_id: null,
                        latest_outcome_id: null,
                    },
                ],
            },
        ],
        current_activity: null,
        background_tasks: [],
        recent_outcomes: [],
        primary_action: null,
        projection_version: 1,
    };
}

describe("missionFromFoundationJourney", () => {
    it("只在当前活动与主操作一致时创建任务视图", () => {
        const input = journey();
        input.current_activity = input.stages[0].activities[0];
        input.primary_action = {
            command_type: "start",
            activity_id: "lesson-1",
            label: "开始学习",
            href: "/newcomer-training/activities/lesson-1",
        };

        expect(missionFromFoundationJourney(input)).toMatchObject({
            activityId: "lesson-1",
            activityType: "lesson",
            actionLabel: "开始学习",
            phaseLabel: "建立基础",
        });
    });

    it("没有唯一当前操作时不伪造任务", () => {
        expect(missionFromFoundationJourney(journey())).toBeNull();
    });
});
