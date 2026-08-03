import type {
    FoundationJourneyActivity,
    FoundationJourneyProjection,
} from "./newcomer-training";

export type FoundationAdminCapability =
    | "view_overview"
    | "edit_paths"
    | "edit_content"
    | "review_questions"
    | "manage_cohorts"
    | "retry_assessments"
    | "regrade_results"
    | "review_readiness"
    | "publish_releases"
    | "govern_ai"
    | "view_sensitive_audit";

export interface FoundationAdminCapabilities {
    capabilities: FoundationAdminCapability[];
    access: Partial<Record<FoundationAdminCapability, true>>;
    permission_help: string;
}

export interface FoundationAdminActionItem {
    id: string;
    category: string;
    priority: "high" | "normal" | "low";
    title: string;
    reason: string;
    affected_object: string;
    status: string;
    waiting_since: string;
    href: string;
}

export interface FoundationAdminOverview {
    capabilities: FoundationAdminCapability[];
    action_items: FoundationAdminActionItem[];
    counts: Record<string, number>;
    generated_at: string;
    is_partial: boolean;
}

export interface FoundationAdminLearnerListItem {
    learner: {
        learner_id: string;
        name: string | null;
    };
    cohort: {
        cohort_id: string;
        name: string;
    };
    enrollment: {
        enrollment_id: string;
        status: string;
        revision_id: string;
        version: number;
    };
    path: {
        path_id: string;
        title: string;
        revision_label: string;
    };
    status: "active" | "blocked" | "awaiting_review" | "completed";
    status_label: string;
    progress: {
        completed_required: number;
        total_required: number;
        percentage: number;
    };
    current_activity: FoundationJourneyActivity | null;
    primary_action: FoundationJourneyProjection["primary_action"];
    updated_at: string;
}

export interface FoundationAdminLearnerListResponse {
    items: FoundationAdminLearnerListItem[];
    total: number;
    limit: number;
    offset: number;
    applied_filters: { search: string | null };
    generated_at: string;
}

export interface FoundationAdminLearnerDetail {
    learner: {
        learner_id: string;
        name: string | null;
    };
    cohort: {
        cohort_id: string;
        name: string;
    };
    journey: FoundationJourneyProjection;
}

export type FoundationActivityTypeV2 =
    | "lesson"
    | "quiz"
    | "audio_assessment"
    | "ai_coach"
    | "assignment";

export interface FoundationRetryPolicyV2 {
    max_attempts: number;
    retry_interval_seconds: number;
}

interface FoundationActivityBaseV2 {
    activity_id: string;
    type: FoundationActivityTypeV2;
    title: string;
    objective: string;
    why_it_matters: string;
    steps: string[];
    success_criteria: string[];
    competency_keys: string[];
    estimated_minutes: number;
    required: boolean;
    prerequisite_activity_ids: string[];
    ai_dependency: "none" | "optional" | "required";
    retry_policy: FoundationRetryPolicyV2;
}

export interface FoundationLessonActivityV2 extends FoundationActivityBaseV2 {
    type: "lesson";
    config: {
        learning_unit_revision_id: string;
        required_checkpoint_ids: string[];
    };
}

export interface FoundationQuizActivityV2 extends FoundationActivityBaseV2 {
    type: "quiz";
    config: { quiz_revision_id: string };
}

export interface FoundationAudioActivityV2 extends FoundationActivityBaseV2 {
    type: "audio_assessment";
    config: {
        audio_material_revision_id: string;
        scoring_scheme_revision_id: string;
        allowed_recording_modes: Array<"browser" | "file">;
        max_duration_seconds: number;
        max_size_bytes: number;
        language: string;
        baseline_only: boolean;
    };
}

export interface FoundationCoachActivityV2 extends FoundationActivityBaseV2 {
    type: "ai_coach";
    config: { coach_profile_revision_id: string };
}

export interface FoundationAssignmentActivityV2 extends FoundationActivityBaseV2 {
    type: "assignment";
    config: {
        scenario_revision_id: string;
        scoring_scheme_revision_id: string;
        allowed_recording_modes: Array<"browser" | "file">;
        max_duration_seconds: number;
        max_size_bytes: number;
        language: string;
        segment_ids: ["discovery", "objection", "commitment"];
    };
}

export type FoundationActivityDefinitionV2 =
    | FoundationLessonActivityV2
    | FoundationQuizActivityV2
    | FoundationAudioActivityV2
    | FoundationCoachActivityV2
    | FoundationAssignmentActivityV2;

export interface FoundationStageDefinitionV2 {
    stage_id: string;
    sequence: number;
    title: string;
    objective: string;
    entry_conditions: string[];
    completion_rule: "all_required" | "all_activities";
    visibility: "learner" | "assigned_only";
    activities: FoundationActivityDefinitionV2[];
}

export interface FoundationPathDraftV2 {
    contract_version: "newcomer_training_path_v2";
    title: string;
    revision_label: string;
    stages: FoundationStageDefinitionV2[];
}

