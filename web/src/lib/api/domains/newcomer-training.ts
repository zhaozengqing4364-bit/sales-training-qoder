import type {
    AiCoachAdminConfigLike,
    AiCoachAdminConfigPublishResponse,
    AiCoachAdminConfigResponse,
    AiCoachAdminConfigSaveResponse,
    AiCoachChatEventAnswerSubmitRequest,
    AiCoachChatMessageCreateRequest,
    AiCoachChatSessionCreateRequest,
    AiCoachChatSessionPublicV1,
    AiCoachChatStreamEvent,
    AiCoachSessionPublicV1,
    AiCoachTurnFeedbackV1,
    AiCoachTurnSubmitRequest,
    BusinessEtiquetteAiCoachProgress,
    BusinessEtiquetteLearningUnitsResponse,
    BusinessEtiquetteRetrainingStartResponse,
    BusinessEtiquetteUnitQuiz,
    BusinessEtiquetteUnitQuizAttempt,
    BusinessEtiquetteUnitQuizAttemptCreateRequest,
    BusinessEtiquetteUnitQuizAttemptListResponse,
    LearningContentBindingImpactResponse,
    NewcomerArticle,
    NewcomerArticleBinding,
    NewcomerArticleBindingUpdateRequest,
    NewcomerArticleProgressResponse,
    NewcomerExamPaper,
    NewcomerExamPaperCreateRequest,
    NewcomerExamPaperListResponse,
    NewcomerExamPaperRevisionListResponse,
    NewcomerExamPaperUpdateRequest,
    NewcomerPaperAttempt,
    NewcomerPaperAttemptCreateRequest,
    NewcomerPaperRollbackRequest,
    NewcomerPathConfigActionRequest,
    NewcomerPathConfigResponse,
    NewcomerPathConfigSaveRequest,
    NewcomerPathRevisionListResponse,
    NewcomerUnitRevisionListResponse,
    NewcomerUnitRollbackRequest,
    SalesTrainerPathListResponse,
    SalesTrainerUnit,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitListResponse,
    SalesTrainerUnitUpdateRequest,
} from "../types";
import type { ApiRequest, ApiStream } from "./shared";
import { buildQueryString } from "./shared";

type NewcomerTrainingDomainDependencies = {
    request: ApiRequest;
    stream: ApiStream;
};

type AdminNewcomerTrainingDomainDependencies = {
    request: ApiRequest;
};

