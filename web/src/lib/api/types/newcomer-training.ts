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
}

export interface RealtimeRoleplayConfig {
    practice_template_id: string;
    runtime_profile_id: string;
    completion_mode: "session_completed" | "scored";
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
    required: boolean;
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
    required: boolean;
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

export interface AdminJourneyItem {
    learner_id: string;
    learner_name: string;
    department: string;
    journey: JourneyResponse;
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
    | { type: "audio_assessment"; material_id: string | null; material_version_id: string | null; material_title: string | null; pass_score: number; max_attempts: number | null }
    | { type: "realtime_roleplay" }
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
