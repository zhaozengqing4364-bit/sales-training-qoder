import { describe, expect, it } from "vitest";

import type { JourneyResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { missionFromCandidate, missionFromJourney } from "./learner-mission";

function legacyJourney(): JourneyResponse {
    return {
        enrollment_id: "enrollment-1",
        path_revision_id: "revision-1",
        path_title: "新人训练",
        progress: { completed: false, completed_count: 0, total_required: 1, percent: 0 },
        primary_next_action: {
            activity_id: "audio-1",
            activity_type: "audio_assessment",
            action_key: "record_audio",
            label: "PPT 讲解录音",
        },
        phases: [{
            phase_id: "phase-1",
            title: "入门认知",
            description: null,
            outcome: null,
            required: true,
            status: "in_progress",
            completed: false,
            completed_count: 0,
            total_required: 1,
            percent: 0,
            locked: false,
            lock_reason: null,
            modules: [{
                module_id: "module-1",
                title: "公司与方案介绍",
                description: null,
                outcome: null,
                required: true,
                estimated_minutes: 20,
                status: "in_progress",
                completed: false,
                completed_count: 0,
                total_required: 1,
                percent: 0,
                locked: false,
                lock_reason: null,
                activities: [{
                    activity_id: "audio-1",
                    activity_type: "audio_assessment",
                    title: "PPT 讲解录音",
                    description: null,
                    objective: null,
                    why_it_matters: null,
                    steps: [],
                    success_criteria: [],
                    primary_action_label: null,
                    required: true,
                    estimated_minutes: 15,
                    status: "pending",
                    completed: false,
                    passed: null,
                    score: null,
                    max_score: null,
                    locked: false,
                    lock_reason: null,
                    action_key: "record_audio",
                    is_primary_next_action: true,
                }],
            }],
        }],
    };
}

describe("learner mission view model", () => {
    it("turns a legacy revision into a concrete task with safe capability defaults", () => {
        const mission = missionFromJourney(legacyJourney());

        expect(mission?.title).toBe("PPT 讲解录音");
        expect(mission?.objective).toBe("完成一次清晰、完整的 PPT 讲解");
        expect(mission?.steps).toEqual([
            "先阅读并熟悉本次讲解材料",
            "按真实客户沟通方式完成讲解",
            "检查录音后提交评测",
        ]);
        expect(mission?.actionLabel).toBe("开始录音讲解");
        expect(mission?.phaseLabel).toBe("入门认知");
    });

    it("prefers configured learner-facing copy and uses the same model for admin preview", () => {
        const path: TrainingPathPayload = {
            schema_version: "newcomer_training_orchestration_v1",
            title: "新人训练",
            description: null,
            phases: [{
                phase_id: "phase-1",
                title: "产品能力",
                description: null,
                outcome: "能独立讲解核心产品",
                order_index: 1,
                required: true,
                modules: [{
                    module_id: "module-1",
                    title: "核心产品",
                    description: null,
                    outcome: "能讲清产品适用场景",
                    order_index: 1,
                    required: true,
                    estimated_minutes: 20,
                    audience_rule: { learner_levels: [], roles: [], departments: [] },
                    prerequisites: [],
                    completion_policy: { mode: "all_required", activity_ids: [], count: null },
                    activities: [{
                        activity_id: "lesson-1",
                        type: "lesson",
                        title: "学习核心产品",
                        description: null,
                        objective: "能向客户说明三个核心价值",
                        why_it_matters: "准确表达是后续演示的基础",
                        steps: ["阅读资料", "记录价值", "完成学习"],
                        success_criteria: ["能说出三个核心价值"],
                        primary_action_label: "开始产品学习",
                        order_index: 1,
                        required: true,
                        estimated_minutes: 20,
                        prerequisites: [],
                        config: { learning_content_id: "content-1", completion_mode: "all_chapters" },
                    }],
                }],
            }],
        };

        expect(missionFromCandidate(path)).toMatchObject({
            title: "学习核心产品",
            objective: "能向客户说明三个核心价值",
            whyItMatters: "准确表达是后续演示的基础",
            steps: ["阅读资料", "记录价值", "完成学习"],
            successCriteria: ["能说出三个核心价值"],
            actionLabel: "开始产品学习",
            moduleOutcome: "能讲清产品适用场景",
        });
    });
});
