// API Response types

export interface ApiResponse<T> {
    success: boolean;
    data?: T;
    error?: string;
    message?: string;
    trace_id?: string;
}

// Dashboard types
export interface DashboardStats {
    weekly_activity: {
        total_duration_minutes: number;
        session_count: number;
        trend_direction: "up" | "down" | "flat";
        trend_percentage: number;
    };
    last_session?: {
        score: number;
        percentile: number;
        trend: "up" | "down" | "stable";
    };
    effectiveness?: {
        pass_rate_3min_flow: number;
        pass_rate_5turn_defense: number;
        pass_rate_4step_structure: number;
        next_day_retry_rate: number;
    };
    score_basis?: string;
    evaluable_sessions?: number;
    not_evaluable_sessions?: number;
}

export interface GrowthAchievement {
    achievement_id: string;
    code: string;
    name: string;
    description: string;
    icon_key: string;
    unlocked_at?: string | null;
    evidence?: Record<string, unknown> | null;
}

export interface GrowthNotification {
    notification_id: string;
    type: "system" | "tip" | "reminder" | "achievement" | "ai_coach" | string;
    title: string;
    content: string;
    action_label?: string | null;
    action_path?: string | null;
    source?: string | null;
    evidence?: Record<string, unknown> | null;
    is_read: boolean;
    created_at?: string | null;
}

export interface GrowthGoal {
    goal_id: string;
    goal_type: "weekly_sessions" | "monthly_presentations" | string;
    period: "weekly" | "monthly" | string;
    target_count: number;
    current_progress: number;
    progress_ratio: number;
    start_date: string;
    end_date: string;
    is_active: boolean;
}

export interface GrowthDashboardResponse {
    achievements: {
        unlocked: GrowthAchievement[];
    };
    notifications: {
        items: GrowthNotification[];
        unread_count: number;
    };
    goal: GrowthGoal | null;
    adaptive_difficulty?: AdaptiveDifficultyDryRunResponse;
    rules?: {
        achievement_ruleset_version?: string | null;
        ai_coach_ruleset_version?: string | null;
    };
}

