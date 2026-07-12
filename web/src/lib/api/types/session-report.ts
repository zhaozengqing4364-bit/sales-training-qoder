/** Session report, evidence, replay, highlight, and diagnostic contracts. */

interface SessionVoicePolicyRuntimeBinding {
    industry_pack_strategy: string;
    customer_pressure_source: string;
    sales_focus: string;
    value_axes: string[];
    objection_axes: string[];
    question_strategy: string;
    revisit_on_evasion: boolean;
    require_evidence: boolean;
    expected_customer_questions: string[];
    knowledge_base_ids: string[];
    runtime_impacts: string[];
}

interface SessionVoicePolicySnapshotReference {
    voice_mode?: string | null;
    runtime_profile_id?: string | null;
    instruction_contract_hash?: string | null;
    network_access_mode?: "off" | "controlled" | string | null;
    tool_policy: Record<string, unknown>;
    knowledge_base_ids: string[];
    source: Record<string, string>;
    resolved_at?: string | null;
    runtime_binding?: SessionVoicePolicyRuntimeBinding | null;
    agent_persona_override_config?: Record<string, unknown> | null;
}

interface SessionRoleplayComplianceTimelineItem {
    event_type: "compliance_decision" | "disclosure" | string;
    turn_number?: number | null;
    response_id?: string | null;
    action?: string | null;
    violation_code?: string | null;
    severity?: string | null;
    sales_stage?: string | null;
    visible_keys_count?: number | null;
    disclosed_keys_count?: number | null;
    created_at?: string | null;
    trace_id?: string | null;
    matched_pattern?: string | null;
    decision?: SessionRoleplayComplianceDecision | null;
    visible_keys?: string[];
    disclosed_keys?: string[];
}

interface SessionRoleplayComplianceDecision {
    allowed?: boolean;
    severity?: "none" | "info" | "warning" | "blocking" | string;
    violation_code?: string | null;
    matched_pattern?: string | null;
    action?: string | null;
    audit_payload?: Record<string, unknown>;
}

interface SessionRoleplayComplianceSummary {
    status: "ready" | "legacy" | "missing" | "invalid" | string;
    schema_version?: string | null;
    contract_hash?: string | null;
    situation_code?: string | null;
    blocking_issues?: string[];
    signal_sources?: string[];
    violation_count?: number;
    blocking_violation_count?: number;
    regenerate_count?: number;
    cancel_stream_count?: number;
    hidden_leak_prevented_count?: number;
    disclosed_keys_count?: number;
    visible_keys_count?: number;
    disclosure_state_status?: string;
    heuristic_only?: boolean;
    llm_status?: string | null;
    llm_timeout?: boolean;
    manual_review_required?: boolean;
    manual_review_reasons?: string[];
    last_decision?: SessionRoleplayComplianceDecision | null;
    last_action_at?: string | null;
    timeline?: SessionRoleplayComplianceTimelineItem[];
}

interface SessionTrainingTaskSummary {
    task_id: string;
    title: string;
    scenario_type: string;
    status: string;
    goal: string;
}

interface SessionTrainingReportEvidenceItem {
    evidence_id: string;
    dimension?: string | null;
    issue?: string | null;
    evidence_type: string;
    turn_number?: number | null;
    speaker?: string | null;
    quote?: string | null;
    source_message_id?: string | null;
    source_page_id?: string | null;
    knowledge_source_id?: string | null;
    reason?: string | null;
    severity?: string | null;
    confidence?: number | null;
}

interface SessionThinkingEvidenceEntry {
    turn_index: number;
    template_stage_key?: string | null;
    response_id: string;
    thinking_text: string;
    captured_at: string;
}

export interface ReplayContextMessage {
    id?: string | null;
    role?: string | null;
    content?: string | null;
    timestamp?: string | null;
}

export interface ReplayHighlightContext {
    prev_message?: ReplayContextMessage | null;
    next_message?: ReplayContextMessage | null;
}

export interface ReplayLearningStage {
    key: SessionEvidenceStage;
    name: string;
}

export interface ReplayLearningEvidence {
    reason?: string | null;
    issue_family?: string | null;
    objection_family?: string | null;
    stage?: ReplayLearningStage | null;
    nearby_context?: ReplayHighlightContext | null;
    suggested_response?: string | null;
    linked_issue?: SessionMainIssue | null;
    linked_goal?: SessionNextGoal | null;
}

