import type {
    RoleplayComplianceDecision,
    RoleplayComplianceSummary,
    RoleplayComplianceTimelineItem,
    SalesTrainerRoleplayObservation,
    SalesTrainerRoleplayObservationSessionResponse,
    SalesTrainerTrainingRecord,
    TrainingJourneyAnalyticsResponse,
} from "@/lib/api/types";

const DIMENSION_LABELS = {
    logic_score: "逻辑结构",
    accuracy_score: "事实准确",
    completeness_score: "覆盖完整",
} as const;

const STATUS_LABELS: Record<string, string> = {
    ready: "配置正常",
    legacy: "历史配置",
    missing: "配置缺失",
    invalid: "配置异常",
};

const ACTION_LABELS: Record<string, string> = {
    allow: "记录为通过",
    cancel_stream: "记入旁路观察",
    disclose_keys: "规则披露记录",
    mark_for_report: "记入旁路观察",
    regenerate_once: "记入旁路观察",
};

const SEVERITY_LABELS: Record<string, string> = {
    blocking: "高风险复盘",
    info: "信息",
    high: "高风险",
    low: "低风险",
    medium: "中风险",
    none: "通过",
    warning: "警告",
};

const VIOLATION_LABELS: Record<string, string> = {
    ROLEPLAY_CONTRACT_LEGACY: "历史合同回退",
    ROLEPLAY_CONTRACT_MISSING: "角色合同缺失",
    ROLEPLAY_FORBIDDEN_CLAIM: "禁用话术触发",
    ROLEPLAY_FORBIDDEN_STAGE: "阶段越界",
    ROLEPLAY_HIDDEN_INFORMATION_LEAK: "隐藏信息泄露",
    ROLEPLAY_HISTORY_CONTRADICTION: "关系史矛盾",
    coach_mode_keywords: "教练模式话术",
    early_close_keywords: "过早结束",
    kb_fact_without_evidence: "缺少证据的事实承诺",
    prompt_leak_risk: "提示词泄露风险",
    stage_keyword_conflict: "阶段越界风险",
    too_many_questions: "连续追问过多",
};

const RISK_TAG_LABELS: Record<string, string> = {
    blocking_roleplay_violation: "需人工复核：高风险角色违规",
    knowledge_gap_degradation: "知识 / LLM 降级",
    low_confidence: "需人工复核：低置信度",
};

export interface RoleplayObservationDimension {
    key: keyof typeof DIMENSION_LABELS;
    label: string;
    score: number | null;
    maxScore: number;
}

export interface RoleplayObservationFinding {
    id: string;
    eventType: string;
    turnNumber: number | null;
    action: string | null;
    actionLabel: string;
    severity: string | null;
    severityLabel: string;
    violationCode: string | null;
    violationLabel: string;
    salesStage: string | null;
    detectionSource: string | null;
    detectionSourceLabel: string;
    createdAt: string | null;
    traceId: string | null;
    matchedPattern: string | null;
    visibleKeysCount: number | null;
    disclosedKeysCount: number | null;
}

export interface RoleplayObservationViewModel {
    summaryStatus: string | null;
    summaryStatusLabel: string;
    contractHash: string | null;
    runtimeDisposition: string | null;
    mainChainEffect: string | null;
    detectionSources: string[];
    detectionSourceLabels: string[];
    dimensionScores: RoleplayObservationDimension[];
    findings: RoleplayObservationFinding[];
    heuristicOnly: boolean;
    hiddenLeakPreventedCount: number;
    lastObservedAt: string | null;
    llmTimedOut: boolean;
    manualReviewReasons: string[];
    manualReviewRequired: boolean;
    repairCount: number;
    riskTags: string[];
    riskTagLabels: string[];
    violationCount: number;
    blockingViolationCount: number;
}

export type RoleplayObservationSourceKind = "endpoint" | "legacy_fallback" | "none";

export interface RoleplayObservationEmptyState {
    kind: "not_persisted" | "historical_legacy" | "llm_disabled";
    title: string;
    description: string;
}

export interface RoleplayObservationPanelState {
    sourceKind: RoleplayObservationSourceKind;
    sourceLabel: string;
    sourceDescription: string;
    observation: RoleplayObservationViewModel | null;
    emptyState: RoleplayObservationEmptyState | null;
}

export interface RoleplayObservationCountBadge {
    key: string;
    label: string;
    count: number;
}

