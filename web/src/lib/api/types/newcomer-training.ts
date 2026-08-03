export type ActivityType =
    | "lesson"
    | "quiz"
    | "audio_assessment"
    | "realtime_roleplay"
    | "ai_coach"
    | "assignment";

export interface LessonConfig {
    learning_content_id: string;
    completion_mode: "all_chapters" | "learner_confirmed";
}

export interface QuizConfig {
    exam_paper_id: string;
    pass_score: number;
    max_attempts: number | null;
}

export interface AudioAssessmentConfig {
    scoring_rubric_id: string;
    material_id: string | null;
    pass_score: number;
    max_attempts: number | null;
    example_transcript?: string | null;
}

export interface RealtimeRoleplayConfig {
    practice_template_id: string;
    runtime_profile_id: string;
    completion_mode: "session_completed" | "scored";
    practice_template_revision_id?: string | null;
    practice_template_version?: number | null;
    practice_template_content_hash?: string | null;
    runtime_profile_snapshot_hash?: string | null;
    governed_assets_snapshot_hash?: string | null;
    runner_snapshot?: Record<string, unknown> | null;
}

export interface AiCoachConfig {
    coach_profile_id: string;
    completion_mode: "session_completed" | "goal_reached";
}

export interface AssignmentConfig {
    submission_type: "text" | "file" | "text_or_file";
    review_mode: "automatic_complete" | "manual_review";
    max_file_size_bytes: number;
}

interface ActivityBase {
    activity_id: string;
    title: string;
    description: string | null;
    order_index: number;
    required: boolean;
    estimated_minutes: number | null;
    prerequisites: string[];
    objective: string | null;
    why_it_matters: string | null;
    steps: string[];
    success_criteria: string[];
    primary_action_label: string | null;
}

export interface LessonActivity extends ActivityBase {
    type: "lesson";
    config: LessonConfig;
}

export interface QuizActivity extends ActivityBase {
    type: "quiz";
    config: QuizConfig;
}

export interface AudioAssessmentActivity extends ActivityBase {
    type: "audio_assessment";
    config: AudioAssessmentConfig;
}

export interface RealtimeRoleplayActivity extends ActivityBase {
    type: "realtime_roleplay";
    config: RealtimeRoleplayConfig;
}

export interface AiCoachActivity extends ActivityBase {
    type: "ai_coach";
    config: AiCoachConfig;
}

export interface AssignmentActivity extends ActivityBase {
    type: "assignment";
    config: AssignmentConfig;
}

export type ActivityConfig =
    | LessonActivity
    | QuizActivity
    | AudioAssessmentActivity
    | RealtimeRoleplayActivity
    | AiCoachActivity
    | AssignmentActivity;

export interface CompletionPolicy {
    mode: "all_required" | "at_least_count";
    activity_ids: string[];
    count: number | null;
}

export interface AudienceRule {
    learner_levels: string[];
    roles: string[];
    departments: string[];
}

export interface ModuleConfig {
    module_id: string;
    title: string;
    description: string | null;
    outcome: string | null;
    order_index: number;
    required: boolean;
    estimated_minutes: number | null;
    audience_rule: AudienceRule;
    prerequisites: string[];
    completion_policy: CompletionPolicy;
    activities: ActivityConfig[];
}

export interface PhaseConfig {
    phase_id: string;
    title: string;
    description: string | null;
    outcome: string | null;
    order_index: number;
    required: boolean;
    modules: ModuleConfig[];
}

export interface TrainingPathPayload {
    schema_version: "newcomer_training_orchestration_v1";
    title: string;
    description: string | null;
    phases: PhaseConfig[];
}

export interface PathIssue {
    code: string;
    message: string;
    object_id: string;
    field_path: string;
    severity: string;
}

export interface PathValidationResponse {
    can_publish: boolean;
    issues: PathIssue[];
}

export interface TrainingPathConfigResponse {
    active_revision_id: string | null;
    active_revision_no: number | null;
    working_revision_id: string | null;
    payload: TrainingPathPayload;
    validation: PathValidationResponse | null;
}

