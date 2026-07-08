import {
    Bot,
    FileAudio,
    GraduationCap,
    Upload,
    type LucideIcon,
} from "lucide-react";

import type {
    TrainingJourneyModuleType,
    TrainingJourneyStage,
} from "@/lib/api/types";

/** Badge 组件支持的 variant 名（与 components/ui/badge.tsx 保持一致） */
export type BadgeVariant =
    | "blue"
    | "purple"
    | "green"
    | "orange"
    | "gray"
    | "red"
    | "neutral"
    | "secondary"
    | "outline"
    | "destructive";

/**
 * 模块闭环状态的语义色调。
 * 用于驱动 Badge variant、卡片左边框、图标块等所有状态色展示。
 */
export type JourneyStageTone =
    | "success"
    | "danger"
    | "warning"
    | "info"
    | "neutral";

/**
 * 将训练阶段映射为语义色调。
 *
 * 修复了原 page.tsx 中 getJourneyStageBadgeClass 的 bug：
 * disabled/archived 不再错误归入蓝色(info)，而是归入 neutral(灰)。
 */
export function getJourneyStageTone(
    stage: TrainingJourneyStage,
): JourneyStageTone {
    if (stage === "passed" || stage === "scored") return "success";
    if (
        stage === "failed" ||
        stage === "error_terminal" ||
        stage === "manual_review"
    ) {
        return "danger";
    }
    if (stage === "needs_remediation" || stage === "error_transient") {
        return "warning";
    }
    if (stage === "disabled" || stage === "archived") return "neutral";
    // not_started / in_progress / waiting_upload / processing
    return "info";
}

const TONE_TO_BADGE_VARIANT: Record<JourneyStageTone, BadgeVariant> = {
    success: "green",
    danger: "red",
    warning: "orange",
    info: "blue",
    neutral: "gray",
};

/**
 * 将训练阶段映射为 Badge 组件的 variant，回归 variant 系统
 * （替代原 page.tsx 中绕过 variant 的裸 className）。
 */
export function getJourneyStageBadgeVariant(
    stage: TrainingJourneyStage,
): BadgeVariant {
    return TONE_TO_BADGE_VARIANT[getJourneyStageTone(stage)];
}

export interface JourneyStageCardAccent {
    /** 图标圆角块背景色 */
    iconBg: string;
    /** 图标前景色 */
    iconColor: string;
}

const TONE_TO_CARD_ACCENT: Record<JourneyStageTone, JourneyStageCardAccent> = {
    success: {
        iconBg: "bg-emerald-100",
        iconColor: "text-emerald-700",
    },
    danger: {
        iconBg: "bg-rose-100",
        iconColor: "text-rose-700",
    },
    warning: {
        iconBg: "bg-amber-100",
        iconColor: "text-amber-700",
    },
    info: {
        iconBg: "bg-blue-100",
        iconColor: "text-blue-700",
    },
    neutral: {
        iconBg: "bg-slate-100",
        iconColor: "text-slate-500",
    },
};

/**
 * 返回卡片层状态色（图标块底色 + 图标前景色）。
 * 用于模块闭环卡片的状态色区分。
 */
export function getJourneyStageCardAccent(
    stage: TrainingJourneyStage,
): JourneyStageCardAccent {
    return TONE_TO_CARD_ACCENT[getJourneyStageTone(stage)];
}

export type ScoreTone = "excellent" | "good" | "poor";

/**
 * 分数语义色分段，复用 ScorePanel.getScoreColor 的阈值：
 * ≥85 优秀(emerald) / ≥70 良好(amber) / <70 需改进(rose)。
 */
export function getScoreTone(score: number): ScoreTone {
    if (score >= 85) return "excellent";
    if (score >= 70) return "good";
    return "poor";
}

const SCORE_TEXT_CLASS: Record<ScoreTone, string> = {
    excellent: "text-emerald-600",
    good: "text-amber-600",
    poor: "text-rose-600",
};

/** 分数 → Tailwind 文字色类 */
export function getScoreTextColorClass(score: number): string {
    return SCORE_TEXT_CLASS[getScoreTone(score)];
}

const SCORE_STROKE_CLASS: Record<ScoreTone, string> = {
    excellent: "stroke-emerald-500",
    good: "stroke-amber-500",
    poor: "stroke-rose-500",
};

/** 分数 → Tailwind stroke 色类（用于 ScoreRing SVG circle） */
export function getScoreStrokeClass(score: number): string {
    return SCORE_STROKE_CLASS[getScoreTone(score)];
}

const SCORE_FILL_CLASS: Record<ScoreTone, string> = {
    excellent: "bg-emerald-500",
    good: "bg-amber-500",
    poor: "bg-rose-500",
};

/** 分数 → Tailwind 填充色类（用于维度进度条填充） */
export function getScoreFillClass(score: number): string {
    return SCORE_FILL_CLASS[getScoreTone(score)];
}

const MODULE_TYPE_ICONS: Partial<Record<TrainingJourneyModuleType, LucideIcon>> = {
    audio_scoring: FileAudio,
    audio_scoring_group: FileAudio,
    article_exam: GraduationCap,
    ai_coach: Bot,
    realtime_roleplay: Bot,
    realtime_placeholder: Bot,
};

/**
 * 模块类型 → 图标映射，复用 sales-trainer-module-grid 的 MODULE_ICONS 模式。
 * 兜底返回 Upload 图标。
 */
export function getModuleIcon(
    moduleType: TrainingJourneyModuleType | string | null | undefined,
): LucideIcon {
    if (!moduleType) return Upload;
    return MODULE_TYPE_ICONS[moduleType as TrainingJourneyModuleType] ?? Upload;
}
