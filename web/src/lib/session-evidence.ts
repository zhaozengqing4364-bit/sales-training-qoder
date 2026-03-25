import type {
    PresentationReview,
    SessionEvidenceCompleteness,
    SessionEvidenceStage,
    SessionNotEvaluableReason,
} from "@/lib/api/types";

const STAGE_LABELS: Record<string, string> = {
    opening: "开场破冰",
    discovery: "需求挖掘",
    objection: "异议处理",
    closing: "促成成交",
};

const NOT_EVALUABLE_REASON_LABELS: Record<string, string> = {
    INSUFFICIENT_TURN_DATA: "对话轮次不足，暂无法形成稳定评估。",
    INSUFFICIENT_SESSION_METRICS: "当前会话缺少稳定指标，暂无法形成评估。",
};

const MISSING_FIELD_LABELS: Record<string, string> = {
    closing_stage: "成交阶段证据",
    stage_summary: "阶段汇总",
    effectiveness_snapshot: "会话结果快照",
    session_scores: "会话评分",
    messages: "对话消息",
};

const ISSUE_TYPE_LABELS: Record<string, string> = {
    objection_response: "异议回应",
    value_gap: "价值表达",
    value_translation_gap: "价值翻译",
    evidence_gap: "证据支撑",
    objection_handling_gap: "异议处理",
    next_step_gap: "推进下一步",
    main_capability_not_passed: "核心能力",
    insufficient_turns: "轮次不足",
    insufficient_turn_data: "证据不足",
    insufficient_sales_evidence: "销售证据不足",
};

const GOAL_TYPE_LABELS: Record<string, string> = {
    objection_response_drill: "异议回应训练",
    objection_progress: "异议推进",
    value_to_benefit_translation: "收益翻译",
    evidence_backing: "证据补强",
    objection_reframe: "重构异议回应",
    next_step_commitment: "下一步承诺",
    single_next_goal: "下一轮重点",
    collect_more_evidence: "补齐有效互动",
    collect_sales_evidence: "补齐销售证据",
};

const PRESENTATION_ISSUE_LABELS: Record<string, string> = {
    forbidden_word: "禁用词提醒",
    missing_point: "遗漏要点",
    vague_response: "表达模糊",
};

const PRESENTATION_DEGRADED_REASON_LABELS: Record<string, string> = {
    missing_page_metadata: "当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。",
};

const CLAIM_TRUTH_LABELS = {
    unsupported_claim: "未被证据支撑",
    weak_evidence: "证据偏弱",
    evidence_pending: "证据待补齐",
    evidence_verified: "证据已验证",
} as const;

const CLAIM_TRUTH_SUMMARIES = {
    unsupported_claim: "当前这场对话里的收益或能力主张还没有被案例、数据或 ROI 证据支撑。",
    weak_evidence: "已经给出了证据，但力度还不够，仍需要更具体的案例、数据或 ROI 证明。",
    evidence_pending: "当前仍在补证据或有效互动不足，暂时不能判定这条主张已经成立。",
    evidence_verified: "当前主张已有足够证据支撑，可以继续沿着这条事实线推进下一步。",
} as const;

export type SessionClaimTruthStatus = keyof typeof CLAIM_TRUTH_LABELS;

export type SessionClaimTruthTone = "critical" | "warning" | "pending" | "verified";

export interface SessionClaimTruth {
    status: SessionClaimTruthStatus;
    label: string;
    source: string;
    reason: string;
    evidence_score?: number;
    closure_state?: string;
}

function isClaimTruthStatus(value: unknown): value is SessionClaimTruthStatus {
    return typeof value === "string" && value in CLAIM_TRUTH_LABELS;
}