export interface ReplayMessage {
    id: string;
    session_id: string;
    turn_number: number;
    role: string;
    content: string;
    timestamp: string;
    audio_url?: string | null;
    duration_ms?: number | null;
    sales_stage?: string | null;
    stage_name?: string | null;
    score_snapshot?: {
        overall?: number | null;
        overall_score?: number | null;
        dimensions?: Array<{
            name: string;
            score: number;
            trend?: string;
            delta?: number;
        }>;
        dimension_scores?: Record<string, number> | null;
        stage_name?: string | null;
        suggestions?: string[];
    } | null;
    transcript_metadata?: {
        knowledge_answer_diagnostics?: Record<string, unknown> | null;
        [key: string]: unknown;
    } | null;
    ai_feedback?: string | null;
    is_highlight?: boolean;
    highlight_type?: string | null;
    highlight_reason?: string | null;
    suggested_response?: string | null;
    learning_evidence?: ReplayLearningEvidence | null;
}

export interface ReplayTimelineMarker {
    timestamp_ms: number;
    type: string;
    label: string;
    message_id: string;
    highlight_type?: string | null;
}

export type SessionEvidenceStage = "opening" | "discovery" | "objection" | "closing" | string;

export type SessionNotEvaluableReason =
    "INSUFFICIENT_TURN_DATA" | "INSUFFICIENT_SESSION_METRICS" | string;

export interface SessionEvidenceCompleteness {
    complete?: boolean;
    missing_fields?: string[];
    message_count?: number;
    legacy_score_key_used?: boolean;
    scenario_type?: "sales" | "presentation" | string;
    presentation_review_available?: boolean;
    page_metadata_complete?: boolean;
    page_summary_count?: number;
    required_talking_points_status?: "complete" | "degraded" | string;
    required_points_total?: number;
    required_points_covered?: number;
    required_points_missing?: number;
    required_coverage_ratio?: number;
    degraded_reasons?: string[];
    [key: string]: unknown;
}

export interface PresentationReviewDimensionScore {
    name: string;
    score: number;
    weight: number;
    description: string;
}

export interface PresentationReviewPageIssueCluster {
    issue_type:
        | "off_page"
        | "missing_point"
        | "overlong_explanation"
        | "forbidden_word"
        | "weak_qa_handling"
        | string;
    summary: string;
    evidence: string[];
    turn_numbers: number[];
    linked_points: string[];
    linked_phrases: string[];
    related_page_numbers: number[];
}

export interface PresentationReviewPageSummary {
    page_number: number;
    stage_number: number;
    start_turn: number;
    end_turn: number;
    average_score: number;
    key_points: string[];
    matched_required_points: string[];
    missing_required_points: string[];
    issue_clusters?: PresentationReviewPageIssueCluster[];
    summary: string;
}

export interface PresentationRequiredTalkingPointCoverage {
    status: "complete" | "degraded";
    total: number;
    covered: number;
    missing: number;
    coverage_ratio: number;
}

export interface PresentationReviewDiagnostics {
    has_page_metadata: boolean;
    pages_with_messages: number;
    total_pages: number;
    page_coverage_ratio: number;
    required_points_total: number;
    required_points_covered: number;
    required_points_missing: number;
    required_coverage_ratio: number;
    degraded_reasons: string[];
    page_issue_cluster_count?: number;
    page_issue_types?: string[];
}

export interface PresentationReview {
    overall_score: number;
    dimension_scores: PresentationReviewDimensionScore[];
    page_summaries: PresentationReviewPageSummary[];
    required_talking_points: PresentationRequiredTalkingPointCoverage;
    issue_counts: Record<string, number>;
    strengths: string[];
    improvements: string[];
    recommendations: string[];
    detailed_feedback: string;
    has_page_metadata: boolean;
    coverage_status: "complete" | "degraded";
    diagnostics: PresentationReviewDiagnostics;
}

export interface SessionStageSummary {
    stage: SessionEvidenceStage;
    duration_ms: number;
    score: number;
}

export interface SessionPassFlags {
    pass_3min_flow: boolean;
    pass_5turn_defense: boolean;
    pass_4step_structure: boolean;
}

export type SessionOverallResult = "pass" | "strong_pass" | "fail";

export interface ReplayAnchorMarker {
    type: "highlight" | "stage_change" | string;
    timestamp_ms: number;
    label: string;
}

export type ReplayAnchorStatus = "resolved" | "degraded" | "missing";

