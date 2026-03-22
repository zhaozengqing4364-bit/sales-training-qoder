/**
 * API Client - Unified API access layer
 * 
 * Handles authentication, error handling, and API calls.
 * Follows Constitution Principle I: No user-visible errors.
 */

import {
    DashboardStats,
    SessionItem,
    PracticeSessionRuntime,
    Recommendation,
    TrainingCategory,
    Agent,
    Persona,
    AnalyticsOverview,
    AnalyticsTrends,
    AnalyticsAgents,
    AnalyticsLeaderboard,
    User,
    AdminUser,
    AdminAgent,
    AdminPersona,
    AdminKnowledgeBase,
    AdminKnowledgeDocument,
    AdminKnowledgeDocumentPreviewResponse,
    AdminKnowledgeSearchResponse,
    AdminSystemLog,
    AdminSystemLogListResponse,
    UserDetailStats,
    UserSessionsResponse,
    UserProgressResponse,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    ScenarioPrompt,
    ScenarioPromptCreate,
    PromptRenderRequest,
    PromptRenderResponse,
    ComprehensiveReport,
    RealtimeEvaluationFeedback,
    ScenarioSummary,
    SalesPersonaOption,
    ReplayData,
    ReplayMessagesResponse,
    HighlightsResponse,
    SessionStats,
    PracticeSessionReport,
    KnowledgeCheckDiagnostics,
    OpenAnalyticsDashboard,
    OpenScoreDistribution,
    SupportRuntimeFaultsResponse,
    SupportRuntimeOverview,
    SessionStatus,
    SessionLifecycleAction,
    SessionLifecycleRequest,
    SessionLifecycleResponse,
    PresentationAIPolicyScopeResponse,
    PresentationAIPolicyPreviewResponse,
    PresentationAIPolicyEffectiveResponse,
    PresentationAIScopeType,
    ManagerLiteListsResponse,
    ManagerLiteRemindResponse,
} from "./types";
import { authHandler } from "@/lib/auth-handler";
import { normalizeCurrentUser } from "@/lib/auth/current-user";
import { buildTraceHeaders } from "@/lib/observability/trace-context";

const LOOPBACK_HOST_FALLBACK_MAP: Record<string, string> = {
    "localhost": "127.0.0.1",
    "127.0.0.1": "localhost",
    "::1": "127.0.0.1",
};

const DEFAULT_API_BASE_URL = "http://localhost:3444/api/v1";
const CONFIGURED_API_BASE_URL = (
    process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

function isLoopbackHost(hostname: string): boolean {
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function resolveApiBaseUrl(): string {
    if (typeof window === "undefined") {
        return CONFIGURED_API_BASE_URL;
    }

    try {
        const parsed = new URL(CONFIGURED_API_BASE_URL);
        if (!isLoopbackHost(parsed.hostname)) {
            return parsed.toString().replace(/\/+$/, "");
        }

        const pageHost = window.location.hostname;
        if (!pageHost || isLoopbackHost(pageHost)) {
            return parsed.toString().replace(/\/+$/, "");
        }

        // When frontend is opened via LAN hostname/IP, keep API host aligned to avoid localhost misrouting.
        parsed.hostname = pageHost;
        return parsed.toString().replace(/\/+$/, "");
    } catch {
        return CONFIGURED_API_BASE_URL;
    }
}

function getLoopbackFallbackUrl(url: string): string | null {
    try {
        const parsed = new URL(url);
        const fallbackHost = LOOPBACK_HOST_FALLBACK_MAP[parsed.hostname];
        if (!fallbackHost) {
            return null;
        }

        parsed.hostname = fallbackHost;
        return parsed.toString();
    } catch {
        return null;
    }
}

async function fetchWithLoopbackRetry(url: string, options: RequestInit): Promise<Response> {
    try {
        return await fetch(url, options);
    } catch (error) {
        if (!(error instanceof TypeError)) {
            throw error;
        }

        const fallbackUrl = getLoopbackFallbackUrl(url);
        if (!fallbackUrl) {
            throw error;
        }

        return fetch(fallbackUrl, options);
    }
}

// Active request tracking for cancellation on page transitions
const activeRequests = new Map<string, AbortController>();
let requestCounter = 0;
let lastSessionExpiredAt = 0;
const SESSION_EXPIRED_NOTIFY_COOLDOWN_MS = 1500;

function triggerSessionExpiredOnce(): void {
    const now = Date.now();
    if (now - lastSessionExpiredAt < SESSION_EXPIRED_NOTIFY_COOLDOWN_MS) {
        return;
    }
    lastSessionExpiredAt = now;
    authHandler.sessionExpired();
}

const API_ERROR_MESSAGE_MAP: Record<string, string> = {
    "[NETWORK_ERROR]": "网络连接失败，请检查后端服务或网络设置后重试。",
    "[INVALID_CLIENT_PAYLOAD]": "请求参数无效，请刷新页面后重试。",
    "[AGENT_PERSONA_PAIR_REQUIRED]": "请选择智能体与角色后再开始训练。",
    "[AGENT_ARCHIVED]": "该智能体已归档，暂时无法创建训练会话。",
    "[AGENT_NOT_PUBLISHED]": "该智能体尚未发布，请选择可用智能体。",
    "[PERSONA_INACTIVE]": "该角色已停用，请更换角色。",
    "[PERSONA_NOT_LINKED_TO_AGENT]": "所选角色未关联当前智能体，请重新选择。",
    "[AGENT_CATEGORY_RESTRICTED]": "当前仅支持创建「销售」与「演讲」两类智能体。",
    "[FIELD_DEPRECATED_PERSONA_CENTERED]": "该配置入口已下线，请改为在角色中心（Persona）配置。",
    "[PROMPT_SCOPE_VIOLATION]": "销售场景仅允许评估/报告相关模板。",
    "[SALES_PERSONA_REQUIRED]": "请先选择销售角色。",
    "[SESSION_NOT_FOUND]": "未找到目标会话，请刷新后重试。",
    "[ACCESS_DENIED]": "你没有权限访问该会话。",
    "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]": "仅管理员可访问提示词治理接口。",
    "[ROLE_REQUIRED]": "当前账号权限不足，无法执行该操作。",
};

type NormalizedApiErrorPayload = {
    status: number;
    errorCode: string;
    message: string;
    traceId?: string;
};

function normalizeApiErrorPayload(status: number, payload: unknown): NormalizedApiErrorPayload {
    const raw = (payload && typeof payload === "object")
        ? payload as Record<string, unknown>
        : {};
    const detail = (raw.detail && typeof raw.detail === "object")
        ? raw.detail as Record<string, unknown>
        : raw;

    const rawCode = detail.error ?? detail.error_code;
    const errorCode = typeof rawCode === "string" && rawCode.trim()
        ? rawCode
        : `[HTTP_${status}]`;
    const rawMessage = detail.message;
    const message = typeof rawMessage === "string" && rawMessage.trim()
        ? rawMessage
        : errorCode;
    const rawTraceId = detail.trace_id;
    const traceId = typeof rawTraceId === "string" && rawTraceId.trim()
        ? rawTraceId
        : undefined;

    return { status, errorCode, message, traceId };
}

function buildApiErrorDisplayMessage(payload: NormalizedApiErrorPayload): string {
    const friendly = API_ERROR_MESSAGE_MAP[payload.errorCode] || payload.message || "请求失败，请稍后重试。";
    const traceSuffix = payload.traceId ? ` (trace_id: ${payload.traceId})` : "";
    return `${friendly}${traceSuffix}`;
}

export class ApiRequestError extends Error {
    readonly status: number;
    readonly errorCode: string;
    readonly traceId?: string;
    readonly rawMessage: string;

    constructor(payload: NormalizedApiErrorPayload) {
        super(buildApiErrorDisplayMessage(payload));
        this.name = "ApiRequestError";
        this.status = payload.status;
        this.errorCode = payload.errorCode;
        this.traceId = payload.traceId;
        this.rawMessage = payload.message;
    }
}

export function getApiErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
        return error.message;
    }
    if (error instanceof Error && error.message.trim()) {
        return error.message;
    }
    return "请求失败，请稍后重试。";
}