export interface RoleplayObservationAnalyticsViewModel {
    status: string | null;
    totalSessionCount: number | null;
    observedSessionCount: number | null;
    legacyFallbackSessionCount: number | null;
    notPersistedSessionCount: number | null;
    manualReviewSessionCount: number | null;
    llmDisabledSessionCount: number | null;
    llmTimeoutSessionCount: number | null;
    observationCount: number | null;
    signalCount: number | null;
    sourceCounts: RoleplayObservationCountBadge[];
    statusCounts: RoleplayObservationCountBadge[];
    generatedAt: string | null;
    fallbackApplied: boolean;
    fallbackReason: string | null;
}

type RuntimeObservability = {
    contractHash: string | null;
    knowledgeTimeoutCount: number;
    manualReviewRequired: boolean;
    manualReviewReasons: string[];
    qualityFlags: string[];
};

export function buildRoleplayObservationPanelState(
    record: SalesTrainerTrainingRecord,
    observationData: SalesTrainerRoleplayObservationSessionResponse | null,
): RoleplayObservationPanelState {
    if (!record.realtime_roleplay_session) {
        return {
            sourceKind: "none",
            sourceLabel: "暂无 observation 记录",
            sourceDescription: "当前训练记录缺少 realtime 会话快照，无法构建角色一致性观察。",
            observation: null,
            emptyState: null,
        };
    }

    const endpointObservation = buildEndpointObservationViewModel(record, observationData);
    if (endpointObservation) {
        return {
            sourceKind: "endpoint",
            sourceLabel: "新 observation endpoint",
            sourceDescription:
                "优先读取 admin observation endpoint；这条链路只记录旁路风险信号，不会打断 learner 实时对练。",
            observation: endpointObservation,
            emptyState: null,
        };
    }

    const legacyObservation = buildLegacyObservationViewModel(record);
    if (legacyObservation) {
        return {
            sourceKind: "legacy_fallback",
            sourceLabel: "legacy compliance fallback",
            sourceDescription:
                "当前没有 sidecar 观测行时，回退到训练记录冻结的 legacy compliance 快照，仅用于历史复盘兼容。",
            observation: legacyObservation,
            emptyState: null,
        };
    }

    return {
        sourceKind: "none",
        sourceLabel: "暂无 observation 记录",
        sourceDescription:
            "当前会话没有可回放的 observation 记录。主链路仍以 realtime runtime 为准，不会因为后台观测缺失而回退成 learner 失败。",
        observation: null,
        emptyState: resolveObservationEmptyState(record, observationData),
    };
}

export function buildRoleplayObservationViewModel(
    record: SalesTrainerTrainingRecord,
    observationData: SalesTrainerRoleplayObservationSessionResponse | null,
): RoleplayObservationViewModel | null {
    return buildRoleplayObservationPanelState(record, observationData).observation;
}

