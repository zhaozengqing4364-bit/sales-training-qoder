import type {
    FoundationActivityType,
    FoundationJourneyProjection,
} from "@/lib/api/types/newcomer-training";

export interface LearnerMissionViewModel {
    activityId: string;
    activityType: FoundationActivityType;
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

export type ActivityGuidance = Pick<
    LearnerMissionViewModel,
    "objective" | "whyItMatters" | "steps" | "successCriteria"
>;

const DEFAULT_GUIDANCE: Record<FoundationActivityType, ActivityGuidance> = {
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
        objective: "完成一次清晰、完整的方案讲解",
        whyItMatters: "把材料转化为自己的表达，提前发现讲解中的遗漏",
        steps: ["熟悉讲解材料", "按真实客户沟通方式完成讲解", "检查录音后提交评测"],
        successCriteria: ["讲解内容完整且表达清晰", "达到本次任务设定的通过分数"],
    },
    ai_coach: {
        objective: "围绕当前薄弱点完成一次针对性辅导",
        whyItMatters: "集中解决一个具体问题，比重复泛学更有效",
        steps: ["回答教练的诊断问题", "按提示补充和修正", "完成本次学习目标"],
        successCriteria: ["完成辅导目标并获得明确的下一步建议"],
    },
    assignment: {
        objective: "完成客户场景录音任务",
        whyItMatters: "通过实际产出把学习内容转化为可复用能力",
        steps: ["阅读场景要求", "完成并检查三段录音", "提交并等待评测"],
        successCriteria: ["三段录音均已提交并符合任务要求"],
    },
};

export function missionFromFoundationJourney(
    journey: FoundationJourneyProjection,
): LearnerMissionViewModel | null {
    const activity = journey.current_activity;
    const action = journey.primary_action;
    if (!activity || !action || action.activity_id !== activity.activity_id) {
        return null;
    }
    const stage = journey.stages.find((item) =>
        item.activities.some((candidate) => candidate.activity_id === activity.activity_id),
    );
    const fallback = DEFAULT_GUIDANCE[activity.type];
    return {
        activityId: activity.activity_id,
        activityType: activity.type,
        pathTitle: journey.path?.title ?? "新人销售基础训练",
        phaseLabel: stage?.title ?? "当前阶段",
        phaseOutcome: stage?.objective ?? null,
        moduleLabel: "",
        moduleOutcome: null,
        title: activity.title,
        objective: activity.objective || fallback.objective,
        whyItMatters: fallback.whyItMatters,
        steps: fallback.steps,
        successCriteria: fallback.successCriteria,
        estimatedMinutes: activity.estimated_minutes,
        actionLabel: action.label,
        progressPercent: journey.progress.percentage,
    };
}
