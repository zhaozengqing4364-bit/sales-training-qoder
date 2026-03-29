import type {
    LiveSessionConclusionSummary,
    PresentationReview,
    PresentationReviewPageIssueCluster,
    RetrievalAttemptSummary,
    RetrievalFacts,
    RetrievalFactsStatus,
    RetrievalLatestAttempt,
    SessionClaimTruthPayload,
    SessionEvidenceCompleteness,
    SessionEvidenceStage,
    SessionMainIssue,
    SessionNextGoal,
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
    off_page: "串页偏题",
    overlong_explanation: "展开过长",
    weak_qa_handling: "问答承接偏弱",
    vague_response: "表达模糊",
};

const PRESENTATION_DEGRADED_REASON_LABELS: Record<string, string> = {
    missing_page_metadata: "当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。",
};

// ─────────────────────────────────────────────────────────────────────────────
// Retrieval truth — canonical labels and extraction helpers
// ─────────────────────────────────────────────────────────────────────────────

const RETRIEVAL_STATUS_LABELS: Record<RetrievalFactsStatus, string> = {
    hit: "已命中",
    miss: "未命中",
    search_failed: "检索失败",
    kb_not_ready: "知识库处理中",
    not_triggered: "未触发检索",
    no_knowledge_base: "未绑定知识库",
    disabled: "检索已关闭",
};

const MAX_RESULT_SUMMARIES = 3;

function isRetrievalFactsStatus(value: unknown): value is RetrievalFactsStatus {
    return typeof value === "string" && value in RETRIEVAL_STATUS_LABELS;
}

export function extractRetrievalFacts(
    effectivenessSnapshot?: Record<string, unknown> | null,
): RetrievalFacts | null {
    if (!effectivenessSnapshot || typeof effectivenessSnapshot !== "object") {
        return null;
    }

    const rawValue = effectivenessSnapshot.retrieval_facts;
    if (!rawValue || typeof rawValue !== "object") {
        return null;
    }
    const raw = rawValue as Record<string, unknown>;

    const kbBound = Boolean(raw.kb_bound);
    const knowledgeBaseIds = Array.isArray(raw.knowledge_base_ids)
        ? raw.knowledge_base_ids.filter((id: unknown): id is string => typeof id === "string" && Boolean(id.trim()))
        : [];
    const knowledgeBaseCount = typeof raw.knowledge_base_count === "number"
        ? raw.knowledge_base_count
        : knowledgeBaseIds.length;
    const retrievalEnabled = Boolean(raw.retrieval_enabled);
    const status = isRetrievalFactsStatus(raw.status)
        ? raw.status
        : "disabled";
    const summary = typeof raw.summary === "string" && raw.summary.trim()
        ? raw.summary.trim()
        : RETRIEVAL_STATUS_LABELS[status];
    const attemptCount = typeof raw.attempt_count === "number"
        ? raw.attempt_count
        : 0;
    const hitCount = typeof raw.hit_count === "number"
        ? raw.hit_count
        : 0;
    const hitRate = typeof raw.hit_rate === "number"
        ? raw.hit_rate
        : 0;

    let latestAttempt: RetrievalLatestAttempt | null = null;
    if (raw.latest_attempt && typeof raw.latest_attempt === "object") {
        const la = raw.latest_attempt as Record<string, unknown>;
        const resultSummaries = normalizeResultSummaries(la.result_summaries);
        latestAttempt = {
            status: typeof la.status === "string" && la.status.trim() ? la.status.trim() : status,
            ...(typeof la.query === "string" && la.query.trim() ? { query: la.query.trim() } : {}),
            ...(typeof la.attempted_at === "string" && la.attempted_at.trim()
                ? { attempted_at: la.attempted_at.trim() }
                : {}),
            ...(typeof la.retrieval_mode === "string" && la.retrieval_mode.trim()
                ? { retrieval_mode: la.retrieval_mode.trim() }
                : {}),
            ...(typeof la.error_summary === "string" && la.error_summary.trim()
                ? { error_summary: la.error_summary.trim() }
                : {}),
            ...(typeof la.result_count === "number" ? { result_count: la.result_count } : {}),
            ...(Array.isArray(la.knowledge_base_ids)
                ? {
                    knowledge_base_ids: la.knowledge_base_ids.filter(
                        (id: unknown): id is string => typeof id === "string" && Boolean(id.trim()),
                    ),
                }
                : {}),
            ...(resultSummaries.length > 0 ? { result_summaries: resultSummaries } : {}),
        };
    }

    return {
        kb_bound: kbBound,
        knowledge_base_ids: knowledgeBaseIds,
        knowledge_base_count: knowledgeBaseCount,
        retrieval_enabled: retrievalEnabled,
        status,
        summary,
        attempt_count: attemptCount,
        hit_count: hitCount,
        hit_rate: hitRate,
        ...(latestAttempt ? { latest_attempt: latestAttempt } : {}),
    };
}