export function buildRoleplayObservationAnalyticsViewModel(
    analytics:
        | TrainingJourneyAnalyticsResponse
        | Record<string, unknown>
        | null
        | undefined,
): RoleplayObservationAnalyticsViewModel | null {
    const analyticsRecord = readRecord(analytics);
    const aggregate = readFirstRecord(analyticsRecord, [
        "additive_observation",
        "roleplay_observation_aggregate",
        "observation_aggregate",
        "roleplay_observation",
        "roleplay_observation_summary",
    ]);
    if (Object.keys(aggregate).length === 0) {
        return null;
    }

    const sourceCounts = buildCountBadges(
        readFirstRecord(aggregate, ["source_counts", "detection_source_counts"]),
        formatDetectionSourceLabel,
    );
    const statusCounts = buildCountBadges(
        readFirstRecord(aggregate, ["status_counts", "evaluator_status_counts"]),
        formatObservationStatusLabel,
    );
    const viewModel: RoleplayObservationAnalyticsViewModel = {
        status: readFirstString(aggregate, ["status", "coverage_status"]),
        totalSessionCount: readFirstNumber(aggregate, [
            "total_session_count",
            "session_count",
            "eligible_session_count",
        ]),
        observedSessionCount: readFirstNumber(aggregate, [
            "observed_session_count",
            "sessions_with_observation",
            "recorded_session_count",
            "endpoint_session_count",
        ]),
        legacyFallbackSessionCount: readFirstNumber(aggregate, [
            "legacy_fallback_session_count",
            "fallback_session_count",
            "legacy_session_count",
        ]),
        notPersistedSessionCount: readFirstNumber(aggregate, [
            "not_persisted_session_count",
            "pending_persistence_session_count",
            "sidecar_missing_session_count",
        ]),
        manualReviewSessionCount: readFirstNumber(aggregate, [
            "manual_review_session_count",
            "manual_review_required_session_count",
        ]),
        llmDisabledSessionCount: readFirstNumber(aggregate, [
            "llm_disabled_session_count",
            "heuristic_only_session_count",
        ]),
        llmTimeoutSessionCount: readFirstNumber(aggregate, [
            "llm_timeout_session_count",
            "timeout_session_count",
        ]),
        observationCount: readFirstNumber(aggregate, [
            "observation_count",
            "total_observation_count",
        ]),
        signalCount: readFirstNumber(aggregate, [
            "signal_count",
            "total_signal_count",
            "violation_count",
        ]),
        sourceCounts,
        statusCounts,
        generatedAt: readFirstString(aggregate, [
            "generated_at",
            "latest_observed_at",
            "last_observed_at",
        ]),
        fallbackApplied: Boolean(readBoolean(aggregate.fallback_applied)),
        fallbackReason: readString(aggregate.fallback_reason),
    };
    const hasUsefulPayload =
        viewModel.status !== null
        || viewModel.totalSessionCount !== null
        || viewModel.observedSessionCount !== null
        || viewModel.legacyFallbackSessionCount !== null
        || viewModel.notPersistedSessionCount !== null
        || viewModel.manualReviewSessionCount !== null
        || viewModel.llmDisabledSessionCount !== null
        || viewModel.llmTimeoutSessionCount !== null
        || viewModel.observationCount !== null
        || viewModel.signalCount !== null
        || viewModel.generatedAt !== null
        || viewModel.fallbackApplied
        || viewModel.fallbackReason !== null
        || viewModel.sourceCounts.length > 0
        || viewModel.statusCounts.length > 0;
    return hasUsefulPayload ? viewModel : null;
}

function buildLegacyObservationViewModel(
    record: SalesTrainerTrainingRecord,
): RoleplayObservationViewModel | null {
    const runtimeObservability = readRuntimeObservability(record);
    const summary = resolveSummary(record);
    const dimensionScores = buildDimensionScores(record);
    const findings = resolveTimeline(record).map((item, index) =>
        buildFinding(item, index),
    );
    const summaryRecord = readRecord(summary);
    const detectionSources = resolveDetectionSources(summary, findings);
    const manualReviewReasons = dedupe([
        ...runtimeObservability.manualReviewReasons,
        ...readStringList(summaryRecord.manual_review_reasons),
    ]);
    const blockingCount = readNumber(summaryRecord.blocking_violation_count) ?? 0;
    const llmTimedOut = Boolean(
        readBoolean(summaryRecord.llm_timeout)
        || (readString(summaryRecord.llm_status) || "").toLowerCase() === "timeout"
        || runtimeObservability.knowledgeTimeoutCount > 0,
    );
    const heuristicOnly = Boolean(
        readBoolean(summaryRecord.heuristic_only)
        || (readString(summaryRecord.llm_status) || "").toLowerCase() === "disabled"
        || (
            detectionSources.length > 0
            && detectionSources.every((source) => source === "heuristic")
        ),
    );
    const riskTags = dedupe([
        ...runtimeObservability.qualityFlags,
        ...manualReviewReasons,
        ...readStringList(summaryRecord.blocking_issues),
        ...(blockingCount > 0 ? [`blocking_violation_count:${blockingCount}`] : []),
        ...findings
            .map((finding) => finding.violationCode)
            .filter((value): value is string => Boolean(value)),
    ]);
    const hasLegacyObservationPayload =
        findings.length > 0
        || riskTags.length > 0
        || detectionSources.length > 0
        || manualReviewReasons.length > 0
        || runtimeObservability.manualReviewRequired
        || runtimeObservability.qualityFlags.length > 0
        || llmTimedOut;
    if (!hasLegacyObservationPayload) {
        return null;
    }

    const status = readString(summaryRecord.status);
    return {
        summaryStatus: status,
        summaryStatusLabel: formatStatusLabel(status),
        contractHash:
            readString(summaryRecord.contract_hash)
            || runtimeObservability.contractHash,
        runtimeDisposition: "record_only",
        mainChainEffect: "none",
        detectionSources,
        detectionSourceLabels: detectionSources.map(formatDetectionSourceLabel),
        dimensionScores,
        findings,
        heuristicOnly,
        hiddenLeakPreventedCount: readNumber(summaryRecord.hidden_leak_prevented_count) ?? 0,
        lastObservedAt: readString(summaryRecord.last_action_at),
        llmTimedOut,
        manualReviewReasons,
        manualReviewRequired: Boolean(
            readBoolean(summaryRecord.manual_review_required)
            || runtimeObservability.manualReviewRequired
            || manualReviewReasons.length > 0,
        ),
        repairCount: 0,
        riskTags,
        riskTagLabels: riskTags.map(formatRiskTagLabel),
        violationCount: readNumber(summaryRecord.violation_count) ?? 0,
        blockingViolationCount: blockingCount,
    };
}

