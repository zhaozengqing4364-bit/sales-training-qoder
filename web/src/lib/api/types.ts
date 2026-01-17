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
}

export interface SessionItem {
    id: string;
    title: string;
    scenario_type: "sales" | "presentation";
    overall_score: number;
    score_trend?: string;
    duration_seconds: number;
    start_time: string;
    status: string;
    user_id?: string;
    user_name?: string;
    agent_name?: string;
    persona_name?: string;
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
    system_prompt?: string;
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
    user_name: string;
    department: string | null;
    total_sessions: number;
    average_score: number;
    best_score: number;
    total_duration_minutes: number;
}

export interface AnalyticsLeaderboard {
    leaderboard: LeaderboardEntry[];
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
    created_at: string;
    last_login?: string;
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
    system_prompt?: string;
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
    capabilities_config?: Record<string, any>;
    default_knowledge_base_ids?: string[];
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
    personality_traits?: string[];
    agent_id?: string;
    agent_name?: string;
    knowledge_bases?: AdminKnowledgeBase[];
    created_at: string;
    updated_at: string;
    usage_count?: number;
}

export interface AdminKnowledgeBase {
    id: string;
    name: string;
    description: string;
    category: string;
    status: string;
    document_count: number;
    total_chunks: number;
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

