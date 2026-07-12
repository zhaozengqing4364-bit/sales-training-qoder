import type {
    ActivityConfig,
    ActivityType,
    JourneyActivityProgress,
    JourneyResponse,
    TrainingPathPayload,
} from "@/lib/api/types/newcomer-training";
import { activityActionLabel } from "./presentation";

export interface LearnerMissionViewModel {
    activityId: string;
    activityType: ActivityType;
    pathTitle: string;
    phaseLabel: string;
    phaseOutcome: string | null;
    moduleLabel: string;
    moduleOutcome: string | null;
    title: string;
    objective: string;
    whyItMatters: string;
    steps: string[];
    successCriteria: string[];
    estimatedMinutes: number | null;
    actionLabel: string;
    progressPercent: number;
}

export type ActivityGuidance = Pick<LearnerMissionViewModel, "objective" | "whyItMatters" | "steps" | "successCriteria">;

const DEFAULT_GUIDANCE: Record<ActivityType, ActivityGuidance> = {
    lesson: {
        objective: "理解本次学习内容，并能说出关键要点",
        whyItMatters: "先建立准确理解，后续讲解和实战才有可靠基础",
        steps: ["阅读本次学习内容", "记录关键要点", "完成学习并确认"],
        successCriteria: ["完成全部必修内容", "能复述本次学习的关键要点"],
    },
    quiz: {
        objective: "完成本次测验，确认自己已经掌握关键知识",
        whyItMatters: "及时发现知识盲区，避免把错误理解带入客户沟通",
        steps: ["阅读题目并独立作答", "提交后查看结果", "针对错题补充学习"],
        successCriteria: ["达到本次测验设定的通过分数"],
    },
    audio_assessment: {
        objective: "完成一次清晰、完整的 PPT 讲解",
        whyItMatters: "把材料转化为自己的表达，提前发现讲解中的遗漏",
        steps: ["先阅读并熟悉本次讲解材料", "按真实客户沟通方式完成讲解", "检查录音后提交评测"],
        successCriteria: ["讲解内容完整且表达清晰", "达到本次任务设定的通过分数"],
    },
    realtime_roleplay: {
        objective: "在模拟客户场景中完成一次完整沟通",
        whyItMatters: "在安全环境中练习临场判断和真实对话节奏",
        steps: ["了解本次客户情境", "完成实时语音对练", "根据反馈复盘改进"],
        successCriteria: ["完成整场对练", "覆盖本次场景的核心沟通目标"],
    },
    ai_coach: {
        objective: "围绕当前薄弱点完成一次针对性辅导",
        whyItMatters: "集中解决一个具体问题，比重复泛学更有效",
        steps: ["回答教练的诊断问题", "按提示补充和修正", "完成本次学习目标"],
        successCriteria: ["完成辅导目标并获得明确的下一步建议"],
    },
    assignment: {
        objective: "完成并提交本次训练作业",
        whyItMatters: "通过实际产出把学习内容转化为可复用能力",
        steps: ["阅读作业要求", "完成并检查内容", "提交作业等待结果"],
        successCriteria: ["提交内容符合本次作业要求"],
    },
};

export function missionFromJourney(journey: JourneyResponse): LearnerMissionViewModel | null {
    const action = journey.primary_next_action;
    if (!action) return null;
    for (const phase of journey.phases) {
        for (const moduleConfig of phase.modules) {
            const activity = moduleConfig.activities.find((item) => item.activity_id === action.activity_id);
            if (!activity) continue;
            return buildMission({
                activity,
                pathTitle: journey.path_title,
                phaseLabel: phase.title,
                phaseOutcome: phase.outcome,
                moduleLabel: moduleConfig.title,
                moduleOutcome: moduleConfig.outcome,
                progressPercent: journey.progress.percent,
                actionLabel: activity.primary_action_label || activityActionLabel(activity.activity_type),
            });
        }
    }
    return null;
}

export function missionFromCandidate(path: TrainingPathPayload): LearnerMissionViewModel | null {
    const phase = [...path.phases].sort(byOrder).find((item) => item.modules.length > 0);
    const moduleConfig = phase && [...phase.modules].sort(byOrder).find((item) => item.activities.length > 0);
    const activity = moduleConfig && [...moduleConfig.activities].sort(byOrder)[0];
    if (!phase || !moduleConfig || !activity) return null;
    return buildMission({
        activity: toJourneyActivity(activity),
        pathTitle: path.title,
        phaseLabel: phase.title,
        phaseOutcome: phase.outcome,
        moduleLabel: moduleConfig.title,
        moduleOutcome: moduleConfig.outcome,
        progressPercent: 0,
        actionLabel: activity.primary_action_label || activityActionLabel(activity.type),
    });
}

function buildMission(input: {
    activity: JourneyActivityProgress;
    pathTitle: string;
    phaseLabel: string;
    phaseOutcome: string | null;
    moduleLabel: string;
    moduleOutcome: string | null;
    progressPercent: number;
    actionLabel: string;
}): LearnerMissionViewModel {
    const guidance = activityGuidance(input.activity);
    return {
        activityId: input.activity.activity_id,
        activityType: input.activity.activity_type,
        pathTitle: input.pathTitle,
        phaseLabel: input.phaseLabel,
        phaseOutcome: input.phaseOutcome,
        moduleLabel: input.moduleLabel,
        moduleOutcome: input.moduleOutcome,
        title: input.activity.title,
        ...guidance,
        estimatedMinutes: input.activity.estimated_minutes,
        actionLabel: input.actionLabel,
        progressPercent: input.progressPercent,
    };
}

export function activityGuidance(activity: Pick<JourneyActivityProgress,
    "activity_type" | "description" | "objective" | "why_it_matters" | "steps" | "success_criteria"
>): ActivityGuidance {
    const fallback = DEFAULT_GUIDANCE[activity.activity_type];
    return {
        objective: activity.objective || activity.description || fallback.objective,
        whyItMatters: activity.why_it_matters || fallback.whyItMatters,
        steps: activity.steps.length > 0 ? activity.steps : fallback.steps,
        successCriteria: activity.success_criteria.length > 0
            ? activity.success_criteria
            : fallback.successCriteria,
    };
}

function toJourneyActivity(activity: ActivityConfig): JourneyActivityProgress {
    return {
        activity_id: activity.activity_id,
        activity_type: activity.type,
        title: activity.title,
        description: activity.description,
        objective: activity.objective,
        why_it_matters: activity.why_it_matters,
        steps: activity.steps,
        success_criteria: activity.success_criteria,
        primary_action_label: activity.primary_action_label,
        required: activity.required,
        estimated_minutes: activity.estimated_minutes,
        status: "pending",
        completed: false,
        passed: null,
        score: null,
        max_score: null,
        locked: false,
        lock_reason: null,
        action_key: null,
        is_primary_next_action: true,
    };
}

function byOrder<T extends { order_index: number }>(left: T, right: T): number {
    return left.order_index - right.order_index;
}
