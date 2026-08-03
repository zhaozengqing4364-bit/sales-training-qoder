import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerAudioScorePromptListResponse,
    SalesTrainerAudioScorePromptUpdateRequest,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioSubmissionListResponse,
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
    SalesTrainerSettings,
    SalesTrainerUnit,
    SalesTrainerUnitBrief,
    SalesTrainerUnitCreateRequest,
    SalesTrainerUnitListResponse,
    SalesTrainerUnitUpdateRequest,
} from "../types/sales-trainer";
import type {
    JourneyResponse,
} from "../types/newcomer-training";
import type {
    RealtimeRoleplayStartRequest,
    RealtimeRoleplayStartResponse,
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

const MATERIAL_UPLOAD_MIN_TIMEOUT_MS = 2 * 60 * 1000;
const MATERIAL_UPLOAD_MAX_TIMEOUT_MS = 30 * 60 * 1000;
const MATERIAL_UPLOAD_RESPONSE_ALLOWANCE_MS = 60 * 1000;
const MATERIAL_UPLOAD_MIN_BYTES_PER_SECOND = 256 * 1024;
const MATERIAL_UPLOAD_TIMEOUT_MESSAGE = "材料上传长时间无响应，已停止本次上传。文件和材料名称均已保留，可直接重试。";

function getMaterialUploadTimeoutMs(fileSizeBytes: number): number {
    const transferTimeMs = Math.ceil(
        Math.max(0, fileSizeBytes) / MATERIAL_UPLOAD_MIN_BYTES_PER_SECOND * 1000,
    );
    return Math.min(
        MATERIAL_UPLOAD_MAX_TIMEOUT_MS,
        Math.max(
            MATERIAL_UPLOAD_MIN_TIMEOUT_MS,
            transferTimeMs + MATERIAL_UPLOAD_RESPONSE_ALLOWANCE_MS,
        ),
    );
}

export function createSalesTrainerDomain({
    request,
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
            return request<JourneyResponse>("/sales-trainer/journey");
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

        createMaterial: async (
            payload: SalesTrainerMaterialCreateRequest,
            signal?: AbortSignal,
        ) => {
            return request<SalesTrainerMaterial>("/admin/sales-trainer/materials", {
                method: "POST",
                body: JSON.stringify(payload),
                signal,
            });
        },

        updateMaterial: async (
            materialId: string,
            payload: SalesTrainerMaterialUpdateRequest,
            signal?: AbortSignal,
        ) => {
            return request<SalesTrainerMaterial>(
                `/admin/sales-trainer/materials/${encodeURIComponent(materialId)}`,
                {
                    method: "PUT",
                    body: JSON.stringify(payload),
                    signal,
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
                {
                    timeoutMs: getMaterialUploadTimeoutMs(payload.file.size),
                    timeoutMessage: MATERIAL_UPLOAD_TIMEOUT_MESSAGE,
                },
            );
        },

        publishMaterialVersion: async (
            versionId: string,
            signal?: AbortSignal,
        ) => {
            return request<SalesTrainerMaterialVersion>(
                `/admin/sales-trainer/materials/versions/${encodeURIComponent(versionId)}/publish`,
                { method: "POST", signal },
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

        getManagerDashboard: async () => {
            return request<SalesTrainerManagerDashboard>("/admin/sales-trainer/manager-dashboard");
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
