import type {
    SalesTrainerAudioSubmissionStatus,
    SalesTrainerQuizAttemptStatus,
    SalesTrainerStatus,
    SalesTrainerUnit,
    SalesTrainerUnitType,
} from "@/lib/api/types";

const LIFECYCLE_STATUS_LABELS = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
} as const satisfies Record<SalesTrainerStatus, string>;

const QUIZ_ATTEMPT_STATUS_LABELS = {
    submitted: "已提交，待判分",
    scored: "已评分",
    failed: "判分失败",
} as const satisfies Record<SalesTrainerQuizAttemptStatus, string>;

const AUDIO_SUBMISSION_STATUS_LABELS = {
    uploaded: "已上传",
    transcribing: "正在转写",
    transcribed: "转写完成",
    transcription_failed: "转写失败",
    scoring: "正在评分",
    scored: "评分完成",
    scoring_failed: "评分失败",
} as const satisfies Record<SalesTrainerAudioSubmissionStatus, string>;

const UNIT_TYPE_LABELS = {
    quiz: "考试",
    audio_scoring: "录音",
    ai_coach: "AI 教练",
    business_etiquette_quiz: "商务礼仪小测",
    realtime_roleplay: "实时对练",
} as const satisfies Record<
    SalesTrainerUnitType | "ai_coach" | "business_etiquette_quiz" | "realtime_roleplay",
    string
>;

export const TRAINING_PURPOSE_OPTIONS = [
    { value: "ppt_pitch", label: "PPT 讲解录音" },
    { value: "general_audio_scoring", label: "通用录音评分" },
    { value: "business_skills", label: "商务技巧" },
    { value: "elevator_pitch", label: "金字塔演讲" },
] as const;

const TRAINING_PURPOSE_LABELS: Readonly<Record<string, string>> = Object.fromEntries(
    TRAINING_PURPOSE_OPTIONS.map((option) => [option.value, option.label]),
);

const LEGACY_BUSINESS_SKILLS_UNIT_NAME = "模块二：拜访前商务";
const LEGACY_BUSINESS_SKILLS_DESCRIPTION_TOKEN = "COO 谈市场十五讲";
const BUSINESS_SKILLS_UNIT_NAME = "模块二：商务技巧";
const BUSINESS_SKILLS_UNIT_DESCRIPTION = "阅读见客户前商务礼仪学习内容，并完成商务技巧考卷。";
const CURRENT_NEWCOMER_PATH_KEY = "newcomer_training_path_v1";
const LEGACY_THREE_MODULE_PATH_KEY = "new_seller_modules_v1";

export interface TrainingTaskDisplay {
    readonly title: string;
    readonly detail: string | null;
}

export function formatAdminStatus(status: SalesTrainerStatus | string | null | undefined): string {
    if (status === "draft" || status === "published" || status === "archived") {
        return LIFECYCLE_STATUS_LABELS[status];
    }
    return "未识别状态";
}

export function formatAdminRecordStatus(status: string | null | undefined): string {
    if (status === "submitted" || status === "scored" || status === "failed") {
        return QUIZ_ATTEMPT_STATUS_LABELS[status];
    }
    if (
        status === "uploaded" ||
        status === "transcribing" ||
        status === "transcribed" ||
        status === "transcription_failed" ||
        status === "scoring" ||
        status === "scoring_failed"
    ) {
        return AUDIO_SUBMISSION_STATUS_LABELS[status];
    }
    if (status === "draft" || status === "published" || status === "archived") {
        return LIFECYCLE_STATUS_LABELS[status];
    }
    if (status === "in_progress") {
        return "进行中";
    }
    if (status === "completed") {
        return "已完成";
    }
    return "未识别状态";
}

export function formatUnitTypeLabel(
    unitType: SalesTrainerUnitType | "ai_coach" | "business_etiquette_quiz" | "realtime_roleplay",
): string {
    return UNIT_TYPE_LABELS[unitType];
}

export function formatScorePromptPurpose(purpose: string | null | undefined): string {
    return formatTrainingPurpose(purpose);
}

export function formatTrainingPurpose(purpose: string | null | undefined): string {
    const trimmedPurpose = purpose?.trim();
    if (!trimmedPurpose) {
        return "未设置用途";
    }
    return TRAINING_PURPOSE_LABELS[trimmedPurpose] ?? "自定义用途";
}

export function formatAudioSourceLabel(sourcePage: string | null | undefined): string {
    const source = sourcePage?.trim();
    if (!source) {
        return "未知来源";
    }
    if (source === "sales_trainer_audio_upload" || source.startsWith("/sales-trainer/audio/")) {
        return "学员录音上传页";
    }
    if (source.startsWith("/sales-trainer/business-skills")) {
        return "商务技巧学习页";
    }
    if (source === "/sales-trainer") {
        return "新人训练路径首页";
    }
    return "自定义入口";
}

export function formatTrainingTaskDisplay(
    unitName: string | null | undefined,
    unitId: string | null | undefined,
): TrainingTaskDisplay {
    const trimmedName = unitName?.trim();
    const trimmedId = unitId?.trim();
    return {
        title: trimmedName || "未命名训练任务",
        detail: trimmedId ? `编号：${trimmedId}` : null,
    };
}

export function normalizeNewcomerUnitDisplay(unit: SalesTrainerUnit): SalesTrainerUnit {
    const isBusinessSkillsUnit =
        unit.config.path?.module_key === "business_skills" ||
        unit.name === LEGACY_BUSINESS_SKILLS_UNIT_NAME ||
        unit.description?.includes(LEGACY_BUSINESS_SKILLS_DESCRIPTION_TOKEN) === true;
    if (!isBusinessSkillsUnit) {
        return unit;
    }
    return {
        ...unit,
        name:
            unit.name === LEGACY_BUSINESS_SKILLS_UNIT_NAME ? BUSINESS_SKILLS_UNIT_NAME : unit.name,
        description: unit.description?.includes(LEGACY_BUSINESS_SKILLS_DESCRIPTION_TOKEN)
            ? BUSINESS_SKILLS_UNIT_DESCRIPTION
            : unit.description,
    };
}

export function filterNewcomerAdminUnits(units: readonly SalesTrainerUnit[]): SalesTrainerUnit[] {
    const currentUnits = units.filter(
        (unit) => unit.config.path?.path_key === CURRENT_NEWCOMER_PATH_KEY,
    );
    if (currentUnits.length > 0) {
        return currentUnits.map(normalizeNewcomerUnitDisplay);
    }
    return units
        .filter((unit) => unit.config.path?.path_key === LEGACY_THREE_MODULE_PATH_KEY)
        .map(normalizeNewcomerUnitDisplay);
}