export interface VoicePolicyRuntimeBinding {
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

export interface VoicePolicySnapshotReference {
    voice_mode?: string | null;
    runtime_profile_id?: string | null;
    instruction_contract_hash?: string | null;
    network_access_mode?: "off" | "controlled" | string | null;
    tool_policy: Record<string, unknown>;
    knowledge_base_ids: string[];
    source: Record<string, string>;
    resolved_at?: string | null;
    runtime_binding?: VoicePolicyRuntimeBinding | null;
    agent_persona_override_config?: Record<string, unknown> | null;
}

export type TrainingRuntimeSubject = "training_scenario_runtime";

export interface TrainingRuntimeDescriptor {
    subject: TrainingRuntimeSubject;
    session_id: string;
    scenario_type: "sales" | "presentation";
    agent_id?: string | null;
    persona_id?: string | null;
    presentation_id?: string | null;
    voice_mode?: "legacy" | "stepfun_realtime" | string | null;
    runtime_profile_id?: string | null;
    focus_intent?: RetryFocusIntent | null;
}

export type SessionStatus =
    | "preparing"
    | "in_progress"
    | "paused"
    | "completed"
    | "scoring";

export type SessionLifecycleAction = "start" | "pause" | "resume" | "end";

export interface SessionLifecycleRequest {
    action: SessionLifecycleAction;
}

export interface SessionLifecycleResponse {
    session_id: string;
    previous_status: SessionStatus;
    status: SessionStatus;
    ai_state: "listening" | "idle";
    changed: boolean;
    scenario_type?: "sales" | "presentation" | null;
    runtime_subject?: TrainingRuntimeSubject;
    start_time: string;
    end_time?: string | null;
    total_duration_seconds?: number | null;
}

export interface SessionItem {
    id: string;
    title: string;
    scenario_type: "sales" | "presentation";
    presentation_id?: string | null;
    overall_score: number;
    duration_seconds: number;
    start_time: string;
    status: SessionStatus;
    report_status?: "pending" | "processing" | "completed" | "failed" | string | null;
    report_generated_at?: string | null;
    user_id?: string;
    username?: string;
    session_id?: string;
    agent_id?: string | null;
    persona_id?: string | null;
    agent_name?: string;
    persona_name?: string;
    voice_mode?: "legacy" | "stepfun_realtime";
    runtime_subject?: TrainingRuntimeSubject;
    runtime_descriptor?: TrainingRuntimeDescriptor | null;
    runtime_profile_id?: string | null;
    voice_policy_snapshot?: Record<string, unknown> | null;
    voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
    effectiveness_snapshot?: Record<string, unknown> | null;
    evaluable?: boolean | null;
    not_evaluable_reason?: SessionNotEvaluableReason | string | null;
    feedback_summary?: string;
}

export interface PracticeSessionRuntime {
    session_id: string;
    scenario_type?: "sales" | "presentation";
    voice_mode?: "legacy" | "stepfun_realtime" | string;
    agent_id?: string | null;
    persona_id?: string | null;
    presentation_id?: string | null;
    runtime_subject?: TrainingRuntimeSubject;
    runtime_descriptor?: TrainingRuntimeDescriptor | null;
    runtime_profile_id?: string | null;
    status?: SessionStatus;
    start_time?: string;
}

export interface TrainingCategory {
    id: string;
    title: string;
    description: string;
    icon_key: string;
    color_theme: string;
    agent_count: number;
    tags: string[];
    status: "active" | "coming_soon" | "inactive";
}

export type SalesCombinationRuleStatus = "draft" | "published" | "archived";

export type SalesCombinationFallbackPolicy = "client_default_v1" | "hide_all";

export interface SalesCombinationRule {
    id: string;
    capability: string;
    role: string;
    priority: number;
    enabled: boolean;
    required_agent_match?: string[];
    required_persona_match?: string[];
}

export interface SalesCombinationRuleAuditSummary {
    published_by?: string | null;
    published_at?: string | null;
    reason?: string | null;
    trace_id?: string | null;
}

export interface SalesCombinationRuleSet {
    rule_set_id: string;
    version: string;
    status: SalesCombinationRuleStatus;
    effective_at: string | null;
    combinations: SalesCombinationRule[];
    fallback_policy: SalesCombinationFallbackPolicy;
    audit_summary?: SalesCombinationRuleAuditSummary;
}

export interface SalesCombinationRulePermission {
    can_view: boolean;
    can_mutate: boolean;
    can_publish: boolean;
    reason?: string | null;
}

export interface BusinessRuleAuditEntry {
    id?: string;
    actor?: string | null;
    action: "draft" | "validate" | "preview" | "publish" | "rollback" | string;
    before_version?: string | null;
    after_version?: string | null;
    reason?: string | null;
    trace_id?: string | null;
    created_at?: string | null;
}

export type BusinessRuleConfigStatus = "draft" | "published" | "archived" | "disabled" | string;

export interface BusinessRuleDefinition {
    key: string;
    domain: string;
    schema_version: string;
    default_value: Record<string, unknown>;
    type: string;
    range_or_allowlist: Record<string, unknown>;
    read_path: string;
    admin_entry: string;
    permission: string;
    audit_policy: string;
    fallback_policy: string;
    rollback_policy: string;
}

export interface BusinessRuleConfigRecord {
    id: string;
    domain: string;
    key: string;
    schema_version: string;
    status: BusinessRuleConfigStatus;
    version: number;
    value: Record<string, unknown>;
    default_value: Record<string, unknown>;
    type: string;
    range_or_allowlist: Record<string, unknown>;
    read_path: string;
    admin_entry: string;
    permission: string;
    audit_policy: string;
    fallback_policy: string;
    rollback_policy: string;
    enabled: boolean;
    validation_errors?: Array<Record<string, unknown>> | null;
    created_by?: string | null;
    updated_by?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface BusinessRuleHistoryResponse {
    definition: BusinessRuleDefinition;
    items: BusinessRuleConfigRecord[];
    total: number;
    audit_logs?: BusinessRuleAuditEntry[];
}

export interface BusinessRuleValidationResponse {
    valid: boolean;
    normalized_value: Record<string, unknown>;
}

export interface BusinessRulePreviewResponse {
    valid: boolean;
    summary: Record<string, unknown>;
    active_version?: number | null;
    active_config_id?: string | null;
}

export type ScoringRulesetScenarioType = "sales" | "presentation";

export type ScoringRulesetStatus = "draft" | "published" | "archived" | string;

export interface ScoringRulesetRecord {
    ruleset_id: string | null;
    scenario_type: ScoringRulesetScenarioType;
    version: string;
    display_name: string;
    description?: string | null;
    status: ScoringRulesetStatus;
    definition: Record<string, unknown>;
    is_active: boolean;
    source: "default" | "admin" | string;
    created_at?: string | null;
    updated_at?: string | null;
    published_at?: string | null;
    actor_id?: string | null;
}

export interface ScoringRulesetListResponse {
    items: ScoringRulesetRecord[];
    total: number;
    actor_id?: string | null;
}

export interface ScoringRulesetCreateRequest {
    scenario_type: ScoringRulesetScenarioType;
    version: string;
    display_name: string;
    description?: string | null;
    definition: Record<string, unknown>;
}

export interface ScoringRulesetUpdateRequest {
    display_name?: string;
    description?: string | null;
    definition?: Record<string, unknown>;
}

export interface ScoringRulesetDryRunResponse {
    session_id: string;
    mode: "dry_run" | string;
    mutates_history: boolean;
    baseline: Record<string, unknown>;
    candidate: Record<string, unknown>;
    delta: Record<string, unknown>;
    actor_id?: string | null;
}

export interface ScoringRulesetAuditEntry {
    id: string;
    action: string;
    actor_id?: string | null;
    actor_role?: string | null;
    reason?: string | null;
    trace_id?: string | null;
    before?: Record<string, unknown> | null;
    after?: Record<string, unknown> | null;
    created_at?: string | null;
}

export interface ScoringRulesetAuditLogResponse {
    items: ScoringRulesetAuditEntry[];
    total: number;
}

export interface AdminPermissionMatrixEntry {
    route_family: string;
    auth_surface: string;
    routes: string[];
    allowed_roles: string[];
    non_admin_deny_path: string;
    current_evidence: string[];
    risk: "high" | "medium" | "baseline" | string;
    priority: "fix-first" | "watch" | "baseline" | string;
    rationale: string;
}

export interface AdminGovernancePermissionsResponse {
    items: AdminPermissionMatrixEntry[];
    total: number;
    fix_first_route_families: string[];
    positive_control_route_families: string[];
    support_log_redaction: {
        visible_fields: string[];
        diagnostic_allowlist: string[];
        backend_only_fields: string[];
        guidance: string;
        quality_event_prerequisite: string;
    };
}

export interface AdminGovernanceSettingsBacklogItem {
    surface: string;
    label: string;
    status: string;
    missing_capabilities: string[];
    fallback_policy: string;
}

export interface AdminGovernanceSettingsBacklogResponse {
    items: AdminGovernanceSettingsBacklogItem[];
    total: number;
    policy: string;
}

export type AdminSettingsSurface = "general" | "security" | "notifications";

export interface AdminSettingsAuditEntry {
    id: string;
    config_id?: string | null;
    action: string;
    actor_id?: string | null;
    before_version?: number | null;
    after_version?: number | null;
    reason?: string | null;
    trace_id?: string | null;
    created_at?: string | null;
}

export interface AdminSettingsConfigRecord {
    id: string;
    key: string;
    status: string;
    version: number;
    value: Record<string, unknown>;
    default_value: Record<string, unknown>;
    enabled: boolean;
    validation_errors: unknown[];
    created_by?: string | null;
    updated_by?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface AdminSettingsSurfaceResponse {
    surface: AdminSettingsSurface;
    key: string;
    definition: BusinessRuleDefinition;
    active: {
        value: Record<string, unknown>;
        source: string;
        config_id?: string | null;
        version?: number | null;
        status?: string | null;
        fallback_reason?: string | null;
    };
    drafts: AdminSettingsConfigRecord[];
    history: AdminSettingsConfigRecord[];
    audit_logs?: AdminSettingsAuditEntry[];
    permissions: {
        can_view: boolean;
        can_mutate: boolean;
        can_publish: boolean;
        permission: string;
    };
}

export interface AdminSettingsPreviewResponse {
    valid: boolean;
    summary: Record<string, unknown>;
    active_version?: number | null;
    active_config_id?: string | null;
}

export interface SalesCombinationRuleSetListResponse {
    active: SalesCombinationRuleSet | null;
    drafts: SalesCombinationRuleSet[];
    history: SalesCombinationRuleSet[];
    audit_log?: BusinessRuleAuditEntry[];
    permissions?: SalesCombinationRulePermission;
}

export interface SalesCombinationRuleValidationIssue {
    path: string;
    message: string;
}

export interface SalesCombinationRuleValidationResult {
    valid: boolean;
    errors: SalesCombinationRuleValidationIssue[];
    warnings?: SalesCombinationRuleValidationIssue[];
}

export type SalesCombinationPreviewStatus =
    | "matched"
    | "missing_agent"
    | "missing_persona"
    | "disabled";

export interface SalesCombinationPreviewItem {
    combination_id: string;
    capability: string;
    role: string;
    status: SalesCombinationPreviewStatus;
    matched_agent_name?: string | null;
    matched_persona_name?: string | null;
    reason?: string | null;
}

export interface SalesCombinationPreviewResponse {
    valid: boolean;
    ruleset_version: string;
    previewed_at?: string | null;
    coverage: {
        total: number;
        matched: number;
        missing_agent: number;
        missing_persona: number;
        disabled: number;
    };
    items: SalesCombinationPreviewItem[];
    validation_errors?: SalesCombinationRuleValidationIssue[];
}

export interface SalesCombinationRuleMutationResponse {
    ruleset: SalesCombinationRuleSet;
    audit: BusinessRuleAuditEntry;
}

export interface Recommendation {
    title: string;
    reason: string;
    action_label: string;
    target_path: string;
    score_basis?: string | null;
    recommendation_kind?: "sales_retry" | "presentation_page_retry" | string | null;
    scenario_type?: "sales" | "presentation" | string | null;
    source_session_id?: string | null;
    rule_version?: string | null;
    ruleset_source?: string | null;
    explanation?: string | null;
    weak_dimension?: string | null;
    evidence_summary?: Record<string, unknown> | null;
    focus_page?: number | null;
    due_reason?: string | null;
    focus?: string | null;
    suggested_duration?: string | number | null;
    suggested_duration_minutes?: number | null;
    is_due_today?: boolean | null;
}

// Agent types
export interface Agent {
    id: string;
    name: string;
    description: string;
    icon?: string;
    category: string;
    status: string;
    role?: string;
    difficulty?: string;
    welcome_message?: string;
    ui_metadata?: {
        icon_key?: string;
        theme_color?: string;
        tags?: string[];
    };
}

export interface Persona {
    id: string;
    name: string;
    description: string;
    icon?: string;
    category: string;
    difficulty: string;
    status: string;
    system_prompt: string;
}

// Analytics types
export interface AnalyticsIssueFamilyBucket {
    issue_type: string;
    issue_text: string;
    count: number;
}

export interface AnalyticsNotEvaluableReasonBucket {
    reason: string;
    count: number;
}

export interface AnalyticsRepeatedGoalBucket {
    goal_type: string;
    goal_text: string;
    count: number;
}

export interface AnalyticsOverview {
    total_users: number;
    active_users_today: number;
    active_users_week: number;
    total_sessions: number;
    sessions_today: number;
    completed_sessions: number;
    completion_rate: number;
    average_score: number;
    average_duration_minutes: number;
    growth: {
        users_rate: number;
        sessions_rate: number;
        score_rate: number;
    };
    evaluable_sessions?: number;
    not_evaluable_sessions?: number;
    score_basis?: string;
    top_issue_families?: AnalyticsIssueFamilyBucket[];
    not_evaluable_reasons?: AnalyticsNotEvaluableReasonBucket[];
}

export interface TrendDataPoint {
    date: string;
    sessions_count: number;
    average_score: number;
    active_users: number;
    evaluable_session_count?: number;
    not_evaluable_session_count?: number;
    logic_score?: number;
    accuracy_score?: number;
    completeness_score?: number;
    overall_result?: SessionOverallResult | null;
    evaluable?: boolean | null;
    not_evaluable_reason?: SessionNotEvaluableReason | null;
    evidence_completeness?: SessionEvidenceCompleteness | null;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
    stage_summary?: SessionStageSummary[] | null;
}

export interface ScoreDistribution {
    excellent: number;
    good: number;
    fair: number;
    poor: number;
}

export interface AnalyticsProjectionSummary {
    average_score?: number;
    best_score?: number;
    evaluable_sessions: number;
    not_evaluable_sessions: number;
    score_basis?: string;
    issue_family_distribution: AnalyticsIssueFamilyBucket[];
    not_evaluable_reasons: AnalyticsNotEvaluableReasonBucket[];
    repeated_main_issues: UserRepeatedMainIssueBucket[];
    repeated_next_goals: AnalyticsRepeatedGoalBucket[];
}

export interface AnalyticsTrends {
    trend_data: TrendDataPoint[];
    score_distribution: ScoreDistribution;
    projection_summary?: AnalyticsProjectionSummary;
}

export interface AgentStatsItem {
    agent_id: string;
    agent_name: string;
    category: string;
    usage_count: number;
    average_score: number;
    completion_rate: number;
    evaluable_sessions?: number;
    not_evaluable_sessions?: number;
    score_basis?: string;
}

export interface PersonaStatsItem {
    persona_id: string;
    persona_name: string;
    difficulty: string;
    usage_count: number;
    average_score: number;
    evaluable_sessions?: number;
    not_evaluable_sessions?: number;
    score_basis?: string;
}

export interface AnalyticsAgents {
    agent_stats: AgentStatsItem[];
    persona_stats: PersonaStatsItem[];
    scenario_distribution: Record<string, number>;
}

export interface LeaderboardEntry {
    rank: number;
    user_id: string;
    username: string;
    department: string | null;
    total_sessions: number;
    average_score: number;
    best_score: number;
    total_duration_minutes: number;
    evaluable_sessions?: number;
    not_evaluable_sessions?: number;
    primary_issue_type?: string | null;
    primary_next_goal_type?: string | null;
    score_basis?: string;
}

export interface AnalyticsLeaderboard {
    leaderboard: LeaderboardEntry[];
}

export type SupportRuntimeReleaseHealthStatus = "healthy" | "warning" | "blocking";

export type SupportRuntimeFaultSeverity = "blocking" | "warning";

export interface SupportRuntimeAnomalySummaryItem {
    kind: string;
    count: number;
}

export interface SupportRuntimeOverview {
    generated_at: string;
    window_hours: number;
    session_health: {
        active_sessions: number;
        total_sessions_window: number;
        completed_sessions_window: number;
        scoring_sessions: number;
        stuck_scoring_sessions: number;
        not_evaluable_completed_sessions_window: number;
        completion_rate: number;
    };
    release_health: {
        status: SupportRuntimeReleaseHealthStatus;
        blocking_count: number;
        warning_count: number;
        typed_anomaly_count: number;
        blocking_sessions_count: number;
        warning_sessions_count: number;
        supplemental_warning_log_count: number;
    };
    anomaly_summary: {
        blocking: SupportRuntimeAnomalySummaryItem[];
        warning: SupportRuntimeAnomalySummaryItem[];
    };
}

export interface AssetGovernanceAnomaly {
    kind: string;
    severity: "warning" | "blocking" | string;
    summary: string;
    detected_at?: string | null;
    session_id?: string | null;
    source?: string | null;
}

export interface AssetGovernanceImpactSummary {
    impact_level: "low" | "medium" | "high" | string;
    recent_session_count: number;
    active_session_count: number;
    impacted_user_count: number;
    last_session_at: string | null;
}

export interface AssetGovernanceRecentChangeSummary {
    last_changed_at: string | null;
    latest_change_type: string;
    latest_change_label: string;
    change_count_7d: number;
    sessions_since_change: number;
}

export interface AssetGovernanceHealthSummary {
    status: "healthy" | "warning" | "blocking" | string;
    anomaly_count: number;
    blocking_count: number;
    warning_count: number;
    sample_anomalies: AssetGovernanceAnomaly[];
}

export interface AssetGovernanceSummary {
    impact_summary?: AssetGovernanceImpactSummary | null;
    recent_change_summary?: AssetGovernanceRecentChangeSummary | null;
    health_summary?: AssetGovernanceHealthSummary | null;
}

export interface LinkedAssetChangeReference {
    asset_type: string;
    asset_label: string;
    asset_id: string;
    asset_name: string;
    admin_path: string;
    latest_change_label: string;
    latest_change_type: string;
    last_changed_at: string | null;
    change_count_7d: number;
    sessions_since_change: number;
    impact_level: string;
    health_status: string;
}

export interface SupportRuntimeFaultDiagnostics {
    linked_asset_changes: LinkedAssetChangeReference[];
    [key: string]: unknown;
}

export interface SupportRuntimeFaultItem {
    source: "session" | "system_log" | string;
    severity: SupportRuntimeFaultSeverity;
    kind: string;
    summary: string;
    detected_at: string | null;
    session_id: string | null;
    scenario_type: "sales" | "presentation" | string | null;
    session_status: string | null;
    report_status: string | null;
    diagnostics: SupportRuntimeFaultDiagnostics;
}

export interface SupportRuntimeFaultsResponse {
    generated_at: string;
    items: SupportRuntimeFaultItem[];
    count: number;
    limit: number;
    severity?: SupportRuntimeFaultSeverity | null;
}

// User types
export interface User {
    user_id: string;
    name: string;
    email: string;
    department?: string;
    role: string;
    is_active: boolean;
    created_at: string;
    last_login?: string;
}

// Admin types
export interface AdminUser {
    id: string;
    user_id: string;
    display_name: string;
    email?: string;
    department?: string;
    role: string;
    is_active: boolean;
    status: string;
    created_at: string;
    last_login?: string;
    last_active_at?: string;
    total_sessions: number;
    total_duration_minutes: number;
    average_score: number;
}

export interface AdminAgent {
    id: string;
    name: string;
    description: string;
    category: string;
    status: string;
    icon?: string;
    welcome_message?: string;
    voice_config?: {
        voice_id?: string;
        speed?: number;
    };
    ui_metadata?: {
        icon_key?: string;
        theme_color?: string;
        tags?: string[];
    };
    created_at: string;
    updated_at: string;
    usage_count?: number;
    persona_count?: number;
    knowledge_base_count?: number;
    capabilities_config?: Record<string, unknown>;
}

export type AdminPersonaPressureSource =
    | "explicit"
    | "legacy_sales_focus_extensions"
    | "none"
    | string;

export interface AdminPersonaPressureDirection {
    sales_focus?: string;
    value_axes?: string[];
    objection_axes?: string[];
    [key: string]: unknown;
}

export interface AdminPersonaPressureFollowUpBehavior {
    question_strategy?: string;
    revisit_on_evasion?: boolean;
    require_evidence?: boolean;
    expected_customer_questions?: string[];
    [key: string]: unknown;
}

export interface AdminPersonaCustomerPressure {
    source?: AdminPersonaPressureSource;
    pressure_direction?: AdminPersonaPressureDirection;
    follow_up_behavior?: AdminPersonaPressureFollowUpBehavior;
    [key: string]: unknown;
}

export interface AdminPersonaPolicy {
    version?: number;
    system_prompt?: string;
    knowledge_base_ids?: string[];
    tool_policy?: Record<string, unknown>;
    sales_focus?: string;
    value_axes?: string[];
    objection_axes?: string[];
    expected_customer_questions?: string[];
    customer_pressure?: AdminPersonaCustomerPressure;
    [key: string]: unknown;
}

export interface AdminIndustryPackRuntimeTarget {
    persisted_in?: string;
    compiled_instruction_section?: string;
    compiled_instruction_sections?: string[];
    runtime_service?: string;
    tool_builder?: string;
    read_side?: string;
    report_evidence_surface?: string;
    session_entry?: string;
    websocket_router?: string;
    note?: string;
    [key: string]: unknown;
}

export interface AdminAgentIndustryPackContract {
    contract_version: number;
    industry_pack: {
        authority_model: string;
        summary: string;
        composition_units?: string[];
    };
    entrypoints: Record<string, string>;
    runtime_authorities: string[];
    composition_rules: string[];
    observability_surfaces: string[];
}

export interface AdminPersonaIndustryPackContract {
    contract_version: number;
    owned_fields: Record<string, string[]>;
    runtime_targets: Record<string, AdminIndustryPackRuntimeTarget>;
    governance_rules: string[];
}

export interface AdminPersonaPolicyHealthIssue {
    persona_id: string;
    persona_name: string;
    issue_types: string[];
    policy_version?: number | null;
    require_kb_grounding?: boolean;
    pressure_source?: string | null;
}

export interface AdminPersonaPolicyHealthReport {
    generated_at: string;
    summary: {
        total: number;
        healthy: number;
        with_issues: number;
    };
    issue_type_counts: Record<string, number>;
    sample_issues: AdminPersonaPolicyHealthIssue[];
}

export interface AdminPersona {
    id: string;
    name: string;
    description: string;
    category: string;
    difficulty: string;
    status: string;
    icon?: string;
    system_prompt: string;
    governance_summary?: AssetGovernanceSummary | null;
    traits?: Record<string, string>;
    agent_id?: string;
    agent_name?: string;
    knowledge_bases?: AdminKnowledgeBase[];
    created_at?: string;
    updated_at?: string;
    usage_count?: number;
    knowledge_base_ids?: string[];
    persona_policy?: AdminPersonaPolicy;
    tts_config?: {
        voice?: string;
        rate?: string;
        volume?: string;
        pitch?: string;
    };
}

export type AdminModelConfigType = "llm" | "embedding" | "asr" | "tts";

export type AdminModelConfigProvider =
    | "openai"
    | "azure"
    | "alibaba"
    | "anthropic"
    | "local"
    | "local_streaming";

export interface AdminModelConfigListItem {
    id: string;
    name: string;
    model_type: AdminModelConfigType;
    provider: AdminModelConfigProvider;
    model_name: string;
    is_default: boolean;
    is_active: boolean;
    last_test_status: string | null;
}

export interface AdminModelConfigGrouped {
    llm: AdminModelConfigListItem[];
    embedding: AdminModelConfigListItem[];
    asr: AdminModelConfigListItem[];
    tts: AdminModelConfigListItem[];
    total: number;
}

export interface AdminModelConfigDetail extends AdminModelConfigListItem {
    base_url: string;
    api_key_masked: string;
    extra_config: Record<string, unknown>;
    last_tested_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface AdminModelConfigCreateRequest {
    name: string;
    model_type: AdminModelConfigType;
    provider: AdminModelConfigProvider;
    base_url: string;
    api_key: string;
    model_name: string;
    extra_config?: Record<string, unknown>;
    is_default?: boolean;
}

export interface AdminModelConfigTestRequest {
    model_type: AdminModelConfigType;
    provider: AdminModelConfigProvider;
    base_url: string;
    api_key: string;
    model_name: string;
    extra_config?: Record<string, unknown>;
}

export interface AdminModelConfigUpdateRequest {
    name?: string;
    base_url?: string;
    api_key?: string;
    model_name?: string;
    extra_config?: Record<string, unknown>;
    is_default?: boolean;
    is_active?: boolean;
}

export interface AdminModelConfigCreateResponse {
    id: string;
    name: string;
    model_type: AdminModelConfigType;
    provider: AdminModelConfigProvider;
    model_name: string;
    is_default: boolean;
    created_at: string;
}

export interface AdminModelConfigTestResponse {
    success: boolean;
    message: string;
    latency_ms?: number;
}

export interface AdminKnowledgeBase {
    id: string;
    name: string;
    description: string;
    category: string;
    status: string;
    document_count: number;
    total_chunks: number;
    doc_count?: number;
    settings?: KnowledgeBaseSettings | null;
    rag_profile_id?: string | null;
    rag_profile_name?: string | null;
    created_at: string;
    updated_at: string;
    governance_summary?: AssetGovernanceSummary | null;
}

export interface KnowledgeBaseSettings {
    chunking: ChunkingSettings;
    semantic_cache: SemanticCacheSettings;
}

export interface ChunkingSettings {
    strategy: "element_boundary" | "fixed_size" | "parent_child";
    chunk_size: number;
    chunk_overlap: number;
}

export interface SemanticCacheSettings {
    enabled: boolean;
    similarity_threshold: number;
    ttl_seconds: number;
}

export interface AssetGovernanceSubject {
    governance_summary?: AssetGovernanceSummary | null;
}

// ── RAG Profile Types ──

export interface RagProfile {
    id: string;
    name: string;
    description: string | null;
    is_system_default: boolean;
    chunking: RagProfileChunking;
    semantic_cache: RagProfileSemanticCache;
    cross_encoder: RagProfileCrossEncoder;
    applied_kb_count: number;
    created_at: string | null;
    updated_at: string | null;
}

export interface RagProfileChunking {
    strategy: "element_boundary" | "fixed_size" | "parent_child";
    chunk_size: number;
    chunk_overlap: number;
}

export interface RagProfileSemanticCache {
    enabled: boolean;
    similarity_threshold: number;
    ttl_seconds: number;
}

export interface RagProfileCrossEncoder {
    backend: string | null;
    model: string | null;
    device: string | null;
    has_api_key: boolean;
}

export interface CreateRagProfileRequest {
    name: string;
    description?: string | null;
    is_system_default?: boolean;
    chunking?: RagProfileChunking;
    semantic_cache?: RagProfileSemanticCache;
    cross_encoder?: RagProfileCrossEncoder & { api_key?: string | null };
}

export interface UpdateRagProfileRequest {
    name?: string | null;
    description?: string | null;
    is_system_default?: boolean | null;
    chunking?: RagProfileChunking | null;
    semantic_cache?: RagProfileSemanticCache | null;
    cross_encoder?: (RagProfileCrossEncoder & { api_key?: string | null }) | null;
}

export interface AdminVoiceRuntimeToolPolicyLexiconItem {
    canonical_term: string;
    aliases: string[];
    scope?: string;
    replace_on_final_only?: boolean;
}

export interface AdminVoiceRuntimeToolPolicy {
    kb_lock_mode?: "strict_audit" | "coach_mode";
    max_questions_per_turn?: number;
    web_search_top_k?: number;
    web_search_timeout_seconds?: number;
    retrieval_top_k?: number;
    retrieval_similarity_threshold?: number;
    retrieval_enable_hybrid?: boolean;
    retrieval_keyword_candidate_limit?: number;
    retrieval_enable_rerank?: boolean;
    retrieval_rerank_top_k?: number;
    transcript_normalization_enabled?: boolean;
    transcript_normalization_apply_to_interim?: boolean;
    transcript_normalization_lexicon?: AdminVoiceRuntimeToolPolicyLexiconItem[];
}

export interface AdminVoiceRuntimeProfile extends AssetGovernanceSubject {
    id: string;
    name: string;
    description?: string | null;
    is_default: boolean;
    is_active: boolean;
    voice_mode: "legacy" | "stepfun_realtime";
    model_name: string;
    voice_name: string;
    temperature: number;
    input_audio_format: string;
    output_audio_format: string;
    output_sample_rate: number;
    turn_detection?: string | null;
    tool_policy: AdminVoiceRuntimeToolPolicy;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface AdminPresentationListItem extends AssetGovernanceSubject {
    presentation_id: string;
    title: string;
    status: "processing" | "ready" | "failed";
    version_number: number;
    file_size_bytes: number;
    page_count: number;
    total_pages?: number;
    uploaded_by_admin_id: string;
    created_at: string;
}

export interface AdminPresentationPage {
    page_id: string;
    page_number: number;
    image_url: string;
    extracted_text?: string;
}

export interface AdminPresentationDetailItem extends AdminPresentationListItem {
    pages: AdminPresentationPage[];
}

export interface AdminKnowledgeDocument {
    id: string;
    file_name: string;
    file_type: string;
    file_size: number;
    chunk_count: number;
    status: string;
    created_at: string;
    error_message?: string | null;
}

export interface AdminKnowledgeAnswerConfigVersion {
    id: string;
    version_name: string;
    status: string;
    enabled: boolean;
    updated_at: string;
}

export interface AdminKnowledgeAnswerConfigSummary {
    query_profile_count: number;
    intent_rule_count: number;
    entity_alias_count: number;
    ranking_profile_count: number;
    answerability_profile_count: number;
}

export interface AdminKnowledgeAnswerSelectedProfiles {
    query_profile_keys: string[];
    ranking_profile_keys: string[];
    answerability_profile_keys: string[];
}

export interface AdminKnowledgeAnswerAdminConfig {
    active_version: AdminKnowledgeAnswerConfigVersion | null;
    profile_source: string | null;
    summary: AdminKnowledgeAnswerConfigSummary;
    selected_profiles: AdminKnowledgeAnswerSelectedProfiles;
}

export interface AdminKnowledgeAnswerConfigOptions {
    versions: AdminKnowledgeAnswerConfigVersion[];
}

export interface AdminKnowledgeAnswerRunListItem {
    id: string;
    session_id: string;
    config_version_id?: string | null;
    entrypoint: string;
    query_text: string;
    answerability: string;
    final_status: string;
    blocked_reason?: string | null;
    step_count: number;
    created_at: string;
    updated_at: string;
}

export interface AdminKnowledgeAnswerRunDetail {
    id: string;
    session_id: string;
    config_version_id?: string | null;
    entrypoint: string;
    query_text: string;
    answerability: string;
    final_status: string;
    blocked_reason?: string | null;
    citations: Array<Record<string, unknown>>;
    retrieval_summary: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export interface AdminKnowledgeAnswerRunStep {
    id: string;
    answer_run_id: string;
    step_name: string;
    step_order: number;
    status: string;
    input_payload: Record<string, unknown>;
    output_payload: Record<string, unknown>;
    duration_ms?: number | null;
    created_at: string;
    updated_at: string;
}

export interface AdminKnowledgeAnswerRunListResponse {
    items: AdminKnowledgeAnswerRunListItem[];
    total: number;
    limit: number;
    page: number;
    offset: number;
    session_id?: string | null;
}

export interface AdminKnowledgeAnswerRunStepsResponse {
    run_id: string;
    items: AdminKnowledgeAnswerRunStep[];
    total: number;
}

// ─── Knowledge Config Version CRUD ───

export interface AdminKnowledgeConfigVersionResponse {
    id: string;
    version_name: string;
    status: string;
    notes: string | null;
    enabled: boolean;
    created_by: string | null;
    updated_by: string | null;
    created_at: string;
    updated_at: string;
}

export interface AdminKnowledgeConfigVersionListResponse {
    items: AdminKnowledgeConfigVersionResponse[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface AdminKnowledgeConfigVersionCreateRequest {
    version_name: string;
    notes?: string | null;
    enabled?: boolean;
}

export interface AdminKnowledgeConfigVersionUpdateRequest {
    version_name?: string | null;
    status?: string | null;
    notes?: string | null;
    enabled?: boolean | null;
}

// ─── Knowledge Query Profile ───

export interface AdminKnowledgeQueryProfile {
    id: string;
    config_version_id: string;
    profile_key: string;
    description: string | null;
    rewrite_strategy: string;
    max_rewrite_queries: number;
    stop_after_first_success: boolean;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

// ─── Knowledge Intent Rule ───

export interface AdminKnowledgeIntentRule {
    id: string;
    config_version_id: string;
    intent_key: string;
    priority: number;
    match_type: string;
    pattern: string;
    profile_key: string;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

// ─── Knowledge Entity Alias ───

export interface AdminKnowledgeEntityAlias {
    id: string;
    config_version_id: string;
    canonical_entity: string;
    alias: string;
    entity_type: string;
    confidence: number;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

// ─── Knowledge Ranking Profile ───

export interface AdminKnowledgeRankingProfile {
    id: string;
    config_version_id: string;
    profile_key: string;
    title_exact_boost: number;
    entity_match_boost: number;
    doc_type_weights: Record<string, number>;
    section_weights: Record<string, number>;
    min_pass_score: number;
    min_pass_score_keyword: number;
    // Unified scoring weights
    base_weight: number;
    coverage_weight: number;
    phrase_bonus: number;
    title_bonus_max: number;
    ratio_bonus_max: number;
    cross_encoder_weight: number;
    diversity_penalty: number;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

// ─── Knowledge Chunking Preset ───

export interface AdminKnowledgeChunkingPreset {
    id: string;
    config_version_id: string;
    profile_key: string;
    description: string | null;
    chunking_strategy: string;
    chunk_size: number;
    chunk_overlap: number;
    is_default: boolean;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

export interface CreateKnowledgeChunkingPresetRequest {
    profile_key: string;
    description?: string | null;
    chunking_strategy?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    is_default?: boolean;
    enabled?: boolean;
}

export interface UpdateKnowledgeChunkingPresetRequest {
    profile_key?: string;
    description?: string | null;
    chunking_strategy?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    is_default?: boolean;
    enabled?: boolean;
}

// ─── Knowledge Answerability Profile ───

export interface AdminKnowledgeAnswerabilityProfile {
    id: string;
    config_version_id: string;
    profile_key: string;
    required_slots: string[];
    optional_slots: string[];
    sufficient_threshold: number;
    partial_threshold: number;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

// ─── Knowledge Debug Trigger ───

export interface AdminKnowledgeDebugTriggerRequest {
    query: string;
    knowledge_base_ids: string[];
    runtime_options?: Record<string, unknown>;
    strict_kb_mode?: boolean;
}

export interface AdminKnowledgeDebugTriggerResponse {
    query: string;
    count: number;
    results: Array<Record<string, unknown>>;
    retrieval_mode: string;
    rewritten_queries: string[];
    status: string;
    _answerability?: Record<string, unknown>;
    _diagnostics?: Record<string, unknown>;
}

export interface AdminKnowledgeDocumentPreviewChunk {
    index: number;
    content: string;
    metadata?: Record<string, unknown>;
}

export interface AdminKnowledgeDocumentPreviewResponse {
    chunks: AdminKnowledgeDocumentPreviewChunk[];
    total_chunks: number;
}

export interface AdminSystemLogDiagnosticItem {
    key: string;
    value: string;
}

export interface AdminSystemLog {
    id: string;
    action: string;
    user_identifier: string;
    ip_address?: string | null;
    status: "success" | "failed" | "warning" | string;
    created_at: string;
    details?: unknown;
    diagnostics?: AdminSystemLogDiagnosticItem[];
    trace_id?: string | null;
    error_code?: string | null;
    phase?: string | null;
    session_id?: string | null;
}

export interface AdminSystemLogExposurePolicy {
    version: string;
    visible_fields: string[];
    internal_only_fields: string[];
    redaction_summary: string;
    diagnostic_fields: string[];
}

export interface AdminSystemLogListResponse {
    items: AdminSystemLog[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
    policy?: AdminSystemLogExposurePolicy;
}

export interface AdminKnowledgeSearchResult {
    content: string;
    score: number;
    metadata: {
        document_id: string;
        document_title: string;
        chunk_index: number;
    };
}

export interface AdminKnowledgeSearchResponse {
    results: AdminKnowledgeSearchResult[];
    total: number;
}

export type PresentationAIScopeType = "global" | "scenario" | "presentation";

export interface PresentationAIPolicy {
    enabled: boolean;
    prompt_config: {
        enable_prompt_first: boolean;
        interruption_template_id?: string | null;
    };
    rule_config: {
        similarity_threshold: number;
        point_tracker_cooldown_seconds: number;
        feedback_cooldown_seconds: number;
        allow_critical_forbidden_interrupt: boolean;
        allow_regular_forbidden_interrupt: boolean;
        missing_points_interrupt_ratio_threshold: number;
        missing_points_min_count: number;
        missing_points_preview_count: number;
    };
    fallback_config: {
        enable_interruption_detector_fallback: boolean;
        allow_scenario_prompt_fallback: boolean;
        fallback_when_template_missing: boolean;
        fallback_when_render_error: boolean;
    };
}

export interface PresentationAIPolicyScopeResponse {
    scope_type: PresentationAIScopeType;
    scope_id?: string | null;
    exists: boolean;
    policy: PresentationAIPolicy;
    meta?: {
        id?: string | null;
        updated_at?: string | null;
        updated_by?: string | null;
    };
}

export interface PresentationAIPolicyPreviewResponse {
    effective_policy: PresentationAIPolicy & {
        source?: Record<string, unknown>;
        resolved_at?: string;
    };
    result: {
        should_interrupt: boolean;
        reason?: string;
        message?: string;
        point_coverage: {
            total: number;
            covered: number;
            missing: number;
        };
        forbidden_matches: Array<{
            word: string;
            suggestion?: string;
            severity?: string;
        }>;
    };
}

export interface PresentationAIPolicyEffectiveResponse extends PresentationAIPolicy {
    source?: Record<string, unknown>;
    resolved_at?: string;
    session_id?: string;
}

// User Detail types
export interface UserStatistics {
    total_sessions: number;
    completed_sessions: number;
    completion_rate: number;
    average_score: number;
    best_score: number;
    worst_score: number;
    evaluable_sessions?: number;
    not_evaluable_sessions?: number;
    score_basis?: string;
    total_duration_minutes: number;
    last_practice: string | null;
    unique_agents_used: number;
    unique_personas_used: number;
}

export interface UsageItem {
    agent_id?: string;
    persona_id?: string;
    name: string;
    count: number;
}

export interface UserDetailStats {
    user: AdminUser;
    statistics: UserStatistics;
    agent_usage: UsageItem[];
    persona_usage: UsageItem[];
}

export interface UserSessionItem {
    session_id: string;
    start_time: string | null;
    end_time: string | null;
    status: string;
    duration_minutes: number;
    scenario_name: string | null;
    scenario_type: string | null;
    agent_name: string | null;
    persona_name: string | null;
    scores: {
        logic: number | null;
        accuracy: number | null;
        completeness: number | null;
        overall: number | null;
    };
    overall_result?: SessionOverallResult | null;
    evaluable?: boolean | null;
    not_evaluable_reason?: SessionNotEvaluableReason | null;
    evidence_completeness?: SessionEvidenceCompleteness | null;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
    feedback_summary?: string | null;
    suggestions?: string[];
    interruption_count: number;
}

export type ManagerInterventionResultStatus =
    | "pending"
    | "not_evaluable"
    | "still_blocked"
    | "improved";

export interface ManagerInterventionResultItem {
    intervention_id: string;
    issue_family: string;
    note?: string | null;
    created_at: string;
    session_id?: string | null;
    session_start_time?: string | null;
    status: ManagerInterventionResultStatus;
    reason: string;
    summary: string;
    overall_result?: SessionOverallResult | null;
    evaluable?: boolean | null;
    not_evaluable_reason?: SessionNotEvaluableReason | null;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
}

export interface UserSessionsResponse {
    items: UserSessionItem[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
    manager_intervention_results?: ManagerInterventionResultItem[];
}

export interface UserProgressDataPoint {
    date: string;
    sessions_count: number;
    evaluable_session_count: number;
    not_evaluable_session_count: number;
    average_score: number;
    logic_score: number;
    accuracy_score: number;
    completeness_score: number;
    overall_result?: SessionOverallResult | null;
    evaluable?: boolean | null;
    not_evaluable_reason?: SessionNotEvaluableReason | null;
    evidence_completeness?: SessionEvidenceCompleteness | null;
    main_issue?: SessionMainIssue | null;
    next_goal?: SessionNextGoal | null;
    stage_summary?: SessionStageSummary[] | null;
}

export interface UserRepeatedMainIssueBucket {
    issue_type: string;
    issue_text: string;
    count: number;
}

export interface UserRepeatedNextGoalBucket {
    goal_type: string;
    goal_text: string;
    count: number;
}

export interface UserProgressRecommendation {
    reason: string;
    summary: string;
}

export interface UserProgressResponse {
    granularity: "day" | "week" | string;
    trend_data: UserProgressDataPoint[];
    improvement_rate: number;
    total_data_points: number;
    completed_session_count: number;
    evaluable_session_count: number;
    not_evaluable_session_count: number;
    non_completed_session_count: number;
    repeated_main_issues: UserRepeatedMainIssueBucket[];
    repeated_next_goals: UserRepeatedNextGoalBucket[];
    should_switch_focus: boolean;
    recommendation: UserProgressRecommendation;
}

export type ManagerInterventionDueState = "pending" | "due" | "resolved";

export type ManagerInterventionReminderStatus = "not_sent" | "sent";

export interface ManagerInterventionItem {
    intervention_id: string;
    manager_user_id: string;
    user_id: string;
    issue_family: string;
    note?: string | null;
    due_state: ManagerInterventionDueState;
    reminder_status: ManagerInterventionReminderStatus;
    reminder_sent_at?: string | null;
    resolving_session_id?: string | null;
    created_at: string;
    updated_at: string;
}


export interface LearnerOpenIntervention {
    intervention_id: string;
    issue_family: string;
    note?: string | null;
    due_state: "pending" | "due";
    reminder_status: ManagerInterventionReminderStatus;
    reminder_sent_at?: string | null;
    created_at: string;
    updated_at: string;
}

export interface ManagerInterventionListResponse {
    items: ManagerInterventionItem[];
    total: number;
}

export interface ManagerInterventionCreateRequest {
    user_id: string;
    issue_family: string;
    note?: string;
    due_state?: ManagerInterventionDueState;
    reminder_status?: ManagerInterventionReminderStatus;
    resolving_session_id?: string | null;
}

export interface ManagerInterventionRemindRequest {
    user_id: string;
    intervention_id?: string;
    note?: string;
}

export interface ManagerInterventionRemindResponse extends ManagerLiteRemindResponse {
    intervention_id?: string | null;
}

// Prompt Template types (B10)
export type PromptType =
    | "summary"
    | "system"
    | "system_prompt"
    | "extraction"
    | "scoring"
    | "realtime_scoring"
    | "stage"
    | "fuzzy_detection"
    | "interruption"
    | "tracking"
    | "welcome"
    | "evaluation"
    | "report";

export interface PromptTemplate {
    id: string;
    name: string;
    prompt_type: PromptType;
    category: string;
    template: string;
    variables: string[];
    is_active: boolean;
    is_default: boolean;
    is_system: boolean;
    created_at: string;
    updated_at: string;
    governance_status?: "valid" | "needs_review" | string;
    governance_issues?: string[];
}

export interface PromptTemplateCreate {
    name: string;
    prompt_type: PromptType;
    category?: string;
    template: string;
    variables?: string[];
    is_active?: boolean;
    is_default?: boolean;
}

export interface PromptTemplateUpdate {
    name?: string;
    prompt_type?: PromptType;
    category?: string;
    template?: string;
    variables?: string[];
    is_active?: boolean;
    is_default?: boolean;
}


export interface PromptTemplateGovernanceIssue {
    code: string;
    severity: "blocking" | "warning" | string;
    message: string;
}

export interface PromptTemplateGovernanceInvalidTemplate {
    id: string;
    name: string;
    prompt_type: string;
    category: string;
    variables: unknown;
    is_active: boolean;
    is_default: boolean;
    updated_at?: string | null;
    issues: PromptTemplateGovernanceIssue[];
    runtime_status: string;
    remediation: string;
}

export interface PromptTemplateGovernanceStatus {
    allowed_prompt_types: string[];
    policy: {
        variables_schema: string;
        invalid_history_runtime_behavior: string;
        rollback: string;
        audit_action: string;
    };
    invalid_count: number;
    invalid_templates: PromptTemplateGovernanceInvalidTemplate[];
    limit: number;
    checked_count: number;
    active_invalid_count: number;
    invalid_active_count: number;
    issues: Array<{
        template_id: string;
        name?: string | null;
        issue_codes: string[];
        messages?: string[];
        recommended_action?: string;
    }>;
    rollback_policy: string;
    audit_log_action: string;
}

export interface PromptTemplateGovernanceRemediationResponse {
    remediated_count: number;
    items: Array<{ before: unknown; after: unknown; issues: PromptTemplateGovernanceIssue[] }>;
    audit: {
        action: string;
        actor_id?: string | null;
        reason: string;
        trace_id?: string | null;
    };
}

export interface PromptTemplateGovernanceRollbackResponse {
    template: PromptTemplate | Record<string, unknown>;
    governance_status: "valid" | "needs_review" | string;
    governance_issues: PromptTemplateGovernanceIssue[];
    audit_action: string;
    message?: string;
}

export interface PromptTemplateOptions {
    allowed_prompt_types: Array<{ value: string; label: string }>;
    sales_allowed_prompt_types: string[];
    variables_schema: string;
    invalid_active_count: number;
    rollback_policy: string;
}

export interface PromptTemplateQuarantineResult {
    checked_count: number;
    quarantined_count: number;
    issues: PromptTemplateGovernanceIssue[];
    audit_log_action: string;
}

export interface PromptTemplateGovernanceRollbackResponse {
    template_id: string;
    rolled_back: boolean;
    runtime_status: "valid" | "needs_review" | string;
    before: Record<string, unknown>;
    after: Record<string, unknown>;
    issues: PromptTemplateGovernanceIssue[];
    safety_overrides: string[];
    audit_log_action: string;
}

export interface ScenarioPrompt {
    id: string;
    scenario_type: string;
    scenario_id?: string;
    prompt_type: string;
    template_id: string;
    template?: PromptTemplate;
    is_active: boolean;
    created_at: string;
}

export interface ScenarioPromptCreate {
    scenario_type: string;
    scenario_id?: string;
    prompt_type: string;
    template_id: string;
    is_active?: boolean;
}

export interface PromptRenderRequest {
    template_id: string;
    variables: Record<string, unknown>;
}

export interface PromptRenderResponse {
    template_id: string;
    rendered: string;
    missing_variables: string[];
    extra_variables: string[];
}

// Staged Evaluation types (C6-C7)
export interface StageEvaluationResult {
    stage_number: number;
    start_turn: number;
    end_turn: number;
    timestamp: string;
    scores: Record<string, number>;
    strengths: string[];
    weaknesses: string[];
    suggestions: string[];
    summary: string;
}

export interface DimensionScore {
    name: string;
    score: number;
    weight: number;
    description: string;
}

export interface StageSummary {
    stage_number: number;
    start_turn: number;
    end_turn: number;
    average_score: number;
    key_points: string[];
    summary: string;
}

export interface ComprehensiveReport {
    session_id: string;
    generated_at: string;
    overall_score: number;
    dimension_scores: DimensionScore[];
    stage_summaries: StageSummary[];
    key_strengths: string[];
    key_improvements: string[];
    detailed_feedback: string;
    recommendations: string[];
    comparison_to_baseline?: Record<string, unknown>;
    voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
}

// Real-time evaluation feedback (C6)
export interface RealtimeEvaluationFeedback {
    stage_number: number;
    timestamp: string;
    scores: Record<string, number>;
    feedback: string;
    suggestions: string[];
    trigger_type: "turn_count" | "time_interval" | "keyword" | "stage_transition";
}



// Scenario types
export interface ScenarioSummary {
    scenario_id: string;
    scenario_type: string;
    name: string;
    description?: string;
    is_active: boolean;
    persona_prompt?: string;
    created_at?: string;
}

export interface SalesPersonaOption {
    id: string;
    name: string;
    description: string;
    characteristics: string[];
    difficulty: string;
}

// Session Replay types
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
    | "INSUFFICIENT_TURN_DATA"
    | "INSUFFICIENT_SESSION_METRICS"
    | string;

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
    issue_type: "off_page" | "missing_point" | "overlong_explanation" | "forbidden_word" | "weak_qa_handling" | string;
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
    degraded_reason?: "missing_marker" | "no_matching_highlight" | "anchor_target_not_found" | string | null;
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
    voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
    total_duration_ms: number;
    overall_score: number;
    messages: ReplayMessage[];
    timeline_markers: ReplayTimelineMarker[];
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

export interface AdaptiveDifficultyDryRunItem {
    session_id: string;
    started_at?: string | null;
    scenario_type?: "sales" | "presentation" | string | null;
    current_difficulty: string;
    suggested_difficulty: string;
    suggested_adjustment: "increase" | "decrease" | "keep" | "none" | string;
    status: "disabled" | "dry_run" | "active_candidate" | "blocked_by_evidence" | "blocked_by_missing_score" | string;
    enabled: boolean;
    overall_score?: number | null;
    score_basis?: string | null;
    policy_version?: string | null;
    policy_source?: string | null;
    rollback_strategy?: string | null;
    explanation?: string | null;
}

export interface AdaptiveDifficultyDryRunResponse {
    feature: "adaptive_difficulty";
    mode: "dry_run_dashboard" | string;
    mutation_enabled: boolean;
    explanation?: string;
    summary: {
        total_sessions: number;
        status_counts: Record<string, number>;
        candidate_count?: number;
        blocked_count?: number;
    };
    items: AdaptiveDifficultyDryRunItem[];
}

export interface SessionStats {
    total_sessions: number;
    weekly_sessions: number;
    average_score: number;
    completed_sessions: number;
    total_practice_minutes: number;
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
    voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
    presentation_review?: PresentationReview | null;
    retry_entry?: RetryEntry | null;
    audio_audit?: AudioAuditPayload | null;
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

export interface HistoryTrendPoint extends Pick<SessionEvidenceContract,
    "overall_score"
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
    status: "disabled" | "no_knowledge_base" | "not_triggered" | "kb_not_ready" | "search_failed" | "hit" | "miss";
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

export interface OpenAnalyticsDashboard {
    scenario_type?: string | null;
    days: number;
    total_sessions: number;
    completed_sessions: number;
    completion_rate: number;
    average_scores: {
        logic: number;
        accuracy: number;
        completeness: number;
        overall: number;
    };
    engagement: {
        average_duration_seconds: number;
        average_interruptions_per_session: number;
    };
    quality: {
        sessions_with_high_vagueness: number;
        sessions_with_forbidden_words: number;
    };
    effectiveness?: {
        pass_rate_3min_flow: number;
        pass_rate_5turn_defense: number;
        pass_rate_4step_structure: number;
        next_day_retry_rate: number;
    };
}

export interface ManagerLiteNotPassedItem {
    user_id: string;
    user_name: string;
    department?: string | null;
    overall_result: string;
    session_id: string;
    session_start_time: string;
    issue_family?: string | null;
}

export interface ManagerLiteInactiveStreakItem {
    user_id: string;
    user_name: string;
    department?: string | null;
    last_session_at: string;
    inactive_days: number;
}

export interface ManagerLiteImprovingItem {
    user_id: string;
    user_name: string;
    department?: string | null;
    pass_gain: number;
    baseline_pass_rate: number;
    current_pass_rate: number;
}

export interface ManagerLiteListsResponse {
    not_passed: ManagerLiteNotPassedItem[];
    inactive_streak: ManagerLiteInactiveStreakItem[];
    improving: ManagerLiteImprovingItem[];
}

export interface AdminOperatingPackIssueBucket {
    issue_family: string;
    issue_type: string;
    issue_text?: string | null;
    count: number;
    user_count: number;
    department_count?: number;
}

export interface AdminOperatingPackReasonBucket {
    reason: string;
    count: number;
}

export interface AdminOperatingPackDegradationBreakdown {
    not_evaluable_reasons: AdminOperatingPackReasonBucket[];
    degraded_reasons: AdminOperatingPackReasonBucket[];
}

export interface AdminOperatingPackDepartmentBucket {
    department: string;
    session_count: number;
    evaluable_sessions: number;
    not_evaluable_sessions: number;
    issue_buckets: AdminOperatingPackIssueBucket[];
    degradation_breakdown: AdminOperatingPackDegradationBreakdown;
}

export interface AdminOperatingPackWeeklySummary {
    window_days?: number | null;
    window_start?: string | null;
    window_end?: string | null;
    completed_sessions: number;
    evaluable_sessions: number;
    not_evaluable_sessions: number;
    degraded_sessions: number;
    active_departments: number;
    at_risk_users: number;
    improving_users: number;
    top_issue_family?: AdminOperatingPackIssueBucket | null;
    top_blocker_family?: AdminOperatingPackIssueBucket | null;
    top_not_evaluable_reason?: AdminOperatingPackReasonBucket | null;
    top_degraded_reason?: AdminOperatingPackReasonBucket | null;
}

export interface AdminOperatingPackResponse {
    score_basis: string;
    weekly_summary: AdminOperatingPackWeeklySummary;
    cohort_issue_buckets: AdminOperatingPackIssueBucket[];
    department_issue_buckets: AdminOperatingPackDepartmentBucket[];
    repeated_blocker_families: AdminOperatingPackIssueBucket[];
    degradation_breakdown: AdminOperatingPackDegradationBreakdown;
    manager_lists: ManagerLiteListsResponse;
}

export interface ManagerLiteRemindResponse {
    sent: boolean;
    reminder_id: string;
    user_id: string;
}

export interface OpenScoreDistribution {
    scenario_type?: string | null;
    days: number;
    distribution: {
        excellent: number;
        good: number;
        fair: number;
        poor: number;
    };
    degradation_breakdown: AdminOperatingPackDegradationBreakdown;
    manager_lists: ManagerLiteListsResponse;
}

export interface ManagerLiteRemindResponse {
    sent: boolean;
    reminder_id: string;
    user_id: string;
}

export interface OpenScoreDistribution {
    scenario_type?: string | null;
    days: number;
    distribution: {
        excellent: number;
        good: number;
        fair: number;
        poor: number;
    };
}
