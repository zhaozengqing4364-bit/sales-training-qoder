import type { SalesTrainerStatus } from "@/lib/api/types";

export const QUESTION_STATUS_LABELS = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
} as const satisfies Record<SalesTrainerStatus, string>;

const QUESTION_TAG_LABELS: Readonly<Record<string, string>> = {
    business_skills: "商务技巧",
    elevator_pitch: "金字塔演讲",
    ppt_explanation: "PPT讲解",
    sales_trainer: "新人训练路径",
} as const;

export function displayQuestionTag(tag: string): string {
    return QUESTION_TAG_LABELS[tag] ?? tag;
}