export function isAuthenticationError(error: unknown): boolean {
    if (error instanceof ApiRequestError) {
        return error.status === 401 || error.status === 403;
    }

    if (typeof error === "object" && error !== null && "status" in error) {
        const status = Number((error as { status?: number }).status);
        return status === 401 || status === 403;
    }

    return false;
}

function normalizeRequiredId(
    id: string,
    options: { fieldName: string },
): string {
    const { fieldName } = options;
    const normalized = typeof id === "string" ? id.trim() : "";
    if (!normalized || normalized === "undefined" || normalized === "null") {
        throw new ApiRequestError({
            status: 400,
            errorCode: "[INVALID_CLIENT_PAYLOAD]",
            message: `${fieldName} is invalid`,
        });
    }
    return normalized;
}


type HistoryApiItem = {
    session_id?: string;
    id?: string;
    title?: string;
    agent_name?: string;
    scenario_name?: string;
    scenario_type?: string;
    overall_score?: number;
    duration_seconds?: number;
    total_duration_seconds?: number;
    start_time?: string;
    status?: string;
    effectiveness_snapshot?: Record<string, unknown> | null;
    feedback_summary?: string;
    [key: string]: unknown;
};

const SESSION_STATUS_VALUES = new Set<SessionStatus>([
    "preparing",
    "in_progress",
    "paused",
    "completed",
    "scoring",
]);

function normalizeSessionStatus(value: unknown): SessionStatus {
    if (typeof value === "string" && SESSION_STATUS_VALUES.has(value as SessionStatus)) {
        return value as SessionStatus;
    }
    return "completed";
}

type AdminModelConfigListItem = {
    id: string;
    name: string;
    model_type: string;
    provider: string;
    model_name: string;
    is_default: boolean;
    is_active: boolean;
    last_test_status: string | null;
};

type AdminModelConfigGrouped = {
    llm: AdminModelConfigListItem[];
    embedding: AdminModelConfigListItem[];
    asr: AdminModelConfigListItem[];
    tts: AdminModelConfigListItem[];
    total: number;
};

type AdminModelConfigDetail = {
    id: string;
    name: string;
    model_type: string;
    provider: string;
    base_url: string;
    api_key_masked: string;
    model_name: string;
    extra_config: Record<string, unknown>;
    is_default: boolean;
    is_active: boolean;
    last_tested_at: string | null;
    last_test_status: string | null;
    created_at: string;
    updated_at: string;
};

type AdminModelConfigUpsertPayload = {
    name?: string;
    model_type?: string;
    provider?: string;
    base_url?: string;
    api_key?: string;
    model_name?: string;
    extra_config?: Record<string, unknown>;
    is_default?: boolean;
    is_active?: boolean;
};

type VoiceRuntimeProfile = {
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
    tool_policy: Record<string, unknown>;
    created_at?: string | null;
    updated_at?: string | null;
};

type VoiceRuntimeProfilePayload = {
    name: string;
    description?: string | null;
    is_default?: boolean;
    is_active?: boolean;
    voice_mode?: "legacy" | "stepfun_realtime";
    model_name?: string;
    voice_name?: string;
    temperature?: number;
    input_audio_format?: string;
    output_audio_format?: string;
    output_sample_rate?: number;
    turn_detection?: string | null;
    tool_policy?: Record<string, unknown>;
};

type AgentVoicePolicy = {
    id?: string | null;
    agent_id: string;
    enabled: boolean;
    runtime_profile_id?: string | null;
    voice_mode_override?: string | null;
    model_override?: string | null;
    voice_override?: string | null;
    temperature_override?: number | null;
    tool_policy_override?: Record<string, unknown>;
    created_at?: string | null;
    updated_at?: string | null;
};

type AgentVoicePolicyUpsertPayload = {
    enabled?: boolean;
    runtime_profile_id?: string | null;
    voice_mode_override?: string | null;
    model_override?: string | null;
    voice_override?: string | null;
    temperature_override?: number | null;
    tool_policy_override?: Record<string, unknown>;
};

type AgentWritePayload = {
    name?: string;
    description?: string;
    icon?: string;
    category?: string;
    welcome_message?: string;
    capabilities_config?: Record<string, unknown>;
};

type PresentationAIPolicyUpsertPayload = {
    scope_type: PresentationAIScopeType;
    scope_id?: string | null;
    enabled?: boolean;
    prompt_config?: Record<string, unknown>;
    rule_config?: Record<string, unknown>;
    fallback_config?: Record<string, unknown>;
};

type PresentationAIPolicyPreviewPayload = {
    scope_type: PresentationAIScopeType;
    scope_id?: string | null;
    transcript: string;
    required_points?: string[];
    forbidden_words?: Array<string | Record<string, unknown>>;
};

type PresentationStatus = "processing" | "ready" | "error";

type PresentationPage = {
    page_id: string;
    page_number: number;
    image_url: string;
    extracted_text?: string;
};

type PresentationListItem = {
    presentation_id: string;
    title: string;
    status: PresentationStatus;
    file_size_bytes: number;
    page_count: number;
    uploaded_by_admin_id: string;
    created_at: string;
};

type PresentationDetailItem = PresentationListItem & {
    pages: PresentationPage[];
};

type PresentationTalkingPoint = {
    point_id: string;
    description: string;
    is_ai_generated: boolean;
    confirmed_by_admin: boolean;
};

type PresentationForbiddenWord = {
    word_id: string;
    phrase: string;
    suggested_alternative?: string;
    page_id?: string;
};