function buildEndpointObservationViewModel(
    record: SalesTrainerTrainingRecord,
    observationData: SalesTrainerRoleplayObservationSessionResponse | null,
): RoleplayObservationViewModel | null {
    if (!observationData || observationData.total <= 0 || observationData.items.length === 0) {
        return null;
    }
    const runtimeObservability = readRuntimeObservability(record);
    const dimensionScores = buildDimensionScores(record);
    const findings = observationData.items.flatMap((item) =>
        buildEndpointFindings(item),
    );
    const signalCount = observationData.items.reduce(
        (total, item) => total + item.signals.length,
        0,
    );
    const highRiskCount = findings.filter((finding) => finding.severity === "high").length;
    const failedItems = observationData.items.filter(
        (item) => item.evaluator_status === "failed",
    );
    const detectionSources = resolveEndpointDetectionSources(observationData, findings);
    const llmStatuses = readEndpointLlmStatuses(observationData);
    const manualReviewReasons = dedupe([
        ...runtimeObservability.manualReviewReasons,
        ...findings
            .filter((finding) => finding.severity === "high")
            .map((finding) => finding.violationCode)
            .filter((value): value is string => Boolean(value)),
        ...failedItems
            .map((item) => item.error?.code || item.error?.message || null)
            .filter((value): value is string => Boolean(value)),
    ]);
    const riskTags = dedupe([
        ...runtimeObservability.qualityFlags,
        ...findings
            .map((finding) => finding.violationCode)
            .filter((value): value is string => Boolean(value)),
        ...failedItems
            .map((item) => item.error?.code || null)
            .filter((value): value is string => Boolean(value)),
    ]);

    return {
        summaryStatus: "ready",
        summaryStatusLabel: "观测已记录",
        contractHash:
            resolveEndpointContractHash(observationData)
            || runtimeObservability.contractHash,
        runtimeDisposition: resolveEndpointRuntimeDisposition(observationData),
        mainChainEffect: resolveEndpointMainChainEffect(observationData),
        detectionSources,
        detectionSourceLabels: detectionSources.map(formatDetectionSourceLabel),
        dimensionScores,
        findings,
        heuristicOnly:
            (llmStatuses.length === 0 || llmStatuses.every((status) => status === "disabled"))
            && detectionSources.length > 0
            && detectionSources.every((source) => source === "heuristic"),
        hiddenLeakPreventedCount: findings.filter(
            (finding) => finding.violationCode === "prompt_leak_risk",
        ).length,
        lastObservedAt: resolveLatestObservationAt(observationData.items),
        llmTimedOut:
            llmStatuses.includes("timeout")
            || observationData.items.some((item) =>
                `${item.error?.code || ""} ${item.error?.message || ""}`
                    .toLowerCase()
                    .includes("timeout"),
            ),
        manualReviewReasons,
        manualReviewRequired:
            highRiskCount > 0
            || failedItems.length > 0
            || runtimeObservability.manualReviewRequired,
        repairCount: 0,
        riskTags,
        riskTagLabels: riskTags.map(formatRiskTagLabel),
        violationCount: signalCount,
        blockingViolationCount: highRiskCount,
    };
}

