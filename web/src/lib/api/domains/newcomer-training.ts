import type {
    FoundationActivityCommand,
    FoundationActivityWorkspace,
    FoundationJourneyProjection,
    FoundationNotificationPage,
    FoundationTaskState,
    FoundationTaskStatus,
    FoundationTaskStatusPage,
    EvidenceDossierV1,
    ReadinessAppealCreateRequest,
    ReadinessAppealProjection,
    ReadinessExceptionPreviewV1,
    ReadinessReviewQueueV1,
} from "../types/newcomer-training";
import type {
    FoundationAdminCapabilities,
    FoundationAdminLearnerDetail,
    FoundationAdminLearnerListResponse,
    FoundationAdminOverview,
    FoundationAudioChangePreview,
    FoundationAuditItem,
    FoundationAssessmentTask,
    FoundationBatchPreview,
    FoundationBindingResourceOption,
    FoundationBindingResourceType,
    FoundationCohortListItem,
    FoundationCohortWorkspace,
    FoundationDurableTaskDetail,
    FoundationLearnerOption,
    FoundationLearningResourceDetail,
    FoundationMigrationPreview,
    FoundationPathDraftV2,
    FoundationPathListItem,
    FoundationPathValidation,
    FoundationPathWorkspace,
    FoundationReleasePlan,
    FoundationReleasePreview,
    FoundationResourceReferences,
    FoundationResourceListItem,
    FoundationRollbackPreview,
    FoundationSourceAnchor,
    FoundationQuestionCandidate,
    FoundationQuestionGenerationBatch,
    FoundationQuestionGenerationOptions,
} from "../types/foundation-admin";
import type { ApiRequest, ApiUpload } from "./shared";

type NewcomerTrainingDomainDependencies = {
    request: ApiRequest;
};

type AdminNewcomerTrainingDomainDependencies = {
    request: ApiRequest;
    upload: ApiUpload;
};

const activityPath = (activityId: string) =>
    `/newcomer-training/activities/${encodeURIComponent(activityId)}`;

export function createNewcomerTrainingDomain({
    request,
}: NewcomerTrainingDomainDependencies) {
    return {
        getJourney: () => request<FoundationJourneyProjection>("/newcomer-training/journey"),
        getDossier: () => request<EvidenceDossierV1>("/newcomer-training/dossier"),
        submitAppeal: (payload: ReadinessAppealCreateRequest, idempotencyKey: string) =>
            request<ReadinessAppealProjection>("/newcomer-training/dossier/appeals", {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify(payload),
            }),
        getActivity: (activityId: string, signal?: AbortSignal) => request<FoundationActivityWorkspace>(
            activityPath(activityId),
            { signal },
        ),
        executeCommand: (
            activityId: string,
            command: FoundationActivityCommand,
            idempotencyKey: string,
            signal?: AbortSignal,
        ) => request<FoundationActivityWorkspace>(`${activityPath(activityId)}/commands`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify(command),
                signal,
            }),
        listNotifications: (params?: {
            read_state?: "all" | "unread" | "read";
            notification_type?: "system" | "tip" | "reminder" | "achievement" | "ai_coach";
            created_from?: string;
            page?: number;
            page_size?: number;
            sort?: "-created_at" | "created_at";
        }) => {
            const search = new URLSearchParams();
            if (params?.read_state) search.set("read_state", params.read_state);
            if (params?.notification_type) search.set("notification_type", params.notification_type);
            if (params?.created_from) search.set("created_from", params.created_from);
            if (params?.page) search.set("page", String(params.page));
            if (params?.page_size) search.set("page_size", String(params.page_size));
            if (params?.sort) search.set("sort", params.sort);
            return request<FoundationNotificationPage>(
                `/newcomer-training/notifications${search.size ? `?${search}` : ""}`,
            );
        },
        listTasks: (params?: { state?: FoundationTaskState; page?: number; page_size?: number }) => {
            const search = new URLSearchParams();
            if (params?.state) search.set("state", params.state);
            if (params?.page) search.set("page", String(params.page));
            if (params?.page_size) search.set("page_size", String(params.page_size));
            return request<FoundationTaskStatusPage>(
                `/newcomer-training/tasks${search.size ? `?${search}` : ""}`,
            );
        },
        getTask: (taskId: string, signal?: AbortSignal) => request<FoundationTaskStatus>(
            `/newcomer-training/tasks/${encodeURIComponent(taskId)}`,
            { signal },
        ),
        requestTaskCancel: (taskId: string, idempotencyKey: string) =>
            request<FoundationTaskStatus>(
                `/newcomer-training/tasks/${encodeURIComponent(taskId)}/commands/request-cancel`,
                {
                    method: "POST",
                    headers: { "Idempotency-Key": idempotencyKey },
                },
            ),
    };
}