export interface ReplayAnchor {
    status: ReplayAnchorStatus;
    message_id: string | null;
    turn_number: number | null;
    marker?: ReplayAnchorMarker | null;
    degraded_reason?:
        "missing_marker" | "no_matching_highlight" | "anchor_target_not_found" | string | null;
}

export interface SessionMainIssue {
    issue_type: string;
    issue_text: string;
    recovery_rule: string;
    replay_anchor?: ReplayAnchor | null;
}

export interface SessionNextGoal {
    goal_type: string;
    goal_text: string;
    rule: string;
    replay_anchor?: ReplayAnchor | null;
}

export interface SessionClaimTruthPayload {
    status: string;
    label?: string;
    source: string;
    reason: string;
    evidence_score?: number | null;
    closure_state?: string | null;
}

export interface LiveSessionConclusionSummary {
    alignment_used: boolean;
    stage_key?: SessionEvidenceStage | null;
    focus_type?: string | null;
    fallback_reason?: string | null;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
    claim_truth?: SessionClaimTruthPayload | null;
}

export interface PresentationPageFocusIntent {
    page_number: number;
    reason?: string | null;
    summary?: string | null;
    missing_required_points?: string[] | null;
}

export interface RetryFocusIntent {
    version: string;
    source_session_id: string;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
    presentation_page?: PresentationPageFocusIntent | null;
}

export interface RetryEntry {
    scenario_type: "sales" | "presentation" | string;
    agent_id?: string | null;
    persona_id?: string | null;
    presentation_id?: string | null;
    focus_intent?: RetryFocusIntent | null;
}

export interface AudioAuditSegment {
    segment_sequence: number;
    created_at?: string | null;
    duration_ms?: number | null;
    size_bytes?: number | null;
    upload_status: string;
    playback_path?: string | null;
    error_message?: string | null;
}

export interface AudioAuditSummary {
    recording_status: string;
    total_segments: number;
    uploaded_segments: number;
    failed_segments: number;
    total_bytes: number;
    latest_segment_sequence?: number | null;
    storage_prefix?: string | null;
    last_uploaded_at?: string | null;
    learner_status: "available" | "partial" | "missing";
    degraded_reasons: string[];
    status?: "available" | "partial" | "missing" | null;
}
export interface AudioAuditPayload {
    summary: AudioAuditSummary;
    segments: AudioAuditSegment[];
}

export interface ConclusionEvidenceSource {
    available: boolean;
    reason?: string | null;
    turn_count?: number | null;
}

export interface ConclusionEvidenceEntry {
    retrieval_source?: ConclusionEvidenceSource | null;
    transcript_source?: ConclusionEvidenceSource | null;
    audio_source?: ConclusionEvidenceSource | null;
}

export interface ConclusionEvidence {
    main_issue?: ConclusionEvidenceEntry | null;
    next_goal?: ConclusionEvidenceEntry | null;
    claim_truth?: ConclusionEvidenceEntry | null;
}

export interface EvidenceDegradationLayer {
    status: "ok" | "degraded";
    token?: string;
    explanation?: string | null;
}

export interface EvidenceDegradation {
    retrieval: EvidenceDegradationLayer;
    transcript: EvidenceDegradationLayer;
    audio: EvidenceDegradationLayer;
    enhanced_report: EvidenceDegradationLayer;
}

export interface CanonicalEvaluationRollup {
    label?: string;
    score: number;
}

export interface CanonicalEvaluationKernel {
    schema_version: string;
    scenario_type: "sales" | "presentation" | string;
    surface_id?: string;
    source_reader_id?: string;
    primary_reader_id?: string;
    mode?: string;
    rollups?: {
        logic?: CanonicalEvaluationRollup | null;
        accuracy?: CanonicalEvaluationRollup | null;
        completeness?: CanonicalEvaluationRollup | null;
    } | null;
    overall_score?: number | null;
    dimensions?: Array<Record<string, unknown>> | null;
    compatibility_reader_ids?: string[] | null;
    downstream_surfaces?: string[] | null;
}

export interface PracticeSessionCompatibilityRollups {
    logic_score?: number | null;
    accuracy_score?: number | null;
    completeness_score?: number | null;
    overall_score?: number | null;
}

export interface PresentationReviewCompatibilityRollups {
    overall_score?: number | null;
}

export interface CompatibilityReaders {
    practice_session_rollup_fields_v1?: PracticeSessionCompatibilityRollups | null;
    presentation_review_dimensions_v1?: PresentationReviewCompatibilityRollups | null;
    [key: string]: unknown;
}