function buildEndpointFindings(
    item: SalesTrainerRoleplayObservation,
): RoleplayObservationFinding[] {
    if (!item.signals.length) {
        return [];
    }
    const captureContext = readCaptureContext(item);
    return item.signals.map((signal, signalIndex) => {
        const signalRecord = readRecord(signal);
        const key = readString(signalRecord.key) || "roleplay_observation_signal";
        const severity = readString(signalRecord.severity);
        const source = normalizeDetectionSource(
            readString(signalRecord.source) || item.source,
        );
        return {
            id: `${item.observation_id}-${key}-${signalIndex}`,
            eventType: "observation_signal",
            turnNumber: item.turn_index,
            action: "mark_for_report",
            actionLabel: formatActionLabel("mark_for_report"),
            severity,
            severityLabel: formatSeverityLabel(severity),
            violationCode: key,
            violationLabel: formatViolationLabel(key),
            salesStage: readString(captureContext.template_stage_key),
            detectionSource: source,
            detectionSourceLabel: formatDetectionSourceLabel(source),
            createdAt: readString(item.created_at),
            traceId: readString(item.trace_id),
            matchedPattern: sanitizeObservationText(firstEvidenceValue(signalRecord.evidence)),
            visibleKeysCount: null,
            disclosedKeysCount: null,
        };
    });
}

function buildDimensionScores(
    record: SalesTrainerTrainingRecord,
): RoleplayObservationDimension[] {
    const scores = readRecord(record.realtime_roleplay_session?.snapshot.scores);
    return (Object.entries(DIMENSION_LABELS) as Array<[keyof typeof DIMENSION_LABELS, string]>)
        .map(([key, label]) => ({
            key,
            label,
            score: readNumber(scores[key]),
            maxScore: 100,
        }))
        .filter((item) => item.score !== null);
}

function resolveObservationEmptyState(
    record: SalesTrainerTrainingRecord,
    observationData: SalesTrainerRoleplayObservationSessionResponse | null,
): RoleplayObservationEmptyState {
    if (isLlmDisabledObservation(record, observationData)) {
        return {
            kind: "llm_disabled",
            title: "LLM 默认关闭，当前没有新增 observation 行",
            description:
                "这条会话仍会继续运行 Heuristic 守护，但背景 LLM 评估默认关闭。若规则侧也没有命中需落库的风险 signal，admin observation endpoint 会保持空态。",
        };
    }
    if (isHistoricalObservationRecord(record)) {
        return {
            kind: "historical_legacy",
            title: "历史旧记录尚未接入新 observation endpoint",
            description:
                "该会话来自旧版 legacy compliance 时段或旧 runtime 语义，sidecar observation 不会回填历史 turn。若仍需复盘，请查看训练记录主快照或更晚的新会话。",
        };
    }
    return {
        kind: "not_persisted",
        title: "观测尚未落库",
        description:
            "当前实时对练已支持新 observation endpoint，但本场会话暂时没有可读取的 sidecar 记录。这通常表示写入延迟，或本场没有触发需保存的旁路观察信号。",
    };
}

function readCaptureContext(
    item: SalesTrainerRoleplayObservation,
): Record<string, unknown> {
    for (const dimension of item.dimensions) {
        const dimensionRecord = readRecord(dimension);
        if (readString(dimensionRecord.key) === "capture_context") {
            return dimensionRecord;
        }
    }
    return {};
}

function readObservationRuntimeDimension(
    item: SalesTrainerRoleplayObservation,
): Record<string, unknown> {
    for (const dimension of item.dimensions) {
        const dimensionRecord = readRecord(dimension);
        if (readString(dimensionRecord.key) === "evaluation_runtime") {
            return dimensionRecord;
        }
    }
    return {};
}

function firstEvidenceValue(value: unknown): string | null {
    if (!Array.isArray(value)) {
        return null;
    }
    for (const item of value) {
        const evidence = readRecord(item);
        const text = readString(evidence.value);
        if (text) {
            return text;
        }
    }
    return null;
}

function buildCountBadges(
    value: Record<string, unknown>,
    formatter: (key: string) => string,
): RoleplayObservationCountBadge[] {
    return Object.entries(value)
        .map(([key, rawCount]) => ({
            key,
            label: formatter(key),
            count: readNumber(rawCount),
        }))
        .filter((item): item is RoleplayObservationCountBadge => item.count !== null && item.count > 0)
        .sort((left, right) => right.count - left.count);
}

function resolveEndpointDetectionSources(
    observationData: SalesTrainerRoleplayObservationSessionResponse,
    findings: RoleplayObservationFinding[],
): string[] {
    const fromCounts = Object.entries(observationData.source_counts)
        .filter(([, count]) => typeof count === "number" && count > 0)
        .map(([source]) => normalizeDetectionSource(source))
        .filter((value): value is string => Boolean(value));
    const fromFindings = findings
        .map((finding) => finding.detectionSource)
        .filter((value): value is string => Boolean(value));
    return dedupe([...fromCounts, ...fromFindings]);
}

