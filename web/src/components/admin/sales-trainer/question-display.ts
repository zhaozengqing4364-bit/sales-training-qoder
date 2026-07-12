import type { SalesTrainerStatus } from "@/lib/api/types";

export const QUESTION_STATUS_LABELS = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
} as const satisfies Record<SalesTrainerStatus, string>;

export function displayQuestionTag(tag: string): string {
    return tag === "sales_trainer" ? "新人训练路径" : tag;
}
