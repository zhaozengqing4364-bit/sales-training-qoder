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
    ComprehensiveReport,
    AdminPresentationListItem,
    AdminPresentationDetailItem,
    AdminPresentationPage,
    PresentationProgress,
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
} from "./types";
import type { ApiRequest, ApiUpload } from "./domains/shared";

export {
    createPracticeDomain,
} from "./domains/practice";
export { createSessionsDomain } from "./domains/sessions";
export {
    createSupportRuntimeDomain,
} from "./domains/support-runtime";
export {
    createAdminSalesTrainerDomain,
    createSalesTrainerDomain,
} from "./domains/sales-trainer";
export {
    createAdminNewcomerTrainingDomain,
    createNewcomerTrainingDomain,
} from "./domains/newcomer-training";

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

export function createAuthDomain({ request }: AuthDomainDependencies) {
    return {
        getProviders: async () => {
            return request<AuthProvidersResponse>("/auth/providers", {
                method: "GET",
                cache: "no-store",
                skipSessionExpiredHandling: true,
                timeoutMs: 8000,
                timeoutMessage: "登录配置加载超时，请刷新页面后重试。",
            });
        },

        login: async (credentials: { email: string; password: string }) => {
            return request<{ token?: string; access_token?: string; user: User & { id?: string } }>("/auth/login", {
                method: "POST",
                body: JSON.stringify(credentials),
                skipSessionExpiredHandling: true,
                timeoutMs: 8000,
                timeoutMessage: "登录超时，请重试。",
            });
        },

        devLogin: async () => {
            return request<{ access_token: string; token_type: string; user: User }>("/auth/dev-login", {
                method: "POST",
                skipSessionExpiredHandling: true,
                timeoutMs: 8000,
                timeoutMessage: "登录超时，请重试。",
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
