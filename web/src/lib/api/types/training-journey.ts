/** Journey, Readiness, realtime-entry, and analytics transport contracts. */

type TrainingJourneyAdminCapabilityKey =
    | "admin_full_access" | "manage_content" | "manage_questions" | "manage_modules"
    | "manage_prompts" | "view_records" | "view_global_records" | "retry_jobs"
    | "regrade_history" | "view_logs" | "view_settings";

type TrainingJourneyConfiguredModuleType =
    | "audio_scoring" | "article_exam" | "audio_scoring_group" | "realtime_placeholder";

type TrainingJourneyCompletionRule = "passed" | "scored" | "submitted";

type TrainingJourneyAiCoachInteractionType =
    | "single_choice" | "multiple_choice" | "short_answer";

interface TrainingJourneyAiCoachAvailability {
    enabled: boolean;
    configured: boolean;
    available: boolean;
    coach_path: string | null;
    disabled_reason: string | null;
    allowed_interaction_types: TrainingJourneyAiCoachInteractionType[];
}

export type TrainingJourneyStage =
    | "not_started"
    | "in_progress"
    | "waiting_upload"
    | "processing"
    | "scored"
    | "passed"
    | "failed"
    | "needs_remediation"
    | "manual_review"
    | "disabled"
    | "archived"
    | "error_terminal"
    | "error_transient";

export type TrainingJourneyLearnerLevelSource =
    "user_profile" | "org_rule" | "admin_assignment" | "training_projection";

export interface TrainingJourneyLearnerLevel {
    level_key: string;
    label: string;
    source: TrainingJourneyLearnerLevelSource;
    rank: number;
    effective_from?: string | null;
    effective_to?: string | null;
    config_revision_id?: string | null;
    description?: string | null;
    fallback_applied?: boolean;
    fallback_reason?: string | null;
    policy_key?: string | null;
    policy_version?: string | null;
    management_entry?: string | null;
}

export type TrainingJourneyRoleCapabilityKey =
    | TrainingJourneyAdminCapabilityKey
    | "learner_enter"
    | "learner_submit"
    | "learner_view_own_records"
    | "sales_trainer.enter_realtime";

export interface TrainingJourneyRoleCapability {
    capability_key: TrainingJourneyRoleCapabilityKey;
    allowed: boolean;
    scope: "own" | "team" | "global" | "none";
    reason_code?: string | null;
}

export interface TrainingJourneyDiagnostic {
    code: string;
    message: string;
    severity: "info" | "warning" | "error";
    terminal: boolean;
}

export type TrainingJourneyModuleType =
    TrainingJourneyConfiguredModuleType | "ai_coach" | "realtime_roleplay";

export type TrainingJourneyModuleKind =
    "audio_submission" | "quiz_attempt" | "ai_coach" | "realtime_roleplay";

export type TrainingJourneyModuleOutcomeRecordType =
    | "audio_submission"
    | "quiz_attempt"
    | "business_etiquette_quiz_attempt"
    | "ai_coach_session"
    | "realtime_roleplay_session"
    | "remediation"
    | "regrade";

export interface TrainingJourneyModuleOutcomeSnapshotRef {
    snapshot_type:
        | "path_revision"
        | "submission_snapshot"
        | "attempt_snapshot"
        | "session_snapshot"
        | "runtime_outcome_snapshot"
        | "regrade_snapshot";
    legacy_snapshot_only: boolean;
    regrade_unavailable?: boolean;
}

export interface TrainingJourneyModuleOutcomeEvidence {
    record_id: string;
    record_type: TrainingJourneyModuleOutcomeRecordType;
    occurred_at?: string | null;
}

export interface TrainingJourneyModuleOutcome {
    outcome_id: string;
    record_type: TrainingJourneyModuleOutcomeRecordType;
    source_record_id: string;
    module_key: string;
    module_type: TrainingJourneyModuleType;
    status: TrainingJourneyStage;
    score?: number | null;
    max_score?: number | null;
    passed?: boolean | null;
    failure_type?: "terminal" | "transient" | "voluntary" | null;
    failure_code?: string | null;
    submitted_at?: string | null;
    completed_at?: string | null;
    path_revision_id: string;
    path_revision_no: number;
    snapshot_ref: TrainingJourneyModuleOutcomeSnapshotRef;
    evidence?: TrainingJourneyModuleOutcomeEvidence;
}

export interface TrainingJourneyModuleUnmetReason {
    code: string;
    message: string;
    severity?: "info" | "warning" | "error";
    terminal: boolean;
}