function resolveEndpointContractHash(
    observationData: SalesTrainerRoleplayObservationSessionResponse,
): string | null {
    for (const item of observationData.items) {
        const hash = readString(readCaptureContext(item).instruction_contract_hash);
        if (hash) {
            return hash;
        }
    }
    return null;
}

function resolveEndpointRuntimeDisposition(
    observationData: SalesTrainerRoleplayObservationSessionResponse,
): string {
    return resolveEndpointContractField(observationData, [
        "realtime_disposition",
        "runtime_disposition",
        "disposition",
    ]) || "record_only";
}

function resolveEndpointMainChainEffect(
    observationData: SalesTrainerRoleplayObservationSessionResponse,
): string {
    return resolveEndpointContractField(observationData, [
        "main_chain_effect",
        "mainChainEffect",
    ]) || "none";
}

function resolveEndpointContractField(
    observationData: SalesTrainerRoleplayObservationSessionResponse,
    keys: string[],
): string | null {
    for (const item of observationData.items) {
        const topLevelValue = readFirstString(readRecord(item), keys);
        if (topLevelValue) {
            return topLevelValue;
        }
        for (const dimension of item.dimensions) {
            const value = readFirstString(readRecord(dimension), keys);
            if (value) {
                return value;
            }
        }
    }
    return null;
}

function resolveLatestObservationAt(
    items: SalesTrainerRoleplayObservation[],
): string | null {
    return items
        .map((item) => readString(item.created_at))
        .filter((value): value is string => Boolean(value))
        .sort()
        .at(-1) ?? null;
}

function buildFinding(
    item: RoleplayComplianceTimelineItem,
    index: number,
): RoleplayObservationFinding {
    const decision = readRecord(item.decision);
    const detectionSource = readFindingDetectionSource(item, decision);
    const action = readString(item.action);
    const severity = readString(item.severity);
    const violationCode = readString(item.violation_code);
    const turnNumber = readNumber(item.turn_number);

    return {
        id: `${item.event_type}-${item.trace_id || item.created_at || turnNumber || index}`,
        eventType: item.event_type || "unknown",
        turnNumber,
        action,
        actionLabel: formatActionLabel(action),
        severity,
        severityLabel: formatSeverityLabel(severity),
        violationCode,
        violationLabel: formatViolationLabel(violationCode),
        salesStage: readString(item.sales_stage),
        detectionSource,
        detectionSourceLabel: formatDetectionSourceLabel(detectionSource),
        createdAt: readString(item.created_at),
        traceId: readString(item.trace_id),
        matchedPattern: sanitizeObservationText(readString(item.matched_pattern)),
        visibleKeysCount: readNumber(item.visible_keys_count),
        disclosedKeysCount: readNumber(item.disclosed_keys_count),
    };
}

function readRuntimeObservability(record: SalesTrainerTrainingRecord): RuntimeObservability {
    const snapshot = readVoicePolicySnapshot(record);
    const runtimeMetrics = readRecord(snapshot.runtime_metrics);
    const observability = readRecord(runtimeMetrics.it_leader_roleplay_v1);
    return {
        contractHash: readString(observability.roleplay_contract_hash),
        knowledgeTimeoutCount: readNumber(observability.knowledge_timeout_count) ?? 0,
        manualReviewRequired: Boolean(readBoolean(observability.manual_review_required)),
        manualReviewReasons: readStringList(observability.manual_review_reasons),
        qualityFlags: readStringList(observability.quality_flags),
    };
}

function readVoicePolicySnapshot(
    record: SalesTrainerTrainingRecord,
): Record<string, unknown> {
    return readRecord(record.realtime_roleplay_session?.snapshot.voice_policy_snapshot);
}