export function createNewcomerTrainingDomain({
    request,
    stream,
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

        getModuleArticleProgress: async (moduleKey: string) => {
            return request<NewcomerArticleProgressResponse>(
                `/newcomer-training/modules/${encodeURIComponent(moduleKey)}/article-progress`,
            );
        },

        getBusinessEtiquetteLearningUnits: async () => {
            return request<BusinessEtiquetteLearningUnitsResponse>(
                "/newcomer-training/business-etiquette/learning-units",
            );
        },

        getBusinessEtiquetteUnitQuiz: async (unitKey: string) => {
            return request<BusinessEtiquetteUnitQuiz>(
                `/newcomer-training/business-etiquette/learning-units/${encodeURIComponent(unitKey)}/quiz`,
            );
        },

        submitBusinessEtiquetteUnitQuizAttempt: async (
            unitKey: string,
            payload: BusinessEtiquetteUnitQuizAttemptCreateRequest,
        ) => {
            return request<BusinessEtiquetteUnitQuizAttempt>(
                `/newcomer-training/business-etiquette/learning-units/${encodeURIComponent(unitKey)}/quiz-attempts`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        listMyBusinessEtiquetteUnitQuizAttempts: async (
            unitKey: string,
            params?: { limit?: number; offset?: number },
        ) => {
            const query = buildQueryString({
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<BusinessEtiquetteUnitQuizAttemptListResponse>(
                `/newcomer-training/business-etiquette/learning-units/${encodeURIComponent(unitKey)}/quiz-attempts${query}`,
            );
        },

        getBusinessEtiquetteAiCoachProgress: async (
            sessionId: string,
            params?: { unit_key?: string | null },
        ) => {
            const query = buildQueryString({
                session_id: sessionId,
                unit_key: params?.unit_key ?? undefined,
            });
            return request<BusinessEtiquetteAiCoachProgress>(
                `/newcomer-training/business-etiquette/ai-coach/progress${query}`,
            );
        },

        startBusinessEtiquetteRetrainingSession: async (payload?: {
            reason?: string | null;
        }) => {
            return request<BusinessEtiquetteRetrainingStartResponse>(
                "/newcomer-training/business-etiquette/retraining-sessions",
                {
                    method: "POST",
                    body: JSON.stringify({ reason: payload?.reason ?? null }),
                },
            );
        },

        completeModuleArticleChapter: async (
            moduleKey: string,
            chapterId: string,
            options?: { learning_content_id?: string | null },
        ) => {
            return request<NewcomerArticleProgressResponse>(
                `/newcomer-training/modules/${encodeURIComponent(moduleKey)}/article-progress`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        chapter_id: chapterId,
                        learning_content_id: options?.learning_content_id ?? null,
                    }),
                },
            );
        },

        startAiCoachSession: async (
            moduleKey: string,
            payload: {
                coach_mode?: string;
                interaction_type?: string;
            } = {},
        ) => {
            return request<AiCoachSessionPublicV1>(
                "/newcomer-training/ai-coach/sessions",
                {
                    method: "POST",
                    body: JSON.stringify({
                        module_key: moduleKey,
                        coach_mode: payload.coach_mode ?? null,
                        interaction_type: payload.interaction_type ?? null,
                    }),
                },
            );
        },

        submitAiCoachTurn: async (
            sessionId: string,
            turnId: string,
            answerPayload: AiCoachTurnSubmitRequest,
        ) => {
            return request<AiCoachTurnFeedbackV1>(
                `/newcomer-training/ai-coach/sessions/${encodeURIComponent(
                    sessionId,
                )}/turns/${encodeURIComponent(turnId)}/submit`,
                {
                    method: "POST",
                    body: JSON.stringify(answerPayload),
                },
            );
        },

        getAiCoachSession: async (sessionId: string) => {
            return request<AiCoachSessionPublicV1>(
                `/newcomer-training/ai-coach/sessions/${encodeURIComponent(sessionId)}`,
            );
        },

        startAiCoachChatSession: async (
            payload: AiCoachChatSessionCreateRequest,
        ) => {
            return request<AiCoachChatSessionPublicV1>(
                "/newcomer-training/ai-coach/chat/sessions",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        startAiCoachChatSessionStream: (
            payload: AiCoachChatSessionCreateRequest,
            signal?: AbortSignal,
        ) => {
            return stream<AiCoachChatStreamEvent>(
                "/newcomer-training/ai-coach/chat/sessions/stream",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                    signal,
                },
            );
        },

        getAiCoachChatSession: async (sessionId: string) => {
            return request<AiCoachChatSessionPublicV1>(
                `/newcomer-training/ai-coach/chat/sessions/${encodeURIComponent(sessionId)}`,
            );
        },

        sendAiCoachChatMessage: async (
            sessionId: string,
            payload: AiCoachChatMessageCreateRequest,
        ) => {
            return request<AiCoachChatSessionPublicV1>(
                `/newcomer-training/ai-coach/chat/sessions/${encodeURIComponent(
                    sessionId,
                )}/messages`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        sendAiCoachChatMessageStream: (
            sessionId: string,
            payload: AiCoachChatMessageCreateRequest,
            signal?: AbortSignal,
        ) => {
            return stream<AiCoachChatStreamEvent>(
                `/newcomer-training/ai-coach/chat/sessions/${encodeURIComponent(
                    sessionId,
                )}/messages/stream`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                    signal,
                },
            );
        },

        submitAiCoachChatEventAnswer: async (
            sessionId: string,
            eventId: string,
            payload: AiCoachChatEventAnswerSubmitRequest,
        ) => {
            return request<AiCoachChatSessionPublicV1>(
                `/newcomer-training/ai-coach/chat/sessions/${encodeURIComponent(
                    sessionId,
                )}/events/${encodeURIComponent(eventId)}/answer`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        submitAiCoachChatEventAnswerStream: (
            sessionId: string,
            eventId: string,
            payload: AiCoachChatEventAnswerSubmitRequest,
            signal?: AbortSignal,
        ) => {
            return stream<AiCoachChatStreamEvent>(
                `/newcomer-training/ai-coach/chat/sessions/${encodeURIComponent(
                    sessionId,
                )}/events/${encodeURIComponent(eventId)}/answer/stream`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                    signal,
                },
            );
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

        getLearningContentBindingImpact: async (contentId: string) => {
            return request<LearningContentBindingImpactResponse>(
                `/admin/newcomer-training/learning-contents/${encodeURIComponent(contentId)}/binding-impact`,
            );
        },

        getAiCoachConfig: async (moduleKey: string) => {
            const response = await request<AiCoachAdminConfigResponse>(
                `/admin/newcomer-training/modules/${encodeURIComponent(moduleKey)}/ai-coach/config`,
            );
            return response.ai_coach ?? null;
        },

        saveAiCoachConfig: async (
            moduleKey: string,
            payload: AiCoachAdminConfigLike,
        ) => {
            return request<AiCoachAdminConfigSaveResponse>(
                `/admin/newcomer-training/modules/${encodeURIComponent(moduleKey)}/ai-coach/config`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                },
            );
        },

        publishAiCoachConfig: async (moduleKey: string) => {
            return request<AiCoachAdminConfigPublishResponse>(
                `/admin/newcomer-training/modules/${encodeURIComponent(moduleKey)}/ai-coach/config/publish`,
                { method: "POST" },
            );
        },
    };
}
