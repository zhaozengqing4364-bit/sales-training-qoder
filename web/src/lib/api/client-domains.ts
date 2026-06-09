/**
 * M019/S03 extracted API domain builders.
 *
 * Edit here when changing page-proved runtime domains behind the outward `api` façade:
 * - `createAuthDomain`          → learner auth/session endpoints
 * - `createPracticeDomain`      → live session create/get/lifecycle transport
 * - `createSessionsDomain`      → report/replay/history read surfaces and media fetch helpers
 * - `createAgentsDomain`        → learner agent/persona lookup
 * - `createPresentationsDomain` → learner/admin presentation runtime assets
 * - `createAdminReportDomain`   → admin comprehensive report actions
 *
 * Keep cross-cutting auth/error/trace/request handling in `client.ts`; pages should continue
 * importing `api` from `client.ts` instead of reaching into these builders directly.
 */
import type {
    Agent,
    Persona,
    User,
    PracticeSessionRuntime,
    PracticeRuntimePreflight,
    RetryFocusIntent,
    SessionItem,
    SessionStats,
    PracticeSessionReport,
    ReportTrendsResponse,
    KnowledgeCheckDiagnostics,
    ReplayData,
    ReplayMessagesResponse,
    HighlightsResponse,
    HighlightReviewItemPayload,
    HighlightReviewResponse,
    HighlightReviewShareSummary,
    HighlightReviewShareCreateResponse,
    SessionLifecycleAction,
    SessionLifecycleRequest,
    SessionLifecycleResponse,
    ComprehensiveReport,
    AdminPresentationListItem,
    AdminPresentationDetailItem,
    AdminPresentationPage,
    PresentationProgress,
    Recommendation,
    TrainingTask,
    TrainingTaskCreateRequest,
    TrainingTaskListResponse,
    TrainingTaskStartSessionRequest,
    TrainingTaskStartSessionResponse,
    TrainingTaskStatus,
    TrainingTaskUpdateRequest,
    BatchAssignRequest,
    BatchAssignResponse,
    LearningPathResponse,
    LearningPathNextTask,
    LearningContentCreateRequest,
    LearningContentListResponse,
    LearningContent,
    LearningContentUpdateRequest,
    LearningChapter,
    LearningChapterCreateRequest,
    LearningChapterUpdateRequest,
    FeatureFlags,
    LearnerStudyContent,
    LearnerStudyChapterCompletionResponse,
    LearnerStudyStartExamResponse,
    ExaminerSessionReport,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerAudioScorePromptListResponse,
    SalesTrainerAudioScorePromptUpdateRequest,
    SalesTrainerAudioScoreResultListResponse,
    SalesTrainerAudioSubmissionCreateRequest,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioSubmissionListResponse,
    SalesTrainerAudioUploadUrlRequest,
    SalesTrainerAudioUploadUrlResponse,
    SalesTrainerMaterial,
    SalesTrainerMaterialCreateRequest,
    SalesTrainerMaterialListResponse,
    SalesTrainerMaterialUpdateRequest,
    SalesTrainerMaterialVersion,
    SalesTrainerMaterialVersionCreateRequest,
    SalesTrainerMaterialVersionUploadRequest,
    SalesTrainerQuizAttempt,
    SalesTrainerQuizAttemptCreateRequest,
    SalesTrainerQuizAttemptListResponse,
    SalesTrainerRegradePreviewRequest,
    SalesTrainerRegradePreviewResponse,
    SalesTrainerRegradeRunRequest,
    SalesTrainerRegradeRunResponse,
    SalesTrainerUnit,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitListResponse,
    SalesTrainerUnitUpdateRequest,
    SalesTrainerOperationLogListResponse,
    SalesTrainerPathListResponse,
    SalesTrainerQuestion,
    SalesTrainerQuestionCategory,
    SalesTrainerQuestionCategoryCreateRequest,
    SalesTrainerQuestionCategoryListResponse,
    SalesTrainerQuestionCategoryUpdateRequest,
    SalesTrainerQuestionCreateRequest,
    SalesTrainerQuestionListResponse,
    SalesTrainerQuestionUpdateRequest,
    SalesTrainerSettings,
    SalesTrainerTrainingRecord,
    SalesTrainerTrainingRecordListResponse,
    SalesTrainerUnitBrief,
    NewcomerArticle,
    NewcomerArticleBinding,
    NewcomerArticleBindingUpdateRequest,
    NewcomerExamPaper,
    NewcomerExamPaperCreateRequest,
    NewcomerExamPaperListResponse,
    NewcomerExamPaperRevisionListResponse,
    NewcomerExamPaperUpdateRequest,
    NewcomerPathConfigActionRequest,
    NewcomerPathConfigResponse,
    NewcomerPathConfigSaveRequest,
    NewcomerPathRevisionListResponse,
    NewcomerPaperAttempt,
    NewcomerPaperAttemptCreateRequest,
    NewcomerPaperRollbackRequest,
    NewcomerUnitRevisionListResponse,
    NewcomerUnitRollbackRequest,
} from "./types";

type ApiRequestOptions = RequestInit & {
    signal?: AbortSignal;
    skipSessionExpiredHandling?: boolean;
};

type ApiRequest = <T>(endpoint: string, options?: ApiRequestOptions) => Promise<T>;
type ApiUpload = <T>(
    endpoint: string,
    formData: FormData,
    signal?: AbortSignal,
    options?: { skipSessionExpiredHandling?: boolean },
) => Promise<T>;

type PresentationListItem = AdminPresentationListItem;
type PresentationDetailItem = AdminPresentationDetailItem;
type PresentationPage = AdminPresentationPage;
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

type SessionsDomainDependencies = {
    request: ApiRequest;
    resolveApiBaseUrl: () => string;
    createHeaders: (existingHeaders?: HeadersInit, includeContentType?: boolean) => Headers;
    fetchWithLoopbackRetry: (url: string, options: RequestInit) => Promise<Response>;
    createApiError: (status: number, payload: unknown) => Error;
    createNetworkError: (error: unknown) => Error;
};

type PresentationsDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
    resolveApiBaseUrl: () => string;
    createHeaders: (existingHeaders?: HeadersInit, includeContentType?: boolean) => Headers;
    fetchWithLoopbackRetry: (url: string, options: RequestInit) => Promise<Response>;
    normalizePresentationListItem: (input: unknown) => PresentationListItem;
    normalizePresentationDetailItem: (input: unknown) => PresentationDetailItem;
    normalizePresentationPage: (input: unknown) => PresentationPage;
    normalizePresentationTalkingPoint: (input: unknown) => PresentationTalkingPoint;
    normalizePresentationForbiddenWord: (input: unknown) => PresentationForbiddenWord;
};

type AgentsDomainDependencies = {
    request: ApiRequest;
};

type AuthDomainDependencies = {
    request: ApiRequest;
};

type AuthProviderStatus = {
    enabled: boolean;
    login_url: string;
    message: string;
};

type AuthProvidersResponse = {
    environment: string;
    wecom: AuthProviderStatus & { configured?: boolean };
    dev_fallback: AuthProviderStatus;
};

type PracticeDomainDependencies = {
    request: ApiRequest;
};

type AdminReportDomainDependencies = {
    request: ApiRequest;
};

type TrainingTasksDomainDependencies = {
    request: ApiRequest;
};

type LearningPathDomainDependencies = {
    request: ApiRequest;
};

type LearningContentsDomainDependencies = {
    request: ApiRequest;
};

type FeatureFlagsDomainDependencies = {
    request: ApiRequest;
};

type LearnerStudyDomainDependencies = {
    request: ApiRequest;
};

type SalesTrainerDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
    resolveApiBaseUrl: () => string;
};

type NewcomerTrainingDomainDependencies = {
    request: ApiRequest;
};

type SalesTrainerAudioUploadPayload = {
    file: File;
    unit_id?: string;
    purpose?: string;
    source_page?: string;
    confirmed_material_version_id?: string | null;
    auto_process?: boolean;
};

type AdminSalesTrainerDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
    resolveApiBaseUrl: () => string;
};

type AdminNewcomerTrainingDomainDependencies = {
    request: ApiRequest;
};

type AudioSegmentUploadUrl = {
    url: string;
    object_key: string;
    expires_at?: string;
};

type AudioSegment = {
    id?: string;
    segment_sequence: number;
    upload_status: string;
    object_key?: string;
    size_bytes?: number;
    duration_ms?: number | null;
    error_message?: string | null;
};

type AudioSegmentFailureToken =
    | "signing_failed"
    | "oss_put_failed"
    | "register_failed"
    | "network_error"
    | "unknown";

export function createAuthDomain({ request }: AuthDomainDependencies) {
    return {
        getProviders: async () => {
            return request<AuthProvidersResponse>("/auth/providers", {
                method: "GET",
                cache: "no-store",
                skipSessionExpiredHandling: true,
            });
        },

        login: async (credentials: { email: string; password: string }) => {
            return request<{ token?: string; access_token?: string; user: User & { id?: string } }>("/auth/login", {
                method: "POST",
                body: JSON.stringify(credentials),
                skipSessionExpiredHandling: true,
            });
        },

        devLogin: async () => {
            return request<{ access_token: string; token_type: string; user: User }>("/auth/dev-login", {
                method: "POST",
                skipSessionExpiredHandling: true,
            });
        },

        logout: async () => {
            return request<void>("/auth/logout", {
                method: "POST",
                skipSessionExpiredHandling: true,
            });
        },

        forgotPassword: async (email: string) => {
            return request<{ message: string }>("/auth/forgot-password", {
                method: "POST",
                body: JSON.stringify({ email }),
                skipSessionExpiredHandling: true,
            });
        },

        resetPassword: async (token: string, newPassword: string) => {
            return request<{ message: string }>("/auth/reset-password", {
                method: "POST",
                body: JSON.stringify({ token, new_password: newPassword }),
                skipSessionExpiredHandling: true,
            });
        },
    };
}