export interface TrainingJourneyModuleNextAction {
    action_key: string;
    label: string;
    target_path?: string | null;
    disabled: boolean;
    disabled_reason?: string | null;
}

export interface TrainingJourneyModuleProgress {
    module_key: string;
    title?: string;
    kind?: TrainingJourneyModuleKind;
    module_type: TrainingJourneyModuleType;
    display_name: string;
    order_index: number;
    target_unit_id?: string | null;
    target_unit_ids?: string[];
    learning_content_id?: string | null;
    exam_paper_id?: string | null;
    enabled: boolean;
    status?: TrainingJourneyStage;
    stage: TrainingJourneyStage;
    passed?: boolean | null;
    score?: number | null;
    max_score?: number | null;
    required?: boolean;
    completion_satisfied?: boolean;
    locked?: boolean;
    block_reason?: string | null;
    completion_rule: TrainingJourneyCompletionRule;
    source?: {
        path_revision_id: string;
        path_revision_no: number;
    };
    learner_level_required?: string[] | null;
    unmet_reasons: TrainingJourneyModuleUnmetReason[];
    diagnostics?: TrainingJourneyDiagnostic[];
    next_action?: TrainingJourneyModuleNextAction | null;
    latest_outcome?: TrainingJourneyModuleOutcome | null;
    outcome_history: TrainingJourneyModuleOutcome[];
}

export interface TrainingJourneyOverallProgress {
    total_modules: number;
    completed_modules: number;
    passed_modules: number;
    failed_modules: number;
    needs_remediation_modules: number;
}

export interface TrainingJourneyRetrainingTargetModule {
    module_key: string | null;
    title: string | null;
    kind: string | null;
    module_type: string | null;
    status: string | null;
    action_label: string | null;
    target_path: string | null;
    disabled: boolean;
    disabled_reason: string | null;
}

export interface TrainingJourneyRetrainingRequest {
    request_id: string;
    task_id: string;
    status: string;
    reason: string | null;
    capability_keys: string[];
    capability_labels: string[];
    source_evidence_count: number;
    target_modules: TrainingJourneyRetrainingTargetModule[];
    primary_target_path: string | null;
    created_at: string;
}

export interface TrainingJourneyLearningTopicUnitProgress {
    unit_key: string;
    title: string;
    order_index: number;
    enabled: boolean;
    capability_keys: string[];
    require_quiz: boolean;
    quiz_question_count: number;
    quiz_pass_threshold: number | null;
    score: number | null;
    max_score: number | null;
    passed: boolean | null;
    status: "not_started" | "submitted" | "scored" | "passed" | "failed";
    latest_attempt_id: string | null;
    latest_attempt_submitted_at: string | null;
}

export interface TrainingJourneyLearningTopicProgress {
    topic_key: string;
    source_module_key: string;
    title: string;
    description: string | null;
    order_index: number;
    learning_content_id: string | null;
    required: false;
    blocks_next: false;
    score_display_policy: "quiz_attempt_score";
    status: "not_started" | "in_progress" | "passed" | "needs_remediation";
    units: TrainingJourneyLearningTopicUnitProgress[];
    ai_coach: TrainingJourneyAiCoachAvailability | null;
    source: Record<string, unknown>;
}

export interface TrainingJourneyResponse {
    journey_id: string;
    learner_id: string;
    learner_name?: string | null;
    team?: {
        team_id: string;
        code: string;
        name: string;
    } | null;
    path_key: "newcomer_training_path_v1";
    path_revision_id: string;
    path_revision_no: number;
    source: "active_revision";
    legacy_snapshot_only: false;
    role_capabilities: TrainingJourneyRoleCapability[];
    learner_level: TrainingJourneyLearnerLevel;
    role_level: TrainingJourneyLearnerLevel;
    training_stage: TrainingJourneyStage;
    modules: TrainingJourneyModuleProgress[];
    learning_topics: TrainingJourneyLearningTopicProgress[];
    overall_progress: TrainingJourneyOverallProgress;
    retraining_requests: TrainingJourneyRetrainingRequest[];
    diagnostics: TrainingJourneyDiagnostic[];
    generated_at: string;
}

export type ReadinessDossierStatus =
    | "not_started"
    | "in_training"
    | "ai_evaluating"
    | "needs_remediation"
    | "pending_review"
    | "approved"
    | "rejected"
    | "manual_follow_up"
    | "blocked_by_config";

export type ReadinessCapabilityStatus =
    | "not_trained"
    | "ai_passed"
    | "ai_failed"
    | "needs_retraining"
    | "pending_review"
    | "approved"
    | "rejected"
    | "blocked_by_config";

export type ReadinessReviewDecision = "approve" | "require_retraining" | "mark_manual_follow_up";