export interface FoundationPathListItem {
    path_id: string;
    stable_key: string;
    title: string;
    status: string;
    working_revision_id: string | null;
    published_revision_id: string | null;
    active_release_plan_id: string | null;
    version: number;
    updated_at: string;
}

export interface FoundationPathRevisionWorkspace {
    revision_id: string;
    revision_no: number;
    revision_label: string;
    status: string;
    snapshot: FoundationPathDraftV2;
    content_hash: string;
    version: number;
    created_at: string;
    published_at: string | null;
}

export interface FoundationPathWorkspace {
    path: Omit<FoundationPathListItem, "updated_at">;
    working_revision: FoundationPathRevisionWorkspace | null;
    published_revision: FoundationPathRevisionWorkspace | null;
    revision_history: Array<Omit<FoundationPathRevisionWorkspace, "snapshot">>;
}

export interface FoundationPathValidationIssue {
    code: string;
    field: string;
    message: string;
    severity?: "blocker" | "warning" | "suggestion";
    activity_id?: string | null;
}

export interface FoundationPathValidation {
    path_id: string;
    revision_id: string;
    content_hash: string;
    valid: boolean;
    issues: FoundationPathValidationIssue[];
}

export interface FoundationReleasePlan {
    release_plan_id: string;
    organization_id: string;
    path_id: string;
    path_revision_id: string;
    previous_release_plan_id: string | null;
    status: "ready" | "blocked" | "publishing" | "published" | "superseded" | "failed" | string;
    version: number;
    contract_hash: string;
    target_revisions: Array<Record<string, unknown>>;
    dependency_graph: { nodes?: Array<Record<string, unknown>>; edges?: Array<Record<string, unknown>>; acyclic?: boolean };
    validation_report: { valid?: boolean; issues?: FoundationPathValidationIssue[]; publish_failure?: { code?: string; message?: string } };
    impact_preview: Record<string, unknown>;
    impact_hash: string;
    reason: string;
    created_by: string;
    published_by: string | null;
    rolled_back_by: string | null;
    created_at: string;
    published_at: string | null;
    rolled_back_at: string | null;
}

export interface FoundationReleasePreview extends FoundationReleasePlan {
    preview_token: string;
    preview_expires_at: string;
}

export interface FoundationRollbackPreview {
    active_release_plan_id: string;
    target_release_plan_id: string;
    preview_token: string;
    impact_hash: string;
    impact: Record<string, unknown>;
    expires_at: string;
}

export interface FoundationResourceListItem {
    resource_type: "source_document" | "learning_unit" | "question" | "quiz";
    resource_id: string;
    stable_key: string;
    title: string;
    status: string;
    version: number;
    working_revision_id: string | null;
    published_revision_id: string | null;
    updated_at: string;
}

export interface FoundationResourceReference {
    reference_type: "path" | "learning_unit" | "question" | "quiz";
    title: string;
    revision_label: string;
    status: string;
    href: string;
}

export interface FoundationResourceReferences {
    items: FoundationResourceReference[];
    total: number;
    is_partial: boolean;
    archive_behavior: "preserve_revisions";
}

export type FoundationBindingResourceType =
    | "learning_unit"
    | "quiz"
    | "audio_material"
    | "scoring_scheme"
    | "scenario"
    | "coach_profile";

export interface FoundationBindingResourceOption {
    resource_type: FoundationBindingResourceType;
    revision_id: string;
    stable_key: string;
    title: string;
    status: string;
    revision_no: number;
    created_at: string;
    bindable: boolean;
    needs_approval: boolean;
    quick_create_supported: boolean;
}

export interface FoundationLearningResourceDetail {
    contract_version: "learning_resource_detail_v1";
    generated_at: string;
    data_freshness: "fresh";
    capabilities: string[];
    resource: FoundationResourceListItem;
    working_revision: Record<string, unknown> | null;
    published_revision: Record<string, unknown> | null;
}

export type FoundationSourceContentKind =
    | "document"
    | "slide_deck"
    | "demo_video"
    | "external_demo"
    | "script"
    | "example_audio"
    | "attachment";

export type FoundationSourceProcessingState =
    | "pending"
    | "processing"
    | "partial"
    | "ready"
    | "failed"
    | "cancelled";

export interface FoundationSourceRevisionDetail {
    revision_id: string;
    revision_no: number;
    revision_label: string;
    status: "working" | "published" | "archived" | string;
    version: number;
    content_hash: string;
    working_revision: {
        revision_label: string;
        source_type: "file" | "url" | "manual";
        content_kind: FoundationSourceContentKind;
        external_url?: string;
        parse_status: "pending" | "ready" | "failed";
        processing_state: FoundationSourceProcessingState;
        processing_stage: string | null;
        original_filename: string | null;
        trusted_mime_type: string | null;
        file_size_bytes: number | null;
        language: string | null;
        page_count: number | null;
        duration_ms: number | null;
        failure_message: string | null;
        manual_content?: string | null;
    };
    preview: {
        kind: FoundationSourceContentKind;
        version: string | null;
        pages: Array<{ page: number; status: "ready" | "failed"; text: string }>;
        sections: Array<{ index: number; text: string; locator: Record<string, unknown> }>;
        missing_pages: number[];
        duration_ms: number | null;
    };
    access: {
        original: string | null;
        preview_page_template: string | null;
        playback: string | null;
    };
}