function coerceFiniteNumber(value: unknown): number | null {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function formatSessionStageLabel(stage?: SessionEvidenceStage | null): string {
    if (!stage) {
        return "未分阶段";
    }
    return STAGE_LABELS[String(stage)] || String(stage);
}

export function formatNotEvaluableReason(
    reason?: SessionNotEvaluableReason | null,
): string {
    if (!reason) {
        return "当前证据不足，暂无法形成稳定评估。";
    }
    return NOT_EVALUABLE_REASON_LABELS[String(reason)] || `当前会话暂不可评估（${String(reason)}）。`;
}

export function formatEvidenceCompletenessNote(
    completeness?: SessionEvidenceCompleteness | null,
): string | null {
    if (!completeness || completeness.complete !== false) {
        return null;
    }

    const missingFields = Array.isArray(completeness.missing_fields)
        ? completeness.missing_fields.filter(Boolean)
        : [];

    if (missingFields.length === 0) {
        return "当前证据仍不完整，部分诊断会在更多事实到齐后更新。";
    }

    const labels = missingFields.map((field) => MISSING_FIELD_LABELS[field] || field);
    return `当前证据仍不完整：${labels.join("、")}。`;
}

export function extractSessionClaimTruth(
    effectivenessSnapshot?: Record<string, unknown> | null,
): SessionClaimTruth | null {
    if (!effectivenessSnapshot || typeof effectivenessSnapshot !== "object") {
        return null;
    }

    const rawClaimTruth = effectivenessSnapshot.claim_truth;
    if (!rawClaimTruth || typeof rawClaimTruth !== "object") {
        return null;
    }

    const claimTruth = rawClaimTruth as Record<string, unknown>;
    const status = claimTruth.status;
    const source = claimTruth.source;
    const reason = claimTruth.reason;
    if (!isClaimTruthStatus(status) || typeof source !== "string" || !source.trim()) {
        return null;
    }
    if (typeof reason !== "string" || !reason.trim()) {
        return null;
    }

    const label = typeof claimTruth.label === "string" && claimTruth.label.trim()
        ? claimTruth.label.trim()
        : CLAIM_TRUTH_LABELS[status];

    const evidenceScore = coerceFiniteNumber(claimTruth.evidence_score);
    const closureState = typeof claimTruth.closure_state === "string" && claimTruth.closure_state.trim()
        ? claimTruth.closure_state.trim()
        : null;

    return {
        status,
        label,
        source: source.trim(),
        reason: reason.trim(),
        ...(evidenceScore !== null ? { evidence_score: evidenceScore } : {}),
        ...(closureState ? { closure_state: closureState } : {}),
    };
}

export function formatClaimTruthSummary(claimTruth?: SessionClaimTruth | null): string | null {
    if (!claimTruth) {
        return null;
    }

    return CLAIM_TRUTH_SUMMARIES[claimTruth.status] || claimTruth.label;
}

export function formatClaimTruthEvidenceNote(claimTruth?: SessionClaimTruth | null): string | null {
    if (!claimTruth) {
        return null;
    }

    const parts: string[] = [];
    if (typeof claimTruth.evidence_score === "number") {
        parts.push(`证据强度：${Math.round(claimTruth.evidence_score)} 分。`);
    }

    if (claimTruth.closure_state === "open") {
        parts.push("当前异议仍未闭环。");
    } else if (claimTruth.closure_state === "gap_acknowledged") {
        parts.push("本轮已明确承认证据缺口。");
    } else if (claimTruth.closure_state === "evidence_provided") {
        parts.push(
            claimTruth.status === "evidence_verified"
                ? "本轮补充的证据已达到可验证水平。"
                : "本轮已补充证据，但说服力仍需加强。",
        );
    }

    return parts.length > 0 ? parts.join("") : null;
}

export function getClaimTruthTone(
    status?: SessionClaimTruthStatus | null,
): SessionClaimTruthTone {
    if (status === "unsupported_claim") {
        return "critical";
    }
    if (status === "weak_evidence") {
        return "warning";
    }
    if (status === "evidence_verified") {
        return "verified";
    }
    return "pending";
}

export function formatIssueTypeLabel(issueType?: string | null): string | null {
    if (!issueType) {
        return null;
    }
    return ISSUE_TYPE_LABELS[String(issueType)] || null;
}

export function formatGoalTypeLabel(goalType?: string | null): string | null {
    if (!goalType) {
        return null;
    }
    return GOAL_TYPE_LABELS[String(goalType)] || null;
}

export function formatPresentationIssueLabel(issueType?: string | null): string | null {
    if (!issueType) {
        return null;
    }
    return PRESENTATION_ISSUE_LABELS[String(issueType)] || null;
}

export function formatPresentationDegradedNote(
    review?: PresentationReview | null,
    completeness?: SessionEvidenceCompleteness | null,
): string | null {
    const reasons = [
        ...(review?.diagnostics?.degraded_reasons || []),
        ...(completeness?.degraded_reasons || []),
    ].filter(Boolean);

    const uniqueReasons = Array.from(new Set(reasons));
    if (uniqueReasons.length === 0) {
        if (review?.coverage_status === "degraded" || completeness?.page_metadata_complete === false) {
            return "当前 PPT 证据不完整，逐页总结和要点覆盖仅展示已确认部分。";
        }
        return null;
    }

    return uniqueReasons
        .map((reason) => PRESENTATION_DEGRADED_REASON_LABELS[reason] || `当前 PPT 证据存在降级原因：${reason}。`)
        .join(" ");
}