export interface AssetRevisionSummary {
    revision_id: string;
    resource_type: string;
    logical_id: string;
    revision_no: number;
    status: "working" | "published" | "archived";
    payload: TrainingPathPayload;
    payload_hash: string;
    change_class: string;
    source_revision_id: string | null;
    reason: string | null;
    trace_id: string | null;
    created_by: string | null;
    published_by: string | null;
    created_at: string | null;
    published_at: string | null;
}

export interface ActivityTypeDescriptor {
    type: ActivityType;
    label: string;
}

export interface CoachProfileOption {
    id: string;
    title: string;
    status: "published";
}

export interface ScoringRubricOption {
    id: string;
    title: string;
    status: "published";
}

export interface ScoringRubricCreateRequest {
    title: string;
    pass_score: number;
    dimensions: Array<{
        key: string;
        label: string;
        description?: string | null;
        weight: number;
    }>;
}

export type FoundationActivityType =
    | "lesson"
    | "quiz"
    | "audio_assessment"
    | "ai_coach"
    | "assignment";

export type FoundationActivityStatus =
    | "available"
    | "locked"
    | "in_progress"
    | "awaiting_review"
    | "completed"
    | "needs_remediation"
    | "retryable"
    | "invalidated";

export interface FoundationJourneyActivity {
    activity_id: string;
    type: FoundationActivityType;
    title: string;
    objective: string;
    status: FoundationActivityStatus;
    status_label: string;
    estimated_minutes: number;
    required: boolean;
    blocked_reason: string | null;
    latest_attempt_id: string | null;
    latest_outcome_id: string | null;
}

export interface FoundationJourneyStage {
    stage_id: string;
    sequence: number;
    title: string;
    objective: string;
    status: "locked" | "current" | "completed";
    activities: FoundationJourneyActivity[];
}

export interface FoundationJourneyProjection {
    contract_version: "journey_projection_v1";
    generated_at: string;
    data_freshness: "fresh" | "stale";
    capabilities: string[];
    status: "not_enrolled" | "active" | "blocked" | "awaiting_review" | "completed";
    status_label: string;
    status_reason: string | null;
    enrollment: {
        enrollment_id: string;
        status: string;
        revision_id: string;
        version: number;
    } | null;
    path: {
        path_id: string;
        title: string;
        revision_label: string;
    } | null;
    progress: {
        completed_required: number;
        total_required: number;
        percentage: number;
    };
    stages: FoundationJourneyStage[];
    current_activity: FoundationJourneyActivity | null;
    background_tasks: Array<Record<string, unknown>>;
    recent_outcomes: Array<{
        outcome_id: string;
        activity_id: string;
        activity_title: string;
        lifecycle_result: string;
        assessment_result: string | null;
        score: number | null;
        max_score: number | null;
        passed: boolean | null;
        produced_at: string;
        next_action: Record<string, unknown> | null;
    }>;
    primary_action: {
        command_type: string;
        activity_id: string;
        label: string;
        href: string;
    } | null;
    projection_version: number;
}

export type FoundationTaskState =
    | "queued"
    | "running"
    | "retry_wait"
    | "cancel_requested"
    | "cancelled"
    | "succeeded"
    | "dead_letter";

export interface FoundationTaskStatus {
    contract_version: "task_status_v1";
    task_id: string;
    title: string;
    state: FoundationTaskState;
    state_label: string;
    progress: {
        current: number | null;
        total: number | null;
        label: string;
    } | null;
    can_cancel: boolean;
    retry_after: string | null;
    result_location: string | null;
    result_path: string | null;
    error: { retryable: boolean; message: string } | null;
    updated_at: string;
}

