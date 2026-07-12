import type {
    ActivityDetailResponse,
    AdminJourneyListResponse,
    ActivityTypeDescriptor,
    CoachProfileOption,
    ScoringRubricCreateRequest,
    ScoringRubricOption,
    AssetRevisionSummary,
    AssignmentSubmissionRequest,
    AudioSubmissionRequest,
    JourneyResponse,
    ModuleDetailResponse,
    PathValidationResponse,
    QuizAttemptRequest,
    RealtimeStartResponse,
    AiCoachStartResponse,
    AiCoachTurnResponse,
    AiCoachTurnStreamEvent,
    TrainingPathConfigResponse,
    TrainingPathPayload,
} from "../types/newcomer-training";
import type { NewcomerExamPaper } from "../types";
import type { ApiRequest, ApiStream, ApiUpload } from "./shared";

type NewcomerTrainingDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
    stream: ApiStream;
};

type AdminNewcomerTrainingDomainDependencies = {
    request: ApiRequest;
};

const activityPath = (activityId: string) =>
    `/newcomer-training/activities/${encodeURIComponent(activityId)}`;

export function createNewcomerTrainingDomain({
    request,
    upload,
    stream,
}: NewcomerTrainingDomainDependencies) {
    return {
        getJourney: () => request<JourneyResponse>("/newcomer-training/journey"),
        getModule: (moduleId: string) => request<ModuleDetailResponse>(
            `/newcomer-training/modules/${encodeURIComponent(moduleId)}`,
        ),
        getActivity: (activityId: string) => request<ActivityDetailResponse>(
            activityPath(activityId),
        ),
        getExamPaper: (paperId: string) => request<NewcomerExamPaper>(
            `/newcomer-training/papers/${encodeURIComponent(paperId)}`,
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
            request<RealtimeStartResponse>(`${activityPath(activityId)}/realtime/sessions`, {
                method: "POST",
                body: JSON.stringify({ client_token: clientToken }),
            }),
        startAiCoach: (activityId: string, clientToken: string) =>
            request<AiCoachStartResponse>(`${activityPath(activityId)}/ai-coach/sessions`, {
                method: "POST",
                body: JSON.stringify({ client_token: clientToken }),
            }),
        submitAiCoachTurn: (activityId: string, sessionId: string, answer: string, clientToken: string) =>
            request<AiCoachTurnResponse>(
                `${activityPath(activityId)}/ai-coach/sessions/${encodeURIComponent(sessionId)}/turns`,
                { method: "POST", body: JSON.stringify({ answer, client_token: clientToken }) },
            ),
        streamAiCoachTurn: (activityId: string, sessionId: string, answer: string, clientToken: string, signal?: AbortSignal) =>
            stream<AiCoachTurnStreamEvent>(
                `${activityPath(activityId)}/ai-coach/sessions/${encodeURIComponent(sessionId)}/turns/stream`,
                { method: "POST", body: JSON.stringify({ answer, client_token: clientToken }), signal },
            ),
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
        saveDraft: (payload: TrainingPathPayload, reason: string, expectedRevisionId?: string | null) =>
            request<AssetRevisionSummary>(`${base}/draft`, {
                method: "PUT",
                body: JSON.stringify({ payload, reason, expected_revision_id: expectedRevisionId ?? null }),
            }),
        deleteDraft: (reason: string) => request<{ deleted: boolean }>(`${base}/draft`, {
            method: "DELETE",
            body: JSON.stringify({ reason }),
        }),
        validateDraft: () => request<PathValidationResponse>(`${base}/validate`, {
            method: "POST",
        }),
        validateCandidate: (payload: TrainingPathPayload) => request<PathValidationResponse>(`${base}/validate-candidate`, {
            method: "POST",
            body: JSON.stringify({ payload }),
        }),
        publish: (reason: string) => request<AssetRevisionSummary>(`${base}/publish`, {
            method: "POST",
            body: JSON.stringify({ reason }),
        }),
        publishCandidate: (payload: TrainingPathPayload, reason: string, expectedRevisionId?: string | null) =>
            request<AssetRevisionSummary>(`${base}/publish-candidate`, {
                method: "POST",
                body: JSON.stringify({ payload, reason, expected_revision_id: expectedRevisionId ?? null }),
            }),
        listRevisions: () => request<AssetRevisionSummary[]>(`${base}/revisions`),
        restoreRevision: (revisionId: string, reason: string, expectedRevisionId?: string | null) =>
            request<AssetRevisionSummary>(
                `${base}/revisions/${encodeURIComponent(revisionId)}/restore`,
                { method: "POST", body: JSON.stringify({ reason, expected_revision_id: expectedRevisionId ?? null }) },
            ),
        listActivityTypes: () => request<ActivityTypeDescriptor[]>(`${base}/activity-types`),
        listCoachProfiles: () => request<CoachProfileOption[]>(`${base}/coach-profiles`),
        listScoringRubrics: () => request<ScoringRubricOption[]>(`${base}/scoring-rubrics`),
        createScoringRubric: (payload: ScoringRubricCreateRequest) =>
            request<ScoringRubricOption>(`${base}/scoring-rubrics`, {
                method: "POST",
                body: JSON.stringify(payload),
            }),
        listJourneys: (params?: { department?: string; limit?: number; offset?: number }) => {
            const search = new URLSearchParams();
            if (params?.department) search.set("department", params.department);
            if (params?.limit !== undefined) search.set("limit", String(params.limit));
            if (params?.offset !== undefined) search.set("offset", String(params.offset));
            return request<AdminJourneyListResponse>(`/admin/newcomer-training/journeys${search.size ? `?${search}` : ""}`);
        },
        getLearnerJourney: (learnerId: string) => request<JourneyResponse>(
            `/admin/newcomer-training/journeys/${encodeURIComponent(learnerId)}`,
        ),
    };
}