export interface SessionEvidenceContract {
    scenario_type?: "sales" | "presentation";
    overall_score: number | null;
    canonical_evaluation_kernel?: CanonicalEvaluationKernel | null;
    compatibility_readers?: CompatibilityReaders | null;
    effectiveness_snapshot?: Record<string, unknown> | null;
    pass_flags?: SessionPassFlags | null;
    main_capability_passed?: boolean | null;
    overall_result?: SessionOverallResult | null;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
    stage_summary: SessionStageSummary[];
    evaluable?: boolean | null;
    not_evaluable_reason?: SessionNotEvaluableReason | null;
    evidence_completeness?: SessionEvidenceCompleteness | null;
    conclusion_evidence?: ConclusionEvidence | null;
    evidence_degradation?: EvidenceDegradation | null;
    presentation_review?: PresentationReview | null;
    audio_audit?: AudioAuditPayload | null;
}

export type ReplayStageSummary = SessionStageSummary;

export interface ReplayData extends SessionEvidenceContract {
    session_id: string;
    presentation_id?: string | null;
    agent_name?: string | null;
    persona_name?: string | null;
    voice_policy_snapshot_ref?: SessionVoicePolicySnapshotReference | null;
    total_duration_ms: number;
    overall_score: number;
    messages: ReplayMessage[];
    timeline_markers: ReplayTimelineMarker[];
    roleplay_compliance_summary?: SessionRoleplayComplianceSummary | null;
    roleplay_compliance_timeline?: SessionRoleplayComplianceTimelineItem[];
}

export interface ReplayMessagesResponse {
    messages: ReplayMessage[];
    total: number;
}

export interface ReplayHighlight {
    id: string;
    turn_number: number;
    role: string;
    content: string;
    timestamp: string;
    highlight_type: string;
    highlight_reason?: string | null;
    ai_feedback?: string | null;
    suggested_response?: string | null;
    sales_stage?: string | null;
    stage_name?: string | null;
    context?: ReplayHighlightContext;
    learning_evidence?: ReplayLearningEvidence | null;
    audio_url?: string | null;
    score?: number | null;
}

export interface HighlightItem {
    id: string;
    turn_number: number;
    role: "assistant" | "user";
    content: string;
    timestamp: string;
    highlight_type: "good" | "bad";
    highlight_reason: string | null;
    ai_feedback: string | null;
    suggested_response: string | null;
    sales_stage: string | null;
    stage_name: string | null;
    context: ReplayHighlightContext;
    learning_evidence?: ReplayLearningEvidence | null;
    audio_url?: string | null;
    score?: number | null;
}

export interface HighlightsResponse {
    highlights: HighlightItem[];
    total_good: number;
    total_bad: number;
}

export interface HighlightReviewItemPayload {
    item_id?: string;
    message_id: string;
    turn_number: number;
    role: "assistant" | "user" | string;
    content: string;
    reason: string | null;
    stage_name: string | null;
    issue_label: string | null;
    suggested_response: string | null;
    sort_order: number;
}

export interface HighlightReviewShareSummary {
    share_id: string;
    channel: "wecom" | string;
    status: "active" | "revoked" | "expired" | string;
    consent_granted: boolean;
    policy_version: string;
    ttl_days: number;
    expires_at: string;
    revoked_at?: string | null;
    created_at: string;
    access_count: number;
    desensitization_version: string;
}

export interface HighlightReviewResponse {
    review_id: string;
    session_id: string;
    user_id: string;
    schema_version: "highlight_review_v1" | string;
    title?: string | null;
    items: HighlightReviewItemPayload[];
    shares: HighlightReviewShareSummary[];
    share_policy?: Record<string, unknown>;
    updated_at: string;
}

export interface HighlightReviewShareCreateResponse extends HighlightReviewShareSummary {
    share_url: string;
    share_token: string;
    public_api_path: string;
}

export interface PracticeSessionReport extends SessionEvidenceContract {
    session_id: string;
    scenario_type: "sales" | "presentation";
    logic_score: number;
    accuracy_score: number;
    completeness_score: number;
    overall_score: number;
    suggestions: string[];
    audio_url?: string | null;
    transcript_url?: string | null;
    voice_policy_snapshot_ref?: SessionVoicePolicySnapshotReference | null;
    presentation_review?: PresentationReview | null;
    retry_entry?: RetryEntry | null;
    audio_audit?: AudioAuditPayload | null;
    roleplay_compliance_summary?: SessionRoleplayComplianceSummary | null;
}