export interface FoundationTaskStatusPage {
    contract_version: "task_status_page_v1";
    items: FoundationTaskStatus[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface FoundationNotificationItem {
    notification_id: string;
    notification_type: "system" | "tip" | "reminder" | "achievement" | "ai_coach";
    type_label: string;
    title: string;
    content: string;
    action_label: string | null;
    action_path: string | null;
    created_from: string;
    is_read: boolean;
    created_at: string;
}

export interface FoundationNotificationPage {
    contract_version: "notification_page_v1";
    items: FoundationNotificationItem[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface FoundationActivityAttempt {
    attempt_id: string;
    organization_id: string;
    enrollment_id: string;
    path_revision_id: string;
    activity_id: string;
    activity_type: FoundationActivityType;
    attempt_no: number;
    status: string;
    version: number;
    task_id: string | null;
    outcome_id: string | null;
}

interface FoundationLessonContentBlockBase {
    block_id: string;
    title: string;
    description: string | null;
    order: number;
    accessibility_alt: string;
}

interface FoundationSourceBackedLessonBlock extends FoundationLessonContentBlockBase {
    source_label: string;
    availability: "ready" | "external" | "unavailable";
    access?: {
        preview_page_template?: string;
        playback?: string;
        download?: string;
    };
}

export type FoundationLessonContentBlock =
    | (FoundationSourceBackedLessonBlock & {
        type: "rich_text";
        markdown: string;
    })
    | (FoundationSourceBackedLessonBlock & {
        type: "source_excerpt";
        excerpt: string;
    })
    | (FoundationSourceBackedLessonBlock & {
        type: "slide_deck";
        start_page: number;
        end_page: number | null;
        page_count: number | null;
    })
    | (FoundationSourceBackedLessonBlock & {
        type: "video";
        start_ms: number;
        end_ms: number | null;
        duration_ms: number | null;
        external_url?: string;
        embed_allowed?: false;
    })
    | (FoundationSourceBackedLessonBlock & {
        type: "audio_example";
        start_ms: number;
        end_ms: number | null;
        duration_ms: number | null;
    })
    | (FoundationSourceBackedLessonBlock & {
        type: "attachment";
        download_label: string;
        filename: string | null;
        file_size_bytes: number | null;
    })
    | (FoundationLessonContentBlockBase & {
        type: "checkpoint";
        prompt: string;
        required: boolean;
    });

export interface FoundationLessonRunner {
    kind: "lesson";
    detail_id: string;
    status: "not_started" | "in_progress" | "completed" | "invalidated";
    version: number;
    title: string;
    objectives: string[];
    key_concepts: Array<{
        concept_id: string;
        title: string;
        content: string;
        sources: string[];
    }>;
    examples: Array<{
        example_id: string;
        title: string;
        content: string;
        sources: string[];
    }>;
    content_blocks?: FoundationLessonContentBlock[];
    checkpoints: Array<{
        checkpoint_id: string;
        prompt: string;
        required: boolean;
    }>;
    practice_hints: string[];
    progress: {
        completed_checkpoint_ids: string[];
        reading_position: Record<string, unknown>;
        last_saved_at: string;
    } | null;
}

export interface FoundationQuizRunner {
    kind: "quiz";
    detail_id: string;
    status:
        | "not_started"
        | "in_progress"
        | "scoring_pending"
        | "needs_review"
        | "scored"
        | "invalidated";
    version: number;
    title: string;
    question_count: number;
    rules: {
        pass_threshold: number;
        max_attempts: number;
        retry_interval_seconds: number;
        feedback_policy: string;
        time_limit_minutes: number | null;
    };
    questions: Array<{
        question_revision_id: string;
        question_type: "single_choice" | "multiple_choice" | "true_false" | "short_answer";
        stem: string;
        options: Array<{ option_id: string; text: string }>;
        points: number;
    }>;
    answers: Array<{
        question_revision_id: string;
        selected_option_ids: string[];
        text_answer: string | null;
    }>;
    result: {
        score: number | null;
        max_score: number;
        passed: boolean | null;
    } | null;
}

export interface FoundationAudioUploadPart {
    part_number: number;
    upload_url: string;
    required_headers: Record<string, string>;
    uploaded: boolean;
    size_bytes: number;
    sha256: string;
}

export interface FoundationAudioUploadSession {
    upload_session_id: string;
    submission_id: string;
    state: "uploading" | "finalized" | "cancelled" | "expired";
    expires_at: string;
    part_size_bytes: number;
    expected_part_count: number;
    uploaded_part_count: number;
    parts: FoundationAudioUploadPart[];
}

export interface FoundationAudioSegmentResult {
    score: number;
    passed: boolean;
    dimension_scores: Array<{
        dimension_key: string;
        label?: string;
        score: number;
        uncertainty?: number;
    }>;
    evidence_spans: Array<{
        dimension_key: string;
        segment_sequence: number | null;
        quote: string;
        rationale: string;
    }>;
    missing_points: string[];
    feedback: string[];
    remediation: string[];
    critical_flags: string[];
    uncertainty: number;
}

export interface FoundationAudioTranscript {
    text: string;
    confidence: number;
    language: string;
    segments: Array<{
        sequence: number;
        start_ms: number;
        end_ms: number;
        text: string;
        confidence: number | null;
        speaker: string | null;
    }>;
}

export interface FoundationAudioRunner {
    kind: "audio_assessment" | "assignment";
    detail_id: string;
    run_id: string;
    status: string;
    version: number;
    rules: {
        allowed_recording_modes: Array<"browser" | "file">;
        allowed_content_types: string[];
        max_duration_seconds: number;
        max_size_bytes: number;
        part_size_bytes: number;
        local_draft_ttl_seconds: number;
        language: string;
        pass_score: number;
    };
    segments: Array<{
        submission_id: string;
        segment_id: string;
        title: string;
        prompt: string;
        customer_context: string | null;
        preparation_hints: string[];
        state: string;
        version: number;
        task_id: string | null;
        error: {
            retryable: boolean;
            message: string;
            failed_stage: string | null;
        } | null;
        transcript: FoundationAudioTranscript | null;
        quality: {
            scorable: boolean;
            flags: string[];
            metrics: Record<string, number | string | boolean | null>;
        } | null;
        result: FoundationAudioSegmentResult | null;
    }>;
    active_upload: FoundationAudioUploadSession | null;
    result: { score: number; passed: boolean } | null;
}

export type FoundationCoachCard =
    | {
        card_id: string;
        card_type: "single_choice" | "multiple_choice" | "scenario_choice";
        prompt: string;
        scenario?: string;
        options: Array<{ option_id: string; text: string }>;
        sources: string[];
    }
    | {
        card_id: string;
        card_type: "ordering";
        prompt: string;
        items: Array<{ item_id: string; text: string }>;
        sources: string[];
    }
    | {
        card_id: string;
        card_type: "short_answer_rewrite";
        prompt: string;
        instruction: string;
        sources: string[];
    }
    | {
        card_id: string;
        card_type: "key_points_completion";
        prompt: string;
        hints: string[];
        sources: string[];
    }
    | {
        card_id: string;
        card_type: "example_comparison";
        prompt: string;
        examples: string[];
        comparison_criteria: string[];
        sources: string[];
    }
    | {
        card_id: string;
        card_type: "summary";
        prompt: string;
        scope: string;
        sources: string[];
    };

export interface FoundationCoachRunner {
    kind: "ai_coach";
    detail_id: string;
    status:
        | "not_started"
        | "preparing"
        | "awaiting_answer"
        | "evaluating"
        | "feedback_ready"
        | "checkpoint_mastered"
        | "remediation_required"
        | "failed_recoverable"
        | "needs_human_help"
        | "completed"
        | "cancelled";
    version: number;
    profile_title: string;
    checkpoint: {
        current: number;
        total: number;
        title: string;
        objective?: string;
    };
    progress: { completed_cards: number; total_cards: number };
    source_context: Array<{
        label: string;
        resource_type: string;
    }>;
    weaknesses: Array<{
        competency_key: string;
        summary: string;
        confidence: number;
    }>;
    current_card: FoundationCoachCard | null;
    last_feedback: {
        card_id: string;
        mastered: boolean;
        evaluation_kind: "deterministic" | "ai";
        score_percent?: number;
        evidence_from_answer?: string[];
        missing_points?: string[];
        misconception?: string | null;
        feedback?: string;
        improvement_action?: string;
        next_suggestion?: string;
        uncertainty?: number;
    } | null;
    assistance: {
        status: "queued" | "completed" | "failed_recoverable";
        assistance_type: "explain" | "example";
        result: {
            explanation: string;
            uncertainty: number;
        } | null;
    } | null;
    mastery: {
        threshold_percent: number;
        cycle: number;
        maximum_automatic_cycles: number;
    };
    failure: {
        stage: string | null;
        message: string | null;
        answer_preserved: boolean;
    } | null;
    human_help: {
        title: string;
        message: string;
        status: "open" | "resolved";
        next_action: {
            type: string;
            guidance?: string | null;
            target_resource_id?: string | null;
        } | null;
    } | null;
}

export interface FoundationActivityWorkspace {
    contract_version: "activity_workspace_v1";
    generated_at: string;
    data_freshness: "fresh";
    capabilities: string[];
    enrollment_version: number;
    activity: {
        id: string;
        type: "lesson" | "quiz" | "audio_assessment" | "ai_coach" | "assignment";
        title: string;
        objective: string;
        why_it_matters: string;
        steps: string[];
        success_criteria: string[];
        estimated_minutes: number;
    };
    attempt: FoundationActivityAttempt | null;
    runner: FoundationLessonRunner | FoundationQuizRunner | FoundationAudioRunner | FoundationCoachRunner;
    task: { task_id: string; state: string } | null;
    outcome: {
        lifecycle_result: string;
        assessment_result: string | null;
        score: number | null;
        max_score: number | null;
        passed: boolean | null;
        next_action: Record<string, unknown> | null;
        produced_at: string;
    } | null;
    available_commands: string[];
    recovery: {
        input_preserved: boolean;
        refresh_on_version_conflict: boolean;
        retry_from_current_activity: boolean;
    };
}

export type FoundationActivityCommand =
    | {
        command_type: "start" | "start_relearn";
        attempt_id: null;
        expected_enrollment_version: number;
        expected_attempt_version: null;
        payload: { relearn_of_detail_id: string | null };
    }
    | {
        command_type: "save_progress";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: {
            completed_checkpoint_ids: string[];
            reading_position: Record<string, unknown>;
        };
    }
    | {
        command_type: "complete";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: Record<string, never>;
    }
    | {
        command_type: "save_answers";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: {
            answers: Array<{
                question_revision_id: string;
                selected_option_ids: string[];
                text_answer: string | null;
            }>;
        };
    }
    | {
        command_type: "submit";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: Record<string, never>;
    }
    | {
        command_type: "create_upload_session";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: {
            segment_id: string;
            recording_mode: "browser" | "file";
            original_filename: string;
            content_type: string;
            size_bytes: number;
            duration_seconds: number;
            manifest_sha256: string;
            parts: Array<{
                part_number: number;
                size_bytes: number;
                sha256: string;
            }>;
        };
    }
    | {
        command_type: "confirm_upload_part";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: {
            upload_session_id: string;
            part_number: number;
            size_bytes: number;
            sha256: string;
        };
    }
    | {
        command_type: "finalize_upload";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: { upload_session_id: string };
    }
    | {
        command_type: "retry_stage";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: { submission_id: string };
    }
    | {
        command_type: "cancel";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: Record<string, never>;
    }
    | {
        command_type: "submit_coach_answer";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: {
            card_id: string;
            client_token: string;
            answer:
                | { answer_type: "choice"; selected_option_ids: string[] }
                | { answer_type: "ordering"; ordered_item_ids: string[] }
                | { answer_type: "text"; text: string };
        };
    }
    | {
        command_type: "continue_coach" | "retry_coach";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: Record<string, never>;
    }
    | {
        command_type: "request_coach_assistance";
        attempt_id: string;
        expected_enrollment_version: null;
        expected_attempt_version: number;
        payload: {
            assistance_type: "explain" | "example";
            card_id: string;
        };
    };

export interface JourneyNextAction {
    activity_id: string;
    activity_type: ActivityType;
    action_key: string;
    label: string;
}

export interface JourneyActivityProgress {
    activity_id: string;
    activity_type: ActivityType;
    title: string;
    description: string | null;
    objective: string | null;
    why_it_matters: string | null;
    steps: string[];
    success_criteria: string[];
    primary_action_label: string | null;
    required: boolean;
    estimated_minutes: number | null;
    status: string;
    completed: boolean;
    passed: boolean | null;
    score: number | null;
    max_score: number | null;
    locked: boolean;
    lock_reason: string | null;
    action_key: string | null;
    is_primary_next_action: boolean;
}

export interface JourneyModuleProgress {
    module_id: string;
    title: string;
    description: string | null;
    outcome: string | null;
    required: boolean;
    estimated_minutes: number | null;
    status: string;
    completed: boolean;
    completed_count: number;
    total_required: number;
    percent: number;
    locked: boolean;
    lock_reason: string | null;
    activities: JourneyActivityProgress[];
}

export interface JourneyPhaseProgress {
    phase_id: string;
    title: string;
    description: string | null;
    outcome: string | null;
    required: boolean;
    status: string;
    completed: boolean;
    completed_count: number;
    total_required: number;
    percent: number;
    locked: boolean;
    lock_reason: string | null;
    modules: JourneyModuleProgress[];
}

export interface JourneyProgressSummary {
    completed: boolean;
    completed_count: number;
    total_required: number;
    percent: number;
}

export interface JourneyResponse {
    enrollment_id: string;
    path_revision_id: string;
    path_title: string;
    phases: JourneyPhaseProgress[];
    progress: JourneyProgressSummary;
    primary_next_action: JourneyNextAction | null;
}

export interface JourneyListCurrentPhase {
    phase_id: string;
    title: string;
    status: string;
}

export interface JourneyListSummary {
    path_revision_id: string;
    path_title: string;
    current_phase: JourneyListCurrentPhase | null;
    progress: JourneyProgressSummary;
    primary_next_action: JourneyNextAction | null;
    risk_labels: string[];
}

export interface AdminJourneyItem {
    learner_id: string;
    learner_name: string;
    team: { team_id: string; code: string; name: string } | null;
    summary: JourneyListSummary;
}

export interface AdminJourneyListResponse {
    items: AdminJourneyItem[];
    total: number;
}

export interface ModuleDetailResponse {
    enrollment_id: string;
    path_revision_id: string;
    phase_id: string;
    module: JourneyModuleProgress;
}

export interface ActivityDetailResponse {
    enrollment_id: string;
    path_revision_id: string;
    phase_id: string;
    module_id: string;
    activity: JourneyActivityProgress;
    runner: ActivityRunnerDescriptor;
}

export type ActivityRunnerDescriptor =
    | { type: "lesson"; learning_content_id: string; completion_mode: "all_chapters" | "learner_confirmed" }
    | { type: "quiz"; exam_paper_id: string; pass_score: number; max_attempts: number | null }
    | {
        type: "audio_assessment";
        material_id: string | null;
        material_version_id: string | null;
        material_title: string | null;
        material_version_label?: string | null;
        material_file_name?: string | null;
        material_content_type?: string | null;
        scoring_rubric_revision_id?: string | null;
        scoring_rubric_revision_no?: number | null;
        scoring_rubric_title?: string | null;
        scoring_focuses?: Array<{
            label: string;
            description: string | null;
            weight: number | null;
        }>;
        example_transcript?: string | null;
        pass_score: number;
        max_attempts: number | null;
    }
    | {
        type: "realtime_roleplay";
        configuration_ready: boolean;
        configuration_message: string | null;
        template_title: string | null;
        template_description: string | null;
        template_version: number | null;
        scenario: string | null;
        counterpart_role: string | null;
        counterpart_style: string | null;
        goals: string[];
        scoring_title: string | null;
        scoring_description: string | null;
        scoring_version: string | null;
        scoring_focuses: Array<{
            label: string;
            description: string | null;
            weight: number | null;
        }>;
        passing_score: number | null;
    }
    | { type: "ai_coach" }
    | { type: "assignment"; submission_type: "text" | "file" | "text_or_file"; review_mode: "automatic_complete" | "manual_review"; max_file_size_bytes: number };

export interface ClientTokenRequest {
    client_token: string;
}

export interface QuizAnswerRequest {
    question_id: string;
    answer_payload: unknown;
}

export interface QuizAttemptRequest extends ClientTokenRequest {
    answers: QuizAnswerRequest[];
}

export interface AudioSubmissionRequest extends ClientTokenRequest {
    file: File;
    confirmed_material_version_id?: string | null;
    confirmed_scoring_rubric_revision_id?: string | null;
}

export interface AssignmentSubmissionRequest extends ClientTokenRequest {
    text?: string | null;
    file?: File | null;
}

export interface RealtimeStartResponse {
    session_id: string;
    detail: ActivityDetailResponse;
}

export interface AiCoachStartResponse {
    session_id: string;
    first_question: string;
    detail: ActivityDetailResponse;
}

export interface AiCoachTurnResponse {
    session_id: string;
    status: string;
    mastery_state: string | null;
    feedback: string | null;
    next_question: string | null;
    detail: ActivityDetailResponse;
}

export type AiCoachTurnStreamEvent =
    | { type: "started" }
    | ({ type: "result" } & AiCoachTurnResponse)
    | { type: "error"; message: string };

export type ReadinessCompetencyStatus = "sufficient" | "gap" | "quality_review" | "missing";

export interface ReadinessCompetencyProjection {
    competency_key: string;
    title: string;
    description: string;
    status: ReadinessCompetencyStatus;
    latest_result: string | null;
    latest_score: number | null;
    latest_max_score: number | null;
    trend: "improving" | "declining" | "stable" | "insufficient_data";
    source_coverage: string[];
    evidence_count: number;
    valid_evidence_count: number;
    evidence_ids: string[];
    gap_reason: string | null;
    review_prerequisite_met: boolean;
}

export interface ReadinessEvidenceProjection {
    evidence_id: string;
    competency_key: string;
    competency_title: string;
    source_activity_id: string;
    outcome_id: string;
    outcome_version: number;
    evidence_type: string;
    observed_score: number | null;
    observed_max_score: number | null;
    observed_result: string | null;
    quality: string;
    validity: string;
    observed_at: string;
}

export interface ReadinessEligibilityProjection {
    eligible: boolean;
    required_activities_complete: boolean;
    competencies_sufficient: boolean;
    no_blocking_tasks: boolean;
    no_unresolved_quality_conflicts: boolean;
    missing_activity_ids: string[];
    competency_gaps: string[];
    quality_conflict_evidence_ids: string[];
    reasons: string[];
}

export interface ReadinessDecisionProjection {
    decision_id: string;
    snapshot_id: string;
    decision_type: string;
    decision_label: string;
    status: string;
    reviewer_id: string;
    competency_keys: string[];
    evidence_ids: string[];
    reason: string;
    notes?: string | null;
    created_at: string;
    supersedes_decision_id: string | null;
}

export interface ReadinessRetrainingProjection {
    assignment_id: string;
    activity_source: "existing_published" | "quick_draft";
    activity_id: string | null;
    activity_title: string;
    target_competency_keys: string[];
    source_evidence_ids: string[];
    reason: string;
    due_at: string | null;
    status: string;
    version: number;
    assigned_at: string;
    completed_at: string | null;
    next_action: { label: string; href: string | null } | null;
}

export interface ReadinessAppealProjection {
    appeal_id: string;
    target_type: "evidence" | "decision" | "transcript" | "score";
    target_id: string;
    reason_category: "audio_quality" | "transcript_error" | "score_error" | "fact_error";
    statement: string;
    status: string;
    assigned_to: string | null;
    resolution: string | null;
    version: number;
    created_at: string;
    updated_at: string;
    resolved_at: string | null;
}

export interface ReadinessExceptionPreviewV1 {
    contract_version: "readiness_exception_preview_v1";
    preview_id: string;
    dossier_id: string;
    snapshot_id: string;
    dossier_version: number;
    status: "previewed" | "consumed" | "expired";
    impact: {
        contract_version: "readiness_exception_impact_v1";
        decision_type: "exception_approved";
        eligibility: ReadinessEligibilityProjection;
        risk_band: "low" | "medium" | "high" | null;
        risk_reasons: string[];
        overridden_competency_gaps: string[];
        quality_conflict_evidence_ids: string[];
        competency_keys: string[];
        evidence_ids: string[];
        reason: string;
        notes_present: boolean;
    };
    impact_hash: string;
    preview_token: string;
    expires_at: string;
    consumed_at: string | null;
}

export interface EvidenceDossierV1 {
    contract_version: "1";
    generated_at: string;
    data_freshness: "fresh" | "stale";
    capabilities: string[];
    dossier_id: string;
    dossier_version: number;
    snapshot_id: string;
    snapshot_version: number;
    snapshot_stale: boolean;
    learner: { learner_id: string; name: string; cohort_id: string; cohort_name: string | null };
    path: { path_revision_id: string; title: string; revision_label: string };
    status: string;
    status_label: string;
    summary: {
        eligibility: ReadinessEligibilityProjection;
        completed_required_activities: number;
        total_required_activities: number;
        evidence_count: number;
        stale_reason: string | null;
        risk_band?: "low" | "medium" | "high";
        risk_reasons?: string[];
    };
    competencies: ReadinessCompetencyProjection[];
    evidence: ReadinessEvidenceProjection[];
    activities: Array<{
        activity_id: string;
        activity_type: string;
        title: string;
        required: boolean;
        status: string;
        latest_attempt_id: string | null;
        latest_outcome_id: string | null;
        latest_outcome_version: number | null;
        latest_outcome_at: string | null;
        processing: boolean;
    }>;
    ai_assessment: {
        status: string;
        label: string;
        message?: string | null;
        draft?: Record<string, unknown> | null;
        evidence_ids?: string[];
    };
    human_decision: ReadinessDecisionProjection | null;
    decision_history: ReadinessDecisionProjection[];
    retraining: ReadinessRetrainingProjection[];
    appeals: ReadinessAppealProjection[];
    next_actions: Array<{ label: string; href?: string | null; command?: string }>;
}

export interface ReadinessAppealCreateRequest {
    target_type: "evidence" | "decision" | "transcript" | "score";
    target_id: string;
    dossier_version: number;
    reason_category: "audio_quality" | "transcript_error" | "score_error" | "fact_error";
    statement: string;
}

export interface ReadinessReviewQueueV1 {
    contract_version: "1";
    generated_at: string;
    data_freshness: "fresh" | "stale";
    capabilities: string[];
    items: Array<{
        object_id: string;
        object_summary: {
            learner: EvidenceDossierV1["learner"];
            path: EvidenceDossierV1["path"];
            status: string;
        };
        queue_reason: string;
        risk_band: "low" | "medium" | "high";
        evidence_gaps: string[];
        reviewer_id: string | null;
        due_at: string | null;
        primary_action: { label: string; href: string };
        capabilities: string[];
        updated_at: string;
    }>;
    total: number;
    limit: number;
    offset: number;
    applied_filters?: {
        state: string | null;
        cohort_id: string | null;
        competency_key: string | null;
        reviewer_id: string | null;
        waiting_hours_gte: number | null;
    };
    sort?: string[];
}
