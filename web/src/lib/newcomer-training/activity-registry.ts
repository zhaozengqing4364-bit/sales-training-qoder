import type { ActivityConfig, ActivityType } from "@/lib/api/types/newcomer-training";

export interface ActivityPresentation {
    type: ActivityType;
    label: string;
    description: string;
}

export const ACTIVITY_PRESENTATIONS: Record<ActivityType, ActivityPresentation> = {
    lesson: { type: "lesson", label: "内容学习", description: "阅读课程内容并完成章节" },
    quiz: { type: "quiz", label: "考试测验", description: "完成已发布试卷" },
    audio_assessment: { type: "audio_assessment", label: "录音讲解", description: "录音并按评分标准评测" },
    realtime_roleplay: { type: "realtime_roleplay", label: "实时对练", description: "进入实时语音情境训练" },
    ai_coach: { type: "ai_coach", label: "AI 教练", description: "围绕学习目标完成辅导" },
    assignment: { type: "assignment", label: "作业任务", description: "提交文字或文件作业" },
};

export function activityPresentation(activity: Pick<ActivityConfig, "type">): ActivityPresentation {
    return ACTIVITY_PRESENTATIONS[activity.type];
}
