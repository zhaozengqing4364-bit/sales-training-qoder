import { describe, expect, it } from "vitest";

import type {
    FoundationJourneyProjection,
    FoundationNotificationPage,
    FoundationTaskStatusPage,
} from "@/lib/api/types/newcomer-training";
import {
    toJourneyPageViewModel,
    toNotificationCenterViewModel,
} from "./view-models";

function journey(): FoundationJourneyProjection {
    return {
        contract_version: "journey_projection_v1",
        generated_at: "2026-07-17T10:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_journey"],
        status: "active",
        status_label: "训练进行中",
        status_reason: null,
        enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "revision-1", version: 1 },
        path: { path_id: "path-1", title: "新人销售基础训练", revision_label: "首发版" },
        progress: { completed_required: 1, total_required: 2, percentage: 7 },
        stages: [{
            stage_id: "stage-1",
            sequence: 1,
            title: "产品基础",
            objective: "准确说明产品价值",
            status: "current",
            activities: [{
                activity_id: "lesson-1",
                type: "lesson",
                title: "产品价值学习",
                objective: "理解客户价值",
                status: "available",
                status_label: "可开始",
                estimated_minutes: 15,
                required: true,
                blocked_reason: null,
                latest_attempt_id: null,
                latest_outcome_id: null,
            }],
        }],
        current_activity: null,
        background_tasks: [],
        recent_outcomes: [],
        primary_action: null,
        projection_version: 1,
    };
}

describe("foundation learner view models", () => {
    it("keeps backend-projected progress authoritative", () => {
        const model = toJourneyPageViewModel(journey());

        expect(model.progressPercent).toBe(7);
        expect(model.progressLabel).toBe("1/2 项必修已完成");
        expect(model.stages[0]?.activities[0]?.href).toBe(
            "/newcomer-training/activities/lesson-1",
        );
    });

    it("deduplicates a persisted task notification by its formal result location", () => {
        const notifications: FoundationNotificationPage = {
            contract_version: "notification_page_v1",
            items: [{
                notification_id: "notice-1",
                notification_type: "reminder",
                type_label: "待办提醒",
                title: "录音评估已完成",
                content: "结果已经保存。",
                action_label: "查看录音反馈",
                action_path: "/newcomer-training/activities/audio-1",
                created_from: "后台任务",
                is_read: false,
                created_at: "2026-07-17T10:01:00Z",
            }],
            total: 1,
            page: 1,
            page_size: 20,
            has_more: false,
        };
        const tasks: FoundationTaskStatusPage = {
            contract_version: "task_status_page_v1",
            items: [{
                contract_version: "task_status_v1",
                task_id: "task-1",
                title: "录音评估",
                state: "succeeded",
                state_label: "已完成",
                progress: null,
                can_cancel: false,
                retry_after: null,
                result_location: "/api/v1/newcomer-training/activities/audio-1",
                result_path: "/newcomer-training/activities/audio-1",
                error: null,
                updated_at: "2026-07-17T10:00:00Z",
            }],
            total: 1,
            page: 1,
            page_size: 20,
            has_more: false,
        };

        const model = toNotificationCenterViewModel({
            notifications,
            tasks,
            page: 1,
            pageSize: 20,
        });

        expect(model.items).toHaveLength(1);
        expect(model.items[0]?.id).toBe("notification:notice-1");
        expect(model.items[0]?.href).toBe("/newcomer-training/activities/audio-1");
    });
});
