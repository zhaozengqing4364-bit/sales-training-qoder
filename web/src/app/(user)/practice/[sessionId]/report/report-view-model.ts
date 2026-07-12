/** Pure report DTO-to-display mapping. */

import type { ComprehensiveReport } from "@/lib/api/types";
import type {
    CalibrationLabel,
    PresentationReview,
    ReadinessStatus,
    ReplayAnchor,
    SupervisorDecision,
} from "@/lib/api/types/session-report";
import { formatPresentationIssueLabel } from "@/lib/session-evidence";

export function hasReplayAnchorTarget(anchor?: ReplayAnchor | null): boolean {
    if (!anchor) return false;
    return Boolean(
        (typeof anchor.message_id === "string" && anchor.message_id.trim())
        || typeof anchor.turn_number === "number",
    );
}

export function formatSnapshotTime(value?: string | null): string {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

export function getScoreColor(score: number): string {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
}

export function getScoreLabel(score: number): string {
    if (score >= 90) return "优秀";
    if (score >= 80) return "良好";
    if (score >= 60) return "及格";
    return "待改进";
}

export const SUPERVISOR_DECISION_LABELS: Record<SupervisorDecision, string> = {
    pending: "待评审",
    approved: "通过",
    rejected: "打回",
    needs_retraining: "要求复训",
};

export const READINESS_STATUS_LABELS: Record<ReadinessStatus, string> = {
    not_ready: "暂不达标",
    shadow_only: "仅影子跟练",
    ready_for_trial: "可试点上岗",
    approved: "正式通过",
};

export const CALIBRATION_LABELS: Record<CalibrationLabel, string> = {
    accurate: "AI 评分准确",
    too_high: "AI 偏高",
    too_low: "AI 偏低",
    wrong_reason: "理由不对",
    missing_evidence: "证据不足",
};

export function formatScoreValue(value?: number | null): string {
    return typeof value === "number" && Number.isFinite(value)
        ? value.toFixed(1)
        : "--";
}

export function formatTrendDelta(delta?: number | null): string {
    if (delta === null || delta === undefined || Number.isNaN(delta)) {
        return "--";
    }
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toFixed(1)} 分`;
}

export function formatTrendDate(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "--";
    }
    return date.toLocaleDateString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
    });
}

export function formatRoleplayStatusLabel(status?: string | null): string {
    switch (status) {
        case "ready": return "配置正常";
        case "legacy": return "历史配置";
        case "missing": return "配置缺失";
        case "invalid": return "配置异常";
        default: return "未记录";
    }
}

export function getRoleplaySummaryTone(status?: string | null, blockingCount = 0) {
    if (status === "missing" || status === "invalid" || blockingCount > 0) {
        return {
            card: "border-amber-200 bg-amber-50/80",
            badge: "border-amber-200 bg-white/80 text-amber-700",
            text: "text-amber-900",
            note: "text-amber-700",
        };
    }
    if (status === "legacy") {
        return {
            card: "border-slate-200 bg-slate-50/80",
            badge: "border-slate-200 bg-white/80 text-slate-700",
            text: "text-slate-900",
            note: "text-slate-600",
        };
    }
    return {
        card: "border-emerald-200 bg-emerald-50/80",
        badge: "border-emerald-200 bg-white/80 text-emerald-700",
        text: "text-emerald-900",
        note: "text-emerald-700",
    };
}


export function buildSalesDimensionScores(scores: {
    logic: number | null;
    accuracy: number | null;
    completeness: number | null;
}) {
    return [
        {
            name: "价值表达",
            score: scores.logic ?? 0,
            description: "是否把产品能力翻译成客户收益与业务价值。",
        },
        {
            name: "证据与收益",
            score: scores.accuracy ?? 0,
            description: "是否用案例、数据或 ROI 证据支撑收益主张。",
        },
        {
            name: "异议推进",
            score: scores.completeness ?? 0,
            description: "是否处理价格/竞品/风险异议并推动下一步。",
        },
    ];
}

export function formatVoiceModeLabel(mode: string | null | undefined): string {
    if (!mode) return "--";
    if (mode === "legacy") return "经典语音模式";
    if (mode === "stepfun_realtime") return "实时语音模式";
    return "已选择语音模式";
}

export function hasVoiceSourceKeys(source: Record<string, string> | null | undefined): boolean {
    if (!source) return false;
    return Object.keys(source).length > 0;
}


export function buildPresentationIssueItems(review?: PresentationReview | null) {
    const pageIssueCounts = (review?.page_summaries || []).reduce((counts, pageSummary) => {
        for (const cluster of pageSummary.issue_clusters || []) {
            counts.set(cluster.issue_type, (counts.get(cluster.issue_type) || 0) + 1);
        }
        return counts;
    }, new Map<string, number>());

    const diagnosticIssueTypes = Array.isArray(review?.diagnostics?.page_issue_types)
        ? review.diagnostics.page_issue_types.filter(Boolean)
        : [];
    const issueTypes = diagnosticIssueTypes.length > 0
        ? diagnosticIssueTypes
        : Array.from(pageIssueCounts.keys());

    if (issueTypes.length > 0) {
        return issueTypes
            .map((issueType) => ({
                issueType,
                count: pageIssueCounts.get(issueType) || Number(review?.issue_counts?.[issueType] || 0),
                label: formatPresentationIssueLabel(issueType) || issueType,
            }))
            .filter((item) => item.count > 0);
    }

    return Object.entries(review?.issue_counts || {})
        .map(([issueType, rawCount]) => ({
            issueType,
            count: Number(rawCount || 0),
            label: formatPresentationIssueLabel(issueType) || issueType,
        }))
        .filter((item) => item.count > 0);
}


export function hasEnhancedInsights(report: ComprehensiveReport | null): boolean {
    if (!report) {
        return false;
    }

    return Boolean(
        report.key_strengths.length
        || report.key_improvements.length
        || report.recommendations.length
        || report.detailed_feedback?.trim(),
    );
}


export function formatReplayAnchorHint(anchor?: ReplayAnchor | null): string {
    if (!anchor || !hasReplayAnchorTarget(anchor) || anchor.status === "missing") {
        return "当前暂无可定位的回放片段。";
    }

    if (anchor.status === "resolved") {
        if (typeof anchor.turn_number === "number") {
            return `回放将定位到第 ${anchor.turn_number} 轮高光片段。`;
        }
        return "回放将定位到对应高光片段。";
    }

    if (anchor.degraded_reason === "missing_marker") {
        if (typeof anchor.turn_number === "number") {
            return `高光标记缺失，回放将直接定位到第 ${anchor.turn_number} 轮。`;
        }
        return "高光标记缺失，回放将直接定位到相关对话片段。";
    }

    if (anchor.degraded_reason === "no_matching_highlight") {
        if (anchor.marker?.label) {
            return `未找到精确高光，回放将定位到“${anchor.marker.label}”阶段。`;
        }
        if (typeof anchor.turn_number === "number") {
            return `未找到精确高光，回放将定位到第 ${anchor.turn_number} 轮附近。`;
        }
    }

    return "当前暂无可定位的回放片段。";
}