export interface FoundationSourceAnchor {
    anchor_id: string;
    anchor_key: string;
    label: string;
    locator_type: "page" | "time_range" | "paragraph" | string;
    locator: Record<string, unknown>;
    created_at: string;
}

export interface FoundationQuestionCandidate {
    candidate_id: string;
    batch_id: string;
    status: string;
    version: number;
    risk_level: "normal" | "high";
    content: {
        question_type: "single_choice" | "multiple_choice" | "true_false" | "short_answer";
        stem: string;
        options: Array<{ option_id: string; text: string; is_correct: boolean }>;
        reference_answer: string | null;
        rubric: Record<string, unknown> | null;
        explanation: string;
        difficulty: "easy" | "medium" | "hard";
        competency_keys: string[];
        source_anchor_ids: string[];
    };
    gate_status: string;
    gate_results: Record<string, unknown>;
    source_revision_id: string;
    learning_unit_revision_id: string;
    reviewed_by: string | null;
    review_reason: string | null;
    created_at: string;
}

export interface FoundationQuestionGenerationOptions {
    prompt_options: Array<{
        template_id: string;
        revision_id: string;
        revision_no: number;
        label: string;
    }>;
    model_routing_options: Array<{
        profile_id: string;
        revision_id: string;
        revision_no: number;
        label: string;
    }>;
    ready: boolean;
    empty_message: string | null;
}

export interface FoundationQuestionGenerationBatch {
    batch_id: string;
    status: "queued" | "running" | "completed" | "failed" | "cancelled";
    requested_count: number;
    candidate_count: number;
    source_revision_id: string;
    learning_unit_revision_id: string;
    task_id: string | null;
    created_at: string;
    completed_at: string | null;
    result_location: string;
    recovery_available: boolean;
}

export interface FoundationLearnerOption {
    learner_id: string;
    name: string;
    email: string | null;
    already_enrolled: boolean;
}

export interface FoundationAuditItem {
    audit_id: string;
    actor_id: string;
    object_type: string;
    object_id: string;
    action: string;
    result: string;
    reason: string | null;
    before_version: number | null;
    after_version: number | null;
    occurred_at: string;
}

export interface FoundationCohortListItem {
    cohort_id: string;
    stable_key: string;
    name: string;
    path_revision_id: string;
    status: string;
    version: number;
    enrollment_count: number;
    updated_at: string;
}

export interface FoundationCohortWorkspace {
    cohort: Omit<FoundationCohortListItem, "enrollment_count" | "updated_at">;
    enrollments: Array<{
        enrollment_id: string;
        learner_id: string;
        learner_name: string;
        learner_email: string | null;
        path_revision_id: string;
        status: string;
        version: number;
        assigned_at: string;
    }>;
}

export interface FoundationBatchItemResult {
    learner_id?: string;
    learner_name?: string | null;
    candidate_id?: string;
    status: "eligible" | "succeeded" | "failed";
    enrollment_id?: string | null;
    reason?: string | null;
    error_code?: string | null;
    message?: string | null;
}

export interface FoundationBatchPreview {
    preview_token: string;
    impact_hash: string;
    eligible_count: number;
    failure_count: number;
    items: FoundationBatchItemResult[];
    expires_at: string;
    import_id?: string;
    review_id?: string;
    cohort_id?: string;
    command?: string;
}

export interface FoundationMigrationPreview {
    migration_id: string;
    preview_token: string;
    impact_hash: string;
    target_revision_id: string;
    eligible_count: number;
    failure_count: number;
    items: Array<{
        enrollment_id: string;
        status: "eligible" | "failed";
        from_revision_id: string | null;
        target_revision_id: string;
        expected_version: number | null;
        reason: string | null;
    }>;
    expires_at: string;
}

export interface FoundationAssessmentTask {
    task_id: string;
    category: string;
    business_object: string;
    resource_type: string;
    resource_id: string;
    state: string;
    state_label: string;
    attempt_count: number;
    waiting_since: string;
    updated_at: string;
    failure: string | null;
    available_actions: string[];
}

export interface FoundationAudioChangePreview {
    preview_token: string;
    impact_hash: string;
    expires_at: string;
    change_type: "regrade" | "invalidation";
    summary: Record<string, unknown>;
}

export interface FoundationDurableTaskDetail {
    task_id: string;
    organization_id: string;
    resource_type: string;
    resource_id: string;
    state: string;
    status_label: string;
    current_step: string;
    progress: { current?: number; total?: number; label?: string } | null;
    can_cancel: boolean;
    can_redrive: boolean;
    result_kind: string | null;
    result_location: string | null;
    partial_success_message: string | null;
    error: { code?: string; message?: string; category?: string } | null;
    attempt_count: number;
    max_attempts: number;
    updated_at: string;
    stale: boolean;
}
