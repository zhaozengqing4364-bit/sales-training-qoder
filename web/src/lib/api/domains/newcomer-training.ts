import type {
    ActivityDetailResponse,
    ActivityTypeDescriptor,
    AssetRevisionSummary,
    AssignmentSubmissionRequest,
    AudioSubmissionRequest,
    JourneyResponse,
    ModuleDetailResponse,
    PathValidationResponse,
    QuizAttemptRequest,
    TrainingPathConfigResponse,
    TrainingPathPayload,
} from "../types/newcomer-training";
import type { ApiRequest, ApiUpload } from "./shared";

type NewcomerTrainingDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
};

type AdminNewcomerTrainingDomainDependencies = {
    request: ApiRequest;
};

const activityPath = (activityId: string) =>
    `/newcomer-training/activities/${encodeURIComponent(activityId)}`;

export function createNewcomerTrainingDomain({
    request,
    upload,
}: NewcomerTrainingDomainDependencies) {
    return {
        getJourney: () => request<JourneyResponse>("/newcomer-training/journey"),
        getModule: (moduleId: string) => request<ModuleDetailResponse>(
            `/newcomer-training/modules/${encodeURIComponent(moduleId)}`,
        ),
        getActivity: (activityId: string) => request<ActivityDetailResponse>(
            activityPath(activityId),
        ),
        completeLessonChapter: (activityId: string, chapterId: string, clientToken: string) =>
            request<ActivityDetailResponse>(
                `${activityPath(activityId)}/lesson/chapters/${encodeURIComponent(chapterId)}/complete`,
                { method: "POST", body: JSON.stringify({ client_token: clientToken }) },
            ),
        confirmLesson: (activityId: string, clientToken: string) =>
            request<ActivityDetailResponse>(`${activityPath(activityId)}/lesson/confirm`, {
                method: "POST",
                body: JSON.stringify({ client_token: clientToken }),
            }),
        submitQuiz: (activityId: string, payload: QuizAttemptRequest) =>
            request<ActivityDetailResponse>(`${activityPath(activityId)}/quiz/attempts`, {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        submitAudio: (activityId: string, payload: AudioSubmissionRequest) => {
            const form = new FormData();
            form.append("client_token", payload.client_token);
            if (payload.confirmed_material_version_id) {
                form.append("confirmed_material_version_id", payload.confirmed_material_version_id);
            }
            form.append("file", payload.file);
            return upload<ActivityDetailResponse>(`${activityPath(activityId)}/audio/submissions`, form);
        },
        startRealtime: (activityId: string, clientToken: string) =>
            request<ActivityDetailResponse>(`${activityPath(activityId)}/realtime/sessions`, {
                method: "POST",
                body: JSON.stringify({ client_token: clientToken }),
            }),
        startAiCoach: (activityId: string, clientToken: string) =>
            request<ActivityDetailResponse>(`${activityPath(activityId)}/ai-coach/sessions`, {
                method: "POST",
                body: JSON.stringify({ client_token: clientToken }),
            }),
        submitAssignment: (activityId: string, payload: AssignmentSubmissionRequest) => {
            const form = new FormData();
            form.append("client_token", payload.client_token);
            if (payload.text) form.append("text", payload.text);
            if (payload.file) form.append("file", payload.file);
            return upload<ActivityDetailResponse>(`${activityPath(activityId)}/assignments`, form);
        },
    };
}

export function createAdminNewcomerTrainingDomain({
    request,
}: AdminNewcomerTrainingDomainDependencies) {
    const base = "/admin/newcomer-training/path";
    return {
        getPath: () => request<TrainingPathConfigResponse>(`${base}/`),
        saveDraft: (payload: TrainingPathPayload, reason: string) =>
            request<AssetRevisionSummary>(`${base}/draft`, {
                method: "PUT",
                body: JSON.stringify({ payload, reason }),
            }),
        deleteDraft: (reason: string) => request<{ deleted: boolean }>(`${base}/draft`, {
            method: "DELETE",
            body: JSON.stringify({ reason }),
        }),
        validateDraft: () => request<PathValidationResponse>(`${base}/validate`, {
            method: "POST",
        }),
        publish: (reason: string) => request<AssetRevisionSummary>(`${base}/publish`, {
            method: "POST",
            body: JSON.stringify({ reason }),
        }),
        listRevisions: () => request<AssetRevisionSummary[]>(`${base}/revisions`),
        restoreRevision: (revisionId: string, reason: string) =>
            request<AssetRevisionSummary>(
                `${base}/revisions/${encodeURIComponent(revisionId)}/restore`,
                { method: "POST", body: JSON.stringify({ reason }) },
            ),
        listActivityTypes: () => request<ActivityTypeDescriptor[]>(`${base}/activity-types`),
    };
}