export function createAdminNewcomerTrainingDomain({
    request,
    upload,
}: AdminNewcomerTrainingDomainDependencies) {
    const v2Base = "/admin/newcomer-training";
    return {
        getCapabilities: () => request<FoundationAdminCapabilities>(`${v2Base}/capabilities`),
        getWorkspace: () => request<FoundationAdminOverview>(`${v2Base}/workspace`),
        listBindingResources: (params: {
            resource_type: FoundationBindingResourceType;
            status?: string;
            search?: string;
            limit?: number;
        }) => {
            const search = new URLSearchParams({ resource_type: params.resource_type });
            if (params.status) search.set("status", params.status);
            if (params.search) search.set("search", params.search);
            if (params.limit) search.set("limit", String(params.limit));
            return request<{ items: FoundationBindingResourceOption[]; limit: number }>(
                `${v2Base}/binding-resources?${search}`,
            );
        },
        listLearnerOptions: (params?: { search?: string; limit?: number }) => {
            const search = new URLSearchParams();
            if (params?.search) search.set("search", params.search);
            if (params?.limit) search.set("limit", String(params.limit));
            return request<{ items: FoundationLearnerOption[]; limit: number }>(
                `${v2Base}/learner-options${search.size ? `?${search}` : ""}`,
            );
        },
        listPaths: (params?: { query?: string; status?: string; limit?: number }) => {
            const search = new URLSearchParams();
            if (params?.query) search.set("query", params.query);
            if (params?.status) search.set("status", params.status);
            if (params?.limit) search.set("limit", String(params.limit));
            return request<{ items: FoundationPathListItem[]; limit: number }>(
                `${v2Base}/paths${search.size ? `?${search}` : ""}`,
            );
        },
        getPathWorkspace: (pathId: string) => request<FoundationPathWorkspace>(
            `${v2Base}/paths/${encodeURIComponent(pathId)}/workspace`,
        ),
        createPathV2: (payload: { stable_key: string; title: string }, idempotencyKey: string) =>
            request<FoundationPathListItem>(`${v2Base}/paths`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify(payload),
            }),
        savePathDraftV2: (
            pathId: string,
            payload: FoundationPathDraftV2,
            expectedVersion: number,
            idempotencyKey: string,
        ) => request<{ revision_id: string; version: number }>(
            `${v2Base}/paths/${encodeURIComponent(pathId)}/working-revision`,
            {
                method: "PUT",
                headers: {
                    "If-Match": `W/"${expectedVersion}"`,
                    "Idempotency-Key": idempotencyKey,
                },
                body: JSON.stringify(payload),
            },
        ),
        validatePathV2: (pathId: string) => request<FoundationPathValidation>(
            `${v2Base}/paths/${encodeURIComponent(pathId)}/commands/validate`,
            { method: "POST" },
        ),
        previewRelease: (pathRevisionId: string, reason: string, idempotencyKey: string) =>
            request<FoundationReleasePreview>(`${v2Base}/release-plans/preview`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({ path_revision_id: pathRevisionId, reason }),
            }),
        publishRelease: (
            plan: Pick<FoundationReleasePreview, "release_plan_id" | "preview_token" | "impact_hash" | "version">,
            idempotencyKey: string,
        ) => request<FoundationReleasePlan>(
            `${v2Base}/release-plans/${encodeURIComponent(plan.release_plan_id)}/commands/publish`,
            {
                method: "POST",
                headers: {
                    "If-Match": `W/"${plan.version}"`,
                    "Idempotency-Key": idempotencyKey,
                },
                body: JSON.stringify({
                    preview_token: plan.preview_token,
                    impact_hash: plan.impact_hash,
                }),
            },
        ),
        listReleasePlans: (pathId?: string) => request<{ items: FoundationReleasePlan[]; limit: number }>(
            `${v2Base}/release-plans${pathId ? `?path_id=${encodeURIComponent(pathId)}` : ""}`,
        ),
        previewReleaseRollback: (activePlanId: string, targetPlanId: string, reason: string) =>
            request<FoundationRollbackPreview>(
                `${v2Base}/release-plans/${encodeURIComponent(activePlanId)}/rollback-preview`,
                { method: "POST", body: JSON.stringify({ target_release_plan_id: targetPlanId, reason }) },
            ),
        confirmReleaseRollback: (
            activePlanId: string,
            preview: FoundationRollbackPreview,
            expectedVersion: number,
            idempotencyKey: string,
        ) => request<FoundationReleasePlan>(
            `${v2Base}/release-plans/${encodeURIComponent(activePlanId)}/commands/rollback`,
            {
                method: "POST",
                headers: {
                    "If-Match": `W/"${expectedVersion}"`,
                    "Idempotency-Key": idempotencyKey,
                },
                body: JSON.stringify({ preview_token: preview.preview_token, impact_hash: preview.impact_hash }),
            },
        ),
        listResourcesV2: (params: {
            resource_type: "source_document" | "learning_unit" | "question" | "quiz";
            status?: string;
            search?: string;
            page?: number;
            page_size?: number;
        }) => {
            const search = new URLSearchParams({ resource_type: params.resource_type });
            if (params.status) search.set("status", params.status);
            if (params.search) search.set("search", params.search);
            if (params.page) search.set("page", String(params.page));
            if (params.page_size) search.set("page_size", String(params.page_size));
            return request<{ items: FoundationResourceListItem[]; total: number; page: number; page_size: number; has_more: boolean }>(
                `${v2Base}/resources?${search}`,
            );
        },
        getResourceV2: (
            resourceType: "source_document" | "learning_unit" | "question" | "quiz",
            resourceId: string,
        ) => request<FoundationLearningResourceDetail>(
            `${v2Base}/resources/${resourceType}/${encodeURIComponent(resourceId)}`,
        ),
        getResourceReferencesV2: (
            resourceType: "source_document" | "learning_unit" | "question" | "quiz",
            resourceId: string,
        ) => request<FoundationResourceReferences>(
            `${v2Base}/resources/${resourceType}/${encodeURIComponent(resourceId)}/references`,
        ),
        createResourceV2: (
            resourceType: "source_document" | "learning_unit" | "question" | "quiz",
            payload: Record<string, unknown>,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(`${v2Base}/resources/${resourceType}`, {
            method: "POST",
            headers: { "Idempotency-Key": idempotencyKey },
            body: JSON.stringify(payload),
        }),
        uploadSourceDocumentV2: (
            formData: FormData,
            idempotencyKey: string,
            signal?: AbortSignal,
        ) => upload<Record<string, unknown>>(
            `${v2Base}/resources/source_document/uploads`,
            formData,
            signal,
            {
                timeoutMs: 60_000,
                timeoutMessage: "材料上传超时，请检查网络后重试。",
                headers: { "Idempotency-Key": idempotencyKey },
            },
        ),
        retrySourceProcessingV2: (
            revisionId: string,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/source-revisions/${encodeURIComponent(revisionId)}/commands/retry-processing`,
            {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
            },
        ),
        saveResourceV2: (
            resourceType: "source_document" | "learning_unit" | "question" | "quiz",
            resourceId: string,
            payload: Record<string, unknown>,
            expectedVersion: number,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/resources/${resourceType}/${encodeURIComponent(resourceId)}/working-revision`,
            {
                method: "PUT",
                headers: {
                    "If-Match": `W/"${expectedVersion}"`,
                    "Idempotency-Key": idempotencyKey,
                },
                body: JSON.stringify(payload),
            },
        ),
        validateResourceV2: (
            resourceType: "source_document" | "learning_unit" | "question" | "quiz",
            resourceId: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/resources/${resourceType}/${encodeURIComponent(resourceId)}/commands/validate`,
            { method: "POST" },
        ),
        archiveResourceV2: (
            resourceType: "source_document" | "learning_unit" | "question" | "quiz",
            resourceId: string,
            expectedVersion: number,
            reason: string,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/resources/${resourceType}/${encodeURIComponent(resourceId)}/commands/archive`,
            {
                method: "POST",
                headers: {
                    "If-Match": `W/"${expectedVersion}"`,
                    "Idempotency-Key": idempotencyKey,
                },
                body: JSON.stringify({ reason }),
            },
        ),
        listSourceAnchorsV2: (revisionId: string) => request<{ items: FoundationSourceAnchor[] }>(
            `${v2Base}/source-revisions/${encodeURIComponent(revisionId)}/anchors`,
        ),
        createSourceAnchorV2: (
            revisionId: string,
            payload: Record<string, unknown>,
            idempotencyKey: string,
        ) => request<FoundationSourceAnchor>(
            `${v2Base}/source-revisions/${encodeURIComponent(revisionId)}/anchors`,
            {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify(payload),
            },
        ),
        getQuestionGenerationOptions: () => request<FoundationQuestionGenerationOptions>(
            `${v2Base}/question-generation-options`,
        ),
        listQuestionGenerationBatches: (limit = 30) => request<{ items: FoundationQuestionGenerationBatch[]; limit: number }>(
            `${v2Base}/question-generation-batches?limit=${limit}`,
        ),
        startQuestionGenerationV2: (
            payload: {
                source_revision_id: string;
                learning_unit_revision_id: string;
                requested_count: number;
                prompt_template_id: string;
                prompt_revision_id: string;
                model_routing_profile_id: string;
                model_routing_revision_id: string;
            },
            idempotencyKey: string,
        ) => request<{ batch_id: string; status: string; task_id: string | null }>(
            `${v2Base}/question-generation-batches`,
            {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify(payload),
            },
        ),
        listCandidatesV2: (params?: { status?: string; batch_id?: string; search?: string; page?: number; page_size?: number }) => {
            const search = new URLSearchParams();
            if (params?.status) search.set("status", params.status);
            if (params?.batch_id) search.set("batch_id", params.batch_id);
            if (params?.search) search.set("search", params.search);
            if (params?.page) search.set("page", String(params.page));
            if (params?.page_size) search.set("page_size", String(params.page_size));
            return request<{ items: FoundationQuestionCandidate[]; total: number; page: number; page_size: number; has_more: boolean }>(
                `${v2Base}/question-candidates${search.size ? `?${search}` : ""}`,
            );
        },
        previewCandidateBulkReview: (
            payload: { command: "approve" | "reject" | "supersede"; candidate_ids: string[]; review_reason: string },
        ) => request<FoundationBatchPreview>(`${v2Base}/question-candidates/bulk-review/preview`, {
            method: "POST",
            body: JSON.stringify(payload),
        }),
        confirmCandidateBulkReview: (preview: FoundationBatchPreview, idempotencyKey: string) =>
            request<Record<string, unknown>>(`${v2Base}/question-candidates/bulk-review/commands/confirm`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({ preview_token: preview.preview_token, impact_hash: preview.impact_hash }),
            }),
        listCohorts: (params?: { query?: string; status?: string; limit?: number }) => {
            const search = new URLSearchParams();
            if (params?.query) search.set("query", params.query);
            if (params?.status) search.set("status", params.status);
            if (params?.limit) search.set("limit", String(params.limit));
            return request<{ items: FoundationCohortListItem[]; limit: number }>(
                `${v2Base}/cohorts${search.size ? `?${search}` : ""}`,
            );
        },
        getCohortWorkspace: (cohortId: string) => request<FoundationCohortWorkspace>(
            `${v2Base}/cohorts/${encodeURIComponent(cohortId)}/workspace`,
        ),
        createCohort: (
            payload: { stable_key: string; name: string; path_revision_id: string },
            idempotencyKey: string,
        ) => request<FoundationCohortListItem>(`${v2Base}/cohorts`, {
            method: "POST",
            headers: { "Idempotency-Key": idempotencyKey },
            body: JSON.stringify(payload),
        }),
        changeCohortStatus: (
            cohortId: string,
            targetStatus: "active" | "paused" | "cancelled" | "closed",
            reason: string,
            expectedVersion: number,
            idempotencyKey: string,
        ) => request<FoundationCohortListItem>(
            `${v2Base}/cohorts/${encodeURIComponent(cohortId)}/commands/change-status`,
            {
                method: "POST",
                headers: {
                    "If-Match": `W/"${expectedVersion}"`,
                    "Idempotency-Key": idempotencyKey,
                },
                body: JSON.stringify({ target_status: targetStatus, reason }),
            },
        ),
        previewEnrollmentImport: (cohortId: string, learnerIds: string[], reason: string) =>
            request<FoundationBatchPreview>(
                `${v2Base}/cohorts/${encodeURIComponent(cohortId)}/enrollment-imports/preview`,
                { method: "POST", body: JSON.stringify({ learner_ids: learnerIds, reason }) },
            ),
        previewEnrollmentEmailImport: (cohortId: string, emails: string[], reason: string) =>
            request<FoundationBatchPreview>(
                `${v2Base}/cohorts/${encodeURIComponent(cohortId)}/enrollment-imports/preview`,
                { method: "POST", body: JSON.stringify({ emails, reason }) },
            ),
        confirmEnrollmentImport: (preview: FoundationBatchPreview, idempotencyKey: string) =>
            request<Record<string, unknown>>(`${v2Base}/enrollment-imports/commands/confirm`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({ preview_token: preview.preview_token, impact_hash: preview.impact_hash }),
            }),
        previewEnrollmentMigration: (
            enrollmentIds: string[],
            targetRevisionId: string,
            reason: string,
        ) => request<FoundationMigrationPreview>(`${v2Base}/enrollment-revision-migrations/preview`, {
            method: "POST",
            body: JSON.stringify({
                enrollment_ids: enrollmentIds,
                target_revision_id: targetRevisionId,
                reason,
            }),
        }),
        confirmEnrollmentMigration: (
            preview: FoundationMigrationPreview,
            reason: string,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/enrollment-revision-migrations/commands/confirm`,
            {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({
                    preview_token: preview.preview_token,
                    impact_hash: preview.impact_hash,
                    reason,
                }),
            },
        ),
        listAssessmentTasks: (params?: { state?: string; limit?: number }) => {
            const search = new URLSearchParams();
            if (params?.state) search.set("state", params.state);
            if (params?.limit) search.set("limit", String(params.limit));
            return request<{ items: FoundationAssessmentTask[]; limit: number }>(
                `${v2Base}/assessment-tasks${search.size ? `?${search}` : ""}`,
            );
        },
        getAssessmentTaskDetail: (taskId: string) => request<FoundationDurableTaskDetail>(
            `/admin/task-runtime/tasks/${encodeURIComponent(taskId)}`,
        ),
        redriveAssessmentTask: (taskId: string, reason: string, idempotencyKey: string) =>
            request<{ task_id: string }>(`/admin/task-runtime/tasks/${encodeURIComponent(taskId)}/redrive`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({ reason }),
            }),
        cancelAssessmentTask: (taskId: string, reason: string, idempotencyKey: string) =>
            request<FoundationDurableTaskDetail>(`/admin/task-runtime/tasks/${encodeURIComponent(taskId)}/cancel`, {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({ reason }),
            }),
        previewAudioRegrade: (submissionId: string, reason: string) =>
            request<FoundationAudioChangePreview>(
                `${v2Base}/audio-submissions/${encodeURIComponent(submissionId)}/regrade/preview`,
                {
                    method: "POST",
                    body: JSON.stringify({ mode: "regrade", reason }),
                },
            ),
        confirmAudioRegrade: (
            submissionId: string,
            preview: FoundationAudioChangePreview,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/audio-submissions/${encodeURIComponent(submissionId)}/regrade/confirm`,
            {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({
                    preview_token: preview.preview_token,
                    impact_hash: preview.impact_hash,
                }),
            },
        ),
        previewAudioInvalidation: (submissionId: string, reason: string) =>
            request<FoundationAudioChangePreview>(
                `${v2Base}/audio-submissions/${encodeURIComponent(submissionId)}/invalidation/preview`,
                { method: "POST", body: JSON.stringify({ reason }) },
            ),
        confirmAudioInvalidation: (
            submissionId: string,
            preview: FoundationAudioChangePreview,
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `${v2Base}/audio-submissions/${encodeURIComponent(submissionId)}/invalidation/confirm`,
            {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body: JSON.stringify({
                    preview_token: preview.preview_token,
                    impact_hash: preview.impact_hash,
                }),
            },
        ),
        listFoundationAudits: (params?: { object_id?: string; limit?: number }) => {
            const search = new URLSearchParams();
            if (params?.object_id) search.set("object_id", params.object_id);
            if (params?.limit) search.set("limit", String(params.limit));
            return request<{ items: FoundationAuditItem[] }>(
                `${v2Base}/audits${search.size ? `?${search}` : ""}`,
            );
        },
        listLearners: (params?: { search?: string; limit?: number; offset?: number }) => {
            const search = new URLSearchParams();
            if (params?.search) search.set("search", params.search);
            if (params?.limit !== undefined) search.set("limit", String(params.limit));
            if (params?.offset !== undefined) search.set("offset", String(params.offset));
            return request<FoundationAdminLearnerListResponse>(`${v2Base}/learners${search.size ? `?${search}` : ""}`);
        },
        getLearner: (learnerId: string) => request<FoundationAdminLearnerDetail>(
            `${v2Base}/learners/${encodeURIComponent(learnerId)}`,
        ),
        listReadinessReviews: (params?: {
            state?: string;
            cohort_id?: string;
            competency_key?: string;
            reviewer_id?: string;
            waiting_hours_gte?: number;
            limit?: number;
            offset?: number;
        }) => {
            const search = new URLSearchParams();
            if (params?.state) search.set("state", params.state);
            if (params?.cohort_id) search.set("cohort_id", params.cohort_id);
            if (params?.competency_key) search.set("competency_key", params.competency_key);
            if (params?.reviewer_id) search.set("reviewer_id", params.reviewer_id);
            if (params?.waiting_hours_gte !== undefined) search.set("waiting_hours_gte", String(params.waiting_hours_gte));
            if (params?.limit !== undefined) search.set("limit", String(params.limit));
            if (params?.offset !== undefined) search.set("offset", String(params.offset));
            return request<ReadinessReviewQueueV1>(`/admin/newcomer-training/reviews${search.size ? `?${search}` : ""}`);
        },
        getReadinessReview: (dossierId: string) => request<EvidenceDossierV1>(
            `/admin/newcomer-training/reviews/${encodeURIComponent(dossierId)}`,
        ),
        previewReadinessException: (
            dossierId: string,
            payload: {
                expected_dossier_version: number;
                snapshot_id: string;
                reason: string;
                notes?: string | null;
                competency_keys: string[];
                evidence_ids: string[];
            },
            idempotencyKey: string,
        ) => request<ReadinessExceptionPreviewV1>(
            `/admin/newcomer-training/reviews/${encodeURIComponent(dossierId)}/commands/preview-exception`,
            {
                method: "POST",
                headers: {
                    "Idempotency-Key": idempotencyKey,
                    "If-Match": `W/"${payload.expected_dossier_version}"`,
                },
                body: JSON.stringify(payload),
            },
        ),
        recordReadinessDecision: (
            dossierId: string,
            payload: {
                decision_type: "approve_foundation_ready" | "request_retraining" | "request_more_evidence" | "reject_due_to_integrity_issue" | "close_without_decision" | "exception_approved";
                expected_dossier_version: number;
                snapshot_id: string;
                reason: string;
                notes?: string | null;
                competency_keys: string[];
                evidence_ids: string[];
                exception_confirmed?: boolean;
                preview_token?: string | null;
                impact_hash?: string | null;
            },
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `/admin/newcomer-training/reviews/${encodeURIComponent(dossierId)}/commands/record-decision`,
            {
                method: "POST",
                headers: {
                    "Idempotency-Key": idempotencyKey,
                    "If-Match": `W/"${payload.expected_dossier_version}"`,
                },
                body: JSON.stringify(payload),
            },
        ),
        assignReadinessRetraining: (
            dossierId: string,
            payload: {
                expected_dossier_version: number;
                snapshot_id: string;
                activity_source: "existing_published" | "quick_draft";
                activity_id: string | null;
                activity_title: string;
                activity_draft: Record<string, unknown> | null;
                target_competency_keys: string[];
                source_evidence_ids: string[];
                reason: string;
                due_at: string | null;
                completion_rule: Record<string, unknown>;
            },
            idempotencyKey: string,
        ) => request<Record<string, unknown>>(
            `/admin/newcomer-training/reviews/${encodeURIComponent(dossierId)}/commands/assign-retraining`,
            {
                method: "POST",
                headers: {
                    "Idempotency-Key": idempotencyKey,
                    "If-Match": `W/"${payload.expected_dossier_version}"`,
                },
                body: JSON.stringify(payload),
            },
        ),
        rebuildReadinessReview: (dossierId: string, reason: string) => request<EvidenceDossierV1>(
            `/admin/newcomer-training/reviews/${encodeURIComponent(dossierId)}/rebuild`,
            { method: "POST", body: JSON.stringify({ reason }) },
        ),
        resolveReadinessAppeal: (
            appealId: string,
            payload: { expected_version: number; action: "begin_review" | "request_regrade" | "resolve" | "reject" | "reopen_review"; resolution: string },
        ) => request<Record<string, unknown>>(
            `/admin/newcomer-training/appeals/${encodeURIComponent(appealId)}/commands`,
            { method: "POST", body: JSON.stringify(payload) },
        ),
    };
}