function toRecord(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function toStringValue(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function toNumberValue(value: unknown, fallback = 0): number {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    return fallback;
}

function normalizePresentationStatus(value: unknown): PresentationStatus {
    if (value === "ready") return "ready";
    if (value === "processing") return "processing";
    if (value === "failed" || value === "error") return "error";
    return "processing";
}

function normalizePresentationPage(input: unknown): PresentationPage {
    const raw = toRecord(input);
    return {
        page_id: toStringValue(raw.page_id),
        page_number: toNumberValue(raw.page_number, 0),
        image_url: toStringValue(raw.image_url),
        extracted_text: toStringValue(raw.extracted_text, toStringValue(raw.ocr_extracted_text)) || undefined,
    };
}

function normalizePresentationListItem(input: unknown): PresentationListItem {
    const raw = toRecord(input);
    const pages = Array.isArray(raw.pages) ? raw.pages : [];
    return {
        presentation_id: toStringValue(raw.presentation_id),
        title: toStringValue(raw.title, "未命名PPT"),
        status: normalizePresentationStatus(raw.status),
        file_size_bytes: toNumberValue(raw.file_size_bytes, 0),
        page_count: toNumberValue(raw.page_count, toNumberValue(raw.total_pages, pages.length)),
        uploaded_by_admin_id: toStringValue(raw.uploaded_by_admin_id),
        created_at: toStringValue(raw.created_at, toStringValue(raw.upload_date)),
    };
}

function normalizePresentationDetailItem(input: unknown): PresentationDetailItem {
    const raw = toRecord(input);
    const pages = Array.isArray(raw.pages) ? raw.pages.map(normalizePresentationPage) : [];
    return {
        ...normalizePresentationListItem(raw),
        page_count: toNumberValue(raw.page_count, toNumberValue(raw.total_pages, pages.length)),
        pages,
    };
}

function normalizePresentationTalkingPoint(input: unknown): PresentationTalkingPoint {
    const raw = toRecord(input);
    return {
        point_id: toStringValue(raw.point_id),
        description: toStringValue(raw.description),
        is_ai_generated: Boolean(raw.is_ai_generated),
        confirmed_by_admin: Boolean(raw.confirmed_by_admin),
    };
}

function normalizePresentationForbiddenWord(input: unknown): PresentationForbiddenWord {
    const raw = toRecord(input);
    const pageId = toStringValue(raw.page_id);
    const alternative = toStringValue(raw.suggested_alternative);
    return {
        word_id: toStringValue(raw.word_id),
        phrase: toStringValue(raw.phrase),
        suggested_alternative: alternative || undefined,
        page_id: pageId || undefined,
    };
}

/**
 * Cancel all in-flight API requests.
 * Call this on route change or component unmount to prevent leaked requests.
 */
export function cancelAllRequests(): void {
    activeRequests.forEach((controller) => controller.abort());
    activeRequests.clear();
}

type ApiFetchOptions = RequestInit & {
    signal?: AbortSignal;
    skipSessionExpiredHandling?: boolean;
};

function createHeaders(
    existingHeaders: HeadersInit | undefined,
    includeContentType = true,
): Headers {
    const headers = new Headers(existingHeaders);

    if (includeContentType && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }

    const traceHeaders = buildTraceHeaders({
        traceId: headers.get("X-Trace-ID") ?? headers.get("x-trace-id"),
        traceparent: headers.get("traceparent"),
        tracestate: headers.get("tracestate"),
    });

    if (!headers.has("X-Trace-ID")) {
        headers.set("X-Trace-ID", traceHeaders["X-Trace-ID"]);
    }
    if (!headers.has("traceparent")) {
        headers.set("traceparent", traceHeaders.traceparent);
    }
    if (!headers.has("tracestate") && traceHeaders.tracestate) {
        headers.set("tracestate", traceHeaders.tracestate);
    }

    return headers;
}

// Generic fetch wrapper with AbortController support
async function apiFetch<T>(
    endpoint: string,
    options: ApiFetchOptions = {},
): Promise<T> {
    const url = `${resolveApiBaseUrl()}${endpoint}`;
    const requestId = `req_${++requestCounter}`;
    const { skipSessionExpiredHandling = false, ...requestOptions } = options;

    // Create AbortController if caller didn't provide a signal
    const controller = new AbortController();
    const externalSignal = requestOptions.signal;
    const signal = externalSignal || controller.signal;

    // If caller provided their own signal, link it to our controller
    if (externalSignal) {
        externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }

    activeRequests.set(requestId, controller);

    try {
        const response = await fetchWithLoopbackRetry(url, {
            ...requestOptions,
            signal,
            credentials: requestOptions.credentials || "include",
            headers: createHeaders(requestOptions.headers),
        });

        const responseJson = await response.json().catch(() => ({}));

        if (!response.ok) {
            const normalized = normalizeApiErrorPayload(response.status, responseJson);

            if (response.status === 401 && !skipSessionExpiredHandling) {
                triggerSessionExpiredOnce();
            }

            throw new ApiRequestError(normalized);
        }

        if (responseJson.success === false) {
            const normalized = normalizeApiErrorPayload(response.status, responseJson);
            throw new ApiRequestError(normalized);
        }

        return responseJson.data !== undefined ? responseJson.data : responseJson;
    } catch (error) {
        if (error instanceof ApiRequestError) {
            throw error;
        }

        if (error instanceof Error && error.name === "AbortError") {
            throw error;
        }

        const message = error instanceof Error && error.message.trim()
            ? error.message
            : "请求失败，请稍后重试。";

        throw new ApiRequestError({
            status: 0,
            errorCode: "[NETWORK_ERROR]",
            message,
        });
    } finally {
        activeRequests.delete(requestId);
    }
}

// File upload fetch wrapper with AbortController support
async function apiUpload<T>(
    endpoint: string,
    formData: FormData,
    signal?: AbortSignal,
    options: { skipSessionExpiredHandling?: boolean } = {},
): Promise<T> {
    const url = `${resolveApiBaseUrl()}${endpoint}`;
    const requestId = `upload_${++requestCounter}`;
    const controller = new AbortController();
    const { skipSessionExpiredHandling = false } = options;

    if (signal) {
        signal.addEventListener("abort", () => controller.abort(), { once: true });
    }

    activeRequests.set(requestId, controller);

    try {
        const response = await fetchWithLoopbackRetry(url, {
            method: "POST",
            body: formData,
            signal: signal || controller.signal,
            credentials: "include",
            headers: createHeaders(undefined, false),
        });

        const responseJson = await response.json().catch(() => ({}));

        if (!response.ok) {
            if (response.status === 401 && !skipSessionExpiredHandling) {
                triggerSessionExpiredOnce();
            }
            throw new ApiRequestError(normalizeApiErrorPayload(response.status, responseJson));
        }

        if (responseJson.success === false) {
            throw new ApiRequestError(normalizeApiErrorPayload(response.status, responseJson));
        }

        return responseJson.data !== undefined ? responseJson.data : responseJson;
    } catch (error) {
        if (error instanceof ApiRequestError) {
            throw error;
        }

        if (error instanceof Error && error.name === "AbortError") {
            throw error;
        }

        const message = error instanceof Error && error.message.trim()
            ? error.message
            : "请求失败，请稍后重试。";

        throw new ApiRequestError({
            status: 0,
            errorCode: "[NETWORK_ERROR]",
            message,
        });
    } finally {
        activeRequests.delete(requestId);
    }
}

// API methods organized by domain
export const api = {
    // Authentication
    auth: {
        login: async (credentials: { email: string; password: string }) => {
            return apiFetch<{ token?: string; access_token?: string; user: User & { id?: string } }>("/auth/login", {
                method: "POST",
                body: JSON.stringify(credentials),
                skipSessionExpiredHandling: true,
            });
        },

        devLogin: async () => {
            return apiFetch<{ access_token: string; token_type: string; user: User }>("/auth/dev-login", {
                method: "POST",
                skipSessionExpiredHandling: true,
            });
        },

        logout: async () => {
            return apiFetch<void>("/auth/logout", {
                method: "POST",
                skipSessionExpiredHandling: true,
            });
        },
    },

    // User
    user: {
        getMe: async () => {
            const profile = await apiFetch<{
                id: string;
                display_name: string;
                avatar_url?: string | null;
                role: string;
                department?: string | null;
                email?: string | null;
            }>("/users/me");
            return normalizeCurrentUser(profile);
        },

        updateProfile: async (data: Partial<User> & { display_name?: string }) => {
            const payload: Record<string, unknown> = {};

            if (typeof data.name === "string") {
                payload.name = data.name;
            } else if (typeof data.display_name === "string") {
                payload.name = data.display_name;
            }

            if (typeof data.department === "string") {
                payload.department = data.department;
            }

            if (typeof data.email === "string") {
                const normalizedEmail = data.email.trim();
                if (normalizedEmail) {
                    payload.email = normalizedEmail;
                }
            }

            const profile = await apiFetch<{
                id: string;
                display_name: string;
                avatar_url?: string | null;
                role: string;
                department?: string | null;
                email?: string | null;
            }>("/users/me", {
                method: "PATCH",
                body: JSON.stringify(payload),
            });
            return normalizeCurrentUser(profile);
        },

        // Story 3.2: Get user history with report summary
        getMyHistory: async (params?: {
            page?: number;
            page_size?: number;
            scenario_type?: "sales" | "presentation";
        }) => {
            const queryParams = new URLSearchParams();
            if (params?.page) queryParams.set("page", String(params.page));
            if (params?.page_size) queryParams.set("page_size", String(params.page_size));
            if (params?.scenario_type) queryParams.set("scenario_type", params.scenario_type);

            return apiFetch<{
                sessions: Array<{
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
                }>;
                total: number;
                page: number;
                page_size: number;
                total_pages: number;
            }>(`/users/me/history?${queryParams}`);
        },
    },

    // Dashboard
    dashboard: {
        getStats: async () => {
            return apiFetch<DashboardStats>("/dashboard/stats");
        },

        getRecommendation: async () => {
            return apiFetch<Recommendation>("/recommendations/latest");
        },

        getHistory: async (limit = 5, scenarioType?: "sales" | "presentation") => {
            const queryParams = new URLSearchParams({ page_size: String(limit) });
            if (scenarioType) queryParams.set("scenario_type", scenarioType);

            const result = await apiFetch<{ items: HistoryApiItem[]; total: number }>(`/practice/history?${queryParams}`);

            return (result.items || []).map<SessionItem>((item, index) => ({
                id: item.session_id || item.id || `session-${index}`,
                title: item.title || item.agent_name || item.scenario_name || "练习记录",
                scenario_type: item.scenario_type === "presentation" ? "presentation" : "sales",
                overall_score: Number(item.overall_score || 0),
                duration_seconds: Number(item.duration_seconds || item.total_duration_seconds || 0),
                start_time: typeof item.start_time === "string" ? item.start_time : new Date(0).toISOString(),
                status: normalizeSessionStatus(item.status),
                user_id: typeof item.user_id === "string" ? item.user_id : undefined,
                username: typeof item.username === "string"
                    ? item.username
                    : typeof item.user_name === "string"
                        ? item.user_name
                        : undefined,
                agent_name: typeof item.agent_name === "string" ? item.agent_name : undefined,
                persona_name: typeof item.persona_name === "string" ? item.persona_name : undefined,
                effectiveness_snapshot:
                    item.effectiveness_snapshot && typeof item.effectiveness_snapshot === "object"
                        ? item.effectiveness_snapshot
                        : null,
                feedback_summary:
                    typeof item.feedback_summary === "string" ? item.feedback_summary : undefined,
                runtime_profile_id:
                    typeof item.runtime_profile_id === "string"
                        ? item.runtime_profile_id
                        : typeof item.voice_runtime_profile_id === "string"
                            ? item.voice_runtime_profile_id
                            : undefined,
            }));
        },

        getHistoryStatistics: async () => {
            return apiFetch<{
                total_sessions: number;
                average_score: number;
                best_score: number;
                total_practice_time_seconds: number;
                total_practice_time_minutes: number;
            }>("/practice/history/statistics");
        },

        getHistoryTrends: async (days = 30) => {
            const result = await apiFetch<{ trends?: Array<Record<string, unknown>> }>(`/practice/history/trends?days=${days}`);
            return Array.isArray(result?.trends) ? result.trends : [];
        },

        getPublicLeaderboard: async (params?: { scenario_type?: string; time_period?: string; include_me?: boolean; limit?: number }) => {
            const queryParams = new URLSearchParams();
            if (params?.scenario_type) queryParams.set("scenario_type", params.scenario_type);
            if (params?.time_period) queryParams.set("time_period", params.time_period);
            if (params?.include_me) queryParams.set("include_me", "true");
            if (params?.limit) queryParams.set("limit", String(params.limit));
            return apiFetch<{
                scenario_type?: string | null;
                time_period: string;
                total_users: number;
                entries: Array<{
                    rank: number;
                    user_id: string;
                    username: string;
                    total_sessions: number;
                    average_score: number;
                    best_score: number;
                }>;
                my_rank?: {
                    user_id: string;
                    rank: number | null;
                    total_sessions: number;
                    average_score: number;
                    total_users?: number;
                    percentile?: number;
                    time_period?: string;
                    scenario_type?: string | null;
                    message?: string;
                };
            }>(`/analytics/leaderboard?${queryParams}`);
        },

        getMyRank: async (
            params?: string | { scenario_type?: string; time_period?: string }
        ) => {
            const scenarioType =
                typeof params === "string" ? params : params?.scenario_type;
            const timePeriod =
                typeof params === "string" ? undefined : params?.time_period;

            const queryParams = new URLSearchParams();
            if (scenarioType) {
                queryParams.set("scenario_type", scenarioType);
            }
            if (timePeriod) {
                queryParams.set("time_period", timePeriod);
            }

            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<{
                user_id: string;
                rank: number | null;
                total_sessions: number;
                average_score: number;
                total_users?: number;
                percentile?: number;
                time_period?: string;
                scenario_type?: string | null;
                message?: string;
            }>(`/analytics/leaderboard/my-rank${query}`);
        },
    },

    // Open analytics capabilities
    analyticsOpen: {
        getDashboard: async (params?: { scenario_type?: string; days?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);
            if (params?.days) searchParams.set("days", String(params.days));
            return apiFetch<OpenAnalyticsDashboard>(`/analytics/dashboard?${searchParams}`);
        },

        getScoreDistribution: async (params?: { scenario_type?: string; days?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);
            if (params?.days) searchParams.set("days", String(params.days));
            return apiFetch<OpenScoreDistribution>(`/analytics/score-distribution?${searchParams}`);
        },

        getTrends: async (params?: { scenario_type?: string; days?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);
            if (params?.days) searchParams.set("days", String(params.days));
            return apiFetch<Array<Record<string, unknown>>>(`/analytics/trends?${searchParams}`);
        },

        getPracticeHistory: async (params?: { scenario_type?: string; limit?: number; offset?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);
            if (params?.limit) searchParams.set("limit", String(params.limit));
            if (params?.offset) searchParams.set("offset", String(params.offset));
            return apiFetch<{ items: HistoryApiItem[]; total: number }>(`/analytics/practice/history?${searchParams}`);
        },

        getStorageStats: async () => {
            return apiFetch<Record<string, unknown>>("/analytics/storage");
        },
    },

    supportRuntime: {
        getOverview: async (params?: { window_hours?: number }) => {
            const searchParams = new URLSearchParams();
            if (typeof params?.window_hours === "number") {
                searchParams.set("window_hours", String(params.window_hours));
            }
            return apiFetch<SupportRuntimeOverview>(`/support/runtime/overview?${searchParams}`);
        },

        getFaults: async (params?: { limit?: number; status?: "failed" | "warning" }) => {
            const searchParams = new URLSearchParams();
            if (typeof params?.limit === "number") {
                searchParams.set("limit", String(params.limit));
            }
            if (params?.status) {
                searchParams.set("status", params.status);
            }
            return apiFetch<SupportRuntimeFaultsResponse>(`/support/runtime/faults?${searchParams}`);
        },
    },

    // Training / Practice
    training: {
        getCategories: async () => {
            return apiFetch<TrainingCategory[]>("/training-categories");
        },

        getSalesAgents: async () => {
            const result = await apiFetch<{ agents: Agent[]; total: number }>("/agents?category=sales&status=published");
            return result.agents || [];
        },

        createSession: async (data: {
            scenario_type: "sales" | "presentation";
            presentation_id?: string;
            agent_id?: string;
            persona_id?: string;
            voice_mode?: "legacy" | "stepfun_realtime";
            runtime_profile_id?: string;
        }) => {
            return apiFetch<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
    },

    // Practice / Sessions
    practice: {
        createSession: async (data: {
            scenario_type: "sales" | "presentation";
            presentation_id?: string;
            agent_id?: string;
            persona_id?: string;
            scenario_id?: string;
            voice_mode?: "legacy" | "stepfun_realtime";
            runtime_profile_id?: string;
        }) => {
            return apiFetch<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        getSession: async (sessionId: string) => {
            return apiFetch<PracticeSessionRuntime>(`/practice/sessions/${sessionId}`);
        },

        controlLifecycle: async (sessionId: string, action: SessionLifecycleAction) => {
            const payload: SessionLifecycleRequest = { action };
            return apiFetch<SessionLifecycleResponse>(`/practice/sessions/${sessionId}/lifecycle`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        startSession: async (sessionId: string) => {
            return api.practice.controlLifecycle(sessionId, "start");
        },

        pauseSession: async (sessionId: string) => {
            return api.practice.controlLifecycle(sessionId, "pause");
        },

        resumeSession: async (sessionId: string) => {
            return api.practice.controlLifecycle(sessionId, "resume");
        },

        endSession: async (sessionId: string) => {
            return api.practice.controlLifecycle(sessionId, "end");
        },
    },

    // Sessions
    sessions: {
        list: async (params?: { limit?: number; page?: number; page_size?: number; sort?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.limit) searchParams.set("limit", String(params.limit));
            if (params?.page) searchParams.set("page", String(params.page));
            if (params?.page_size) searchParams.set("page_size", String(params.page_size));
            if (params?.sort) searchParams.set("sort", params.sort);
            return apiFetch<{ total: number; items: SessionItem[]; page: number; page_size: number; has_more: boolean }>(`/sessions?${searchParams}`);
        },

        getStats: async () => {
            return apiFetch<SessionStats>("/sessions/stats");
        },

        getReport: async (sessionId: string) => {
            return apiFetch<PracticeSessionReport>(`/practice/sessions/${sessionId}/report`);
        },

        getKnowledgeCheck: async (sessionId: string) => {
            return apiFetch<KnowledgeCheckDiagnostics>(`/practice/sessions/${sessionId}/knowledge-check`);
        },

        getEnhancedReport: async (sessionId: string) => {
            return apiFetch<Record<string, unknown>>(`/sessions/${sessionId}/enhanced-report`);
        },

        getReplay: async (sessionId: string) => {
            return apiFetch<ReplayData>(`/sessions/${sessionId}/replay`);
        },

        getMessages: async (sessionId: string, page = 1, pageSize = 50) => {
            return apiFetch<ReplayMessagesResponse>(`/sessions/${sessionId}/messages?page=${page}&page_size=${pageSize}`);
        },

        getMessageDetail: async (sessionId: string, messageId: string) => {
            return apiFetch<Record<string, unknown>>(`/sessions/${sessionId}/messages/${messageId}`);
        },

        getHighlights: async (sessionId: string) => {
            return apiFetch<HighlightsResponse>(`/sessions/${sessionId}/highlights`);
        },

        getAudioBlobUrl: async (sessionId: string, messageId: string) => {
            const response = await fetch(`${resolveApiBaseUrl()}/sessions/${sessionId}/audio/${messageId}`, {
                credentials: "include",
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            return URL.createObjectURL(blob);
        },
    },

    // Scenarios (user-facing)
    scenarios: {
        list: async (scenarioType?: string) => {
            const query = scenarioType ? `?scenario_type=${encodeURIComponent(scenarioType)}` : "";
            return apiFetch<ScenarioSummary[]>(`/scenarios${query}`);
        },

        getSalesPersonas: async (agentId?: string) => {
            const query = agentId
                ? `?agent_id=${encodeURIComponent(agentId)}`
                : "";
            return apiFetch<SalesPersonaOption[]>(`/scenarios/sales/personas${query}`);
        },

        getById: async (scenarioId: string) => {
            return apiFetch<ScenarioSummary>(`/scenarios/${scenarioId}`);
        },
    },

    // Agents (user-facing)
    agents: {
        list: async (params?: { category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await apiFetch<{ agents: Agent[]; total: number }>(`/agents?${searchParams}`);
            return result.agents || [];
        },

        getList: async (category: string) => {
            const result = await apiFetch<{ agents: Agent[]; total: number }>(`/agents?category=${category}&status=published`);
            return result.agents || [];
        },

        get: async (id: string) => {
            return apiFetch<Agent>(`/agents/${id}`);
        },

        getAgentWithPersonas: async (agentId: string) => {
            const [agent, personasResult] = await Promise.all([
                apiFetch<Agent>(`/agents/${agentId}`),
                apiFetch<{ personas: Persona[] }>(`/agents/${agentId}/personas`),
            ]);
            return {
                ...agent,
                personas: personasResult.personas || [],
            };
        },
    },

    // Admin - Analytics
    analytics: {
        getOverview: async (params?: { time_range?: string; scenario_type?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);

            return apiFetch<AnalyticsOverview>(`/admin/analytics/overview?${searchParams}`);
        },

        getTrends: async (params?: { time_range?: string; granularity?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.granularity) searchParams.set("granularity", params.granularity);

            return apiFetch<AnalyticsTrends>(`/admin/analytics/trends?${searchParams}`);
        },

        getAgents: async (params?: { time_range?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.limit) searchParams.set("limit", params.limit.toString());

            return apiFetch<AnalyticsAgents>(`/admin/analytics/agents?${searchParams}`);
        },

        getLeaderboard: async (params?: { time_range?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.limit) searchParams.set("limit", params.limit.toString());

            const payload = await apiFetch<{
                leaderboard: Array<{
                    rank: number;
                    user_id: string;
                    username?: string;
                    user_name?: string;
                    department: string | null;
                    total_sessions: number;
                    average_score: number;
                    best_score: number;
                    total_duration_minutes: number;
                }>;
            }>(`/admin/analytics/leaderboard?${searchParams}`);

            return {
                leaderboard: (payload.leaderboard || []).map((entry) => ({
                    ...entry,
                    username: entry.username || entry.user_name || "-",
                })),
            } as AnalyticsLeaderboard;
        },

        exportReport: async (params?: { time_range?: string; format?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.format) searchParams.set("format", params.format);

            const url = `${resolveApiBaseUrl()}/admin/analytics/export?${searchParams}`;

            const response = await fetch(url, {
                credentials: "include",
            });

            if (!response.ok) {
                throw new Error("Export failed");
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `analytics_report.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        },

        getManagerLiteLists: async (params?: { time_range?: string; limit?: number; inactive_days?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
            if (typeof params?.inactive_days === "number") {
                searchParams.set("inactive_days", String(params.inactive_days));
            }
            return apiFetch<ManagerLiteListsResponse>(`/admin/interventions/lists?${searchParams}`);
        },

        remindFromManagerLite: async (data: { user_id: string; note?: string }) => {
            return apiFetch<ManagerLiteRemindResponse>(`/admin/interventions/remind`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
    },

    // Admin operations
    admin: {
        // Training Records
        getTrainingRecords: async (params: {
            search?: string;
            category?: string;
            page?: number;
            page_size?: number;
        }) => {
            const searchParams = new URLSearchParams();
            if (params.search) searchParams.set("search", params.search);
            if (params.category && params.category !== "all") {
                searchParams.set("scenario_type", params.category);
            }
            if (params.page) searchParams.set("page", params.page.toString());
            if (params.page_size) searchParams.set("page_size", params.page_size.toString());

            const result = await apiFetch<{ items: SessionItem[]; total: number }>(`/admin/training-records?${searchParams}`);
            return result.items;
        },

        deleteTrainingRecord: async (id: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/training-records/${id}`, {
                method: "DELETE",
            });
        },

        // Users
        getUsers: async (params?: { page?: number; page_size?: number; search?: string; status?: string; role?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);
            if (params?.status) searchParams.set("status", params.status);
            if (params?.role) searchParams.set("role", params.role);

            return apiFetch<{ items: AdminUser[]; total: number }>(`/admin/users?${searchParams}`);
        },

        createUser: async (data: { display_name: string; email?: string; password?: string; name?: string; department?: string; role?: string }) => {
            return apiFetch<AdminUser>("/admin/users", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateUser: async (id: string, data: Partial<AdminUser>) => {
            return apiFetch<AdminUser>(`/admin/users/${id}`, {
                method: "PATCH",
                body: JSON.stringify(data),
            });
        },

        deleteUser: async (id: string) => {
            return apiFetch<void>(`/admin/users/${id}`, { method: "DELETE" });
        },

        suspendUser: async (id: string) => {
            return apiFetch<AdminUser>(`/admin/users/${id}/suspend`, { method: "POST" });
        },

        activateUser: async (id: string) => {
            return apiFetch<AdminUser>(`/admin/users/${id}/activate`, { method: "POST" });
        },

        // User Details API
        getUserStats: async (userId: string, params?: { time_range?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);

            return apiFetch<UserDetailStats>(`/admin/users/${userId}/stats?${searchParams}`);
        },

        getUserSessions: async (userId: string, params?: { page?: number; page_size?: number; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.status) searchParams.set("status", params.status);

            return apiFetch<UserSessionsResponse>(`/admin/users/${userId}/sessions?${searchParams}`);
        },

        getUserProgress: async (userId: string, params?: { time_range?: string; granularity?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.granularity) searchParams.set("granularity", params.granularity);

            return apiFetch<UserProgressResponse>(`/admin/users/${userId}/progress?${searchParams}`);
        },

        exportUsers: async (format: string, params?: { search?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            searchParams.set("format", format);
            if (params?.search) searchParams.set("search", params.search);
            if (params?.status) searchParams.set("status", params.status);

            const url = `${resolveApiBaseUrl()}/admin/users/export?${searchParams}`;

            const response = await fetch(url, {
                credentials: "include",
            });

            if (!response.ok) throw new Error("Export failed");

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `users.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        },

        // Agents
        getAgents: async (params?: { page?: number; page_size?: number; search?: string; category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await apiFetch<{ agents?: AdminAgent[]; items?: AdminAgent[]; total?: number }>(`/admin/agents?${searchParams}`);
            return {
                items: (result.agents || result.items || []) as AdminAgent[],
                total: result.total || 0
            };
        },

        getAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}`);
        },

        createAgent: async (data: AgentWritePayload) => {
            return apiFetch<AdminAgent>("/admin/agents", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateAgent: async (id: string, data: AgentWritePayload) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteAgent: async (id: string) => {
            return apiFetch<void>(`/admin/agents/${id}`, { method: "DELETE" });
        },

        publishAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}/publish`, { method: "POST" });
        },

        unpublishAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}/unpublish`, { method: "POST" });
        },

        archiveAgent: async (id: string) => {
            return apiFetch<AdminAgent>(`/admin/agents/${id}/archive`, { method: "POST" });
        },

        getAgentPersonas: async (agentId: string) => {
            const result = await apiFetch<{ personas?: AdminPersona[]; items?: AdminPersona[] }>(`/admin/agents/${agentId}/personas`);
            return (result.personas || result.items || []) as AdminPersona[];
        },

        addPersonaToAgent: async (
            agentId: string,
            data: {
                persona_id: string;
                display_order?: number;
                is_default?: boolean;
                override_config?: Record<string, unknown>;
            }
        ) => {
            return apiFetch<void>(`/admin/agents/${agentId}/personas`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        removePersonaFromAgent: async (agentId: string, personaId: string) => {
            return apiFetch<void>(`/admin/agents/${agentId}/personas/${personaId}`, {
                method: "DELETE",
            });
        },

        updateAgentPersona: async (
            agentId: string,
            personaId: string,
            data: {
                display_order?: number;
                is_default?: boolean;
                override_config?: Record<string, unknown>;
            }
        ) => {
            return apiFetch<void>(`/admin/agents/${agentId}/personas/${personaId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        // Personas
        getPersonas: async (params?: { page?: number; page_size?: number; search?: string; category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await apiFetch<{ personas?: AdminPersona[]; items?: AdminPersona[]; total?: number }>(`/admin/personas?${searchParams}`);
            return {
                items: (result.personas || result.items || []) as AdminPersona[],
                total: result.total || 0
            };
        },

        getPersona: async (id: string) => {
            return apiFetch<AdminPersona>(`/admin/personas/${id}`);
        },

        createPersona: async (data: Partial<AdminPersona>) => {
            return apiFetch<AdminPersona>("/admin/personas", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updatePersona: async (id: string, data: Partial<AdminPersona>) => {
            return apiFetch<AdminPersona>(`/admin/personas/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deletePersona: async (id: string) => {
            return apiFetch<void>(`/admin/personas/${id}`, { method: "DELETE" });
        },

        // Knowledge Bases
        getKnowledgeBases: async (params?: { page?: number; page_size?: number; search?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", params.page.toString());
            if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
            if (params?.search) searchParams.set("search", params.search);

            const result = await apiFetch<{ knowledge_bases?: AdminKnowledgeBase[]; items?: AdminKnowledgeBase[]; total?: number }>(`/admin/knowledge?${searchParams}`);
            return {
                items: (result.knowledge_bases || result.items || []) as AdminKnowledgeBase[],
                total: result.total || 0
            };
        },

        getKnowledgeBase: async (id: string) => {
            return apiFetch<AdminKnowledgeBase>(`/admin/knowledge/${id}`);
        },

        createKnowledgeBase: async (data: { name: string; description?: string; category?: string }) => {
            return apiFetch<AdminKnowledgeBase>("/admin/knowledge", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeBase: async (id: string, data: Partial<AdminKnowledgeBase>) => {
            return apiFetch<AdminKnowledgeBase>(`/admin/knowledge/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeBase: async (id: string) => {
            return apiFetch<void>(`/admin/knowledge/${id}`, { method: "DELETE" });
        },

        // Knowledge Base Documents
        getKnowledgeBaseDocuments: async (kbId: string) => {
            const result = await apiFetch<{ documents?: Array<AdminKnowledgeDocument & { title?: string; file_type?: string }>; items?: Array<AdminKnowledgeDocument & { title?: string; file_type?: string }> }>(`/admin/knowledge/${kbId}/documents`);
            const docs = (result.documents || result.items || []);
            // Map backend 'title' field to frontend 'file_name' field
            return docs.map((doc) => ({
                ...doc,
                file_name: doc.file_name || doc.title || doc.file_type || "未命名文件",
            })) as AdminKnowledgeDocument[];
        },

        uploadDocument: async (kbId: string, formData: FormData) => {
            const result = await apiUpload<AdminKnowledgeDocument & { title?: string; file_type?: string }>(`/admin/knowledge/${kbId}/documents`, formData);
            // Map backend 'title' field to frontend 'file_name' field
            return {
                ...result,
                file_name: result.file_name || result.title || result.file_type || "未命名文件",
            } as AdminKnowledgeDocument;
        },

        deleteDocument: async (kbId: string, docId: string) => {
            return apiFetch<void>(`/admin/knowledge/${kbId}/documents/${docId}`, {
                method: "DELETE",
            });
        },

        getDocumentPreview: async (kbId: string, docId: string) => {
            return apiFetch<AdminKnowledgeDocumentPreviewResponse>(`/admin/knowledge/${kbId}/documents/${docId}/preview`);
        },

        searchKnowledgeBase: async (
            kbId: string,
            query: string,
            topK = 5,
            similarityThreshold = 0.7,
        ) => {
            return apiFetch<AdminKnowledgeSearchResponse>(`/admin/knowledge/${kbId}/search`, {
                method: "POST",
                body: JSON.stringify({
                    query,
                    top_k: topK,
                    similarity_threshold: similarityThreshold,
                }),
            });
        },

        // Model Configs
        getModelConfigs: async () => {
            return apiFetch<AdminModelConfigGrouped | AdminModelConfigListItem[]>("/admin/model-configs");
        },

        getModelConfig: async (id: string) => {
            return apiFetch<AdminModelConfigDetail>(`/admin/model-configs/${id}`);
        },

        createModelConfig: async (data: AdminModelConfigUpsertPayload) => {
            return apiFetch<AdminModelConfigDetail>("/admin/model-configs", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateModelConfig: async (id: string, data: AdminModelConfigUpsertPayload) => {
            return apiFetch<AdminModelConfigDetail>(`/admin/model-configs/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteModelConfig: async (id: string) => {
            return apiFetch<void>(`/admin/model-configs/${id}`, { method: "DELETE" });
        },

        testModelConfig: async (id: string) => {
            return apiFetch<{ success: boolean; message: string; latency_ms?: number }>(`/admin/model-configs/${id}/test`, {
                method: "POST",
            });
        },

        testModelConfigInline: async (data: AdminModelConfigUpsertPayload) => {
            return apiFetch<{ success: boolean; message: string; latency_ms?: number }>("/admin/model-configs/test", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        // Voice Runtime Policies
        getVoiceRuntimeProfiles: async (params?: { only_active?: boolean }) => {
            const queryParams = new URLSearchParams();
            if (params?.only_active !== undefined) {
                queryParams.set("only_active", String(params.only_active));
            }
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<{ items: VoiceRuntimeProfile[]; total: number }>(`/admin/voice-runtime/profiles${query}`);
        },

        createVoiceRuntimeProfile: async (data: VoiceRuntimeProfilePayload) => {
            return apiFetch<VoiceRuntimeProfile>("/admin/voice-runtime/profiles", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateVoiceRuntimeProfile: async (profileId: string, data: Partial<VoiceRuntimeProfilePayload>) => {
            return apiFetch<VoiceRuntimeProfile>(`/admin/voice-runtime/profiles/${profileId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteVoiceRuntimeProfile: async (profileId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/voice-runtime/profiles/${profileId}`, {
                method: "DELETE",
            });
        },

        getAgentVoicePolicy: async (agentId: string) => {
            return apiFetch<AgentVoicePolicy>(`/admin/voice-runtime/agents/${agentId}/policy`);
        },

        updateAgentVoicePolicy: async (agentId: string, data: AgentVoicePolicyUpsertPayload) => {
            return apiFetch<AgentVoicePolicy>(`/admin/voice-runtime/agents/${agentId}/policy`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        previewEffectiveVoicePolicy: async (agentId: string, params?: {
            persona_id?: string;
            voice_mode_override?: "legacy" | "stepfun_realtime";
            runtime_profile_id?: string;
        }) => {
            const queryParams = new URLSearchParams();
            if (params?.persona_id) queryParams.set("persona_id", params.persona_id);
            if (params?.voice_mode_override) queryParams.set("voice_mode_override", params.voice_mode_override);
            if (params?.runtime_profile_id) queryParams.set("runtime_profile_id", params.runtime_profile_id);
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<Record<string, unknown>>(`/admin/voice-runtime/agents/${agentId}/effective${query}`);
        },

        getPresentationAIPolicy: async (params?: {
            scope_type?: PresentationAIScopeType;
            scope_id?: string;
        }) => {
            const queryParams = new URLSearchParams();
            if (params?.scope_type) queryParams.set("scope_type", params.scope_type);
            if (params?.scope_id) queryParams.set("scope_id", params.scope_id);
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<PresentationAIPolicyScopeResponse>(
                `/admin/presentation-ai/policy${query}`,
            );
        },

        updatePresentationAIPolicy: async (data: PresentationAIPolicyUpsertPayload) => {
            return apiFetch<PresentationAIPolicyScopeResponse>("/admin/presentation-ai/policy", {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        previewPresentationAIPolicy: async (data: PresentationAIPolicyPreviewPayload) => {
            return apiFetch<PresentationAIPolicyPreviewResponse>("/admin/presentation-ai/policy/preview", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        getEffectivePresentationAIPolicy: async (params?: {
            session_id?: string;
            scenario_id?: string;
            presentation_id?: string;
        }) => {
            const queryParams = new URLSearchParams();
            if (params?.session_id) queryParams.set("session_id", params.session_id);
            if (params?.scenario_id) queryParams.set("scenario_id", params.scenario_id);
            if (params?.presentation_id) queryParams.set("presentation_id", params.presentation_id);
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<PresentationAIPolicyEffectiveResponse>(
                `/admin/presentation-ai/policy/effective${query}`,
            );
        },

        // Prompt Templates (B10)
        getPromptTemplates: async (params?: { prompt_type?: string; category?: string; is_active?: boolean }) => {
            const queryParams = new URLSearchParams();
            if (params?.prompt_type) queryParams.append("prompt_type", params.prompt_type);
            if (params?.category) queryParams.append("category", params.category);
            if (params?.is_active !== undefined) queryParams.append("is_active", String(params.is_active));
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<PromptTemplate[]>(`/prompt-templates${query}`);
        },

        getPromptTemplate: async (id: string) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            return apiFetch<PromptTemplate>(`/prompt-templates/${normalizedId}`);
        },

        createPromptTemplate: async (data: PromptTemplateCreate) => {
            return apiFetch<PromptTemplate>("/prompt-templates", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updatePromptTemplate: async (id: string, data: PromptTemplateUpdate) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            return apiFetch<PromptTemplate>(`/prompt-templates/${normalizedId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deletePromptTemplate: async (id: string) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            return apiFetch<void>(`/prompt-templates/${normalizedId}`, {
                method: "DELETE",
            });
        },

        renderPromptTemplate: async (id: string, variables: Record<string, unknown>) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            const request: PromptRenderRequest = { template_id: normalizedId, variables };
            return apiFetch<PromptRenderResponse>(`/prompt-templates/${normalizedId}/render`, {
                method: "POST",
                body: JSON.stringify(request),
            });
        },

        setDefaultPromptTemplate: async (id: string, promptType: string) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            return apiFetch<PromptTemplate>(`/prompt-templates/${normalizedId}/set-default?prompt_type=${promptType}`, {
                method: "POST",
            });
        },

        getPromptTemplateForScenario: async (scenarioType: string, promptType: string, scenarioId?: string) => {
            const queryParams = new URLSearchParams({ prompt_type: promptType });
            if (scenarioId) queryParams.append("scenario_id", scenarioId);
            return apiFetch<PromptTemplate | null>(`/prompt-templates/by-scenario/${scenarioType}?${queryParams.toString()}`);
        },

        // Scenario Prompts
        getScenarioPrompts: async (params?: { scenario_type?: string; prompt_type?: string }) => {
            const queryParams = new URLSearchParams();
            if (params?.scenario_type) queryParams.append("scenario_type", params.scenario_type);
            if (params?.prompt_type) queryParams.append("prompt_type", params.prompt_type);
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<ScenarioPrompt[]>(`/scenario-prompts${query}`);
        },

        createScenarioPrompt: async (data: ScenarioPromptCreate) => {
            return apiFetch<ScenarioPrompt>("/scenario-prompts", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        deleteScenarioPrompt: async (id: string) => {
            return apiFetch<void>(`/scenario-prompts/${id}`, {
                method: "DELETE",
            });
        },

        // Staged Evaluation & Comprehensive Report (C6-C7)
        getComprehensiveReport: async (sessionId: string) => {
            return apiFetch<ComprehensiveReport>(`/evaluation/sessions/${sessionId}/report`);
        },

        generateComprehensiveReport: async (sessionId: string) => {
            return apiFetch<ComprehensiveReport>(`/evaluation/sessions/${sessionId}/report`, {
                method: "POST",
            });
        },

        getRealtimeEvaluationFeedback: async (sessionId: string) => {
            return apiFetch<RealtimeEvaluationFeedback[]>(`/evaluation/sessions/${sessionId}/feedback`);
        },
    },

    // Admin toolchain and lower-level capabilities
    adminTools: {
        getSystemLogs: async (params?: { status?: string; search?: string; page?: number; page_size?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.status) searchParams.set("status", params.status);
            if (params?.search) searchParams.set("search", params.search);
            if (params?.page) searchParams.set("page", String(params.page));
            if (params?.page_size) searchParams.set("page_size", String(params.page_size));
            return apiFetch<AdminSystemLogListResponse>(`/admin/system-logs?${searchParams}`);
        },

        getSystemLog: async (logId: string) => {
            return apiFetch<AdminSystemLog>(`/admin/system-logs/${logId}`);
        },

        duplicatePersona: async (personaId: string, name?: string) => {
            const query = name ? `?name=${encodeURIComponent(name)}` : "";
            return apiFetch<Record<string, unknown>>(`/admin/personas/${personaId}/duplicate${query}`, {
                method: "POST",
            });
        },

        previewTTS: async (payload: { text: string; voice?: string; speed?: number }) => {
            return apiFetch<Record<string, unknown>>("/admin/model-configs/tts/preview", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        reprocessKnowledgeDocument: async (kbId: string, docId: string) => {
            return apiFetch<Record<string, unknown>>(`/admin/knowledge/${kbId}/documents/${docId}/reprocess`, {
                method: "POST",
            });
        },

        exportUsersFile: async (params?: { format?: "csv" | "json"; include_inactive?: boolean }) => {
            const searchParams = new URLSearchParams();
            if (params?.format) searchParams.set("format", params.format);
            if (params?.include_inactive !== undefined) searchParams.set("include_inactive", String(params.include_inactive));

            const response = await fetch(`${resolveApiBaseUrl()}/admin/users/export?${searchParams}`, {
                headers: createHeaders(undefined, false),
                credentials: "include",
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.blob();
        },

        exportAnalyticsFile: async (params?: { time_range?: string; format?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.format) searchParams.set("format", params.format);

            const response = await fetch(`${resolveApiBaseUrl()}/admin/analytics/export?${searchParams}`, {
                headers: createHeaders(undefined, false),
                credentials: "include",
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.blob();
        },
    },

    // Presentation coach (user)
    presentations: {
        list: async (params?: { status?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.status) searchParams.set("status", params.status);
            if (params?.limit) searchParams.set("limit", params.limit.toString());
            const query = searchParams.toString();
            const result = await apiFetch<Array<Record<string, unknown>>>(`/presentations${query ? `?${query}` : ""}`);
            return result.map(normalizePresentationListItem);
        },

        upload: async ({ title, file }: { title: string; file: File }) => {
            const formData = new FormData();
            formData.append("title", title);
            formData.append("file", file);
            const result = await apiUpload<Record<string, unknown>>("/presentations", formData);
            return normalizePresentationListItem(result);
        },

        get: async (presentationId: string) => {
            const result = await apiFetch<Record<string, unknown>>(`/presentations/${presentationId}`);
            return normalizePresentationDetailItem(result);
        },

        delete: async (presentationId: string) => {
            return apiFetch<void>(`/presentations/${presentationId}`, {
                method: "DELETE",
            });
        },

        getForbiddenWords: async (presentationId: string) => {
            const result = await apiFetch<Array<Record<string, unknown>>>(`/presentations/${presentationId}/forbidden-words`);
            return result.map(normalizePresentationForbiddenWord);
        },

        addForbiddenWord: async (presentationId: string, payload: { phrase: string; suggested_alternative?: string }) => {
            const result = await apiFetch<Record<string, unknown>>(`/presentations/${presentationId}/forbidden-words`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            return normalizePresentationForbiddenWord(result);
        },

        deleteForbiddenWord: async (_presentationId: string, wordId: string) => {
            return apiFetch<void>(`/admin/forbidden-words/${wordId}`, {
                method: "DELETE",
            });
        },

        getPages: async (presentationId: string) => {
            const result = await apiFetch<Array<Record<string, unknown>>>(`/presentations/${presentationId}/pages`);
            return result.map(normalizePresentationPage);
        },

        getThumbnailBlob: async (presentationId: string, pageNumber: number) => {
            const response = await fetchWithLoopbackRetry(
                `${resolveApiBaseUrl()}/presentations/${presentationId}/pages/${pageNumber}/thumbnail`,
                {
                    method: "GET",
                    headers: createHeaders(undefined, false),
                    credentials: "include",
                },
            );
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.blob();
        },

        getTalkingPoints: async (presentationId: string, pageNumber: number) => {
            const result = await apiFetch<Array<Record<string, unknown>>>(`/presentations/${presentationId}/pages/${pageNumber}/talking-points`);
            return result.map(normalizePresentationTalkingPoint);
        },

        addTalkingPoint: async (presentationId: string, pageNumber: number, payload: { description: string }) => {
            const result = await apiFetch<Record<string, unknown>>(`/presentations/${presentationId}/pages/${pageNumber}/talking-points`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            return normalizePresentationTalkingPoint(result);
        },

        deleteTalkingPoint: async (_presentationId: string, pointId: string) => {
            return apiFetch<void>(`/admin/talking-points/${pointId}`, {
                method: "DELETE",
            });
        },
    },

    // Presentation coach (admin)
    adminPresentations: {
        list: async () => {
            return apiFetch<Array<Record<string, unknown>>>("/admin/presentations");
        },

        create: async (payload: Record<string, unknown>) => {
            return apiFetch<Record<string, unknown>>("/admin/presentations", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        upload: async (formData: FormData) => {
            return apiUpload<Record<string, unknown>>("/admin/presentations/upload", formData);
        },

        get: async (presentationId: string) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}`);
        },

        delete: async (presentationId: string) => {
            return apiFetch<void>(`/admin/presentations/${presentationId}`, {
                method: "DELETE",
            });
        },

        getPages: async (presentationId: string) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}/pages`);
        },

        updatePage: async (presentationId: string, pageNumber: number, payload: Record<string, unknown>) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}/pages/${pageNumber}`, {
                method: "PUT",
                body: JSON.stringify(payload),
            });
        },

        getTalkingPoints: async (presentationId: string, pageNumber: number) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}/pages/${pageNumber}/talking-points`);
        },

        addTalkingPoint: async (presentationId: string, pageNumber: number, payload: Record<string, unknown>) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}/pages/${pageNumber}/talking-points`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        deleteTalkingPoint: async (pointId: string) => {
            return apiFetch<void>(`/admin/talking-points/${pointId}`, {
                method: "DELETE",
            });
        },

        getForbiddenWords: async (presentationId: string) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}/forbidden-words`);
        },

        addForbiddenWord: async (presentationId: string, payload: Record<string, unknown>) => {
            return apiFetch<Record<string, unknown>>(`/admin/presentations/${presentationId}/forbidden-words`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        deleteForbiddenWord: async (wordId: string) => {
            return apiFetch<void>(`/admin/forbidden-words/${wordId}`, {
                method: "DELETE",
            });
        },
    },

    // Internal capabilities
    internal: {
        searchKnowledge: async (kbId: string, query: string, topK = 5) => {
            return apiFetch<Record<string, unknown>>(`/internal/knowledge/${kbId}/search`, {
                method: "POST",
                body: JSON.stringify({ query, top_k: topK }),
            });
        },

        health: async () => {
            const root = resolveApiBaseUrl().replace(/\/api\/v1$/, "");
            const response = await fetch(`${root}/health`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        },
    },
};