export type ReadinessWorkbenchGroupKey =
    | "pending_review"
    | "not_passed"
    | "needs_retraining"
    | "approved"
    | "config_exception"
    | "in_training";

export interface ReadinessDossierLearner {
    learner_id: string;
    name: string | null;
    team: { team_id: string; code: string; name: string } | null;
}

export interface ReadinessDossierPath {
    path_key: string | null;
    path_revision_id: string | null;
    path_revision_no: number | null;
    source: string | null;
}

export interface ReadinessDossierModuleNextAction {
    label: string | null;
    target_path: string | null;
    disabled: boolean;
    disabled_reason: string | null;
}

export interface ReadinessDossierModuleSummary {
    module_key: string | null;
    title: string | null;
    kind: string | null;
    module_type: string | null;
    order_index: number | null;
    status: string | null;
    passed: boolean | null;
    score: number | null;
    max_score: number | null;
    required: boolean | null;
    completion_satisfied: boolean | null;
    locked: boolean | null;
    block_reason: string | null;
    capability_keys: string[];
    evidence_ids: string[];
    next_action: ReadinessDossierModuleNextAction | null;
}

export interface ReadinessDossierEvidence {
    evidence_id: string;
    evidence_type: string;
    source_record_id: string;
    record_type: string;
    module_key: string | null;
    module_title: string | null;
    module_type: string | null;
    capability_keys: string[];
    status: string | null;
    score: number | null;
    max_score: number | null;
    passed: boolean | null;
    submitted_at: string | null;
    completed_at: string | null;
    target_path: string | null;
    material_snapshot: Record<string, unknown> | null;
    scoring_snapshot: Record<string, unknown> | null;
    task_brief_snapshot: Record<string, unknown> | null;
    snapshot_ref: Record<string, unknown> | null;
    result_summary: string | null;
}

export interface ReadinessDossierCompetency {
    capability_key: string;
    display_name: string;
    description: string | null;
    status: ReadinessCapabilityStatus;
    score: number | null;
    max_score: number | null;
    weak: boolean;
    evidence_ids: string[];
    latest_evidence_id: string | null;
    review_decision: string | null;
    reason: string | null;
}

export interface ReadinessDossierRetrainingTaskComparison {
    before_evidence_ids: string[];
    after_evidence_ids: string[];
    after_status?: string | null;
    after_passed?: boolean | null;
    after_score?: number | null;
    after_max_score?: number | null;
    [key: string]: unknown;
}

export interface ReadinessDossierRetrainingTask {
    task_id: string;
    status: string;
    source?: string | null;
    capability_keys: string[];
    source_evidence_ids: string[];
    target_learner_id?: string | null;
    completed_at?: string | null;
    completed_evidence_ids?: string[];
    comparison?: ReadinessDossierRetrainingTaskComparison | null;
    [key: string]: unknown;
}

export interface ReadinessDossierReviewAction {
    action_id: string;
    audit_log_id: string;
    decision: ReadinessReviewDecision;
    decision_label: string;
    reason: string | null;
    capability_keys: string[];
    source_evidence_ids: string[];
    reviewer_id: string | null;
    reviewer_role: string | null;
    created_at: string;
    retraining_task: ReadinessDossierRetrainingTask | null;
    state_storage: "operation_log";
}

export interface ReadinessDossierReviewActionCreateRequest {
    decision: ReadinessReviewDecision;
    reason: string;
    capability_keys: string[];
    source_evidence_ids: string[];
}

export interface ReadinessDossierRealtimeGate {
    module_key: string | null;
    status: string | null;
    locked: boolean;
    reason: string | null;
    training_gate_status: ReadinessDossierStatus;
    provider_readiness: Record<string, unknown> | null;
}

export interface ReadinessDossierNextAction {
    action_key: string;
    label: string;
    target_path: string | null;
    primary: boolean;
    capability_keys?: string[];
}

export interface ReadinessDossierSummary {
    total_modules: number;
    completed_modules: number;
    passed_modules: number;
    failed_modules: number;
    needs_remediation_modules: number;
    evidence_count: number;
    review_action_count: number;
    weak_capability_count: number;
    retraining_task_count: number;
    completed_retraining_task_count: number;
    review_state_source: "operation_log";
    [key: string]: unknown;
}

