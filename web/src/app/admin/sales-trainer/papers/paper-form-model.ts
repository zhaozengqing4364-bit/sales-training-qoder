import type {
    NewcomerExamPaper,
    SalesTrainerUnitQuestionBinding,
    SalesTrainerStatus,
} from "@/lib/api/types";

export const BUSINESS_SKILLS_MODULE_KEY = "business_skills";

export const PAPER_STATUS_LABELS = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
} as const satisfies Record<SalesTrainerStatus, string>;

export function buildBusinessSkillsPaperKey(now: number): string {
    return `business_skills_paper_${Math.max(1, Math.floor(now))}`;
}

export function buildPaperQuestionBindings(
    selectedQuestionIds: readonly string[],
    points: number,
): SalesTrainerUnitQuestionBinding[] {
    return selectedQuestionIds.map((questionId, index) => ({
        question_id: questionId,
        order_index: index + 1,
        points,
    }));
}

export function selectedPaperQuestionIds(paper: NewcomerExamPaper): string[] {
    return [...paper.questions]
        .sort((left, right) => left.order_index - right.order_index)
        .map((question) => question.question_id);
}

export function defaultPaperQuestionPoints(paper: NewcomerExamPaper): string {
    const orderedQuestions = [...paper.questions].sort(
        (left, right) => left.order_index - right.order_index,
    );
    return String(orderedQuestions[0]?.points ?? 10);
}
