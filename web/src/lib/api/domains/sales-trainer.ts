import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerAudioScorePromptListResponse,
    SalesTrainerAudioScorePromptUpdateRequest,
    SalesTrainerAudioScoreResultListResponse,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioSubmissionCreateRequest,
    SalesTrainerAudioSubmissionListResponse,
    SalesTrainerAudioUploadUrlRequest,
    SalesTrainerAudioUploadUrlResponse,
    SalesTrainerManagerDashboard,
    SalesTrainerMaterial,
    SalesTrainerMaterialCreateRequest,
    SalesTrainerMaterialListResponse,
    SalesTrainerMaterialUpdateRequest,
    SalesTrainerMaterialVersion,
    SalesTrainerMaterialVersionCreateRequest,
    SalesTrainerMaterialVersionUploadRequest,
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
    SalesTrainerQuizAttempt,
    SalesTrainerQuizAttemptCreateRequest,
    SalesTrainerQuizAttemptListResponse,
    SalesTrainerRegradePreviewRequest,
    SalesTrainerRegradePreviewResponse,
    SalesTrainerRegradeRunRequest,
    SalesTrainerRegradeRunResponse,
    SalesTrainerRoleplayObservationSessionResponse,
    SalesTrainerSettings,
    SalesTrainerTrainingRecord,
    SalesTrainerTrainingRecordListResponse,
    SalesTrainerTrainingRecordType,
    SalesTrainerUnit,
    SalesTrainerUnitBrief,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitListResponse,
    SalesTrainerUnitUpdateRequest,
} from "../types/sales-trainer";
import type {
    ReadinessDossier,
    ReadinessDossierReviewAction,
    ReadinessDossierReviewActionCreateRequest,
    ReadinessWorkbenchResponse,
    RealtimeRoleplayStartRequest,
    RealtimeRoleplayStartResponse,
    TrainingJourneyAnalyticsQuery,
    TrainingJourneyAnalyticsResponse,
    TrainingJourneyListQuery,
    TrainingJourneyListResponse,
    TrainingJourneyResponse,
} from "../types/training-journey";
import type {
    NewcomerExamPaper,
    NewcomerExamPaperCreateRequest,
    NewcomerExamPaperListResponse,
} from "../types";
import type { ApiRequest, ApiUpload } from "./shared";
import { buildQueryString } from "./shared";

type SalesTrainerDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
    resolveApiBaseUrl: () => string;
};

type AdminSalesTrainerDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
    resolveApiBaseUrl: () => string;
};

