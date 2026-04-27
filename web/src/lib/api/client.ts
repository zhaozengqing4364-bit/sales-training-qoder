/**
 * API Client - Unified API access layer
 * 
 * Handles authentication, error handling, and API calls.
 * Follows Constitution Principle I: No user-visible errors.
 */

import {
    DashboardStats,
    GrowthDashboardResponse,
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
    AdminPersonaCustomerPressure,
    AdminPersonaPolicy,
    AdminPersonaPolicyHealthReport,
    AdminAgentIndustryPackContract,
    AdminPersonaIndustryPackContract,
    AdminKnowledgeBase,
    AdminKnowledgeDocument,
    AdminKnowledgeDocumentPreviewResponse,
    AdminKnowledgeSearchResponse,
    AdminKnowledgeAnswerAdminConfig,
    AdminKnowledgeAnswerConfigOptions,
    AdminKnowledgeAnswerRunDetail,
    AdminKnowledgeAnswerRunListResponse,
    AdminKnowledgeAnswerRunStepsResponse,
    AdminKnowledgeConfigVersionResponse,
    AdminKnowledgeConfigVersionListResponse,
    AdminKnowledgeQueryProfile,
    AdminKnowledgeIntentRule,
    AdminKnowledgeEntityAlias,
    AdminKnowledgeRankingProfile,
    AdminKnowledgeAnswerabilityProfile,
    AdminKnowledgeDebugTriggerRequest,
    AdminKnowledgeDebugTriggerResponse,
    AdminSystemLog,
    AdminSystemLogListResponse,
    AdminVoiceRuntimeProfile,
    AdminPresentationListItem,
    AdminPresentationDetailItem,
    AdminPresentationPage,
    UserDetailStats,
    UserSessionsResponse,
    UserProgressResponse,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateGovernanceRemediationResponse,
    PromptTemplateGovernanceStatus,
    PromptTemplateOptions,
    PromptTemplateQuarantineResult,
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
    HighlightReviewItemPayload,
    HighlightReviewResponse,
    HighlightReviewShareCreateResponse,
    SalesCombinationPreviewResponse,
    SalesCombinationRuleMutationResponse,
    SalesCombinationRuleSet,
    SalesCombinationRuleSetListResponse,
    SalesCombinationRuleValidationResult,
    SessionStats,
    PracticeSessionReport,
    HistoryListResponse,
    HistoryStatistics,
    HistoryTrendPoint,
    KnowledgeCheckDiagnostics,
    OpenAnalyticsDashboard,
    OpenScoreDistribution,
    SupportRuntimeFaultsResponse,
    SupportRuntimeOverview,
    SessionStatus,
    SessionLifecycleAction,
    SessionLifecycleRequest,
    SessionLifecycleResponse,
    RetryFocusIntent,
    PresentationAIPolicyScopeResponse,
    PresentationAIPolicyPreviewResponse,
    PresentationAIPolicyEffectiveResponse,
    PresentationAIScopeType,
    ManagerLiteListsResponse,
    ManagerLiteRemindResponse,
    AdminOperatingPackResponse,
    ManagerInterventionCreateRequest,
    ManagerInterventionItem,
    LearnerOpenIntervention,
    ManagerInterventionListResponse,
    ManagerInterventionRemindRequest,
    ManagerInterventionRemindResponse,
    AssetGovernanceAnomaly,
    AssetGovernanceHealthSummary,
    AssetGovernanceImpactSummary,
    AssetGovernanceRecentChangeSummary,
    AssetGovernanceSummary,
    LinkedAssetChangeReference,
    SupportRuntimeFaultDiagnostics,
    RagProfile,
    CreateRagProfileRequest,
    UpdateRagProfileRequest,
    AdminKnowledgeChunkingPreset,
    CreateKnowledgeChunkingPresetRequest,
    UpdateKnowledgeChunkingPresetRequest,
    AdminModelConfigCreateRequest,
    AdminModelConfigCreateResponse,
    AdminModelConfigDetail,
    AdminModelConfigGrouped,
    AdminModelConfigTestResponse,
    AdminModelConfigTestRequest,
    AdminModelConfigUpdateRequest,
    AdaptiveDifficultyDryRunResponse,
} from "./types";
import { authHandler } from "@/lib/auth-handler";
import { normalizeCurrentUser } from "@/lib/auth/current-user";
import { buildTraceHeaders } from "@/lib/observability/trace-context";
import {
    createAdminReportDomain,
    createAgentsDomain,
    createAuthDomain,
    createPracticeDomain,
    createPresentationsDomain,
    createSessionsDomain,
} from "./client-domains";

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
const CSRF_COOKIE_NAME = "app_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";

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
    "[HTTP_404]": "请求的配置接口暂未开通或资源不存在，请刷新后重试或联系管理员。",
    "[BUSINESS_RULE_KEY_UNSUPPORTED]": "业务规则配置暂不支持该类型，请刷新后重试或联系管理员。",
    "[BUSINESS_RULE_SCHEMA_INVALID]": "业务规则配置校验未通过，请检查必填项、唯一性和兜底策略。",
    "[REQUEST_VALIDATION_ERROR]": "请求参数缺失或格式不正确，请检查后重试。",
    "[INVALID_CLIENT_PAYLOAD]": "请求参数无效，请刷新页面后重试。",
    "[AUTHENTICATION_REQUIRED]": "当前请求需要登录后才能继续。",
    "[INVALID_TOKEN]": "登录态已失效，请重新登录。",
    "[AUTH_USER_NOT_FOUND]": "登录用户不存在或已被删除。",
    "[AUTH_USER_DISABLED]": "当前账号已被停用。",
    "[AGENT_PERSONA_PAIR_REQUIRED]": "请选择智能体与角色后再开始训练。",
    "[AGENT_ARCHIVED]": "该智能体已归档，暂时无法创建训练会话。",
    "[AGENT_NOT_PUBLISHED]": "该智能体尚未发布，请选择可用智能体。",
    "[PERSONA_INACTIVE]": "该角色已停用，请更换角色。",
    "[PERSONA_NOT_LINKED_TO_AGENT]": "所选角色未关联当前智能体，请重新选择。",
    "[AGENT_CATEGORY_RESTRICTED]": "当前仅支持创建「销售」与「演讲」两类智能体。",
    "[AGENT_NOT_FOUND]": "智能体不存在，请刷新后重试。",
    "[AGENT_CANNOT_DELETE]": "该智能体仍有关联会话，暂时不能删除。",
    "[AGENT_ALREADY_PUBLISHED]": "该智能体已经发布，无需重复操作。",
    "[AGENT_ALREADY_DRAFT]": "该智能体已经处于草稿状态。",
    "[FIELD_DEPRECATED_PERSONA_CENTERED]": "该配置入口已下线，请改为在角色中心（Persona）配置。",
    "[PROMPT_TEMPLATE_ID_INVALID]": "模板ID无效，请检查后重试。",
    "[PROMPT_SCOPE_VIOLATION]": "销售场景仅允许评估/报告相关模板。",
    "[SALES_PERSONA_REQUIRED]": "请先选择销售角色。",
    "[SESSION_NOT_FOUND]": "未找到目标会话，请刷新后重试。",
    "[SESSION_NOT_COMPLETED]": "当前会话还在评分中，回放会在持久化完成后解锁。",
    "[ACCESS_DENIED]": "你没有权限访问该会话。",
    "[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]": "仅管理员可访问提示词治理接口。",
    "[PROMPT_TEMPLATE_NOT_FOUND]": "模板不存在。",
    "[SCENARIO_PROMPT_NOT_FOUND]": "场景提示词绑定不存在。",
    "[ROLE_REQUIRED]": "当前账号权限不足，无法执行该操作。",
    "[PRESENTATION_NOT_FOUND]": "演示文稿不存在。",
    "[PRESENTATION_DELETE_FORBIDDEN]": "你没有权限删除该演示文稿。",
    "[PRESENTATION_PAGE_NOT_FOUND]": "演示页不存在。",
    "[PRESENTATION_THUMBNAIL_NOT_FOUND]": "演示页缩略图不存在。",
    "[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]": "当前有进行中的演练正在使用该标准PPT，请结束后再替换。",
    "[VOICE_RUNTIME_PROFILE_NOT_FOUND]": "运行时配置不存在，请刷新后重试。",
    "[REPORT_NOT_FOUND]": "目标报告尚未生成或已不存在。",
    "[REPORT_FETCH_FAILED]": "报告暂时无法读取，请稍后重试。",
    "[REPORT_GENERATION_FAILED]": "报告生成失败，请稍后重试。",
    "[TTS_PREVIEW_FAILED]": "语音试听失败，请稍后重试。",
    "[HIGHLIGHT_REVIEW_SAVE_FAILED]": "高光复习清单保存失败，请稍后重试。",
    "[HIGHLIGHT_MESSAGE_NOT_FOUND]": "所选高光片段已变化，请刷新报告后重新选择。",
    "[HIGHLIGHT_REVIEW_EMPTY]": "请先选择至少一个高光片段再分享。",
    "[WECOM_SHARE_NOT_AVAILABLE]": "企业微信分享试点暂未通过治理配置开放。",
    "[SHARE_CONSENT_REQUIRED]": "请先确认同意分享脱敏高光清单。",
    "[HIGHLIGHT_SHARE_INACTIVE]": "分享链接已过期或已撤销。",
};

type NormalizedApiErrorPayload = {
    status: number;
    errorCode: string;
    message: string;
    traceId?: string;
};

/**
 * M016/S02/T01 error-contract inventory:
 * - apiFetch/apiUpload normalize both top-level Result-style errors
 *   ({ success:false, error, message, trace_id }) and HTTPException-style
 *   payloads ({ detail: { error, message } }).
 * - Most pages already consume this seam only through ApiRequestError + getApiErrorMessage.
 * - The remaining client-local parsing fork lives in getSegmentAudioBlobUrl(), which still reads
 *   raw payload fields and throws bare Error(errorCode) instead of reusing ApiRequestError.
 */