export function createPracticeDomain({ request }: PracticeDomainDependencies) {
    const controlLifecycle = async (sessionId: string, action: SessionLifecycleAction) => {
        const payload: SessionLifecycleRequest = { action };
        return request<SessionLifecycleResponse>(`/practice/sessions/${sessionId}/lifecycle`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
    };

    return {
        createSession: async (data: {
            scenario_type: "sales" | "presentation";
            presentation_id?: string;
            agent_id?: string;
            persona_id?: string;
            scenario_id?: string;
            voice_mode?: "legacy" | "stepfun_realtime";
            runtime_profile_id?: string;
            focus_intent?: RetryFocusIntent;
        }) => {
            return request<{ session_id: string }>("/practice/sessions", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        getSession: async (sessionId: string) => {
            return request<PracticeSessionRuntime>(`/practice/sessions/${sessionId}`);
        },

        getRuntimePreflight: async (sessionId: string) => {
            return request<PracticeRuntimePreflight>(
                `/practice/sessions/${sessionId}/runtime-preflight`,
            );
        },

        controlLifecycle,
        startSession: async (sessionId: string) => controlLifecycle(sessionId, "start"),
        pauseSession: async (sessionId: string) => controlLifecycle(sessionId, "pause"),
        resumeSession: async (sessionId: string) => controlLifecycle(sessionId, "resume"),
        endSession: async (sessionId: string) => controlLifecycle(sessionId, "end"),
        audioSegments: {
            createUploadUrl: async (
                sessionId: string,
                payload: { segment_sequence: number; content_type: string },
            ) => {
                return request<AudioSegmentUploadUrl>(`/practice/sessions/${sessionId}/audio-upload-urls`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            },
            register: async (
                sessionId: string,
                payload: {
                    segment_sequence: number;
                    object_key: string;
                    size_bytes: number;
                    duration_ms?: number;
                },
            ) => {
                return request<AudioSegment>(`/practice/sessions/${sessionId}/audio-segments`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            },
            registerFailure: async (
                sessionId: string,
                payload: { segment_sequence: number; error_token: AudioSegmentFailureToken },
            ) => {
                return request<AudioSegment>(`/practice/sessions/${sessionId}/audio-segments/failure`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            },
        },
    };
}

export function createLearningPathDomain({ request }: LearningPathDomainDependencies) {
    return {
        getMine: async () => request<LearningPathResponse>("/curriculum-practice/learning-path/me"),
        getNextTask: async () => request<LearningPathNextTask>("/curriculum-practice/learning-path/me/next-task"),
    };
}

export function createLearningContentsDomain({ request }: LearningContentsDomainDependencies) {
    return {
        list: async (filters?: { status?: string; query?: string }) => {
            const searchParams = new URLSearchParams();
            if (filters?.status && filters.status !== "all") searchParams.set("status", filters.status);
            if (filters?.query) searchParams.set("query", filters.query);
            const query = searchParams.toString();
            return request<LearningContentListResponse>(`/curriculum/learning-contents${query ? `?${query}` : ""}`);
        },

        create: async (payload: LearningContentCreateRequest) => {
            return request<LearningContent>("/curriculum/learning-contents", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        get: async (contentId: string) => {
            return request<LearningContent>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}`);
        },

        update: async (contentId: string, payload: LearningContentUpdateRequest) => {
            return request<LearningContent>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}`, {
                method: "PUT",
                body: JSON.stringify(payload),
            });
        },

        delete: async (contentId: string) => {
            return request<void>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}`, { method: "DELETE" });
        },

        addChapter: async (contentId: string, payload: LearningChapterCreateRequest) => {
            return request<LearningChapter>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}/chapters`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        updateChapter: async (contentId: string, chapterId: string, payload: LearningChapterUpdateRequest) => {
            return request<LearningChapter>(
                `/curriculum/learning-contents/${encodeURIComponent(contentId)}/chapters/${encodeURIComponent(chapterId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        deleteChapter: async (contentId: string, chapterId: string) => {
            return request<void>(
                `/curriculum/learning-contents/${encodeURIComponent(contentId)}/chapters/${encodeURIComponent(chapterId)}`,
                { method: "DELETE" },
            );
        },

        reorderChapters: async (contentId: string, chapterIds: string[]) => {
            return request<void>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}/chapters/reorder`, {
                method: "PUT",
                body: JSON.stringify({ chapter_ids: chapterIds }),
            });
        },

        publish: async (contentId: string) => {
            return request<LearningContent>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}/publish`, {
                method: "POST",
            });
        },

        archive: async (contentId: string) => {
            return request<LearningContent>(`/curriculum/learning-contents/${encodeURIComponent(contentId)}/archive`, {
                method: "POST",
            });
        },
    };
}

export function createFeatureFlagsDomain({ request }: FeatureFlagsDomainDependencies) {
    return {
        get: async () => request<FeatureFlags>("/feature-flags"),
    };
}

export function createLearnerStudyDomain({ request }: LearnerStudyDomainDependencies) {
    return {
        getContent: async (contentId: string) => {
            return request<LearnerStudyContent>(
                `/curriculum-practice/study/learning-contents/${encodeURIComponent(contentId)}`,
            );
        },

        completeChapter: async (contentId: string, chapterId: string) => {
            return request<LearnerStudyChapterCompletionResponse>(
                `/curriculum-practice/study/learning-contents/${encodeURIComponent(contentId)}/chapters/${encodeURIComponent(chapterId)}/complete`,
                { method: "POST" },
            );
        },

        startExam: async (contentId: string) => {
            return request<LearnerStudyStartExamResponse>(
                `/curriculum-practice/study/learning-contents/${encodeURIComponent(contentId)}/start-exam`,
                { method: "POST" },
            );
        },

        getExamReport: async (sessionId: string) => {
            return request<ExaminerSessionReport>(
                `/curriculum-practice/study/exam-sessions/${encodeURIComponent(sessionId)}/report`,
            );
        },
    };
}

export function createSessionsDomain({
    request,
    resolveApiBaseUrl,
    createHeaders,
    fetchWithLoopbackRetry,
    createApiError,
    createNetworkError,
}: SessionsDomainDependencies) {
    return {
        list: async (params?: { limit?: number; page?: number; page_size?: number; sort?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.limit) searchParams.set("limit", String(params.limit));
            if (params?.page) searchParams.set("page", String(params.page));
            if (params?.page_size) searchParams.set("page_size", String(params.page_size));
            if (params?.sort) searchParams.set("sort", params.sort);
            return request<{ total: number; items: SessionItem[]; page: number; page_size: number; has_more: boolean }>(`/sessions?${searchParams}`);
        },

        getStats: async () => request<SessionStats>("/sessions/stats"),
        getReport: async (sessionId: string) => request<PracticeSessionReport>(`/practice/sessions/${sessionId}/report`),
        getReportTrends: async (sessionId: string, limit = 5) => request<ReportTrendsResponse>(`/practice/sessions/${sessionId}/report-trends?limit=${limit}`),
        getNextRecommendation: async (sessionId: string) => request<Recommendation>(`/practice/sessions/${sessionId}/next-recommendation`),
        getKnowledgeCheck: async (sessionId: string) => request<KnowledgeCheckDiagnostics>(`/practice/sessions/${sessionId}/knowledge-check`),
        getEnhancedReport: async (sessionId: string) => request<Record<string, unknown>>(`/sessions/${sessionId}/enhanced-report`),
        getReplay: async (sessionId: string) => request<ReplayData>(`/sessions/${sessionId}/replay`),
        getMessages: async (sessionId: string, page = 1, pageSize = 50) => {
            return request<ReplayMessagesResponse>(`/sessions/${sessionId}/messages?page=${page}&page_size=${pageSize}`);
        },
        getMessageDetail: async (sessionId: string, messageId: string) => {
            return request<Record<string, unknown>>(`/sessions/${sessionId}/messages/${messageId}`);
        },
        getHighlights: async (sessionId: string) => request<HighlightsResponse>(`/sessions/${sessionId}/highlights`),
        getHighlightReview: async (sessionId: string) => request<HighlightReviewResponse | null>(`/sessions/${sessionId}/highlight-review`),
        saveHighlightReview: async (
            sessionId: string,
            payload: { items: Array<Partial<HighlightReviewItemPayload> & { id?: string }>; title?: string | null },
        ) => request<HighlightReviewResponse>(`/sessions/${sessionId}/highlight-review`, {
            method: "PUT",
            body: JSON.stringify({
                schema_version: "highlight_review_v1",
                title: payload.title ?? null,
                items: payload.items.map((item) => ({
                    id: item.id ?? item.message_id,
                    message_id: item.message_id ?? item.id,
                    reason: item.reason ?? null,
                    stage_name: item.stage_name ?? null,
                    issue_label: item.issue_label ?? null,
                    suggested_response: item.suggested_response ?? null,
                })),
            }),
        }),
        createHighlightReviewShare: async (
            sessionId: string,
            payload: { consent_granted: boolean; consent_text?: string | null; ttl_days?: number | null; channel?: "wecom" },
        ) => request<HighlightReviewShareCreateResponse>(`/sessions/${sessionId}/highlight-review/shares`, {
            method: "POST",
            body: JSON.stringify({
                channel: payload.channel ?? "wecom",
                consent_granted: payload.consent_granted,
                consent_text: payload.consent_text ?? null,
                ttl_days: payload.ttl_days ?? null,
            }),
        }),
        revokeHighlightReviewShare: async (
            sessionId: string,
            shareId: string,
            reason?: string | null,
        ) => request<HighlightReviewShareSummary>(`/sessions/${sessionId}/highlight-review/shares/${shareId}/revoke`, {
            method: "POST",
            body: JSON.stringify({ reason: reason ?? null }),
        }),

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

        getSegmentAudioBlobUrl: async (sessionId: string, segmentSequence: number) => {
            try {
                const response = await fetchWithLoopbackRetry(
                    `${resolveApiBaseUrl()}/sessions/${sessionId}/audio-segments/${segmentSequence}`,
                    {
                        credentials: "include",
                        headers: createHeaders(undefined, false),
                    },
                );

                if (!response.ok) {
                    const payload = await response.json().catch(() => ({}));
                    throw createApiError(response.status, payload);
                }

                const blob = await response.blob();
                return URL.createObjectURL(blob);
            } catch (error) {
                if (error instanceof Error && error.name === "AbortError") {
                    throw error;
                }
                if (error instanceof Error && error.name === "ApiRequestError") {
                    throw error;
                }
                throw createNetworkError(error);
            }
        },
    };
}

export function createAgentsDomain({ request }: AgentsDomainDependencies) {
    return {
        list: async (params?: { category?: string; status?: string }) => {
            const searchParams = new URLSearchParams();
            if (params?.category) searchParams.set("category", params.category);
            if (params?.status) searchParams.set("status", params.status);

            const result = await request<{ agents: Agent[]; total: number }>(`/agents?${searchParams}`);
            return result.agents || [];
        },

        getList: async (category: string) => {
            const result = await request<{ agents: Agent[]; total: number }>(`/agents?category=${category}&status=published`);
            return result.agents || [];
        },

        get: async (id: string) => request<Agent>(`/agents/${id}`),

        getAgentWithPersonas: async (agentId: string) => {
            const [agent, personasResult] = await Promise.all([
                request<Agent>(`/agents/${agentId}`),
                request<{ personas: Persona[] }>(`/agents/${agentId}/personas`),
            ]);
            return {
                ...agent,
                personas: personasResult.personas || [],
            };
        },
    };
}

export function createPresentationsDomain({
    request,
    upload,
    resolveApiBaseUrl,
    createHeaders,
    fetchWithLoopbackRetry,
    normalizePresentationListItem,
    normalizePresentationDetailItem,
    normalizePresentationPage,
    normalizePresentationTalkingPoint,
    normalizePresentationForbiddenWord,
}: PresentationsDomainDependencies) {
    return {
        list: async (params?: { status?: string; limit?: number }) => {
            const searchParams = new URLSearchParams();
            if (params?.status) searchParams.set("status", params.status);
            if (params?.limit) searchParams.set("limit", params.limit.toString());
            const query = searchParams.toString();
            const result = await request<Array<Record<string, unknown>>>(`/presentations${query ? `?${query}` : ""}`);
            return result.map(normalizePresentationListItem);
        },

        upload: async ({ title, file }: { title: string; file: File }) => {
            const formData = new FormData();
            formData.append("title", title);
            formData.append("file", file);
            const result = await upload<Record<string, unknown>>("/presentations", formData);
            return normalizePresentationListItem(result);
        },

        replace: async (presentationId: string, payload: { file: File; title?: string }) => {
            const formData = new FormData();
            if (payload.title) {
                formData.append("title", payload.title);
            }
            formData.append("file", payload.file);
            const result = await upload<Record<string, unknown>>(`/presentations/${presentationId}/replace`, formData);
            return normalizePresentationDetailItem(result);
        },

        get: async (presentationId: string) => {
            const result = await request<Record<string, unknown>>(`/presentations/${presentationId}`);
            return normalizePresentationDetailItem(result);
        },

        getProgress: async (presentationId: string) => {
            return request<PresentationProgress | null>(`/presentations/${presentationId}/progress`);
        },

        saveProgress: async (presentationId: string, payload: { last_page_number: number; session_id?: string | null }) => {
            return request<PresentationProgress>(`/presentations/${presentationId}/progress`, {
                method: "PUT",
                body: JSON.stringify(payload),
            });
        },

        delete: async (presentationId: string) => {
            return request<void>(`/presentations/${presentationId}`, { method: "DELETE" });
        },

        getForbiddenWords: async (presentationId: string) => {
            const result = await request<Array<Record<string, unknown>>>(`/presentations/${presentationId}/forbidden-words`);
            return result.map(normalizePresentationForbiddenWord);
        },

        addForbiddenWord: async (presentationId: string, payload: { phrase: string; suggested_alternative?: string }) => {
            const result = await request<Record<string, unknown>>(`/presentations/${presentationId}/forbidden-words`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            return normalizePresentationForbiddenWord(result);
        },

        deleteForbiddenWord: async (_presentationId: string, wordId: string) => {
            return request<void>(`/admin/forbidden-words/${wordId}`, { method: "DELETE" });
        },

        getPages: async (presentationId: string) => {
            const result = await request<Array<Record<string, unknown>>>(`/presentations/${presentationId}/pages`);
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
            const result = await request<Array<Record<string, unknown>>>(`/presentations/${presentationId}/pages/${pageNumber}/talking-points`);
            return result.map(normalizePresentationTalkingPoint);
        },

        addTalkingPoint: async (presentationId: string, pageNumber: number, payload: { description: string }) => {
            const result = await request<Record<string, unknown>>(`/presentations/${presentationId}/pages/${pageNumber}/talking-points`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            return normalizePresentationTalkingPoint(result);
        },

        deleteTalkingPoint: async (_presentationId: string, pointId: string) => {
            return request<void>(`/admin/talking-points/${pointId}`, { method: "DELETE" });
        },
    };
}

export function createAdminReportDomain({ request }: AdminReportDomainDependencies) {
    return {
        getComprehensiveReport: async (sessionId: string) => {
            return request<ComprehensiveReport>(`/evaluation/sessions/${sessionId}/report`);
        },

        generateComprehensiveReport: async (sessionId: string) => {
            return request<ComprehensiveReport>(`/evaluation/sessions/${sessionId}/report`, {
                method: "POST",
            });
        },
    };
}

export function createTrainingTasksDomain({ request }: TrainingTasksDomainDependencies) {
    return {
        create: async (data: TrainingTaskCreateRequest) => {
            return request<TrainingTask>("/training-tasks", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },

        list: async (params?: { page?: number; page_size?: number; status?: TrainingTaskStatus }) => {
            const searchParams = new URLSearchParams();
            if (params?.page) searchParams.set("page", String(params.page));
            if (params?.page_size) searchParams.set("page_size", String(params.page_size));
            if (params?.status) searchParams.set("status", params.status);
            const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
            return request<TrainingTaskListResponse>(`/training-tasks${query}`);
        },

        get: async (taskId: string) => {
            return request<TrainingTask>(`/training-tasks/${taskId}`);
        },

        update: async (taskId: string, data: TrainingTaskUpdateRequest) => {
            return request<TrainingTask>(`/training-tasks/${taskId}`, {
                method: "PATCH",
                body: JSON.stringify(data),
            });
        },

        startSession: async (taskId: string, payload?: TrainingTaskStartSessionRequest) => {
            return request<TrainingTaskStartSessionResponse>(`/training-tasks/${taskId}/start-session`, {
                method: "POST",
                body: JSON.stringify(payload ?? {}),
            });
        },

        batchAssign: async (data: BatchAssignRequest) => {
            return request<BatchAssignResponse>("/training-tasks/batch-assign", {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
    };
}

function buildQueryString(params: Record<string, string | number | boolean | null | undefined>): string {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value === undefined || value === null || value === "") {
            continue;
        }
        searchParams.set(key, String(value));
    }
    const query = searchParams.toString();
    return query ? `?${query}` : "";
}

function buildSalesTrainerAudioUploadFormData(payload: SalesTrainerAudioUploadPayload): FormData {
    const formData = new FormData();
    formData.append("file", payload.file);
    if (payload.unit_id) {
        formData.append("unit_id", payload.unit_id);
    }
    formData.append("purpose", payload.purpose ?? "general_audio_scoring");
    if (payload.source_page) {
        formData.append("source_page", payload.source_page);
    }
    if (payload.confirmed_material_version_id) {
        formData.append("confirmed_material_version_id", payload.confirmed_material_version_id);
    }
    formData.append("auto_process", String(payload.auto_process ?? true));
    return formData;
}

function getUploadErrorMessage(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
}

export function createSalesTrainerDomain({
    request,
    upload,
    resolveApiBaseUrl,
}: SalesTrainerDomainDependencies) {
    return {
        listUnits: async () => {
            return request<SalesTrainerUnitListResponse>("/sales-trainer/units");
        },

        listPaths: async () => {
            return request<SalesTrainerPathListResponse>("/sales-trainer/paths");
        },

        getUnit: async (unitId: string) => {
            return request<SalesTrainerUnit>(`/sales-trainer/units/${encodeURIComponent(unitId)}`);
        },

        getUnitBrief: async (unitId: string) => {
            return request<SalesTrainerUnitBrief>(
                `/sales-trainer/units/${encodeURIComponent(unitId)}/brief`,
            );
        },

        submitQuizAttempt: async (payload: SalesTrainerQuizAttemptCreateRequest) => {
            return request<SalesTrainerQuizAttempt>("/sales-trainer/quiz-attempts", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        getQuizAttempt: async (attemptId: string) => {
            return request<SalesTrainerQuizAttempt>(
                `/sales-trainer/quiz-attempts/${encodeURIComponent(attemptId)}`,
            );
        },

        getAudioUploadUrl: async (payload: SalesTrainerAudioUploadUrlRequest) => {
            return request<SalesTrainerAudioUploadUrlResponse>(
                "/sales-trainer/audio-submissions/upload-url",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        uploadAudioSubmission: async (
            payload: SalesTrainerAudioUploadPayload,
            signal?: AbortSignal,
        ) => {
            return upload<SalesTrainerAudioSubmission>(
                "/sales-trainer/audio-submissions/upload",
                buildSalesTrainerAudioUploadFormData(payload),
                signal,
            );
        },

        uploadAudioSubmissionDirect: async (
            payload: SalesTrainerAudioUploadPayload,
            signal?: AbortSignal,
        ) => {
            const uploadWithMultipartFallback = (directErrorMessage: string) => {
                return upload<SalesTrainerAudioSubmission>(
                    "/sales-trainer/audio-submissions/upload",
                    buildSalesTrainerAudioUploadFormData(payload),
                    signal,
                ).catch((fallbackError: unknown) => {
                    throw new Error(
                        `${directErrorMessage} 已自动尝试后端中转上传但仍失败：${getUploadErrorMessage(fallbackError)}`,
                    );
                });
            };
            const uploadUrl = await request<SalesTrainerAudioUploadUrlResponse>(
                "/sales-trainer/audio-submissions/upload-url",
                {
                    method: "POST",
                    body: JSON.stringify({
                        filename: payload.file.name,
                        content_type: payload.file.type || "application/octet-stream",
                    }),
                },
            );
            if (
                uploadUrl.storage_backend === "local" ||
                uploadUrl.upload_url.startsWith("local://")
            ) {
                return uploadWithMultipartFallback("对象存储直传不可用。");
            }
            let putResponse: Response;
            try {
                putResponse = await fetch(uploadUrl.upload_url, {
                    method: "PUT",
                    body: payload.file,
                    headers: { "Content-Type": uploadUrl.content_type },
                    signal,
                });
            } catch (error) {
                if (error instanceof DOMException && error.name === "AbortError") {
                    throw error;
                }
                return uploadWithMultipartFallback(
                    "对象存储直传失败，请检查 COS/OSS 跨域 CORS 配置。",
                );
            }
            if (!putResponse.ok) {
                const detail = await putResponse.text().catch(() => "");
                return uploadWithMultipartFallback(
                    detail || `对象存储上传失败：HTTP ${putResponse.status}`,
                );
            }
            return request<SalesTrainerAudioSubmission>("/sales-trainer/audio-submissions", {
                method: "POST",
                body: JSON.stringify({
                    unit_id: payload.unit_id ?? null,
                    purpose: payload.purpose ?? "general_audio_scoring",
                    original_filename: payload.file.name,
                    content_type: payload.file.type || uploadUrl.content_type,
                    size_bytes: payload.file.size,
                    storage_key: uploadUrl.storage_key,
                    source_page: payload.source_page ?? null,
                    confirmed_material_version_id: payload.confirmed_material_version_id ?? null,
                    auto_process: payload.auto_process ?? true,
                }),
            });
        },

        registerAudioSubmission: async (payload: SalesTrainerAudioSubmissionCreateRequest) => {
            return request<SalesTrainerAudioSubmission>("/sales-trainer/audio-submissions", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        getAudioSubmission: async (submissionId: string) => {
            return request<SalesTrainerAudioSubmission>(
                `/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}`,
            );
        },

        getAudioSubmissionFileUrl: (submissionId: string) => {
            return `${resolveApiBaseUrl()}/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}/file`;
        },

        getMaterialVersionFileUrl: (versionId: string) => {
            return `${resolveApiBaseUrl()}/sales-trainer/materials/versions/${encodeURIComponent(versionId)}/file`;
        },
    };
}

export function createNewcomerTrainingDomain({
    request,
}: NewcomerTrainingDomainDependencies) {
    return {
        listPaths: async () => {
            return request<SalesTrainerPathListResponse>("/sales-trainer/paths");
        },

        getModuleArticle: async (moduleKey: string, params?: { learning_content_id?: string }) => {
            const query = buildQueryString({
                learning_content_id: params?.learning_content_id,
            });
            return request<NewcomerArticle>(
                `/newcomer-training/modules/${encodeURIComponent(moduleKey)}/article${query}`,
            );
        },

        getPaper: async (paperId: string) => {
            return request<NewcomerExamPaper>(
                `/newcomer-training/papers/${encodeURIComponent(paperId)}`,
            );
        },

        submitPaperAttempt: async (payload: NewcomerPaperAttemptCreateRequest) => {
            return request<NewcomerPaperAttempt>("/newcomer-training/paper-attempts", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },
    };
}

export function createAdminSalesTrainerDomain({
    request,
    upload,
    resolveApiBaseUrl,
}: AdminSalesTrainerDomainDependencies) {
    return {
        listUnits: async (params?: { include_archived?: boolean; limit?: number; offset?: number }) => {
            const query = buildQueryString({
                include_archived: params?.include_archived,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerUnitListResponse>(`/admin/sales-trainer/units${query}`);
        },

        createUnit: async (payload: SalesTrainerUnitCreateRequest) => {
            return request<SalesTrainerUnit>("/admin/sales-trainer/units", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        updateUnit: async (unitId: string, payload: SalesTrainerUnitUpdateRequest) => {
            return request<SalesTrainerUnit>(
                `/admin/sales-trainer/units/${encodeURIComponent(unitId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        publishUnit: async (unitId: string) => {
            return request<SalesTrainerUnit>(
                `/admin/sales-trainer/units/${encodeURIComponent(unitId)}/publish`,
                { method: "POST" },
            );
        },

        archiveUnit: async (unitId: string) => {
            return request<SalesTrainerUnit>(
                `/admin/sales-trainer/units/${encodeURIComponent(unitId)}/archive`,
                { method: "POST" },
            );
        },

        listMaterials: async (params?: { include_archived?: boolean; limit?: number; offset?: number }) => {
            const query = buildQueryString({
                include_archived: params?.include_archived,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerMaterialListResponse>(
                `/admin/sales-trainer/materials${query}`,
            );
        },

        createMaterial: async (payload: SalesTrainerMaterialCreateRequest) => {
            return request<SalesTrainerMaterial>("/admin/sales-trainer/materials", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        updateMaterial: async (
            materialId: string,
            payload: SalesTrainerMaterialUpdateRequest,
        ) => {
            return request<SalesTrainerMaterial>(
                `/admin/sales-trainer/materials/${encodeURIComponent(materialId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        archiveMaterial: async (materialId: string) => {
            return request<SalesTrainerMaterial>(
                `/admin/sales-trainer/materials/${encodeURIComponent(materialId)}/archive`,
                { method: "POST" },
            );
        },

        createMaterialVersion: async (
            materialId: string,
            payload: SalesTrainerMaterialVersionCreateRequest,
        ) => {
            return request<SalesTrainerMaterialVersion>(
                `/admin/sales-trainer/materials/${encodeURIComponent(materialId)}/versions`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        uploadMaterialVersion: async (
            materialId: string,
            payload: SalesTrainerMaterialVersionUploadRequest,
            signal?: AbortSignal,
        ) => {
            const formData = new FormData();
            formData.append("version_label", payload.version_label);
            formData.append("title", payload.title);
            if (payload.release_notes) {
                formData.append("release_notes", payload.release_notes);
            }
            formData.append("file", payload.file);
            return upload<SalesTrainerMaterialVersion>(
                `/admin/sales-trainer/materials/${encodeURIComponent(materialId)}/versions/upload`,
                formData,
                signal,
            );
        },

        publishMaterialVersion: async (versionId: string) => {
            return request<SalesTrainerMaterialVersion>(
                `/admin/sales-trainer/materials/versions/${encodeURIComponent(versionId)}/publish`,
                { method: "POST" },
            );
        },

        listQuestionCategories: async () => {
            return request<SalesTrainerQuestionCategoryListResponse>(
                "/admin/sales-trainer/question-categories",
            );
        },

        createQuestionCategory: async (
            payload: SalesTrainerQuestionCategoryCreateRequest,
        ) => {
            return request<SalesTrainerQuestionCategory>(
                "/admin/sales-trainer/question-categories",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        updateQuestionCategory: async (
            categoryId: string,
            payload: SalesTrainerQuestionCategoryUpdateRequest,
        ) => {
            return request<SalesTrainerQuestionCategory>(
                `/admin/sales-trainer/question-categories/${encodeURIComponent(categoryId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        listQuestions: async (params?: {
            category_id?: string;
            difficulty?: string;
            status?: string;
            tag?: string;
        }) => {
            const query = buildQueryString({
                category_id: params?.category_id,
                difficulty: params?.difficulty,
                status: params?.status,
                tag: params?.tag,
            });
            return request<SalesTrainerQuestionListResponse>(
                `/admin/sales-trainer/questions${query}`,
            );
        },

        createQuestion: async (payload: SalesTrainerQuestionCreateRequest) => {
            return request<SalesTrainerQuestion>("/admin/sales-trainer/questions", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        getQuestion: async (questionId: string) => {
            return request<SalesTrainerQuestion>(
                `/admin/sales-trainer/questions/${encodeURIComponent(questionId)}`,
            );
        },

        updateQuestion: async (
            questionId: string,
            payload: SalesTrainerQuestionUpdateRequest,
        ) => {
            return request<SalesTrainerQuestion>(
                `/admin/sales-trainer/questions/${encodeURIComponent(questionId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        publishQuestion: async (questionId: string) => {
            return request<SalesTrainerQuestion>(
                `/admin/sales-trainer/questions/${encodeURIComponent(questionId)}/publish`,
                { method: "POST" },
            );
        },

        archiveQuestion: async (questionId: string) => {
            return request<SalesTrainerQuestion>(
                `/admin/sales-trainer/questions/${encodeURIComponent(questionId)}/archive`,
                { method: "POST" },
            );
        },

        listAudioSubmissions: async (params?: { user_id?: string; limit?: number; offset?: number }) => {
            const query = buildQueryString({
                user_id: params?.user_id,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerAudioSubmissionListResponse>(
                `/admin/sales-trainer/audio-submissions${query}`,
            );
        },

        getAudioSubmission: async (submissionId: string) => {
            return request<SalesTrainerAudioSubmission>(
                `/admin/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}`,
            );
        },

        retryAudioTranscription: async (submissionId: string) => {
            return request<SalesTrainerAudioSubmission>(
                `/admin/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}/retry-transcription`,
                { method: "POST" },
            );
        },

        retryAudioScoring: async (submissionId: string) => {
            return request<SalesTrainerAudioSubmission>(
                `/admin/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}/retry-scoring`,
                { method: "POST" },
            );
        },

        getAudioSubmissionFileUrl: (submissionId: string) => {
            return `${resolveApiBaseUrl()}/admin/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}/file`;
        },

        listScorePrompts: async (params?: { include_archived?: boolean }) => {
            const query = buildQueryString({ include_archived: params?.include_archived });
            return request<SalesTrainerAudioScorePromptListResponse>(
                `/admin/sales-trainer/audio-score-prompts${query}`,
            );
        },

        createScorePrompt: async (payload: SalesTrainerAudioScorePromptCreateRequest) => {
            return request<SalesTrainerAudioScorePrompt>("/admin/sales-trainer/audio-score-prompts", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        updateScorePrompt: async (
            promptId: string,
            payload: SalesTrainerAudioScorePromptUpdateRequest,
        ) => {
            return request<SalesTrainerAudioScorePrompt>(
                `/admin/sales-trainer/audio-score-prompts/${encodeURIComponent(promptId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        publishScorePrompt: async (promptId: string) => {
            return request<SalesTrainerAudioScorePrompt>(
                `/admin/sales-trainer/audio-score-prompts/${encodeURIComponent(promptId)}/publish`,
                { method: "POST" },
            );
        },

        listScoreResults: async (params?: {
            user_id?: string;
            submission_id?: string;
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                user_id: params?.user_id,
                submission_id: params?.submission_id,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerAudioScoreResultListResponse>(
                `/admin/sales-trainer/score-results${query}`,
            );
        },

        listTrainingRecords: async (params?: {
            user_id?: string;
            unit_id?: string;
            material_version_id?: string;
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                user_id: params?.user_id,
                unit_id: params?.unit_id,
                material_version_id: params?.material_version_id,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerTrainingRecordListResponse>(
                `/admin/sales-trainer/training-records${query}`,
            );
        },

        getAudioTrainingRecord: async (submissionId: string) => {
            return request<SalesTrainerTrainingRecord>(
                `/admin/sales-trainer/training-records/audio/${encodeURIComponent(submissionId)}`,
            );
        },

        listQuizAttempts: async (params?: {
            user_id?: string;
            unit_id?: string;
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                user_id: params?.user_id,
                unit_id: params?.unit_id,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerQuizAttemptListResponse>(
                `/admin/sales-trainer/quiz-attempts${query}`,
            );
        },

        getQuizAttempt: async (attemptId: string) => {
            return request<SalesTrainerQuizAttempt>(
                `/admin/sales-trainer/quiz-attempts/${encodeURIComponent(attemptId)}`,
            );
        },

        previewQuizAttemptRegrade: async (
            attemptId: string,
            payload: SalesTrainerRegradePreviewRequest,
        ) => {
            return request<SalesTrainerRegradePreviewResponse>(
                `/admin/sales-trainer/regrades/quiz-attempts/${encodeURIComponent(attemptId)}/preview`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        runQuizAttemptRegrade: async (
            attemptId: string,
            payload: SalesTrainerRegradeRunRequest,
        ) => {
            return request<SalesTrainerRegradeRunResponse>(
                `/admin/sales-trainer/regrades/quiz-attempts/${encodeURIComponent(attemptId)}/run`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        previewAudioSubmissionRegrade: async (
            submissionId: string,
            payload: SalesTrainerRegradePreviewRequest,
        ) => {
            return request<SalesTrainerRegradePreviewResponse>(
                `/admin/sales-trainer/regrades/audio-submissions/${encodeURIComponent(submissionId)}/preview`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        runAudioSubmissionRegrade: async (
            submissionId: string,
            payload: SalesTrainerRegradeRunRequest,
        ) => {
            return request<SalesTrainerRegradeRunResponse>(
                `/admin/sales-trainer/regrades/audio-submissions/${encodeURIComponent(submissionId)}/run`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        listOperationLogs: async (params?: {
            actor_id?: string;
            target_type?: string;
            target_id?: string;
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                actor_id: params?.actor_id,
                target_type: params?.target_type,
                target_id: params?.target_id,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerOperationLogListResponse>(
                `/admin/sales-trainer/operation-logs${query}`,
            );
        },

        getSettings: async () => {
            return request<SalesTrainerSettings>("/admin/sales-trainer/settings");
        },
    };
}

export function createAdminNewcomerTrainingDomain({
    request,
}: AdminNewcomerTrainingDomainDependencies) {
    return {
        listUnits: async (params?: { include_archived?: boolean; limit?: number; offset?: number }) => {
            const query = buildQueryString({
                include_archived: params?.include_archived,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerUnitListResponse>(
                `/admin/newcomer-training/units${query}`,
            );
        },

        createUnit: async (payload: SalesTrainerUnitCreateRequest) => {
            return request<SalesTrainerUnit>("/admin/newcomer-training/units", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        updateUnit: async (unitId: string, payload: SalesTrainerUnitUpdateRequest) => {
            return request<SalesTrainerUnit>(
                `/admin/newcomer-training/units/${encodeURIComponent(unitId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        listUnitRevisions: async (unitId: string) => {
            return request<NewcomerUnitRevisionListResponse>(
                `/admin/newcomer-training/units/${encodeURIComponent(unitId)}/revisions`,
                { method: "GET" },
            );
        },

        publishUnit: async (unitId: string) => {
            return request<SalesTrainerUnit>(
                `/admin/newcomer-training/units/${encodeURIComponent(unitId)}/publish`,
                { method: "POST" },
            );
        },

        archiveUnit: async (unitId: string) => {
            return request<SalesTrainerUnit>(
                `/admin/newcomer-training/units/${encodeURIComponent(unitId)}/archive`,
                { method: "POST" },
            );
        },

        rollbackUnit: async (
            unitId: string,
            payload: NewcomerUnitRollbackRequest,
        ) => {
            return request<SalesTrainerUnit>(
                `/admin/newcomer-training/units/${encodeURIComponent(unitId)}/rollback`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        getPathConfig: async () => {
            return request<NewcomerPathConfigResponse>(
                "/admin/newcomer-training/path-config",
                { method: "GET" },
            );
        },

        savePathConfig: async (payload: NewcomerPathConfigSaveRequest) => {
            return request<NewcomerPathConfigResponse>(
                "/admin/newcomer-training/path-config",
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        publishPathConfig: async (payload: NewcomerPathConfigActionRequest) => {
            return request<NewcomerPathConfigResponse>(
                "/admin/newcomer-training/path-config/publish",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        listPathConfigRevisions: async () => {
            return request<NewcomerPathRevisionListResponse>(
                "/admin/newcomer-training/path-config/revisions",
                { method: "GET" },
            );
        },

        rollbackPathConfig: async (payload: NewcomerPathConfigActionRequest) => {
            return request<NewcomerPathConfigResponse>(
                "/admin/newcomer-training/path-config/rollback",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        listPapers: async (params?: { include_archived?: boolean; limit?: number; offset?: number }) => {
            const query = buildQueryString({
                include_archived: params?.include_archived,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<NewcomerExamPaperListResponse>(
                `/admin/newcomer-training/papers${query}`,
            );
        },

        createPaper: async (payload: NewcomerExamPaperCreateRequest) => {
            return request<NewcomerExamPaper>("/admin/newcomer-training/papers", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        updatePaper: async (paperId: string, payload: NewcomerExamPaperUpdateRequest) => {
            return request<NewcomerExamPaper>(
                `/admin/newcomer-training/papers/${encodeURIComponent(paperId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        listPaperRevisions: async (paperId: string) => {
            return request<NewcomerExamPaperRevisionListResponse>(
                `/admin/newcomer-training/papers/${encodeURIComponent(paperId)}/revisions`,
                { method: "GET" },
            );
        },

        publishPaper: async (paperId: string) => {
            return request<NewcomerExamPaper>(
                `/admin/newcomer-training/papers/${encodeURIComponent(paperId)}/publish`,
                { method: "POST" },
            );
        },

        rollbackPaper: async (
            paperId: string,
            payload: NewcomerPaperRollbackRequest,
        ) => {
            return request<NewcomerExamPaper>(
                `/admin/newcomer-training/papers/${encodeURIComponent(paperId)}/rollback`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        archivePaper: async (paperId: string) => {
            return request<NewcomerExamPaper>(
                `/admin/newcomer-training/papers/${encodeURIComponent(paperId)}/archive`,
                { method: "POST" },
            );
        },

        bindModuleArticle: async (
            moduleKey: string,
            payload: NewcomerArticleBindingUpdateRequest,
        ) => {
            return request<NewcomerArticleBinding>(
                `/admin/newcomer-training/modules/${encodeURIComponent(moduleKey)}/article-binding`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },
    };
}