type SalesTrainerAudioUploadPayload = {
    file: File;
    unit_id?: string;
    purpose?: string;
    source_page?: string;
    confirmed_material_version_id?: string | null;
    auto_process?: boolean;
};

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

        getJourney: async () => {
            return request<TrainingJourneyResponse>("/sales-trainer/journey");
        },

        startRealtimeRoleplay: async (payload: RealtimeRoleplayStartRequest = {}) => {
            return request<RealtimeRoleplayStartResponse>(
                "/sales-trainer/realtime-roleplay/start",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
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

        listMyAudioSubmissions: async (params?: {
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerAudioSubmissionListResponse>(
                `/sales-trainer/audio-submissions${query}`,
            );
        },

        getAudioSubmissionFileUrl: (submissionId: string) => {
            return `${resolveApiBaseUrl()}/sales-trainer/audio-submissions/${encodeURIComponent(submissionId)}/file`;
        },

        getMaterialVersionFileUrl: (
            versionId: string,
            options?: { disposition?: "attachment" | "inline" },
        ) => {
            const query = options ? buildQueryString(options) : "";
            return `${resolveApiBaseUrl()}/sales-trainer/materials/versions/${encodeURIComponent(versionId)}/file${query}`;
        },
    };
}

export function createAdminSalesTrainerDomain({
    request,
    upload,
    resolveApiBaseUrl,
}: AdminSalesTrainerDomainDependencies) {
    return {
        getCapabilities: async () => {
            return request<SalesTrainerAdminCapabilities>("/admin/sales-trainer/capabilities");
        },

        listUnits: async (params?: {
            include_archived?: boolean;
            limit?: number;
            offset?: number;
        }) => {
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

        listMaterials: async (params?: {
            include_archived?: boolean;
            limit?: number;
            offset?: number;
        }) => {
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

        updateMaterial: async (materialId: string, payload: SalesTrainerMaterialUpdateRequest) => {
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

        createQuestionCategory: async (payload: SalesTrainerQuestionCategoryCreateRequest) => {
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

        listExamPapers: async (params?: { include_archived?: boolean }) => {
            const query = buildQueryString({ include_archived: params?.include_archived });
            return request<NewcomerExamPaperListResponse>(
                `/admin/newcomer-training/papers${query}`,
            );
        },

        createExamPaper: async (payload: NewcomerExamPaperCreateRequest) => {
            return request<NewcomerExamPaper>("/admin/newcomer-training/papers", {
                method: "POST",
                body: JSON.stringify(payload),
            });
        },

        publishExamPaper: async (paperId: string) => {
            return request<NewcomerExamPaper>(
                `/admin/newcomer-training/papers/${encodeURIComponent(paperId)}/publish`,
                { method: "POST" },
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

        updateQuestion: async (questionId: string, payload: SalesTrainerQuestionUpdateRequest) => {
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

        listAudioSubmissions: async (params?: {
            user_id?: string;
            limit?: number;
            offset?: number;
        }) => {
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
            const query = buildQueryString({
                include_archived: params?.include_archived,
            });
            return request<SalesTrainerAudioScorePromptListResponse>(
                `/admin/sales-trainer/audio-score-prompts${query}`,
            );
        },

        createScorePrompt: async (payload: SalesTrainerAudioScorePromptCreateRequest) => {
            return request<SalesTrainerAudioScorePrompt>(
                "/admin/sales-trainer/audio-score-prompts",
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
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
            training_stage?: string;
            module_key?: string;
            learner_level?: string;
            role_level?: string;
            status?: string;
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                user_id: params?.user_id,
                unit_id: params?.unit_id,
                material_version_id: params?.material_version_id,
                training_stage: params?.training_stage,
                module_key: params?.module_key,
                learner_level: params?.learner_level,
                role_level: params?.role_level,
                status: params?.status,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<SalesTrainerTrainingRecordListResponse>(
                `/admin/sales-trainer/training-records${query}`,
            );
        },

        getManagerDashboard: async () => {
            return request<SalesTrainerManagerDashboard>("/admin/sales-trainer/manager-dashboard");
        },

        getReadinessWorkbench: async (params?: {
            department?: string;
            limit?: number;
            offset?: number;
        }) => {
            const query = buildQueryString({
                department: params?.department,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<ReadinessWorkbenchResponse>(
                `/admin/newcomer-training/readiness/workbench${query}`,
            );
        },

        getReadinessDossier: async (learnerId: string) => {
            return request<ReadinessDossier>(
                `/admin/newcomer-training/readiness/dossiers/${encodeURIComponent(learnerId)}`,
            );
        },

        createReadinessReviewAction: async (
            learnerId: string,
            payload: ReadinessDossierReviewActionCreateRequest,
        ) => {
            return request<ReadinessDossierReviewAction>(
                `/admin/newcomer-training/readiness/dossiers/${encodeURIComponent(learnerId)}/review-actions`,
                {
                    method: "POST",
                    body: JSON.stringify(payload),
                },
            );
        },

        getJourneyAnalytics: async (params?: TrainingJourneyAnalyticsQuery) => {
            const query = buildQueryString({
                department: params?.department,
                training_stage: params?.training_stage,
                module_key: params?.module_key,
                learner_level: params?.learner_level,
                role_level: params?.role_level,
                limit: params?.limit,
            });
            return request<TrainingJourneyAnalyticsResponse>(
                `/admin/sales-trainer/journeys/analytics${query}`,
            );
        },

        listAdminJourneys: async (params?: TrainingJourneyListQuery) => {
            const query = buildQueryString({
                department: params?.department,
                training_stage: params?.training_stage,
                module_key: params?.module_key,
                learner_level: params?.learner_level,
                role_level: params?.role_level,
                limit: params?.limit,
                offset: params?.offset,
            });
            return request<TrainingJourneyListResponse>(
                `/admin/sales-trainer/journeys${query}`,
            );
        },

        getAdminJourney: async (learnerId: string) => {
            return request<TrainingJourneyResponse>(
                `/admin/sales-trainer/journeys/${encodeURIComponent(learnerId)}`,
            );
        },

        getAudioTrainingRecord: async (submissionId: string) => {
            return request<SalesTrainerTrainingRecord>(
                `/admin/sales-trainer/training-records/audio/${encodeURIComponent(submissionId)}`,
            );
        },

        getTrainingRecordDetail: async (
            recordType: SalesTrainerTrainingRecordType,
            recordId: string,
        ) => {
            return request<SalesTrainerTrainingRecord>(
                `/admin/sales-trainer/training-records/detail/${encodeURIComponent(recordType)}/${encodeURIComponent(recordId)}`,
            );
        },

        getRealtimeRoleplayObservations: async (sessionId: string) => {
            return request<SalesTrainerRoleplayObservationSessionResponse>(
                `/admin/sales-trainer/training-records/realtime-roleplay/${encodeURIComponent(sessionId)}/observations`,
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