export interface ReadinessDossier {
    contract_version: "readiness_dossier_v1";
    learner: ReadinessDossierLearner;
    path: ReadinessDossierPath;
    status: ReadinessDossierStatus;
    status_label: string;
    status_reason: string;
    summary: ReadinessDossierSummary;
    modules: ReadinessDossierModuleSummary[];
    competencies: ReadinessDossierCompetency[];
    evidence: ReadinessDossierEvidence[];
    review_actions: ReadinessDossierReviewAction[];
    latest_review_action: ReadinessDossierReviewAction | null;
    retraining_tasks: ReadinessDossierRetrainingTask[];
    realtime_gate: ReadinessDossierRealtimeGate;
    diagnostics: TrainingJourneyDiagnostic[];
    next_actions: ReadinessDossierNextAction[];
    generated_at: string;
}

export interface ReadinessWorkbenchItem {
    learner: ReadinessDossierLearner;
    status: ReadinessDossierStatus;
    status_label: string;
    status_reason: string;
    path: ReadinessDossierPath;
    weak_capability_keys: string[];
    weak_capability_labels: string[];
    evidence_count: number;
    latest_review_action: ReadinessDossierReviewAction | null;
    next_action: ReadinessDossierNextAction | null;
    target_path: string | null;
}

export interface ReadinessWorkbenchGroup {
    group_key: ReadinessWorkbenchGroupKey;
    label: string;
    count: number;
    items: ReadinessWorkbenchItem[];
}

export interface ReadinessWorkbenchSummary {
    learner_count: number;
    loaded_learner_count: number;
    pending_review_count: number;
    not_passed_count: number;
    needs_retraining_count: number;
    approved_count: number;
    config_exception_count: number;
    in_training_count: number;
}

export interface ReadinessWorkbenchResponse {
    contract_version: "readiness_dossier_v1";
    generated_at: string;
    groups: Record<ReadinessWorkbenchGroupKey, ReadinessWorkbenchGroup>;
    summary: ReadinessWorkbenchSummary;
    filters: {
        limit: number;
        offset: number;
    };
}

export interface RealtimeRoleplayStartRequest {
    module_key?: "realtime_roleplay";
}

export interface RealtimeRoleplayProviderReadinessSnapshot {
    provider: "stepfun_realtime" | "legacy" | "mock";
    ready: boolean;
    checked_at: string;
    config_revision_id?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
}

export interface RealtimeRoleplayRegistryReadinessSnapshot {
    ready: boolean;
    checked_at?: string | null;
    failure_code?: string | null;
    failure_message?: string | null;
}

export interface RealtimeRoleplayRegistryDescriptorSnapshot {
    descriptor_id: string;
    label?: string | null;
    provider: "stepfun_realtime" | "phase4_local_stepfun" | "mock";
    runtime_owner: "training_runtime" | "sales_bot";
    enabled: boolean;
    runtime_profile_id?: string | null;
    config_revision_id?: string | null;
    rollback_to_descriptor_id?: string | null;
    readiness: RealtimeRoleplayRegistryReadinessSnapshot;
}

export interface RealtimeRoleplayRuntimeRegistrySnapshot {
    registry_key: "sales_trainer.realtime_provider.registry";
    config_id?: string | null;
    version?: number | null;
    source: string;
    status?: string | null;
    fallback_reason?: string | null;
    descriptor: RealtimeRoleplayRegistryDescriptorSnapshot;
}

export interface RealtimeRoleplayFailurePolicySnapshot {
    terminal_codes: string[];
    transient_codes: string[];
    voluntary_codes: string[];
    terminal_retry_allowed: false;
}

export interface RealtimeRoleplayExternalBindingSnapshot {
    owner: "sales_trainer";
    path_key: "newcomer_training_path_v1";
    path_revision_id: string;
    path_revision_no: number;
    module_key: "realtime_roleplay";
    binding_key: "newcomer_realtime_roleplay_v1";
    runtime_descriptor_id: string;
    scenario_key: string;
    runtime_config_revision_id: string;
    runtime_registry: RealtimeRoleplayRuntimeRegistrySnapshot;
    roleplay_contract_revision_id?: string | null;
    practice_template_id: string;
    provider_readiness_snapshot: RealtimeRoleplayProviderReadinessSnapshot;
    failure_policy: RealtimeRoleplayFailurePolicySnapshot;
    started_by_user_id: string;
    started_at: string;
}

export interface RealtimeRoleplayStartResponse {
    session_id: string;
    module_key: "realtime_roleplay";
    path_key: "newcomer_training_path_v1";
    path_revision_id: string;
    path_revision_no: number;
    practice_url: string;
    runtime_descriptor_id: string;
    runtime_registry: RealtimeRoleplayRuntimeRegistrySnapshot;
    provider_readiness_snapshot: RealtimeRoleplayProviderReadinessSnapshot;
    external_binding: RealtimeRoleplayExternalBindingSnapshot;
}