function normalizeResultSummaries(
    raw?: unknown,
): RetrievalAttemptSummary[] {
    if (!Array.isArray(raw)) {
        return [];
    }

    return raw
        .filter((item: unknown): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .slice(0, MAX_RESULT_SUMMARIES)
        .map((item) => ({
            knowledge_base_id: typeof item.knowledge_base_id === "string" ? item.knowledge_base_id : "",
            ...(typeof item.knowledge_base_name === "string" && item.knowledge_base_name.trim()
                ? { knowledge_base_name: item.knowledge_base_name }
                : {}),
            ...(typeof item.snippet === "string" && item.snippet.trim()
                ? { snippet: item.snippet.trim() }
                : {}),
            ...(typeof item.retrieval_mode === "string"
                ? { retrieval_mode: item.retrieval_mode }
                : {}),
            ...(typeof item.score === "number"
                ? { score: item.score }
                : {}),
        }))
        .filter((item) => item.knowledge_base_id);
}

export function formatRetrievalStatusLabel(status?: string | null): string {
    if (!status) {
        return "--";
    }
    return RETRIEVAL_STATUS_LABELS[String(status)] || String(status);
}

export function formatRetrievalStatusTone(
    status?: string | null,
): "success" | "warning" | "error" | "neutral" {
    if (status === "hit") {
        return "success";
    }
    if (status === "miss" || status === "kb_not_ready") {
        return "warning";
    }
    if (status === "search_failed" || status === "no_knowledge_base" || status === "disabled") {
        return "error";
    }
    return "neutral";
}

export function formatLatestAttemptCopy(facts: RetrievalFacts): string | null {
    const la = facts.latest_attempt;
    if (!la) {
        return null;
    }

    const parts: string[] = [];

    if (typeof la.query === "string" && la.query.trim()) {
        parts.push(`最近检索问题：${la.query.trim()}`);
    }

    if (typeof la.result_count === "number") {
        parts.push(`命中片段：${la.result_count}`);
    }

    if (typeof la.error_summary === "string" && la.error_summary.trim()) {
        parts.push(la.error_summary);
    }

    if (la.result_summaries && la.result_summaries.length > 0) {
        const snippetCopy = la.result_summaries
            .filter((s) => s.snippet)
            .map((s) => s.snippet)
            .join("；");
        if (snippetCopy) {
            parts.push(`相关片段：${snippetCopy}`);
        }
    }

    return parts.length > 0 ? parts.join("。") : null;
}

export function formatMissExplanation(facts: RetrievalFacts): string | null {
    if (facts.status !== "miss") {
        return null;
    }

    const la = facts.latest_attempt;
    const query = la?.query;
    if (typeof query === "string" && query.trim()) {
        return `检索「${query}」未在知识库中找到相关内容，建议优化检索词或补充知识库文档。`;
    }
    return "最近一次检索未在知识库中命中有效内容，建议优化提问或补充知识库。";
}

export function formatSearchFailedExplanation(facts: RetrievalFacts): string | null {
    if (facts.status !== "search_failed") {
        return null;
    }

    const la = facts.latest_attempt;
    const errorSummary = la?.error_summary;
    if (typeof errorSummary === "string" && errorSummary.trim()) {
        return `知识检索服务异常：${errorSummary}`;
    }
    return "知识检索服务暂不可用，请稍后重试或联系管理员。";
}

export function formatWeakEvidenceRetrievalNote(
    claimTruth: SessionClaimTruth | null,
    retrievalFacts: RetrievalFacts | null,
): string | null {
    if (!claimTruth || claimTruth.status !== "weak_evidence") {
        return null;
    }
    if (!retrievalFacts || !retrievalFacts.retrieval_enabled) {
        return null;
    }

    if (retrievalFacts.status === "hit") {
        return "知识库已命中相关内容，但当前证据力度仍不够——建议引用更具体的数据或案例。";
    }
    if (retrievalFacts.status === "miss") {
        return "知识库检索未命中，可能缺少对应文档——建议补充相关产品或案例资料。";
    }
    if (retrievalFacts.status === "search_failed") {
        return "知识库检索暂时异常，无法确认是否有相关内容支撑当前主张。";
    }
    return null;
}

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

function cleanText(value?: string | null): string | null {
    return typeof value === "string" && value.trim() ? value.trim() : null;
}

function extractSessionClaimTruthFromPayload(
    payload?: SessionClaimTruthPayload | Record<string, unknown> | null,
): SessionClaimTruth | null {
    if (!payload || typeof payload !== "object") {
        return null;
    }

    const status = payload.status;
    const source = payload.source;
    const reason = payload.reason;
    if (!isClaimTruthStatus(status) || typeof source !== "string" || !source.trim()) {
        return null;
    }
    if (typeof reason !== "string" || !reason.trim()) {
        return null;
    }

    const label = typeof payload.label === "string" && payload.label.trim()
        ? payload.label.trim()
        : CLAIM_TRUTH_LABELS[status];

    const evidenceScore = coerceFiniteNumber(payload.evidence_score);
    const closureState = typeof payload.closure_state === "string" && payload.closure_state.trim()
        ? payload.closure_state.trim()
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

export interface SessionLearningCue {
    issueLabel: string | null;
    issueText: string | null;
    issueAction: string | null;
    goalLabel: string | null;
    goalText: string | null;
    goalRule: string | null;
    summary: string | null;
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

    return extractSessionClaimTruthFromPayload(
        effectivenessSnapshot.claim_truth as SessionClaimTruthPayload | Record<string, unknown> | null | undefined,
    );
}

export function extractLiveSessionClaimTruth(
    liveSessionSummary?: LiveSessionConclusionSummary | null,
): SessionClaimTruth | null {
    return extractSessionClaimTruthFromPayload(liveSessionSummary?.claim_truth ?? null);
}

export function extractLiveSessionLearningCue(
    liveSessionSummary?: LiveSessionConclusionSummary | null,
): SessionLearningCue | null {
    return extractSessionLearningCue({
        mainIssue: liveSessionSummary?.main_issue,
        nextGoal: liveSessionSummary?.next_goal,
    });
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

export function extractSessionLearningCue(input: {
    mainIssue?: SessionMainIssue | null;
    nextGoal?: SessionNextGoal | null;
    feedbackSummary?: string | null;
}): SessionLearningCue | null {
    const issueLabel = formatIssueTypeLabel(input.mainIssue?.issue_type);
    const issueText = cleanText(input.mainIssue?.issue_text);
    const issueAction = cleanText(input.mainIssue?.recovery_rule);
    const goalLabel = formatGoalTypeLabel(input.nextGoal?.goal_type);
    const goalText = cleanText(input.nextGoal?.goal_text);
    const goalRule = cleanText(input.nextGoal?.rule);
    const summary = cleanText(input.feedbackSummary) || issueText || goalText;

    if (!issueLabel && !issueText && !issueAction && !goalLabel && !goalText && !goalRule && !summary) {
        return null;
    }

    return {
        issueLabel,
        issueText,
        issueAction,
        goalLabel,
        goalText,
        goalRule,
        summary,
    };
}

export function formatPresentationIssueLabel(issueType?: string | null): string | null {
    if (!issueType) {
        return null;
    }
    return PRESENTATION_ISSUE_LABELS[String(issueType)] || null;
}

export function formatPresentationIssueContextLines(
    issue?: PresentationReviewPageIssueCluster | null,
): string[] {
    if (!issue) {
        return [];
    }

    const lines: string[] = [];
    const relatedPageNumbers = Array.isArray(issue.related_page_numbers)
        ? issue.related_page_numbers.filter((value) => Number.isFinite(value))
        : [];
    const linkedPoints = Array.isArray(issue.linked_points)
        ? issue.linked_points.filter(Boolean)
        : [];
    const linkedPhrases = Array.isArray(issue.linked_phrases)
        ? issue.linked_phrases.filter(Boolean)
        : [];
    const turnNumbers = Array.isArray(issue.turn_numbers)
        ? issue.turn_numbers.filter((value) => Number.isFinite(value))
        : [];

    if (relatedPageNumbers.length > 0) {
        lines.push(`关联页：${relatedPageNumbers.map((pageNumber) => `第 ${pageNumber} 页`).join("、")}`);
    }

    if (linkedPoints.length > 0) {
        lines.push(`关联要点：${linkedPoints.join("、")}`);
    }

    if (linkedPhrases.length > 0) {
        lines.push(`触发短语：${linkedPhrases.join("、")}`);
    }

    if (turnNumbers.length > 0) {
        lines.push(`涉及回合：${turnNumbers.join("、")}`);
    }

    return lines;
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