function resolveSummary(record: SalesTrainerTrainingRecord): RoleplayComplianceSummary | null {
    const voicePolicySnapshot = readVoicePolicySnapshot(record);
    const runtimeMetrics = readRecord(voicePolicySnapshot.runtime_metrics);
    const compliance = readRecord(runtimeMetrics.roleplay_compliance);
    if (Object.keys(compliance).length === 0) {
        return null;
    }
    const voiceMode = readString(voicePolicySnapshot.voice_mode);
    const contractHash = readString(voicePolicySnapshot.roleplay_contract_hash);

    return {
        status: voiceMode === "legacy" ? "legacy" : contractHash ? "ready" : "missing",
        contract_hash: contractHash,
        violation_count: readNumber(compliance.violation_count) ?? 0,
        blocking_violation_count: readNumber(compliance.blocking_violation_count) ?? 0,
        regenerate_count: readNumber(compliance.regenerate_count) ?? 0,
        cancel_stream_count: readNumber(compliance.cancel_stream_count) ?? 0,
        hidden_leak_prevented_count: readNumber(compliance.hidden_leak_prevented_count) ?? 0,
        last_action_at: readString(compliance.last_action_at),
        last_decision: readRecord(compliance.last_decision) as RoleplayComplianceDecision,
        timeline: readTimelineItems(compliance.timeline),
        signal_sources: readStringList(compliance.signal_sources),
        llm_status: readString(compliance.llm_status),
        llm_timeout: readBoolean(compliance.llm_timeout) ?? undefined,
        heuristic_only: readBoolean(compliance.heuristic_only) ?? undefined,
        manual_review_required: readBoolean(compliance.manual_review_required) ?? undefined,
        manual_review_reasons: readStringList(compliance.manual_review_reasons),
        blocking_issues: readStringList(compliance.blocking_issues),
    };
}

function resolveTimeline(record: SalesTrainerTrainingRecord): RoleplayComplianceTimelineItem[] {
    const summary = resolveSummary(record);
    if (summary?.timeline?.length) {
        return summary.timeline;
    }
    const voicePolicySnapshot = readVoicePolicySnapshot(record);
    const runtimeMetrics = readRecord(voicePolicySnapshot.runtime_metrics);
    const compliance = readRecord(runtimeMetrics.roleplay_compliance);
    return readTimelineItems(compliance.timeline);
}

function resolveDetectionSources(
    summary: RoleplayComplianceSummary | null,
    findings: RoleplayObservationFinding[],
): string[] {
    const summaryRecord = readRecord(summary);
    const explicit = readStringList(summaryRecord.signal_sources);
    if (explicit.length > 0) {
        return dedupe(explicit.map(normalizeDetectionSource).filter(Boolean) as string[]);
    }
    const fromFindings = dedupe(
        findings
            .map((finding) => finding.detectionSource)
            .filter((value): value is string => Boolean(value)),
    );
    if (fromFindings.length > 0) {
        return fromFindings;
    }
    return [];
}

function readTimelineItems(value: unknown): RoleplayComplianceTimelineItem[] {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter((item): item is RoleplayComplianceTimelineItem => Boolean(item));
}

function readFindingDetectionSource(
    item: RoleplayComplianceTimelineItem,
    decision: Record<string, unknown>,
): string | null {
    const explicit =
        normalizeDetectionSource(readString(readRecord(item).signal_source))
        || normalizeDetectionSource(readString(readRecord(item).detection_source))
        || normalizeDetectionSource(readString(readRecord(decision).signal_source))
        || normalizeDetectionSource(
            readString(readRecord(readRecord(decision).audit_payload).signal_source),
        );
    if (explicit) {
        return explicit;
    }
    if (item.event_type === "disclosure") {
        return "rule_disclosure";
    }
    if (item.event_type === "compliance_decision") {
        return "heuristic";
    }
    return null;
}

function readEndpointLlmStatuses(
    observationData: SalesTrainerRoleplayObservationSessionResponse,
): string[] {
    return dedupe(
        observationData.items
            .map((item) => {
                const runtime = readObservationRuntimeDimension(item);
                const llm = readRecord(runtime.llm);
                return normalizeDetectionSource(
                    readString(llm.status)
                    || readString(runtime.llm_status),
                );
            })
            .filter((value): value is string => Boolean(value)),
    );
}

function isLlmDisabledObservation(
    record: SalesTrainerTrainingRecord,
    observationData: SalesTrainerRoleplayObservationSessionResponse | null,
): boolean {
    if (observationData && readEndpointLlmStatuses(observationData).includes("disabled")) {
        return true;
    }
    const summaryRecord = readRecord(resolveSummary(record));
    if ((readString(summaryRecord.llm_status) || "").toLowerCase() === "disabled") {
        return true;
    }
    return Boolean(
        readBoolean(summaryRecord.heuristic_only)
        && (readNumber(summaryRecord.violation_count) ?? 0) === 0
        && readTimelineItems(summaryRecord.timeline).length === 0,
    );
}

