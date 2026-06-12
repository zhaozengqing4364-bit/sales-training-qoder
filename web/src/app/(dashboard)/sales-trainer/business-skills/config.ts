import type { NewcomerArticleChapter, SalesTrainerUnit } from "@/lib/api/types";
import { ApiRequestError, getApiErrorMessage } from "@/lib/api/client";

export const BUSINESS_SKILLS_MODULE_KEY = "business_skills";
export const BUSINESS_SKILLS_COACH_ACTION_LABEL = "先去 AI 教练练一轮";

export const BUSINESS_SKILLS_EXAM_COPY = {
    pageTitle: "商务技巧考试",
    pageSubtitle: "完成学习后提交商务技巧考卷。",
    submitButton: "提交考卷",
    backLink: "返回商务技巧学习",
    paperMissingTitle: "暂未绑定商务技巧考卷",
    paperMissingDescription:
        "请管理员到 新人训练路径配置中心 → 商务技巧 → 考卷管理 绑定已发布考卷。",
    learningGateTitle: "请先完成商务技巧学习",
    learningGateDescription: "完成全部章节后再进入考试，系统会自动开放考卷入口。",
    learningMismatchTitle: "请先匹配当前学习内容",
    learningMismatchDescription:
        "当前学习进度与最新绑定不一致。返回学习页重新完成全部章节后再次进入考试。",
    learningGateActionLabel: "返回学习页",
} as const;

export const BUSINESS_SKILLS_EXAM_GATE_COPY = {
    actionLabel: BUSINESS_SKILLS_EXAM_COPY.learningGateActionLabel,
    description: BUSINESS_SKILLS_EXAM_COPY.learningGateDescription,
    title: BUSINESS_SKILLS_EXAM_COPY.learningGateTitle,
} as const;

export function businessSkillsCompletionStorageKey(contentId: string): string {
    return `newcomer-business-skills:${contentId}:completed-chapters`;
}

export function readBusinessSkillsCompletedChapterIds(contentId: string): readonly string[] {
    if (typeof window === "undefined") {
        return [];
    }
    const rawValue = window.localStorage.getItem(businessSkillsCompletionStorageKey(contentId));
    if (!rawValue) {
        return [];
    }
    try {
        const parsedValue: unknown = JSON.parse(rawValue);
        return Array.isArray(parsedValue) ? parsedValue.filter((item): item is string => typeof item === "string") : [];
    } catch (error) {
        if (error instanceof SyntaxError) {
            return [];
        }
        throw error;
    }
}

export function saveBusinessSkillsCompletedChapterIds(
    contentId: string,
    chapterIds: readonly string[],
): void {
    window.localStorage.setItem(businessSkillsCompletionStorageKey(contentId), JSON.stringify([...chapterIds]));
}

export function hasCompletedBusinessSkillsChapters(
    contentId: string,
    chapters: readonly NewcomerArticleChapter[],
): boolean {
    const completedIds = new Set(readBusinessSkillsCompletedChapterIds(contentId));
    return chapters.length > 0 && chapters.every((chapter) => completedIds.has(chapter.chapter_id));
}

export function paperIdFromUnit(unit: SalesTrainerUnit | undefined): string | null {
    const paperId = unit?.config.path?.exam_paper_id;
    return typeof paperId === "string" && paperId.trim() ? paperId.trim() : null;
}

export function learningContentIdFromUnit(unit: SalesTrainerUnit | undefined): string | null {
    const contentId = unit?.config.path?.learning_content_id;
    return typeof contentId === "string" && contentId.trim() ? contentId.trim() : null;
}

export function resolveBusinessSkillsUnit(
    units: readonly SalesTrainerUnit[],
    unitId: string | null,
): SalesTrainerUnit | undefined {
    return units.find((unit) => unit.unit_id === unitId)
        ?? units.find((unit) => unit.config.path?.module_key === BUSINESS_SKILLS_MODULE_KEY)
        ?? units.find((unit) => paperIdFromUnit(unit));
}

export function fallbackPaperId(units: readonly SalesTrainerUnit[]): string | null {
    return paperIdFromUnit(units.find((unit) => paperIdFromUnit(unit)));
}

export function businessSkillsExamHref(unitId: string | null): string {
    return unitId
        ? `/sales-trainer/business-skills/exam?unitId=${encodeURIComponent(unitId)}`
        : "/sales-trainer/business-skills/exam";
}

export function businessSkillsArticleErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError && error.errorCode.includes("CHAPTERS_MISSING")) {
        return "商务技巧文章还没有学习章节。请管理员到 新人训练路径配置中心 → 商务技巧 → 学习文章 添加第一节、第二节等学习章节。";
    }
    if (error instanceof ApiRequestError && (error.status === 404 || error.errorCode.includes("BINDING"))) {
        return "当前模块未绑定已发布文章。请管理员到 新人训练路径配置中心 → 商务技巧 → 学习文章 完成绑定。";
    }
    if (error instanceof ApiRequestError && error.errorCode.includes("NOT_PUBLISHED")) {
        return "当前绑定文章尚未发布。请管理员发布文章后，在新人训练路径配置中心重新确认绑定。";
    }
    return getApiErrorMessage(error);
}

export function chapterDisplayLabel(index: number): string {
    const labels = ["第一节", "第二节", "第三节", "第四节", "第五节"] as const;
    return labels[index] ?? `第${index + 1}节`;
}