function normalizeApiErrorPayload(status: number, payload: unknown): NormalizedApiErrorPayload {
    const raw = (payload && typeof payload === "object")
        ? payload as Record<string, unknown>
        : {};
    const detail = (raw.detail && typeof raw.detail === "object" && !Array.isArray(raw.detail))
        ? raw.detail as Record<string, unknown>
        : null;
    const validationItems = Array.isArray(raw.detail) ? raw.detail : null;

    const rawCode = detail?.error
        ?? detail?.error_code
        ?? raw.error
        ?? raw.error_code;
    const errorCode = typeof rawCode === "string" && rawCode.trim()
        ? rawCode.trim()
        : validationItems
            ? "[REQUEST_VALIDATION_ERROR]"
            : `[HTTP_${status}]`;

    const validationMessage = validationItems
        ?.map((item) => {
            if (!item || typeof item !== "object") {
                return "";
            }
            const msg = (item as { msg?: unknown }).msg;
            return typeof msg === "string" ? msg.trim() : "";
        })
        .find(Boolean);

    const rawMessage = detail?.message ?? raw.message;
    const message = typeof rawMessage === "string" && rawMessage.trim()
        ? rawMessage.trim()
        : validationMessage || errorCode;

    const rawTraceId = raw.trace_id ?? detail?.trace_id;
    const traceId = typeof rawTraceId === "string" && rawTraceId.trim()
        ? rawTraceId.trim()
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
    evaluable?: boolean | null;
    not_evaluable_reason?: string | null;
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

type VoiceRuntimeProfile = AdminVoiceRuntimeProfile;

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

type PresentationStatus = "processing" | "ready" | "failed";

type PresentationPage = AdminPresentationPage;

type PresentationListItem = AdminPresentationListItem;

type PresentationDetailItem = AdminPresentationDetailItem;

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

function toNullableStringValue(value: unknown): string | null {
    const normalized = toStringValue(value).trim();
    return normalized ? normalized : null;
}

function normalizeAssetGovernanceAnomaly(value: unknown): AssetGovernanceAnomaly {
    const raw = toRecord(value);
    return {
        kind: toStringValue(raw.kind),
        severity: toStringValue(raw.severity),
        summary: toStringValue(raw.summary),
        detected_at: toNullableStringValue(raw.detected_at),
        session_id: toNullableStringValue(raw.session_id),
        source: toNullableStringValue(raw.source),
    };
}

function normalizeAssetGovernanceSummary(value: unknown): AssetGovernanceSummary | null {
    const raw = toRecord(value);
    if (!Object.keys(raw).length) {
        return null;
    }

    const impact = toRecord(raw.impact_summary);
    const recentChange = toRecord(raw.recent_change_summary);
    const health = toRecord(raw.health_summary);

    if (!Object.keys(impact).length && !Object.keys(recentChange).length && !Object.keys(health).length) {
        return null;
    }

    const impactSummary: AssetGovernanceImpactSummary | null = Object.keys(impact).length
        ? {
            impact_level: toStringValue(impact.impact_level, "low"),
            recent_session_count: toNumberValue(impact.recent_session_count, 0),
            active_session_count: toNumberValue(impact.active_session_count, 0),
            impacted_user_count: toNumberValue(impact.impacted_user_count, 0),
            last_session_at: toNullableStringValue(impact.last_session_at),
        }
        : null;

    const recentChangeSummary: AssetGovernanceRecentChangeSummary | null = Object.keys(recentChange).length
        ? {
            last_changed_at: toNullableStringValue(recentChange.last_changed_at),
            latest_change_type: toStringValue(recentChange.latest_change_type),
            latest_change_label: toStringValue(recentChange.latest_change_label),
            change_count_7d: toNumberValue(recentChange.change_count_7d, 0),
            sessions_since_change: toNumberValue(recentChange.sessions_since_change, 0),
        }
        : null;

    const healthSummary: AssetGovernanceHealthSummary | null = Object.keys(health).length
        ? {
            status: toStringValue(health.status, "healthy"),
            anomaly_count: toNumberValue(health.anomaly_count, 0),
            blocking_count: toNumberValue(health.blocking_count, 0),
            warning_count: toNumberValue(health.warning_count, 0),
            sample_anomalies: Array.isArray(health.sample_anomalies)
                ? health.sample_anomalies.map(normalizeAssetGovernanceAnomaly)
                : [],
        }
        : null;

    return {
        impact_summary: impactSummary,
        recent_change_summary: recentChangeSummary,
        health_summary: healthSummary,
    };
}

function normalizeLinkedAssetChangeReference(value: unknown): LinkedAssetChangeReference | null {
    const raw = toRecord(value);
    const assetName = toStringValue(raw.asset_name).trim();
    const adminPath = toStringValue(raw.admin_path).trim();
    const latestChangeLabel = toStringValue(raw.latest_change_label).trim();

    if (!assetName || !adminPath || !latestChangeLabel) {
        return null;
    }

    return {
        asset_type: toStringValue(raw.asset_type),
        asset_label: toStringValue(raw.asset_label),
        asset_id: toStringValue(raw.asset_id),
        asset_name: assetName,
        admin_path: adminPath,
        latest_change_label: latestChangeLabel,
        latest_change_type: toStringValue(raw.latest_change_type),
        last_changed_at: toNullableStringValue(raw.last_changed_at),
        change_count_7d: toNumberValue(raw.change_count_7d, 0),
        sessions_since_change: toNumberValue(raw.sessions_since_change, 0),
        impact_level: toStringValue(raw.impact_level, "low"),
        health_status: toStringValue(raw.health_status, "healthy"),
    };
}

function normalizeSupportRuntimeFaultDiagnostics(value: unknown): SupportRuntimeFaultDiagnostics {
    const raw = toRecord(value);
    const linkedAssetChanges = Array.isArray(raw.linked_asset_changes)
        ? raw.linked_asset_changes
            .map(normalizeLinkedAssetChangeReference)
            .filter((item): item is LinkedAssetChangeReference => Boolean(item))
        : [];

    return {
        ...raw,
        linked_asset_changes: linkedAssetChanges,
    };
}

function normalizeSupportRuntimeFaultItem(
    input: unknown,
): SupportRuntimeFaultsResponse["items"][number] {
    const raw = toRecord(input);
    return {
        source: toStringValue(raw.source),
        severity: raw.severity === "warning" ? "warning" : "blocking",
        kind: toStringValue(raw.kind),
        summary: toStringValue(raw.summary),
        detected_at: toNullableStringValue(raw.detected_at),
        session_id: toNullableStringValue(raw.session_id),
        scenario_type: toNullableStringValue(raw.scenario_type),
        session_status: toNullableStringValue(raw.session_status),
        report_status: toNullableStringValue(raw.report_status),
        diagnostics: normalizeSupportRuntimeFaultDiagnostics(raw.diagnostics),
    };
}

function normalizeSupportRuntimeFaultsResponse(input: unknown): SupportRuntimeFaultsResponse {
    const raw = toRecord(input);
    return {
        generated_at: toStringValue(raw.generated_at),
        items: Array.isArray(raw.items) ? raw.items.map(normalizeSupportRuntimeFaultItem) : [],
        count: toNumberValue(raw.count, 0),
        limit: toNumberValue(raw.limit, 0),
        severity: raw.severity === "warning" || raw.severity === "blocking"
            ? raw.severity
            : null,
    };
}

function normalizeAdminKnowledgeBase(input: unknown): AdminKnowledgeBase {
    const raw = toRecord(input);
    return {
        ...raw,
        id: toStringValue(raw.id),
        name: toStringValue(raw.name),
        description: toStringValue(raw.description),
        category: toStringValue(raw.category),
        status: toStringValue(raw.status),
        document_count: toNumberValue(raw.document_count, toNumberValue(raw.doc_count, 0)),
        total_chunks: toNumberValue(raw.total_chunks, 0),
        doc_count: raw.doc_count === undefined ? undefined : toNumberValue(raw.doc_count, 0),
        created_at: toStringValue(raw.created_at),
        updated_at: toStringValue(raw.updated_at),
        governance_summary: normalizeAssetGovernanceSummary(raw.governance_summary),
    };
}

function normalizeVoiceRuntimeProfile(input: unknown): VoiceRuntimeProfile {
    const raw = toRecord(input);
    return {
        ...raw,
        id: toStringValue(raw.id),
        name: toStringValue(raw.name),
        description: toNullableStringValue(raw.description),
        is_default: Boolean(raw.is_default),
        is_active: raw.is_active !== false,
        voice_mode: raw.voice_mode === "legacy" ? "legacy" : "stepfun_realtime",
        model_name: toStringValue(raw.model_name),
        voice_name: toStringValue(raw.voice_name),
        temperature: toNumberValue(raw.temperature, 0.7),
        input_audio_format: toStringValue(raw.input_audio_format),
        output_audio_format: toStringValue(raw.output_audio_format),
        output_sample_rate: toNumberValue(raw.output_sample_rate, 24000),
        turn_detection: toNullableStringValue(raw.turn_detection),
        tool_policy: toRecord(raw.tool_policy),
        created_at: toNullableStringValue(raw.created_at),
        updated_at: toNullableStringValue(raw.updated_at),
        governance_summary: normalizeAssetGovernanceSummary(raw.governance_summary),
    };
}

function normalizePresentationStatus(value: unknown): PresentationStatus {
    if (value === "ready") return "ready";
    if (value === "processing") return "processing";
    if (value === "failed" || value === "error") return "failed";
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
    const totalPages = toNumberValue(raw.total_pages, pages.length);
    return {
        presentation_id: toStringValue(raw.presentation_id),
        title: toStringValue(raw.title, "未命名PPT"),
        status: normalizePresentationStatus(raw.status),
        version_number: toNumberValue(raw.version_number, 1),
        file_size_bytes: toNumberValue(raw.file_size_bytes, 0),
        page_count: toNumberValue(raw.page_count, totalPages),
        total_pages: totalPages,
        uploaded_by_admin_id: toStringValue(raw.uploaded_by_admin_id),
        created_at: toStringValue(raw.created_at, toStringValue(raw.upload_date)),
        governance_summary: normalizeAssetGovernanceSummary(raw.governance_summary),
    };
}

function normalizePresentationDetailItem(input: unknown): PresentationDetailItem {
    const raw = toRecord(input);
    const pages = Array.isArray(raw.pages) ? raw.pages.map(normalizePresentationPage) : [];
    const totalPages = toNumberValue(raw.total_pages, pages.length);
    return {
        ...normalizePresentationListItem(raw),
        page_count: toNumberValue(raw.page_count, totalPages),
        total_pages: totalPages,
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

function normalizeStringList(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }

    const normalized: string[] = [];
    const seen = new Set<string>();
    for (const item of value) {
        const text = typeof item === "string" ? item.trim() : String(item ?? "").trim();
        if (!text) {
            continue;
        }
        const dedupeKey = text.toLowerCase();
        if (seen.has(dedupeKey)) {
            continue;
        }
        seen.add(dedupeKey);
        normalized.push(text);
    }
    return normalized;
}

function normalizeAdminPersonaCustomerPressure(value: unknown): AdminPersonaCustomerPressure | undefined {
    const raw = toRecord(value);
    if (!Object.keys(raw).length) {
        return undefined;
    }

    const pressureDirection = toRecord(raw.pressure_direction);
    const followUpBehavior = toRecord(raw.follow_up_behavior);

    return {
        ...raw,
        source: toStringValue(raw.source) || undefined,
        pressure_direction: {
            ...pressureDirection,
            sales_focus: toStringValue(pressureDirection.sales_focus) || undefined,
            value_axes: normalizeStringList(pressureDirection.value_axes),
            objection_axes: normalizeStringList(pressureDirection.objection_axes),
        },
        follow_up_behavior: {
            ...followUpBehavior,
            question_strategy: toStringValue(followUpBehavior.question_strategy) || undefined,
            revisit_on_evasion: Boolean(followUpBehavior.revisit_on_evasion),
            require_evidence: Boolean(followUpBehavior.require_evidence),
            expected_customer_questions: normalizeStringList(
                followUpBehavior.expected_customer_questions,
            ),
        },
    };
}

function normalizeAdminPersonaPolicy(value: unknown): AdminPersonaPolicy | undefined {
    const raw = toRecord(value);
    if (!Object.keys(raw).length) {
        return undefined;
    }

    return {
        ...raw,
        version: typeof raw.version === "number" ? raw.version : undefined,
        system_prompt: toStringValue(raw.system_prompt) || undefined,
        knowledge_base_ids: normalizeStringList(raw.knowledge_base_ids),
        tool_policy: toRecord(raw.tool_policy),
        sales_focus: toStringValue(raw.sales_focus) || undefined,
        value_axes: normalizeStringList(raw.value_axes),
        objection_axes: normalizeStringList(raw.objection_axes),
        expected_customer_questions: normalizeStringList(raw.expected_customer_questions),
        customer_pressure: normalizeAdminPersonaCustomerPressure(raw.customer_pressure),
    };
}

function normalizeAdminPersona(input: unknown): AdminPersona {
    const raw = toRecord(input);
    return {
        ...raw,
        id: toStringValue(raw.id),
        name: toStringValue(raw.name),
        description: toStringValue(raw.description),
        category: toStringValue(raw.category),
        difficulty: toStringValue(raw.difficulty),
        status: toStringValue(raw.status),
        system_prompt: toStringValue(raw.system_prompt),
        governance_summary: normalizeAssetGovernanceSummary(raw.governance_summary),
        created_at: toStringValue(raw.created_at) || undefined,
        updated_at: toStringValue(raw.updated_at) || undefined,
        knowledge_bases: Array.isArray(raw.knowledge_bases)
            ? raw.knowledge_bases.map(normalizeAdminKnowledgeBase)
            : undefined,
        knowledge_base_ids: normalizeStringList(raw.knowledge_base_ids),
        persona_policy: normalizeAdminPersonaPolicy(raw.persona_policy),
        tts_config: toRecord(raw.tts_config) as AdminPersona["tts_config"],
    };
}

const ADMIN_ANALYTICS_SCORE_BASIS = "session_evidence_projection_evaluable_only";

function normalizeAnalyticsIssueFamilyBucket(input: unknown) {
    const raw = toRecord(input);
    return {
        issue_type: toStringValue(raw.issue_type),
        issue_text: toStringValue(raw.issue_text),
        count: toNumberValue(raw.count, 0),
    };
}

function normalizeAnalyticsNotEvaluableReasonBucket(input: unknown) {
    const raw = toRecord(input);
    return {
        reason: toStringValue(raw.reason),
        count: toNumberValue(raw.count, 0),
    };
}

function normalizeAnalyticsRepeatedGoalBucket(input: unknown) {
    const raw = toRecord(input);
    return {
        goal_type: toStringValue(raw.goal_type),
        goal_text: toStringValue(raw.goal_text),
        count: toNumberValue(raw.count, 0),
    };
}

function normalizeAnalyticsOverview(input: unknown): AnalyticsOverview {
    const raw = toRecord(input);
    const growth = toRecord(raw.growth);
    return {
        total_users: toNumberValue(raw.total_users, 0),
        active_users_today: toNumberValue(raw.active_users_today, 0),
        active_users_week: toNumberValue(raw.active_users_week, 0),
        total_sessions: toNumberValue(raw.total_sessions, 0),
        sessions_today: toNumberValue(raw.sessions_today, 0),
        completed_sessions: toNumberValue(raw.completed_sessions, 0),
        completion_rate: toNumberValue(raw.completion_rate, 0),
        average_score: toNumberValue(raw.average_score, 0),
        average_duration_minutes: toNumberValue(raw.average_duration_minutes, 0),
        growth: {
            users_rate: toNumberValue(growth.users_rate, 0),
            sessions_rate: toNumberValue(growth.sessions_rate, 0),
            score_rate: toNumberValue(growth.score_rate, 0),
        },
        evaluable_sessions: toNumberValue(raw.evaluable_sessions, 0),
        not_evaluable_sessions: toNumberValue(raw.not_evaluable_sessions, 0),
        score_basis: toStringValue(raw.score_basis, ADMIN_ANALYTICS_SCORE_BASIS),
        top_issue_families: Array.isArray(raw.top_issue_families)
            ? raw.top_issue_families.map(normalizeAnalyticsIssueFamilyBucket)
            : [],
        not_evaluable_reasons: Array.isArray(raw.not_evaluable_reasons)
            ? raw.not_evaluable_reasons.map(normalizeAnalyticsNotEvaluableReasonBucket)
            : [],
    };
}

function normalizeAnalyticsProjectionSummary(input: unknown) {
    const raw = toRecord(input);
    return {
        average_score: toNumberValue(raw.average_score, 0),
        best_score: toNumberValue(raw.best_score, 0),
        evaluable_sessions: toNumberValue(raw.evaluable_sessions, 0),
        not_evaluable_sessions: toNumberValue(raw.not_evaluable_sessions, 0),
        score_basis: toStringValue(raw.score_basis, ADMIN_ANALYTICS_SCORE_BASIS),
        issue_family_distribution: Array.isArray(raw.issue_family_distribution)
            ? raw.issue_family_distribution.map(normalizeAnalyticsIssueFamilyBucket)
            : [],
        not_evaluable_reasons: Array.isArray(raw.not_evaluable_reasons)
            ? raw.not_evaluable_reasons.map(normalizeAnalyticsNotEvaluableReasonBucket)
            : [],
        repeated_main_issues: Array.isArray(raw.repeated_main_issues)
            ? raw.repeated_main_issues.map((item) => {
                const bucket = toRecord(item);
                return {
                    issue_type: toStringValue(bucket.issue_type),
                    issue_text: toStringValue(bucket.issue_text),
                    count: toNumberValue(bucket.count, 0),
                };
            })
            : [],
        repeated_next_goals: Array.isArray(raw.repeated_next_goals)
            ? raw.repeated_next_goals.map(normalizeAnalyticsRepeatedGoalBucket)
            : [],
    };
}

function normalizeAnalyticsTrends(input: unknown): AnalyticsTrends {
    const raw = toRecord(input);
    const scoreDistribution = toRecord(raw.score_distribution);

    return {
        trend_data: Array.isArray(raw.trend_data)
            ? raw.trend_data.map((item) => {
                const point = toRecord(item);
                return {
                    ...point,
                    date: toStringValue(point.date),
                    sessions_count: toNumberValue(point.sessions_count, 0),
                    average_score: toNumberValue(point.average_score, 0),
                    active_users: toNumberValue(point.active_users, 0),
                    evaluable_session_count: toNumberValue(point.evaluable_session_count, 0),
                    not_evaluable_session_count: toNumberValue(point.not_evaluable_session_count, 0),
                    logic_score: toNumberValue(point.logic_score, 0),
                    accuracy_score: toNumberValue(point.accuracy_score, 0),
                    completeness_score: toNumberValue(point.completeness_score, 0),
                };
            })
            : [],
        score_distribution: {
            excellent: toNumberValue(scoreDistribution.excellent, 0),
            good: toNumberValue(scoreDistribution.good, 0),
            fair: toNumberValue(scoreDistribution.fair, 0),
            poor: toNumberValue(scoreDistribution.poor, 0),
        },
        projection_summary: Object.keys(toRecord(raw.projection_summary)).length > 0
            ? normalizeAnalyticsProjectionSummary(raw.projection_summary)
            : undefined,
    };
}

function normalizeAnalyticsAgents(input: unknown): AnalyticsAgents {
    const raw = toRecord(input);
    const normalizeDistribution = (distribution: unknown): Record<string, number> => {
        const normalized: Record<string, number> = {};
        Object.entries(toRecord(distribution)).forEach(([key, value]) => {
            normalized[key] = toNumberValue(value, 0);
        });
        return normalized;
    };

    return {
        agent_stats: Array.isArray(raw.agent_stats)
            ? raw.agent_stats.map((item) => {
                const entry = toRecord(item);
                return {
                    agent_id: toStringValue(entry.agent_id),
                    agent_name: toStringValue(entry.agent_name),
                    category: toStringValue(entry.category),
                    usage_count: toNumberValue(entry.usage_count, 0),
                    average_score: toNumberValue(entry.average_score, 0),
                    completion_rate: toNumberValue(entry.completion_rate, 0),
                    evaluable_sessions: toNumberValue(entry.evaluable_sessions, 0),
                    not_evaluable_sessions: toNumberValue(entry.not_evaluable_sessions, 0),
                    score_basis: toStringValue(entry.score_basis, ADMIN_ANALYTICS_SCORE_BASIS),
                };
            })
            : [],
        persona_stats: Array.isArray(raw.persona_stats)
            ? raw.persona_stats.map((item) => {
                const entry = toRecord(item);
                return {
                    persona_id: toStringValue(entry.persona_id),
                    persona_name: toStringValue(entry.persona_name),
                    difficulty: toStringValue(entry.difficulty),
                    usage_count: toNumberValue(entry.usage_count, 0),
                    average_score: toNumberValue(entry.average_score, 0),
                    evaluable_sessions: toNumberValue(entry.evaluable_sessions, 0),
                    not_evaluable_sessions: toNumberValue(entry.not_evaluable_sessions, 0),
                    score_basis: toStringValue(entry.score_basis, ADMIN_ANALYTICS_SCORE_BASIS),
                };
            })
            : [],
        scenario_distribution: normalizeDistribution(raw.scenario_distribution),
    };
}

function normalizeAnalyticsLeaderboard(input: unknown): AnalyticsLeaderboard {
    const raw = toRecord(input);
    return {
        leaderboard: Array.isArray(raw.leaderboard)
            ? raw.leaderboard.map((item) => {
                const entry = toRecord(item);
                const username = toStringValue(entry.username, toStringValue(entry.user_name, "-"));
                return {
                    rank: toNumberValue(entry.rank, 0),
                    user_id: toStringValue(entry.user_id),
                    username: username || "-",
                    department: typeof entry.department === "string" ? entry.department : null,
                    total_sessions: toNumberValue(entry.total_sessions, 0),
                    average_score: toNumberValue(entry.average_score, 0),
                    best_score: toNumberValue(entry.best_score, 0),
                    total_duration_minutes: toNumberValue(entry.total_duration_minutes, 0),
                    evaluable_sessions: toNumberValue(entry.evaluable_sessions, 0),
                    not_evaluable_sessions: toNumberValue(entry.not_evaluable_sessions, 0),
                    primary_issue_type: toStringValue(entry.primary_issue_type) || null,
                    primary_next_goal_type: toStringValue(entry.primary_next_goal_type) || null,
                    score_basis: toStringValue(entry.score_basis, ADMIN_ANALYTICS_SCORE_BASIS),
                };
            })
            : [],
    };
}

function normalizeManagerLiteLists(input: unknown): ManagerLiteListsResponse {
    const raw = toRecord(input);
    return {
        not_passed: Array.isArray(raw.not_passed)
            ? raw.not_passed.map((item) => {
                const entry = toRecord(item);
                return {
                    user_id: toStringValue(entry.user_id),
                    user_name: toStringValue(entry.user_name),
                    department: typeof entry.department === "string" ? entry.department : null,
                    overall_result: toStringValue(entry.overall_result, "fail"),
                    session_id: toStringValue(entry.session_id),
                    session_start_time: toStringValue(entry.session_start_time),
                    issue_family: toStringValue(entry.issue_family) || null,
                };
            })
            : [],
        inactive_streak: Array.isArray(raw.inactive_streak)
            ? raw.inactive_streak.map((item) => {
                const entry = toRecord(item);
                return {
                    user_id: toStringValue(entry.user_id),
                    user_name: toStringValue(entry.user_name),
                    department: typeof entry.department === "string" ? entry.department : null,
                    last_session_at: toStringValue(entry.last_session_at),
                    inactive_days: toNumberValue(entry.inactive_days, 0),
                };
            })
            : [],
        improving: Array.isArray(raw.improving)
            ? raw.improving.map((item) => {
                const entry = toRecord(item);
                return {
                    user_id: toStringValue(entry.user_id),
                    user_name: toStringValue(entry.user_name),
                    department: typeof entry.department === "string" ? entry.department : null,
                    pass_gain: toNumberValue(entry.pass_gain, 0),
                    baseline_pass_rate: toNumberValue(entry.baseline_pass_rate, 0),
                    current_pass_rate: toNumberValue(entry.current_pass_rate, 0),
                };
            })
            : [],
    };
}

function normalizeAdminOperatingPack(input: unknown): AdminOperatingPackResponse {
    const raw = toRecord(input);
    const weeklySummary = toRecord(raw.weekly_summary);
    const normalizeIssueBucket = (value: unknown) => {
        const entry = toRecord(value);
        return {
            issue_family: toStringValue(entry.issue_family),
            issue_type: toStringValue(entry.issue_type, toStringValue(entry.issue_family)),
            issue_text: toStringValue(entry.issue_text) || null,
            count: toNumberValue(entry.count, 0),
            user_count: toNumberValue(entry.user_count, 0),
            department_count: entry.department_count === undefined
                ? undefined
                : toNumberValue(entry.department_count, 0),
        };
    };
    const normalizeReasonBucket = (value: unknown) => {
        const entry = toRecord(value);
        return {
            reason: toStringValue(entry.reason),
            count: toNumberValue(entry.count, 0),
        };
    };
    const normalizeDegradationBreakdown = (value: unknown) => {
        const entry = toRecord(value);
        return {
            not_evaluable_reasons: Array.isArray(entry.not_evaluable_reasons)
                ? entry.not_evaluable_reasons.map(normalizeReasonBucket)
                : [],
            degraded_reasons: Array.isArray(entry.degraded_reasons)
                ? entry.degraded_reasons.map(normalizeReasonBucket)
                : [],
        };
    };

    return {
        score_basis: toStringValue(raw.score_basis, ADMIN_ANALYTICS_SCORE_BASIS),
        weekly_summary: {
            window_days: weeklySummary.window_days === undefined
                ? undefined
                : toNumberValue(weeklySummary.window_days, 0),
            window_start: toStringValue(weeklySummary.window_start) || null,
            window_end: toStringValue(weeklySummary.window_end) || null,
            completed_sessions: toNumberValue(weeklySummary.completed_sessions, 0),
            evaluable_sessions: toNumberValue(weeklySummary.evaluable_sessions, 0),
            not_evaluable_sessions: toNumberValue(weeklySummary.not_evaluable_sessions, 0),
            degraded_sessions: toNumberValue(weeklySummary.degraded_sessions, 0),
            active_departments: toNumberValue(weeklySummary.active_departments, 0),
            at_risk_users: toNumberValue(weeklySummary.at_risk_users, 0),
            improving_users: toNumberValue(weeklySummary.improving_users, 0),
            top_issue_family: Object.keys(toRecord(weeklySummary.top_issue_family)).length > 0
                ? normalizeIssueBucket(weeklySummary.top_issue_family)
                : null,
            top_blocker_family: Object.keys(toRecord(weeklySummary.top_blocker_family)).length > 0
                ? normalizeIssueBucket(weeklySummary.top_blocker_family)
                : null,
            top_not_evaluable_reason: Object.keys(toRecord(weeklySummary.top_not_evaluable_reason)).length > 0
                ? normalizeReasonBucket(weeklySummary.top_not_evaluable_reason)
                : null,
            top_degraded_reason: Object.keys(toRecord(weeklySummary.top_degraded_reason)).length > 0
                ? normalizeReasonBucket(weeklySummary.top_degraded_reason)
                : null,
        },
        cohort_issue_buckets: Array.isArray(raw.cohort_issue_buckets)
            ? raw.cohort_issue_buckets.map(normalizeIssueBucket)
            : [],
        department_issue_buckets: Array.isArray(raw.department_issue_buckets)
            ? raw.department_issue_buckets.map((item) => {
                const entry = toRecord(item);
                return {
                    department: toStringValue(entry.department, "未分配部门"),
                    session_count: toNumberValue(entry.session_count, 0),
                    evaluable_sessions: toNumberValue(entry.evaluable_sessions, 0),
                    not_evaluable_sessions: toNumberValue(entry.not_evaluable_sessions, 0),
                    issue_buckets: Array.isArray(entry.issue_buckets)
                        ? entry.issue_buckets.map(normalizeIssueBucket)
                        : [],
                    degradation_breakdown: normalizeDegradationBreakdown(entry.degradation_breakdown),
                };
            })
            : [],
        repeated_blocker_families: Array.isArray(raw.repeated_blocker_families)
            ? raw.repeated_blocker_families.map(normalizeIssueBucket)
            : [],
        degradation_breakdown: normalizeDegradationBreakdown(raw.degradation_breakdown),
        manager_lists: normalizeManagerLiteLists(raw.manager_lists),
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

type AdminTTSPreviewRequest = {
    text: string;
    voice?: string;
    rate?: string;
    volume?: string;
    pitch?: string;
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

function readBrowserCookie(name: string): string | null {
    if (typeof document === "undefined") {
        return null;
    }

    const encodedName = `${encodeURIComponent(name)}=`;
    const cookieEntry = document.cookie
        .split(";")
        .map((item) => item.trim())
        .find((item) => item.startsWith(encodedName));

    if (!cookieEntry) {
        return null;
    }

    const cookieValue = cookieEntry.slice(encodedName.length);
    if (!cookieValue) {
        return null;
    }

    try {
        return decodeURIComponent(cookieValue);
    } catch {
        return cookieValue;
    }
}

function isUnsafeHttpMethod(method: string | undefined): boolean {
    const normalizedMethod = (method || "GET").trim().toUpperCase();
    return !["GET", "HEAD", "OPTIONS", "TRACE"].includes(normalizedMethod);
}

function attachCsrfHeader(
    headers: Headers,
    options: {
        method: string | undefined;
        credentials: RequestCredentials | undefined;
    },
): Headers {
    const { method, credentials } = options;
    if (credentials !== "include" || !isUnsafeHttpMethod(method) || headers.has(CSRF_HEADER_NAME)) {
        return headers;
    }

    const csrfToken = readBrowserCookie(CSRF_COOKIE_NAME);
    if (csrfToken) {
        headers.set(CSRF_HEADER_NAME, csrfToken);
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
        const resolvedCredentials = requestOptions.credentials || "include";
        const headers = attachCsrfHeader(
            createHeaders(requestOptions.headers),
            {
                method: requestOptions.method,
                credentials: resolvedCredentials,
            },
        );
        const response = await fetchWithLoopbackRetry(url, {
            ...requestOptions,
            signal,
            credentials: resolvedCredentials,
            headers,
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
        const resolvedCredentials = "include";
        const headers = attachCsrfHeader(
            createHeaders(undefined, false),
            {
                method: "POST",
                credentials: resolvedCredentials,
            },
        );
        const response = await fetchWithLoopbackRetry(url, {
            method: "POST",
            body: formData,
            signal: signal || controller.signal,
            credentials: resolvedCredentials,
            headers,
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

async function apiFetchBlob(
    endpoint: string,
    options: ApiFetchOptions = {},
): Promise<Blob> {
    const url = `${resolveApiBaseUrl()}${endpoint}`;
    const requestId = `blob_${++requestCounter}`;
    const { skipSessionExpiredHandling = false, ...requestOptions } = options;
    const controller = new AbortController();
    const externalSignal = requestOptions.signal;
    const signal = externalSignal || controller.signal;

    if (externalSignal) {
        externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }

    activeRequests.set(requestId, controller);

    try {
        const resolvedCredentials = requestOptions.credentials || "include";
        const headers = attachCsrfHeader(
            createHeaders(requestOptions.headers, false),
            {
                method: requestOptions.method,
                credentials: resolvedCredentials,
            },
        );
        const response = await fetchWithLoopbackRetry(url, {
            ...requestOptions,
            signal,
            credentials: resolvedCredentials,
            headers,
        });

        if (!response.ok) {
            const responseJson = await response.json().catch(() => ({}));
            if (response.status === 401 && !skipSessionExpiredHandling) {
                triggerSessionExpiredOnce();
            }
            throw new ApiRequestError(normalizeApiErrorPayload(response.status, responseJson));
        }

        return response.blob();
    } catch (error) {
        if (error instanceof ApiRequestError) {
            throw error;
        }

        if (error instanceof Error && error.name === "AbortError") {
            throw error;
        }

        throw new ApiRequestError({
            status: 0,
            errorCode: "[NETWORK_ERROR]",
            message: error instanceof Error && error.message.trim()
                ? error.message
                : "请求失败，请稍后重试。",
        });
    } finally {
        activeRequests.delete(requestId);
    }
}

/**
 * M019/S03/T01 domain client seam inventory
 *
 * Cross-cutting seam that must stay centralized even after client.ts is split:
 * - auth/session expiry handling: authHandler + triggerSessionExpiredOnce
 * - request transport: apiFetch / apiUpload / fetchWithLoopbackRetry
 * - trace propagation: createHeaders(buildTraceHeaders(...))
 * - error normalization: normalizeApiErrorPayload -> ApiRequestError -> getApiErrorMessage
 *
 * Domain surfaces currently exposed through the outward `api` façade:
 * - extracted in `client-domains.ts`: auth, practice, sessions, agents, presentations,
 *   and admin report helpers consumed through `api.admin`
 * - currently still inline in `client.ts`: user, dashboard, analyticsOpen, supportRuntime,
 *   training, scenarios, analytics, admin, adminTools, adminPresentations, internal
 *
 * High-fan-out consumers confirmed by repo inventory:
 * - learner/auth/dashboard/practice/report/replay/profile pages import the façade directly
 * - admin analytics/users/personas/knowledge/settings/prompts plus debug panels depend on `api.admin*`
 * - shell/auth guards consume `isAuthenticationError` / `getApiErrorMessage`, not raw payload parsing
 *
 * Split rule for follow-up tasks: keep page/component imports pointed at this façade and let
 * domain modules live behind it, otherwise pages will start bypassing auth/error/trace seams.
 */
const authDomain = createAuthDomain({ request: apiFetch });
const practiceDomain = createPracticeDomain({ request: apiFetch });
const sessionsDomain = createSessionsDomain({
    request: apiFetch,
    resolveApiBaseUrl,
    createHeaders,
    fetchWithLoopbackRetry,
    createApiError: (status, payload) => new ApiRequestError(normalizeApiErrorPayload(status, payload)),
    createNetworkError: (error) => {
        if (error instanceof ApiRequestError) {
            return error;
        }
        return new ApiRequestError({
            status: 0,
            errorCode: "[NETWORK_ERROR]",
            message: error instanceof Error && error.message.trim()
                ? error.message
                : "请求失败，请稍后重试。",
        });
    },
});
const agentsDomain = createAgentsDomain({ request: apiFetch });
const presentationsDomain = createPresentationsDomain({
    request: apiFetch,
    upload: apiUpload,
    resolveApiBaseUrl,
    createHeaders,
    fetchWithLoopbackRetry,
    normalizePresentationListItem,
    normalizePresentationDetailItem,
    normalizePresentationPage,
    normalizePresentationTalkingPoint,
    normalizePresentationForbiddenWord,
});
const adminReportDomain = createAdminReportDomain({ request: apiFetch });

export interface AudioSegmentUploadUrlRequest {
    segment_sequence: number;
    content_type: string;
}

export interface AudioSegmentUploadUrlResponse {
    url: string;
    object_key: string;
    expires_at?: string;
}

export interface AudioSegmentRegisterRequest {
    segment_sequence: number;
    object_key: string;
    size_bytes: number;
    duration_ms?: number;
}

export type AudioSegmentFailureToken =
    | "signing_failed"
    | "oss_put_failed"
    | "register_failed"
    | "network_error"
    | "unknown";

export interface AudioSegmentFailureRequest {
    segment_sequence: number;
    error_token: AudioSegmentFailureToken;
}

export const api = {
    // Authentication
    auth: authDomain,

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

        updateProfile: async (data: Partial<User> & { display_name?: string; voice_speed_preference?: number }) => {
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

        getTrainingPreferences: async () => {
            const result = await apiFetch<{
                voice_mode?: "legacy" | "stepfun_realtime" | null;
                agent_id?: string | null;
                persona_id?: string | null;
                presentation_id?: string | null;
                updated_at?: string | null;
            }>("/users/me/training-preferences");
            return {
                voiceMode: result.voice_mode ?? undefined,
                agentId: result.agent_id ?? null,
                personaId: result.persona_id ?? null,
                presentationId: result.presentation_id ?? null,
                updatedAt: result.updated_at ?? null,
            };
        },

        updateTrainingPreferences: async (data: {
            voiceMode?: "legacy" | "stepfun_realtime" | null;
            agentId?: string | null;
            personaId?: string | null;
            presentationId?: string | null;
            updatedAt?: string | null;
        }) => {
            const result = await apiFetch<{
                voice_mode?: "legacy" | "stepfun_realtime" | null;
                agent_id?: string | null;
                persona_id?: string | null;
                presentation_id?: string | null;
                updated_at?: string | null;
            }>("/users/me/training-preferences", {
                method: "PATCH",
                body: JSON.stringify({
                    voice_mode: data.voiceMode ?? null,
                    agent_id: data.agentId ?? null,
                    persona_id: data.personaId ?? null,
                    presentation_id: data.presentationId ?? null,
                    updated_at: data.updatedAt ?? null,
                }),
            });
            return {
                voiceMode: result.voice_mode ?? undefined,
                agentId: result.agent_id ?? null,
                personaId: result.persona_id ?? null,
                presentationId: result.presentation_id ?? null,
                updatedAt: result.updated_at ?? null,
            };
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

            return apiFetch<HistoryListResponse>(`/users/me/history?${queryParams}`);
        },

        getOpenIntervention: async () => {
            return apiFetch<LearnerOpenIntervention | null>("/users/me/interventions/open");
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

        getGrowth: async () => {
            return apiFetch<GrowthDashboardResponse>("/growth/dashboard");
        },

        getAdaptiveDifficultyDryRun: async (limit = 10) => {
            return apiFetch<AdaptiveDifficultyDryRunResponse>(`/growth/adaptive-difficulty/dry-run?limit=${limit}`);
        },

        markNotificationRead: async (notificationId: string) => {
            return apiFetch<GrowthDashboardResponse["notifications"]["items"][number]>(
                `/growth/notifications/${notificationId}/read`,
                { method: "POST" },
            );
        },

        getHistory: async (limit = 5, scenarioType?: "sales" | "presentation") => {
            const queryParams = new URLSearchParams({ page_size: String(limit) });
            if (scenarioType) queryParams.set("scenario_type", scenarioType);

            const result = await apiFetch<{ items: HistoryApiItem[]; total: number }>(`/practice/history?${queryParams}`);

            return (result.items || []).map<SessionItem>((item, index) => ({
                id: item.session_id || item.id || `session-${index}`,
                session_id:
                    typeof item.session_id === "string"
                        ? item.session_id
                        : typeof item.id === "string"
                            ? item.id
                            : undefined,
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
                evaluable:
                    typeof item.evaluable === "boolean"
                        ? item.evaluable
                        : item.effectiveness_snapshot && typeof item.effectiveness_snapshot === "object" && typeof item.effectiveness_snapshot.evaluable === "boolean"
                            ? item.effectiveness_snapshot.evaluable
                            : null,
                not_evaluable_reason:
                    typeof item.not_evaluable_reason === "string"
                        ? item.not_evaluable_reason
                        : item.effectiveness_snapshot && typeof item.effectiveness_snapshot === "object" && typeof item.effectiveness_snapshot.not_evaluable_reason === "string"
                            ? item.effectiveness_snapshot.not_evaluable_reason
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
            return apiFetch<HistoryStatistics>("/practice/history/statistics");
        },

        getHistoryTrends: async (days = 30) => {
            const result = await apiFetch<{ trends?: HistoryTrendPoint[] }>(`/practice/history/trends?days=${days}`);
            return Array.isArray(result?.trends) ? result.trends : [];
        },

        getPublicLeaderboard: async (params?: {
            scenario_type?: string;
            time_period?: string;
            leaderboard_mode?: "score" | "improvement" | "issue_type" | string;
            issue_type?: string;
            include_me?: boolean;
            limit?: number;
        }) => {
            const queryParams = new URLSearchParams();
            if (params?.scenario_type) queryParams.set("scenario_type", params.scenario_type);
            if (params?.time_period) queryParams.set("time_period", params.time_period);
            if (params?.leaderboard_mode) queryParams.set("leaderboard_mode", params.leaderboard_mode);
            if (params?.issue_type) queryParams.set("issue_type", params.issue_type);
            if (params?.include_me) queryParams.set("include_me", "true");
            if (params?.limit) queryParams.set("limit", String(params.limit));
            return apiFetch<{
                scenario_type?: string | null;
                time_period: string;
                leaderboard_mode?: string;
                score_basis?: string;
                evaluable_sessions?: number;
                not_evaluable_sessions?: number;
                eligibility?: {
                    score_basis?: string;
                    min_evaluable_sessions?: number;
                    explanation?: string;
                };
                issue_type?: string | null;
                issue_type_buckets?: Array<{
                    issue_type: string;
                    count?: number;
                    evaluable_sessions?: number;
                }>;
                total_users: number;
                entries: Array<{
                    rank: number;
                    user_id: string;
                    username: string;
                    total_sessions: number;
                    average_score: number;
                    best_score: number;
                    improvement_score?: number;
                    first_score?: number;
                    latest_score?: number;
                    sample_size?: number;
                    issue_type?: string | null;
                    score_basis?: string;
                    evaluable_sessions?: number;
                    not_evaluable_sessions?: number;
                }>;
                my_rank?: {
                    user_id: string;
                    rank: number | null;
                    total_sessions: number;
                    average_score: number;
                    improvement_score?: number;
                    first_score?: number;
                    latest_score?: number;
                    sample_size?: number;
                    issue_type?: string | null;
                    score_basis?: string;
                    evaluable_sessions?: number;
                    not_evaluable_sessions?: number;
                    total_users?: number;
                    percentile?: number;
                    time_period?: string;
                    scenario_type?: string | null;
                    message?: string;
                };
            }>(`/analytics/leaderboard?${queryParams}`);
        },

        getMyRank: async (
            params?: string | {
                scenario_type?: string;
                time_period?: string;
                leaderboard_mode?: "score" | "improvement" | "issue_type" | string;
                issue_type?: string;
            }
        ) => {
            const scenarioType =
                typeof params === "string" ? params : params?.scenario_type;
            const timePeriod =
                typeof params === "string" ? undefined : params?.time_period;
            const leaderboardMode =
                typeof params === "string" ? undefined : params?.leaderboard_mode;
            const issueType =
                typeof params === "string" ? undefined : params?.issue_type;

            const queryParams = new URLSearchParams();
            if (scenarioType) {
                queryParams.set("scenario_type", scenarioType);
            }
            if (timePeriod) {
                queryParams.set("time_period", timePeriod);
            }
            if (leaderboardMode) {
                queryParams.set("leaderboard_mode", leaderboardMode);
            }
            if (issueType) {
                queryParams.set("issue_type", issueType);
            }

            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<{
                user_id: string;
                rank: number | null;
                total_sessions: number;
                average_score: number;
                improvement_score?: number;
                first_score?: number;
                latest_score?: number;
                sample_size?: number;
                issue_type?: string | null;
                score_basis?: string;
                evaluable_sessions?: number;
                not_evaluable_sessions?: number;
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

        getFaults: async (params?: { limit?: number; severity?: "blocking" | "warning" }) => {
            const searchParams = new URLSearchParams();
            if (typeof params?.limit === "number") {
                searchParams.set("limit", String(params.limit));
            }
            if (params?.severity) {
                searchParams.set("severity", params.severity);
            }
            const result = await apiFetch<SupportRuntimeFaultsResponse>(`/support/runtime/faults?${searchParams}`);
            return normalizeSupportRuntimeFaultsResponse(result);
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

        getActiveSalesCombinations: async () => {
            return apiFetch<SalesCombinationRuleSet>("/business-rules/sales-combinations/active");
        },

        createSession: async (data: {
            scenario_type: "sales" | "presentation";
            presentation_id?: string;
            agent_id?: string;
            persona_id?: string;
            voice_mode?: "legacy" | "stepfun_realtime";
            runtime_profile_id?: string;
            focus_intent?: RetryFocusIntent;
        }) => {
            return apiFetch<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
    },

    // Practice / Sessions
    practice: practiceDomain,

    // Browser-direct audio segment upload metadata.
    // Keep these calls on apiFetch so base URL resolution, cookies, CSRF,
    // trace headers, session-expiry handling, and error normalization stay unified.
    audioSegments: {
        createUploadUrl: async (
            sessionId: string,
            payload: AudioSegmentUploadUrlRequest,
        ) => {
            return apiFetch<AudioSegmentUploadUrlResponse>(
                `/practice/sessions/${sessionId}/audio-upload-urls`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },
        register: async (
            sessionId: string,
            payload: AudioSegmentRegisterRequest,
        ) => {
            return apiFetch<Record<string, unknown>>(
                `/practice/sessions/${sessionId}/audio-segments`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },
        registerFailure: async (
            sessionId: string,
            payload: AudioSegmentFailureRequest,
        ) => {
            return apiFetch<Record<string, unknown>>(
                `/practice/sessions/${sessionId}/audio-segments/failure`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },
    },

    // Sessions
    sessions: sessionsDomain,

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
    agents: agentsDomain,

    // Admin - Analytics
    analytics: {
        getOverview: async (params?: { time_range?: string; scenario_type?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);

            const payload = await apiFetch<AnalyticsOverview>(`/admin/analytics/overview?${searchParams}`);
            return normalizeAnalyticsOverview(payload);
        },

        getTrends: async (params?: { time_range?: string; granularity?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.granularity) searchParams.set("granularity", params.granularity);

            const payload = await apiFetch<AnalyticsTrends>(`/admin/analytics/trends?${searchParams}`);
            return normalizeAnalyticsTrends(payload);
        },

        getAgents: async (params?: { time_range?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.limit) searchParams.set("limit", params.limit.toString());

            const payload = await apiFetch<AnalyticsAgents>(`/admin/analytics/agents?${searchParams}`);
            return normalizeAnalyticsAgents(payload);
        },

        getLeaderboard: async (params?: { time_range?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.limit) searchParams.set("limit", params.limit.toString());

            const payload = await apiFetch<AnalyticsLeaderboard>(`/admin/analytics/leaderboard?${searchParams}`);
            return normalizeAnalyticsLeaderboard(payload);
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
            const payload = await apiFetch<ManagerLiteListsResponse>(`/admin/interventions/lists?${searchParams}`);
            return normalizeManagerLiteLists(payload);
        },

        getOperatingPack: async (params?: { time_range?: string; scenario_type?: string; limit?: number; inactive_days?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.time_range) searchParams.set("time_range", params.time_range);
            if (params?.scenario_type) searchParams.set("scenario_type", params.scenario_type);
            if (typeof params?.limit === "number") searchParams.set("limit", String(params.limit));
            if (typeof params?.inactive_days === "number") {
                searchParams.set("inactive_days", String(params.inactive_days));
            }
            const payload = await apiFetch<AdminOperatingPackResponse>(`/admin/analytics/operating-pack?${searchParams}`);
            return normalizeAdminOperatingPack(payload);
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
        ...adminReportDomain,
        // Business Rule Governance
        getSalesCombinationRuleSets: async () => {
            return apiFetch<SalesCombinationRuleSetListResponse>("/admin/business-rules/sales-combinations");
        },

        validateSalesCombinationRuleSet: async (ruleset: SalesCombinationRuleSet) => {
            return apiFetch<SalesCombinationRuleValidationResult>("/admin/business-rules/sales-combinations/validate", {
                method: "POST",
                body: JSON.stringify(ruleset),
            });
        },

        previewSalesCombinationRuleSet: async (ruleset: SalesCombinationRuleSet) => {
            return apiFetch<SalesCombinationPreviewResponse>("/admin/business-rules/sales-combinations/preview", {
                method: "POST",
                body: JSON.stringify(ruleset),
            });
        },

        publishSalesCombinationRuleSet: async (rulesetId: string, reason: string) => {
            return apiFetch<SalesCombinationRuleMutationResponse>(
                `/admin/business-rules/sales-combinations/${encodeURIComponent(rulesetId)}/publish`,
                {
                    method: "POST",
                    body: JSON.stringify({ reason }),
                },
            );
        },

        rollbackSalesCombinationRuleSet: async (rulesetId: string, reason: string) => {
            return apiFetch<SalesCombinationRuleMutationResponse>(
                `/admin/business-rules/sales-combinations/${encodeURIComponent(rulesetId)}/rollback`,
                {
                    method: "POST",
                    body: JSON.stringify({ reason }),
                },
            );
        },

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

        listManagerInterventions: async (userId: string, params?: { limit?: number }) => {
            const searchParams = new URLSearchParams();
            searchParams.set("user_id", normalizeRequiredId(userId, { fieldName: "user_id" }));
            if (typeof params?.limit === "number") {
                searchParams.set("limit", String(params.limit));
            }
            return apiFetch<ManagerInterventionListResponse>(`/admin/interventions?${searchParams}`);
        },

        createManagerIntervention: async (data: ManagerInterventionCreateRequest) => {
            return apiFetch<ManagerInterventionItem>("/admin/interventions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        remindManagerIntervention: async (data: ManagerInterventionRemindRequest) => {
            return apiFetch<ManagerInterventionRemindResponse>("/admin/interventions/remind", {
                method: "POST",
                body: JSON.stringify(data),
            });
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

        getAgentIndustryPackContract: async () => {
            return apiFetch<AdminAgentIndustryPackContract>("/admin/agents/industry-pack-contract");
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
                items: (result.personas || result.items || []).map(normalizeAdminPersona),
                total: result.total || 0
            };
        },

        getPersonaPolicyHealth: async (sampleLimit = 50) => {
            const searchParams = new URLSearchParams();
            searchParams.set("sample_limit", String(sampleLimit));
            const result = await apiFetch<AdminPersonaPolicyHealthReport>(`/admin/personas/policy-health?${searchParams}`);
            return {
                generated_at: toStringValue(result?.generated_at),
                summary: {
                    total: toNumberValue(result?.summary?.total, 0),
                    healthy: toNumberValue(result?.summary?.healthy, 0),
                    with_issues: toNumberValue(result?.summary?.with_issues, 0),
                },
                issue_type_counts:
                    result?.issue_type_counts && typeof result.issue_type_counts === "object"
                        ? result.issue_type_counts
                        : {},
                sample_issues: Array.isArray(result?.sample_issues) ? result.sample_issues : [],
            } satisfies AdminPersonaPolicyHealthReport;
        },

        getPersona: async (id: string) => {
            const result = await apiFetch<AdminPersona>(`/admin/personas/${id}`);
            return normalizeAdminPersona(result);
        },

        getPersonaIndustryPackContract: async () => {
            return apiFetch<AdminPersonaIndustryPackContract>("/admin/personas/industry-pack-contract");
        },

        createPersona: async (data: Partial<AdminPersona>) => {
            const result = await apiFetch<AdminPersona>("/admin/personas", {
                method: "POST",
                body: JSON.stringify(data),
            });
            return normalizeAdminPersona(result);
        },

        updatePersona: async (id: string, data: Partial<AdminPersona>) => {
            const result = await apiFetch<AdminPersona>(`/admin/personas/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            return normalizeAdminPersona(result);
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

            const result = await apiFetch<{ knowledge_bases?: unknown[]; items?: unknown[]; total?: unknown }>(`/admin/knowledge?${searchParams}`);
            const items = Array.isArray(result.knowledge_bases)
                ? result.knowledge_bases
                : Array.isArray(result.items)
                    ? result.items
                    : [];

            return {
                items: items.map(normalizeAdminKnowledgeBase),
                total: toNumberValue(result.total, 0),
            };
        },

        getKnowledgeBase: async (id: string) => {
            const result = await apiFetch<unknown>(`/admin/knowledge/${id}`);
            return normalizeAdminKnowledgeBase(result);
        },

        createKnowledgeBase: async (data: { name: string; description?: string; category?: string }) => {
            const result = await apiFetch<unknown>("/admin/knowledge", {
                method: "POST",
                body: JSON.stringify(data),
            });
            return normalizeAdminKnowledgeBase(result);
        },

        updateKnowledgeBase: async (id: string, data: Partial<AdminKnowledgeBase>) => {
            const result = await apiFetch<unknown>(`/admin/knowledge/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            return normalizeAdminKnowledgeBase(result);
        },

        deleteKnowledgeBase: async (id: string) => {
            return apiFetch<void>(`/admin/knowledge/${id}`, { method: "DELETE" });
        },

        // ── RAG Profile Management ──
        listRagProfiles: async () => {
            const result = await apiFetch<{ success: boolean; data: RagProfile[] }>("/admin/rag-profiles");
            return result.data;
        },

        getRagProfile: async (id: string) => {
            const result = await apiFetch<{ success: boolean; data: RagProfile }>(`/admin/rag-profiles/${id}`);
            return result.data;
        },

        createRagProfile: async (data: CreateRagProfileRequest) => {
            const result = await apiFetch<{ success: boolean; data: RagProfile }>("/admin/rag-profiles", {
                method: "POST",
                body: JSON.stringify(data),
            });
            return result.data;
        },

        updateRagProfile: async (id: string, data: UpdateRagProfileRequest) => {
            const result = await apiFetch<{ success: boolean; data: RagProfile }>(`/admin/rag-profiles/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            return result.data;
        },

        deleteRagProfile: async (id: string) => {
            return apiFetch<{ success: boolean; message: string }>(`/admin/rag-profiles/${id}`, {
                method: "DELETE",
            });
        },

        setRagProfileDefault: async (id: string) => {
            const result = await apiFetch<{ success: boolean; data: RagProfile }>(
                `/admin/rag-profiles/${id}/set-default`,
                { method: "POST" },
            );
            return result.data;
        },

        getRagProfileKnowledgeBases: async (id: string) => {
            const result = await apiFetch<{ success: boolean; data: { id: string; name: string; category: string; document_count: number; status: string }[] }>(
                `/admin/rag-profiles/${id}/knowledge-bases`,
            );
            return result.data;
        },

        assignRagProfileToKb: async (kbId: string, ragProfileId: string | null) => {
            return apiFetch<{ success: boolean; data: { rag_profile_id: string | null } }>(
                `/admin/knowledge/${kbId}/rag-profile`,
                {
                    method: "PATCH",
                    body: JSON.stringify({ rag_profile_id: ragProfileId }),
                },
            );
        },

        getKnowledgeAnswerAdminConfig: async () => {
            return apiFetch<AdminKnowledgeAnswerAdminConfig>("/admin/knowledge-answer/config");
        },

        getKnowledgeAnswerAdminConfigOptions: async () => {
            return apiFetch<AdminKnowledgeAnswerConfigOptions>("/admin/knowledge-answer/config/options");
        },

        updateKnowledgeAnswerAdminConfig: async (data: { config_version_id: string }) => {
            return apiFetch<AdminKnowledgeAnswerAdminConfig>("/admin/knowledge-answer/config", {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        // ─── Knowledge Config Version CRUD ───

        getKnowledgeConfigVersions: async (params?: { page?: number; page_size?: number; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", String(params.page));
            if (params?.page_size) searchParams.set("page_size", String(params.page_size));
            if (params?.status) searchParams.set("status", params.status);
            const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
            return apiFetch<AdminKnowledgeConfigVersionListResponse>(`/admin/knowledge-answer/versions${query}`);
        },

        getKnowledgeConfigVersion: async (versionId: string) => {
            return apiFetch<AdminKnowledgeConfigVersionResponse>(`/admin/knowledge-answer/versions/${versionId}`);
        },

        createKnowledgeConfigVersion: async (data: { version_name: string; notes?: string; enabled?: boolean }) => {
            return apiFetch<AdminKnowledgeConfigVersionResponse>("/admin/knowledge-answer/versions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeConfigVersion: async (versionId: string, data: { version_name?: string; status?: string; notes?: string; enabled?: boolean }) => {
            return apiFetch<AdminKnowledgeConfigVersionResponse>(`/admin/knowledge-answer/versions/${versionId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeConfigVersion: async (versionId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}`, {
                method: "DELETE",
            });
        },

        // ─── Knowledge Query Profiles CRUD ───

        getKnowledgeQueryProfiles: async (versionId: string) => {
            const result = await apiFetch<{ items: AdminKnowledgeQueryProfile[]; total: number }>(`/admin/knowledge-answer/versions/${versionId}/query-profiles`);
            return result.items || [];
        },

        createKnowledgeQueryProfile: async (versionId: string, data: Partial<AdminKnowledgeQueryProfile>) => {
            return apiFetch<AdminKnowledgeQueryProfile>(`/admin/knowledge-answer/versions/${versionId}/query-profiles`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeQueryProfile: async (versionId: string, profileId: string, data: Partial<AdminKnowledgeQueryProfile>) => {
            return apiFetch<AdminKnowledgeQueryProfile>(`/admin/knowledge-answer/versions/${versionId}/query-profiles/${profileId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeQueryProfile: async (versionId: string, profileId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}/query-profiles/${profileId}`, {
                method: "DELETE",
            });
        },

        // ─── Knowledge Intent Rules CRUD ───

        getKnowledgeIntentRules: async (versionId: string) => {
            const result = await apiFetch<{ items: AdminKnowledgeIntentRule[]; total: number }>(`/admin/knowledge-answer/versions/${versionId}/intent-rules`);
            return result.items || [];
        },

        createKnowledgeIntentRule: async (versionId: string, data: Partial<AdminKnowledgeIntentRule>) => {
            return apiFetch<AdminKnowledgeIntentRule>(`/admin/knowledge-answer/versions/${versionId}/intent-rules`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeIntentRule: async (versionId: string, ruleId: string, data: Partial<AdminKnowledgeIntentRule>) => {
            return apiFetch<AdminKnowledgeIntentRule>(`/admin/knowledge-answer/versions/${versionId}/intent-rules/${ruleId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeIntentRule: async (versionId: string, ruleId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}/intent-rules/${ruleId}`, {
                method: "DELETE",
            });
        },

        // ─── Knowledge Entity Aliases CRUD ───

        getKnowledgeEntityAliases: async (versionId: string) => {
            const result = await apiFetch<{ items: AdminKnowledgeEntityAlias[]; total: number }>(`/admin/knowledge-answer/versions/${versionId}/entity-aliases`);
            return result.items || [];
        },

        createKnowledgeEntityAlias: async (versionId: string, data: Partial<AdminKnowledgeEntityAlias>) => {
            return apiFetch<AdminKnowledgeEntityAlias>(`/admin/knowledge-answer/versions/${versionId}/entity-aliases`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeEntityAlias: async (versionId: string, aliasId: string, data: Partial<AdminKnowledgeEntityAlias>) => {
            return apiFetch<AdminKnowledgeEntityAlias>(`/admin/knowledge-answer/versions/${versionId}/entity-aliases/${aliasId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeEntityAlias: async (versionId: string, aliasId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}/entity-aliases/${aliasId}`, {
                method: "DELETE",
            });
        },

        // ─── Knowledge Ranking Profiles CRUD ───

        getKnowledgeRankingProfiles: async (versionId: string) => {
            const result = await apiFetch<{ items: AdminKnowledgeRankingProfile[]; total: number }>(`/admin/knowledge-answer/versions/${versionId}/ranking-profiles`);
            return result.items || [];
        },

        createKnowledgeRankingProfile: async (versionId: string, data: Partial<AdminKnowledgeRankingProfile>) => {
            return apiFetch<AdminKnowledgeRankingProfile>(`/admin/knowledge-answer/versions/${versionId}/ranking-profiles`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeRankingProfile: async (versionId: string, profileId: string, data: Partial<AdminKnowledgeRankingProfile>) => {
            return apiFetch<AdminKnowledgeRankingProfile>(`/admin/knowledge-answer/versions/${versionId}/ranking-profiles/${profileId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeRankingProfile: async (versionId: string, profileId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}/ranking-profiles/${profileId}`, {
                method: "DELETE",
            });
        },

        // ─── Knowledge Chunking Presets CRUD ───

        getKnowledgeChunkingPresets: async (versionId: string) => {
            const result = await apiFetch<{ success: boolean; data: { items: AdminKnowledgeChunkingPreset[]; total: number } }>(`/admin/knowledge-answer/versions/${versionId}/chunking-presets`);
            return result.data?.items || [];
        },

        createKnowledgeChunkingPreset: async (versionId: string, data: CreateKnowledgeChunkingPresetRequest) => {
            const result = await apiFetch<{ success: boolean; data: AdminKnowledgeChunkingPreset }>(`/admin/knowledge-answer/versions/${versionId}/chunking-presets`, {
                method: "POST",
                body: JSON.stringify(data),
            });
            return result.data;
        },

        updateKnowledgeChunkingPreset: async (versionId: string, presetId: string, data: UpdateKnowledgeChunkingPresetRequest) => {
            const result = await apiFetch<{ success: boolean; data: AdminKnowledgeChunkingPreset }>(`/admin/knowledge-answer/versions/${versionId}/chunking-presets/${presetId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            return result.data;
        },

        deleteKnowledgeChunkingPreset: async (versionId: string, presetId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}/chunking-presets/${presetId}`, {
                method: "DELETE",
            });
        },

        setDefaultChunkingPreset: async (versionId: string, presetId: string) => {
            const result = await apiFetch<{ success: boolean; data: AdminKnowledgeChunkingPreset }>(`/admin/knowledge-answer/versions/${versionId}/chunking-presets/${presetId}/set-default`, {
                method: "POST",
            });
            return result.data;
        },

        // ─── Knowledge Answerability Profiles CRUD ───

        getKnowledgeAnswerabilityProfiles: async (versionId: string) => {
            const result = await apiFetch<{ items: AdminKnowledgeAnswerabilityProfile[]; total: number }>(`/admin/knowledge-answer/versions/${versionId}/answerability-profiles`);
            return result.items || [];
        },

        createKnowledgeAnswerabilityProfile: async (versionId: string, data: Partial<AdminKnowledgeAnswerabilityProfile>) => {
            return apiFetch<AdminKnowledgeAnswerabilityProfile>(`/admin/knowledge-answer/versions/${versionId}/answerability-profiles`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateKnowledgeAnswerabilityProfile: async (versionId: string, profileId: string, data: Partial<AdminKnowledgeAnswerabilityProfile>) => {
            return apiFetch<AdminKnowledgeAnswerabilityProfile>(`/admin/knowledge-answer/versions/${versionId}/answerability-profiles/${profileId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteKnowledgeAnswerabilityProfile: async (versionId: string, profileId: string) => {
            return apiFetch<{ deleted: boolean }>(`/admin/knowledge-answer/versions/${versionId}/answerability-profiles/${profileId}`, {
                method: "DELETE",
            });
        },

        // ─── Knowledge Debug Trigger ───

        debugTriggerKnowledgeAnswer: async (data: AdminKnowledgeDebugTriggerRequest) => {
            return apiFetch<AdminKnowledgeDebugTriggerResponse>("/admin/knowledge-answer/debug/trigger", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        listKnowledgeAnswerRuns: async (params?: { limit?: number; page?: number; session_id?: string; query?: string; answerability?: string; final_status?: string }) => {
            const queryParams = new URLSearchParams();
            if (params?.limit) queryParams.set("limit", String(params.limit));
            if (params?.page) queryParams.set("page", String(params.page));
            if (params?.session_id) queryParams.set("session_id", params.session_id);
            if (params?.query) queryParams.set("query", params.query);
            if (params?.answerability) queryParams.set("answerability", params.answerability);
            if (params?.final_status) queryParams.set("final_status", params.final_status);
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            return apiFetch<AdminKnowledgeAnswerRunListResponse>(`/knowledge-debug/runs${query}`);
        },

        getKnowledgeAnswerRunDetail: async (runId: string) => {
            return apiFetch<AdminKnowledgeAnswerRunDetail>(`/knowledge-debug/runs/${runId}`);
        },

        getKnowledgeAnswerRunSteps: async (runId: string) => {
            return apiFetch<AdminKnowledgeAnswerRunStepsResponse>(`/knowledge-debug/runs/${runId}/steps`);
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
            return apiFetch<AdminModelConfigGrouped>("/admin/model-configs");
        },

        getModelConfig: async (id: string) => {
            return apiFetch<AdminModelConfigDetail>(`/admin/model-configs/${id}`);
        },

        createModelConfig: async (data: AdminModelConfigCreateRequest) => {
            return apiFetch<AdminModelConfigCreateResponse>("/admin/model-configs", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        updateModelConfig: async (id: string, data: AdminModelConfigUpdateRequest) => {
            return apiFetch<AdminModelConfigDetail>(`/admin/model-configs/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
        },

        deleteModelConfig: async (id: string) => {
            return apiFetch<void>(`/admin/model-configs/${id}`, { method: "DELETE" });
        },

        testModelConfig: async (id: string) => {
            return apiFetch<AdminModelConfigTestResponse>(`/admin/model-configs/${id}/test`, {
                method: "POST",
            });
        },

        testModelConfigInline: async (data: AdminModelConfigTestRequest) => {
            return apiFetch<AdminModelConfigTestResponse>("/admin/model-configs/test", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        previewTTSBlob: async (params: {
            text: string;
            voice?: string;
            rate?: string;
            volume?: string;
            pitch?: string;
        }) => {
            const searchParams = new URLSearchParams({
                text: params.text,
                voice: params.voice || "zh-CN-XiaoxiaoNeural",
                rate: params.rate || "+0%",
                volume: params.volume || "+0%",
                pitch: params.pitch || "+0Hz",
            });

            return apiFetchBlob(`/admin/model-configs/tts/preview?${searchParams}`, {
                method: "POST",
            });
        },

        // Voice Runtime Policies
        getVoiceRuntimeProfiles: async (params?: { only_active?: boolean }) => {
            const queryParams = new URLSearchParams();
            if (params?.only_active !== undefined) {
                queryParams.set("only_active", String(params.only_active));
            }
            const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
            const result = await apiFetch<{ items?: unknown[]; total?: unknown }>(`/admin/voice-runtime/profiles${query}`);
            const items = Array.isArray(result.items) ? result.items : [];
            return {
                items: items.map(normalizeVoiceRuntimeProfile),
                total: toNumberValue(result.total, 0),
            };
        },

        createVoiceRuntimeProfile: async (data: VoiceRuntimeProfilePayload) => {
            const result = await apiFetch<unknown>("/admin/voice-runtime/profiles", {
                method: "POST",
                body: JSON.stringify(data),
            });
            return normalizeVoiceRuntimeProfile(result);
        },

        updateVoiceRuntimeProfile: async (profileId: string, data: Partial<VoiceRuntimeProfilePayload>) => {
            const result = await apiFetch<unknown>(`/admin/voice-runtime/profiles/${profileId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            return normalizeVoiceRuntimeProfile(result);
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

        getPromptTemplateOptions: async () => {
            return apiFetch<PromptTemplateOptions>("/prompt-templates/options");
        },


        quarantineInvalidPromptTemplates: async (reason: string) => {
            const query = new URLSearchParams({ reason }).toString();
            return apiFetch<PromptTemplateQuarantineResult>(
                `/prompt-templates/governance/quarantine-invalid?${query}`,
                { method: "POST" },
            );
        },

        getPromptTemplate: async (id: string) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            return apiFetch<PromptTemplate>(`/prompt-templates/${normalizedId}`);
        },

        getPromptTemplateGovernanceStatus: async () => {
            return apiFetch<PromptTemplateGovernanceStatus>("/prompt-templates/governance/status");
        },

        remediateInvalidPromptTemplates: async (reason: string) => {
            return apiFetch<PromptTemplateGovernanceRemediationResponse>("/prompt-templates/governance/remediate-invalid", {
                method: "POST",
                body: JSON.stringify({ reason }),
            });
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

        migrateInvalidPromptTemplates: async (data: { reason: string; dry_run?: boolean }) => {
            return apiFetch<{ success: boolean; data: { dry_run: boolean; checked: number; remediated: number; items: Array<Record<string, unknown>>; audit_action?: string | null } }>("/prompt-templates/governance/migrate-invalid", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        rollbackPromptTemplateGovernance: async (id: string, data: { reason: string }) => {
            const normalizedId = normalizeRequiredId(id, { fieldName: "prompt_template_id" });
            return apiFetch<PromptTemplate>(`/prompt-templates/governance/${normalizedId}/rollback`, {
                method: "POST",
                body: JSON.stringify(data),
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

        previewTTSBlob: async (params: {
            text: string;
            voice?: string;
            rate?: string;
            volume?: string;
            pitch?: string;
        }) => {
            const searchParams = new URLSearchParams();
            Object.entries(params).forEach(([key, value]) => {
                if (typeof value === "string" && value.trim()) {
                    searchParams.set(key, value);
                }
            });

            return apiFetchBlob(`/admin/model-configs/tts/preview?${searchParams}`, {
                method: "POST",
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
    presentations: presentationsDomain,

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
