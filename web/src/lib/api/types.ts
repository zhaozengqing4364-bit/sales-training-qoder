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

export interface Recommendation {
    title: string;
    reason: string;
    action_label: string;
    target_path: string;
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
}

export interface TrendDataPoint {
    date: string;
    sessions_count: number;
    average_score: number;
    active_users: number;
}

export interface ScoreDistribution {
    excellent: number;
    good: number;
    fair: number;
    poor: number;
}

export interface AnalyticsTrends {
    trend_data: TrendDataPoint[];
    score_distribution: ScoreDistribution;
}

export interface AgentStatsItem {
    agent_id: string;
    agent_name: string;
    category: string;
    usage_count: number;
    average_score: number;
    completion_rate: number;
}

export interface PersonaStatsItem {
    persona_id: string;
    persona_name: string;
    difficulty: string;
    usage_count: number;
    average_score: number;
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
}

export interface AnalyticsLeaderboard {
    leaderboard: LeaderboardEntry[];
}

export interface SupportRuntimeOverview {
    generated_at: string;
    window_hours: number;
    session_health: {
        active_sessions: number;
        total_sessions_window: number;
        completed_sessions_window: number;
        completion_rate: number;
    };
    fault_health: {
        failed_or_warning_logs_window: number;
    };
}

export interface SupportRuntimeFaultItem {
    log_id: string;
    action: string;
    status: string;
    user_identifier: string;
    created_at: string | null;
    details: Record<string, unknown> | string | null;
}

export interface SupportRuntimeFaultsResponse {
    generated_at: string;
    items: SupportRuntimeFaultItem[];
    count: number;
    limit: number;
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

export interface AdminPersona {
    id: string;
    name: string;
    description: string;
    category: string;
    difficulty: string;
    status: string;
    icon?: string;
    system_prompt: string;
    traits?: Record<string, string>;
    agent_id?: string;
    agent_name?: string;
    knowledge_bases?: AdminKnowledgeBase[];
    created_at: string;
    updated_at: string;
    usage_count?: number;
    knowledge_base_ids?: string[];
    persona_policy?: {
        version?: number;
        system_prompt?: string;
        knowledge_base_ids?: string[];
        tool_policy?: Record<string, unknown>;
        [key: string]: unknown;
    };
    tts_config?: {
        voice?: string;
        rate?: string;
        volume?: string;
        pitch?: string;
    };
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
    created_at: string;
    updated_at: string;
}

export interface AdminKnowledgeDocument {
    id: string;
    file_name: string;
    file_type: string;
    file_size: number;
    chunk_count: number;
    status: string;
    created_at: string;
    error_message?: string;
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

export interface AdminSystemLog {
    id: string;
    action: string;
    user_identifier: string;
    ip_address?: string | null;
    status: "success" | "failed" | "warning" | string;
    created_at: string;
    details?: string | null;
}

export interface AdminSystemLogListResponse {
    items: AdminSystemLog[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
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
    interruption_count: number;
}

export interface UserSessionsResponse {
    items: UserSessionItem[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface UserProgressDataPoint {
    date: string;
    sessions_count: number;
    average_score: number;
    logic_score: number;
    accuracy_score: number;
    completeness_score: number;
}

export interface UserProgressResponse {
    trend_data: UserProgressDataPoint[];
    improvement_rate: number;
    total_data_points: number;
}

// Prompt Template types (B10)
export type PromptType =
    | "summary"
    | "system"
    | "system_prompt"
    | "extraction"
    | "scoring"
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
export interface ReplayMessage {
    id: string;
    session_id: string;
    turn_number: number;
    role: string;
    content: string;
    timestamp: string;
    audio_url?: string | null;
    duration_ms?: number | null;
    score_snapshot?: {
        overall?: number | null;
        overall_score?: number | null;
        dimensions?: Array<{
            name: string;
            score: number;
            trend?: string;
            delta?: number;
        }>;
    } | null;
    ai_feedback?: string | null;
    is_highlight?: boolean;
    highlight_type?: string | null;
    highlight_reason?: string | null;
}

export interface ReplayTimelineMarker {
    timestamp_ms: number;
    type: string;
    label: string;
    message_id: string;
    highlight_type?: string | null;
}

export interface ReplayStageSummary {
    stage: string;
    duration_ms: number;
    score: number;
}

export interface ReplayData {
    session_id: string;
    agent_name?: string | null;
    persona_name?: string | null;
    voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
    total_duration_ms: number;
    messages: ReplayMessage[];
    timeline_markers: ReplayTimelineMarker[];
    stage_summary: ReplayStageSummary[];
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
    audio_url?: string | null;
    score?: number | null;
}

export interface ReplayHighlightContext {
    prev_message?: {
        id: string;
        role: string;
        content: string;
        timestamp: string;
    } | null;
    next_message?: {
        id: string;
        role: string;
        content: string;
        timestamp: string;
    } | null;
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
    audio_url?: string | null;
    score?: number | null;
}

export interface HighlightsResponse {
    highlights: HighlightItem[];
    total_good: number;
    total_bad: number;
}

export interface SessionStats {
    total_sessions: number;
    weekly_sessions: number;
    average_score: number;
    completed_sessions: number;
    total_practice_minutes: number;
}

export interface PracticeSessionReport {
    session_id: string;
    logic_score: number;
    accuracy_score: number;
    completeness_score: number;
    overall_score: number;
    suggestions: string[];
    audio_url?: string | null;
    transcript_url?: string | null;
    voice_policy_snapshot_ref?: VoicePolicySnapshotReference | null;
    effectiveness_snapshot?: Record<string, unknown> | null;
    pass_flags?: {
        pass_3min_flow: boolean;
        pass_5turn_defense: boolean;
        pass_4step_structure: boolean;
    } | null;
    main_capability_passed?: boolean | null;
    overall_result?: "pass" | "strong_pass" | "fail" | null;
    main_issue?: {
        issue_type: string;
        issue_text: string;
        recovery_rule: string;
    } | null;
    next_goal?: {
        goal_type: string;
        goal_text: string;
        rule: string;
    } | null;
    retry_entry?: {
        scenario_type: "sales" | "presentation" | string;
        agent_id?: string | null;
        persona_id?: string | null;
        presentation_id?: string | null;
    } | null;
}

export interface KnowledgeCheckDiagnostics {
    session_id: string;
    voice_mode?: "legacy" | "stepfun_realtime" | string;
    status: "disabled" | "no_knowledge_base" | "not_triggered" | "kb_not_ready" | "hit" | "miss";
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

export interface ManagerLiteListsResponse {
    not_passed: Array<{
        user_id: string;
        user_name: string;
        department?: string | null;
        overall_result: string;
        session_id: string;
        session_start_time: string;
    }>;
    inactive_streak: Array<{
        user_id: string;
        user_name: string;
        department?: string | null;
        last_session_at: string;
        inactive_days: number;
    }>;
    improving: Array<{
        user_id: string;
        user_name: string;
        department?: string | null;
        pass_gain: number;
        baseline_pass_rate: number;
        current_pass_rate: number;
    }>;
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