export interface ReportTrendPoint {
    session_id: string;
    date: string;
    scenario_type: "sales" | "presentation" | string;
    logic_score: number;
    accuracy_score: number;
    completeness_score: number;
    overall_score: number;
    is_current: boolean;
}

export interface ReportTrendsResponse {
    session_id: string;
    scenario_type: "sales" | "presentation" | string;
    score_basis: string;
    points: ReportTrendPoint[];
    delta_vs_previous: {
        logic_score: number;
        accuracy_score: number;
        completeness_score: number;
        overall_score: number;
    } | null;
    explanation?: string | null;
}

export interface PresentationProgress {
    source: "user_presentation_progress" | string;
    user_id: string;
    presentation_id: string;
    last_page_number: number;
    last_session_id?: string | null;
    last_practice_at?: string | null;
    updated_at?: string | null;
}

export interface HistorySessionSummary extends SessionEvidenceContract {
    session_id: string;
    scenario_name: string;
    scenario_type: "sales" | "presentation";
    persona_name: string | null;
    agent_name: string | null;
    start_time: string;
    duration_seconds: number;
    overall_score: number | null;
    report_status: "pending" | "processing" | "completed" | "failed";
    report_generated_at: string | null;
    status: string;
    feedback_summary?: string | null;
}

export interface HistoryListResponse {
    sessions: HistorySessionSummary[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface HistoryStatistics {
    total_sessions: number;
    evaluable_sessions: number;
    not_evaluable_sessions: number;
    average_score: number;
    best_score: number;
    score_basis?: string;
    total_practice_time_seconds: number;
    total_practice_time_minutes: number;
}

export interface HistoryTrendPoint extends Pick<
    SessionEvidenceContract,
    | "overall_score"
    | "evaluable"
    | "not_evaluable_reason"
    | "evidence_completeness"
    | "canonical_evaluation_kernel"
    | "compatibility_readers"
    | "stage_summary"
    | "main_issue"
    | "next_goal"
> {
    session_id: string;
    date: string;
    logic_score?: number;
    accuracy_score?: number;
    completeness_score?: number;
    scenario_type?: string;
}

// Canonical retrieval truth — produced by the backend read-model
// `build_retrieval_facts` and persisted in `effectiveness_snapshot.retrieval_facts`.
export type RetrievalFactsStatus =
    | "hit"
    | "miss"
    | "search_failed"
    | "kb_not_ready"
    | "not_triggered"
    | "no_knowledge_base"
    | "disabled";

export interface RetrievalAttemptSummary {
    knowledge_base_id: string;
    knowledge_base_name?: string;
    snippet?: string;
    retrieval_mode?: string;
    score?: number;
}

export interface RetrievalLatestAttempt {
    status: string;
    query?: string;
    attempted_at?: string | null;
    retrieval_mode?: string | null;
    error_summary?: string | null;
    result_count?: number;
    knowledge_base_ids?: string[];
    result_summaries?: RetrievalAttemptSummary[];
}

export interface RetrievalFacts {
    kb_bound: boolean;
    knowledge_base_ids: string[];
    knowledge_base_count: number;
    retrieval_enabled: boolean;
    status: RetrievalFactsStatus;
    summary: string;
    attempt_count: number;
    hit_count: number;
    hit_rate: number;
    latest_attempt?: RetrievalLatestAttempt | null;
    recent_attempts?: RetrievalLatestAttempt[];
    miss_explanation?: string | null;
    failure_explanation?: string | null;
}

export interface KnowledgeCheckDiagnostics {
    session_id: string;
    voice_mode?: "legacy" | "stepfun_realtime" | string;
    status:
        | "disabled"
        | "no_knowledge_base"
        | "not_triggered"
        | "kb_not_ready"
        | "search_failed"
        | "hit"
        | "miss";
    summary: string;
    internal_retrieval_enabled: boolean;
    knowledge_base_ids: string[];
    knowledge_base_count: number;
    attempt_count: number;
    hit_query_count: number;
    total_results: number;
    hit_rate: number;
    last_query: string;
    last_result_count: number;
    last_status: string;
    last_top_k?: number | null;
    last_similarity_threshold?: number | null;
    last_error?: string;
    last_retrieval_mode?: string;
    recent_queries: string[];
    updated_at?: string | null;
    evidence_degradation?: EvidenceDegradation | null;
    knowledge_answer_diagnostics?: Record<string, unknown> | null;
}
export type SupervisorDecision = "pending" | "approved" | "rejected" | "needs_retraining";

export type ReadinessStatus = "not_ready" | "shadow_only" | "ready_for_trial" | "approved";

export type RetrainingTaskStatus = "todo" | "in_progress" | "completed" | "cancelled";

export interface ScoreDimensionDelta {
    name: string;
    original_score?: number | null;
    retraining_score?: number | null;
    delta?: number | null;
}

export interface BeforeAfterComparison {
    source_session_id: string;
    completed_session_id?: string | null;
    original_score?: number | null;
    retraining_score?: number | null;
    score_delta?: number | null;
    weak_dimension_changes: ScoreDimensionDelta[];
    retraining_completed: boolean;
}

export type CalibrationLabel =
    "accurate" | "too_high" | "too_low" | "wrong_reason" | "missing_evidence";

export interface SupervisorScoreCalibration {
    review_id: string;
    session_id: string;
    dimension: string;
    ai_score?: number | null;
    supervisor_score?: number | null;
    calibration_label: CalibrationLabel;
    comment?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface SupervisorScoreCalibrationUpsertRequest {
    session_id: string;
    dimension: string;
    ai_score?: number | null;
    supervisor_score?: number | null;
    calibration_label: CalibrationLabel;
    comment?: string | null;
}

export interface RetrainingTask {
    task_id: string;
    user_id: string;
    source_session_id: string;
    source_review_id: string;
    training_task_id?: string | null;
    training_task?: SessionTrainingTaskSummary | null;
    skill_dimension: string;
    title: string;
    description?: string | null;
    status: RetrainingTaskStatus;
    completed_session_id?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
    before_after?: BeforeAfterComparison | null;
}

export interface RetrainingTaskCreateRequest {
    user_id?: string | null;
    source_session_id: string;
    source_review_id: string;
    skill_dimension: string;
    title: string;
    description?: string | null;
}

export interface RetrainingTaskCompleteRequest {
    completed_session_id: string;
}

export interface RetrainingTaskStartResponse {
    task: RetrainingTask;
    session_id: string;
}

export interface SupervisorReview {
    review_id: string;
    session_id: string;
    trainee_user_id: string;
    supervisor_user_id: string;
    decision: SupervisorDecision;
    readiness_status: ReadinessStatus;
    comment?: string | null;
    required_retraining: boolean;
    audit_metadata?: Record<string, unknown> | null;
    created_at?: string | null;
    updated_at?: string | null;
    retraining_tasks: RetrainingTask[];
    before_after?: BeforeAfterComparison | null;
    calibrations: SupervisorScoreCalibration[];
}

export interface SupervisorReviewCreateRequest {
    session_id: string;
    decision?: SupervisorDecision;
    readiness_status?: ReadinessStatus;
    comment?: string | null;
    required_retraining?: boolean;
    skill_dimension?: string | null;
    audit_metadata?: Record<string, unknown> | null;
}

export interface SupervisorReviewDecisionUpdateRequest {
    decision: SupervisorDecision;
    readiness_status?: ReadinessStatus | null;
    comment?: string | null;
    required_retraining?: boolean | null;
    skill_dimension?: string | null;
    audit_metadata?: Record<string, unknown> | null;
}

export interface SupervisorTeamReport {
    session_id: string;
    trainee_user_id: string;
    trainee_name?: string | null;
    scenario_type: string;
    status: string;
    report_status?: string | null;
    overall_score?: number | null;
    started_at?: string | null;
    completed_at?: string | null;
    latest_review?: SupervisorReview | null;
    before_after?: BeforeAfterComparison | null;
}

export interface CertificationReviewQueueItem {
    review_id: string;
    session_id: string;
    report_id: string;
    learner: {
        user_id: string;
        name?: string | null;
        email?: string | null;
    };
    curriculum: {
        practice_template: Record<string, unknown>;
        stage_keys: string[];
        stage_snapshots: Record<string, unknown>;
    };
    score?: number | null;
    evidence: {
        transcript_anchors: SessionTrainingReportEvidenceItem[];
        stage_snapshots: Record<string, unknown>;
        thinking_evidence: SessionThinkingEvidenceEntry[];
    };
    submitted_at?: string | null;
    outcome: SupervisorDecision;
}