function isHistoricalObservationRecord(record: SalesTrainerTrainingRecord): boolean {
    const session = record.realtime_roleplay_session;
    if (!session) {
        return false;
    }
    const voiceSnapshot = readVoicePolicySnapshot(record);
    const voiceMode = readString(voiceSnapshot.voice_mode);
    if (voiceMode && voiceMode !== "stepfun_realtime") {
        return true;
    }
    const bindingOwner =
        readString(readRecord(session.external_binding).owner)
        || readString(readRecord(voiceSnapshot.external_binding).owner);
    if (bindingOwner && bindingOwner !== "sales_trainer") {
        return true;
    }
    return readString(readRecord(resolveSummary(record)).status) === "legacy";
}

function sanitizeObservationText(value: string | null): string | null {
    if (!value) {
        return null;
    }
    return value
        .replace(/\bBearer\s+[A-Za-z0-9._-]+\b/gi, "Bearer <redacted>")
        .replace(
            /\b(api[_-]?key|token|secret|authorization|cookie|jwt)\s*[:=]\s*([^\s,;]+)/gi,
            "$1=<redacted>",
        );
}

function normalizeDetectionSource(value: string | null): string | null {
    if (!value) {
        return null;
    }
    return value.trim().toLowerCase() || null;
}

function readRecord(value: unknown): Record<string, unknown> {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return {};
    }
    return value as Record<string, unknown>;
}

function readFirstRecord(
    value: Record<string, unknown>,
    keys: string[],
): Record<string, unknown> {
    for (const key of keys) {
        const nested = readRecord(value[key]);
        if (Object.keys(nested).length > 0) {
            return nested;
        }
    }
    return {};
}

function readString(value: unknown): string | null {
    if (typeof value !== "string") {
        return null;
    }
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
}

function readFirstString(
    value: Record<string, unknown>,
    keys: string[],
): string | null {
    for (const key of keys) {
        const text = readString(value[key]);
        if (text) {
            return text;
        }
    }
    return null;
}

function readNumber(value: unknown): number | null {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}

function readFirstNumber(
    value: Record<string, unknown>,
    keys: string[],
): number | null {
    for (const key of keys) {
        const number = readNumber(value[key]);
        if (number !== null) {
            return number;
        }
    }
    return null;
}

function readBoolean(value: unknown): boolean | null {
    if (typeof value === "boolean") {
        return value;
    }
    return null;
}

function readStringList(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }
    return value
        .map((item) => (typeof item === "string" ? item.trim() : String(item).trim()))
        .filter(Boolean);
}

function dedupe(items: string[]): string[] {
    return [...new Set(items)];
}

function formatStatusLabel(status: string | null): string {
    if (!status) {
        return "未记录";
    }
    return STATUS_LABELS[status] ?? status;
}

function formatActionLabel(action: string | null): string {
    if (!action) {
        return "--";
    }
    return ACTION_LABELS[action] ?? action;
}

function formatSeverityLabel(severity: string | null): string {
    if (!severity) {
        return "--";
    }
    return SEVERITY_LABELS[severity] ?? severity;
}

function formatViolationLabel(violationCode: string | null): string {
    if (!violationCode) {
        return "未命中违规码";
    }
    return VIOLATION_LABELS[violationCode] ?? violationCode;
}

function formatRiskTagLabel(tag: string): string {
    if (RISK_TAG_LABELS[tag]) {
        return RISK_TAG_LABELS[tag];
    }
    if (tag.startsWith("blocking_violation_count:")) {
        const count = tag.split(":")[1] || "0";
        return `高风险角色违规 ${count} 次`;
    }
    if (VIOLATION_LABELS[tag]) {
        return VIOLATION_LABELS[tag];
    }
    return tag;
}

function formatDetectionSourceLabel(source: string | null): string {
    if (!source) {
        return "未记录";
    }
    if (source.includes("heuristic")) {
        return "Heuristic 规则";
    }
    if (source.includes("timeout")) {
        return "LLM 超时";
    }
    if (source.includes("disabled")) {
        return "LLM 已关闭";
    }
    if (source.includes("llm")) {
        return "LLM 辅助";
    }
    if (source === "rule_disclosure") {
        return "规则披露";
    }
    return source;
}

function formatObservationStatusLabel(status: string): string {
    switch (status) {
        case "completed":
            return "观测完成";
        case "failed":
            return "观测失败";
        case "ignored":
            return "已忽略";
        case "pending":
            return "等待观测";
        default:
            return status;
    }
}
