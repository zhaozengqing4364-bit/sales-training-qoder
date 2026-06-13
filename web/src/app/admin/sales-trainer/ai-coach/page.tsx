"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Save, Send, Sparkles } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AiCoachAdminConfigLike } from "@/lib/api/client-domains";

type CoachMode = "single_choice_drill" | "multiple_choice_drill" | "short_answer_drill" | "mixed_drill";
type InteractionType = "single_choice" | "multiple_choice" | "short_answer";
type UiEventType = "quiz_card" | "explanation_card" | "summary_card" | "followup_prompt";
type SessionStartBehavior = "welcome_only" | "plan_then_wait" | "plan_and_first_card";
type RemediationStrategy = "explain_then_retry" | "ask_user_choice" | "simplify_then_retry";
type EntryResumePolicy = "latest_active_or_new" | "latest_in_progress" | "new";
type NextAction =
    | "continue_drill"
    | "increase_difficulty"
    | "remediate"
    | "switch_scenario"
    | "summarize"
    | "ask_user_choice"
    | "end_session";

const COACH_MODE_OPTIONS: ReadonlyArray<{ value: CoachMode; label: string }> = [
    { value: "single_choice_drill", label: "单选题训练" },
    { value: "multiple_choice_drill", label: "多选题训练" },
    { value: "short_answer_drill", label: "简答题训练" },
    { value: "mixed_drill", label: "混合训练" },
];

const INTERACTION_TYPE_OPTIONS: ReadonlyArray<{ value: InteractionType; label: string }> = [
    { value: "single_choice", label: "单选题" },
    { value: "multiple_choice", label: "多选题" },
    { value: "short_answer", label: "简答题" },
];

const UI_EVENT_TYPE_OPTIONS: ReadonlyArray<{ value: UiEventType; label: string }> = [
    { value: "quiz_card", label: "互动卡片" },
    { value: "explanation_card", label: "解析卡片" },
    { value: "summary_card", label: "复盘卡片" },
    { value: "followup_prompt", label: "追问卡片" },
];

const SESSION_START_BEHAVIOR_OPTIONS: ReadonlyArray<{ value: SessionStartBehavior; label: string }> = [
    { value: "welcome_only", label: "只显示欢迎语" },
    { value: "plan_then_wait", label: "计划后等待" },
    { value: "plan_and_first_card", label: "计划并出首题" },
];

const REMEDIATION_STRATEGY_OPTIONS: ReadonlyArray<{ value: RemediationStrategy; label: string }> = [
    { value: "explain_then_retry", label: "解释后重练" },
    { value: "ask_user_choice", label: "让学员选择" },
    { value: "simplify_then_retry", label: "简化后重练" },
];

const ENTRY_RESUME_POLICY_OPTIONS: ReadonlyArray<{ value: EntryResumePolicy; label: string }> = [
    { value: "latest_active_or_new", label: "只恢复可作答局，否则新开" },
    { value: "latest_in_progress", label: "恢复最近未结束会话" },
    { value: "new", label: "每次都新开" },
];

const NEXT_ACTION_OPTIONS: ReadonlyArray<{ value: NextAction; label: string }> = [
    { value: "continue_drill", label: "继续训练" },
    { value: "increase_difficulty", label: "提高难度" },
    { value: "remediate", label: "补救讲解" },
    { value: "switch_scenario", label: "切换场景" },
    { value: "summarize", label: "阶段复盘" },
    { value: "ask_user_choice", label: "让学员选择" },
    { value: "end_session", label: "结束会话" },
];

function isCoachMode(value: string): value is CoachMode {
    return COACH_MODE_OPTIONS.some((option) => option.value === value);
}

function isInteractionType(value: string): value is InteractionType {
    return INTERACTION_TYPE_OPTIONS.some((option) => option.value === value);
}

function isUiEventType(value: string): value is UiEventType {
    return UI_EVENT_TYPE_OPTIONS.some((option) => option.value === value);
}

function isSessionStartBehavior(value: string): value is SessionStartBehavior {
    return SESSION_START_BEHAVIOR_OPTIONS.some((option) => option.value === value);
}

function isRemediationStrategy(value: string): value is RemediationStrategy {
    return REMEDIATION_STRATEGY_OPTIONS.some((option) => option.value === value);
}

function isEntryResumePolicy(value: string): value is EntryResumePolicy {
    return ENTRY_RESUME_POLICY_OPTIONS.some((option) => option.value === value);
}

function isNextAction(value: string): value is NextAction {
    return NEXT_ACTION_OPTIONS.some((option) => option.value === value);
}

interface AiCoachAdminConfig {
    enabled: boolean;
    chat_enabled: boolean;
    streaming_enabled: boolean;
    entry_resume_policy: EntryResumePolicy;
    generation_timeout_seconds: number;
    coach_mode: CoachMode;
    allowed_interaction_types: InteractionType[];
    allowed_ui_event_types: UiEventType[];
    max_cards_per_message: number;
    proactive_coaching_enabled: boolean;
    session_start_behavior: SessionStartBehavior;
    auto_advance_enabled: boolean;
    max_auto_steps_per_session: number;
    correct_streak_to_increase_difficulty: number;
    incorrect_streak_to_remediate: number;
    incorrect_streak_to_pause: number;
    remediation_strategy: RemediationStrategy;
    summary_when_mastery_reached: boolean;
    allowed_next_actions: NextAction[];
    chat_welcome_message: string;
    empty_response_recovery_message: string;
    empty_response_recovery_prompts: string[];
    generation_failure_recovery_message: string;
    generation_failure_recovery_prompts: string[];
    min_turns: number;
    max_turns: number;
    mastery_threshold: number;
    prompt_template_id: string | null;
    prompt_revision_id: string | null;
    prompt_contract_hash: string | null;
    scoring_prompt_template_id: string | null;
    scoring_prompt_revision_id: string | null;
    scoring_contract_hash: string | null;
    output_schema_version: string;
    [key: string]: unknown;
}

interface ConfigResponse {
    module_key: string;
    ai_coach: AiCoachAdminConfig;
}

const DEFAULT_CONFIG: AiCoachAdminConfig = {
    enabled: false,
    chat_enabled: true,
    streaming_enabled: true,
    entry_resume_policy: "latest_active_or_new",
    generation_timeout_seconds: 30,
    coach_mode: "mixed_drill",
    allowed_interaction_types: ["single_choice", "multiple_choice"],
    allowed_ui_event_types: ["quiz_card", "explanation_card", "summary_card", "followup_prompt"],
    max_cards_per_message: 3,
    proactive_coaching_enabled: false,
    session_start_behavior: "welcome_only",
    auto_advance_enabled: false,
    max_auto_steps_per_session: 5,
    correct_streak_to_increase_difficulty: 2,
    incorrect_streak_to_remediate: 1,
    incorrect_streak_to_pause: 2,
    remediation_strategy: "explain_then_retry",
    summary_when_mastery_reached: true,
    allowed_next_actions: [
        "continue_drill",
        "increase_difficulty",
        "remediate",
        "switch_scenario",
        "summarize",
        "ask_user_choice",
        "end_session",
    ],
    chat_welcome_message: "你好，我是商务技巧 AI 教练。你可以直接说想练什么，我会把练习卡片放在对话里。",
    empty_response_recovery_message: "我没有拿到可操作的训练卡片。你可以继续下一题、换个场景，或先总结本轮。",
    empty_response_recovery_prompts: ["继续下一题", "换个场景", "总结本轮"],
    generation_failure_recovery_message: "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。",
    generation_failure_recovery_prompts: ["重试下一题", "换主题", "总结一下"],
    min_turns: 3,
    max_turns: 10,
    mastery_threshold: 80,
    prompt_template_id: null,
    prompt_revision_id: null,
    prompt_contract_hash: null,
    scoring_prompt_template_id: null,
    scoring_prompt_revision_id: null,
    scoring_contract_hash: null,
    output_schema_version: "ai_coach_interaction_v1",
};

const MIN_TURNS_MIN = 1;
const MIN_TURNS_MAX = 20;
const MAX_TURNS_MIN = 1;
const MAX_TURNS_MAX = 50;
const MASTERY_MIN = 0;
const MASTERY_MAX = 100;
const MAX_AUTO_STEPS_MIN = 1;
const MAX_AUTO_STEPS_MAX = 10;
const STREAK_MIN = 1;
const STREAK_MAX = 10;
const GENERATION_TIMEOUT_MIN = 5;
const GENERATION_TIMEOUT_MAX = 120;
const RECOVERY_PROMPT_MIN = 1;
const RECOVERY_PROMPT_MAX = 4;

function validate(config: AiCoachAdminConfig): string | null {
    if (!isCoachMode(config.coach_mode)) {
        return `coach_mode 非法: ${String(config.coach_mode)}`;
    }
    if (!isEntryResumePolicy(config.entry_resume_policy)) {
        return `entry_resume_policy 非法: ${String(config.entry_resume_policy)}`;
    }
    if (
        !Number.isFinite(config.generation_timeout_seconds)
        || config.generation_timeout_seconds < GENERATION_TIMEOUT_MIN
        || config.generation_timeout_seconds > GENERATION_TIMEOUT_MAX
    ) {
        return `generation_timeout_seconds 必须在 ${GENERATION_TIMEOUT_MIN}-${GENERATION_TIMEOUT_MAX} 之间`;
    }
    if (!Array.isArray(config.allowed_interaction_types) || config.allowed_interaction_types.length === 0) {
        return "allowed_interaction_types 必须非空";
    }
    for (const value of config.allowed_interaction_types) {
        if (!isInteractionType(value)) {
            return `allowed_interaction_types 含非法值: ${String(value)}`;
        }
    }
    if (!Array.isArray(config.allowed_ui_event_types) || config.allowed_ui_event_types.length === 0) {
        return "allowed_ui_event_types 必须非空";
    }
    for (const value of config.allowed_ui_event_types) {
        if (!isUiEventType(value)) {
            return `allowed_ui_event_types 含非法值: ${String(value)}`;
        }
    }
    if (!config.allowed_ui_event_types.includes("quiz_card")) {
        return "allowed_ui_event_types 必须包含 quiz_card";
    }
    if (!isSessionStartBehavior(config.session_start_behavior)) {
        return `session_start_behavior 非法: ${String(config.session_start_behavior)}`;
    }
    if (!isRemediationStrategy(config.remediation_strategy)) {
        return `remediation_strategy 非法: ${String(config.remediation_strategy)}`;
    }
    if (!Array.isArray(config.allowed_next_actions) || config.allowed_next_actions.length === 0) {
        return "allowed_next_actions 必须非空";
    }
    for (const value of config.allowed_next_actions) {
        if (!isNextAction(value)) {
            return `allowed_next_actions 含非法值: ${String(value)}`;
        }
    }
    if (
        !Number.isFinite(config.max_cards_per_message)
        || config.max_cards_per_message < 1
        || config.max_cards_per_message > 5
    ) {
        return "max_cards_per_message 必须在 1-5 之间";
    }
    if (
        !Number.isFinite(config.max_auto_steps_per_session)
        || config.max_auto_steps_per_session < MAX_AUTO_STEPS_MIN
        || config.max_auto_steps_per_session > MAX_AUTO_STEPS_MAX
    ) {
        return `max_auto_steps_per_session 必须在 ${MAX_AUTO_STEPS_MIN}-${MAX_AUTO_STEPS_MAX} 之间`;
    }
    if (
        !Number.isFinite(config.correct_streak_to_increase_difficulty)
        || config.correct_streak_to_increase_difficulty < STREAK_MIN
        || config.correct_streak_to_increase_difficulty > STREAK_MAX
    ) {
        return `correct_streak_to_increase_difficulty 必须在 ${STREAK_MIN}-${STREAK_MAX} 之间`;
    }
    if (
        !Number.isFinite(config.incorrect_streak_to_remediate)
        || config.incorrect_streak_to_remediate < STREAK_MIN
        || config.incorrect_streak_to_remediate > STREAK_MAX
    ) {
        return `incorrect_streak_to_remediate 必须在 ${STREAK_MIN}-${STREAK_MAX} 之间`;
    }
    if (
        !Number.isFinite(config.incorrect_streak_to_pause)
        || config.incorrect_streak_to_pause < STREAK_MIN
        || config.incorrect_streak_to_pause > STREAK_MAX
    ) {
        return `incorrect_streak_to_pause 必须在 ${STREAK_MIN}-${STREAK_MAX} 之间`;
    }
    if (config.incorrect_streak_to_pause < config.incorrect_streak_to_remediate) {
        return "incorrect_streak_to_pause 必须 ≥ incorrect_streak_to_remediate";
    }
    if (!config.chat_welcome_message.trim()) {
        return "chat_welcome_message 不能为空";
    }
    if (!config.empty_response_recovery_message.trim()) {
        return "empty_response_recovery_message 不能为空";
    }
    if (!config.generation_failure_recovery_message.trim()) {
        return "generation_failure_recovery_message 不能为空";
    }
    if (
        !Array.isArray(config.empty_response_recovery_prompts)
        || config.empty_response_recovery_prompts.length < RECOVERY_PROMPT_MIN
        || config.empty_response_recovery_prompts.length > RECOVERY_PROMPT_MAX
    ) {
        return `empty_response_recovery_prompts 必须保留 ${RECOVERY_PROMPT_MIN}-${RECOVERY_PROMPT_MAX} 个`;
    }
    for (const value of config.empty_response_recovery_prompts) {
        if (!value.trim()) {
            return "empty_response_recovery_prompts 不能包含空字符串";
        }
    }
    if (
        !Array.isArray(config.generation_failure_recovery_prompts)
        || config.generation_failure_recovery_prompts.length < RECOVERY_PROMPT_MIN
        || config.generation_failure_recovery_prompts.length > RECOVERY_PROMPT_MAX
    ) {
        return `generation_failure_recovery_prompts 必须保留 ${RECOVERY_PROMPT_MIN}-${RECOVERY_PROMPT_MAX} 个`;
    }
    for (const value of config.generation_failure_recovery_prompts) {
        if (!value.trim()) {
            return "generation_failure_recovery_prompts 不能包含空字符串";
        }
    }
    if (!Number.isFinite(config.min_turns) || config.min_turns < MIN_TURNS_MIN || config.min_turns > MIN_TURNS_MAX) {
        return `min_turns 必须在 ${MIN_TURNS_MIN}-${MIN_TURNS_MAX} 之间`;
    }
    if (!Number.isFinite(config.max_turns) || config.max_turns < MAX_TURNS_MIN || config.max_turns > MAX_TURNS_MAX) {
        return `max_turns 必须在 ${MAX_TURNS_MIN}-${MAX_TURNS_MAX} 之间`;
    }
    if (config.max_turns < config.min_turns) {
        return "max_turns 必须 ≥ min_turns";
    }
    if (
        !Number.isFinite(config.mastery_threshold)
        || config.mastery_threshold < MASTERY_MIN
        || config.mastery_threshold > MASTERY_MAX
    ) {
        return `mastery_threshold 必须在 ${MASTERY_MIN}-${MASTERY_MAX} 之间`;
    }
    if (config.prompt_template_id !== null && config.prompt_template_id.trim() === "") {
        return "prompt_template_id 不能为空字符串";
    }
    if (config.prompt_revision_id !== null && config.prompt_revision_id.trim() === "") {
        return "prompt_revision_id 不能为空字符串";
    }
    if (
        config.allowed_interaction_types.includes("short_answer")
        && !config.scoring_prompt_template_id?.trim()
    ) {
        return "启用简答题时必须填写 scoring_prompt_template_id";
    }
    if (config.scoring_prompt_template_id !== null && config.scoring_prompt_template_id.trim() === "") {
        return "scoring_prompt_template_id 不能为空字符串";
    }
    if (config.scoring_prompt_revision_id !== null && config.scoring_prompt_revision_id.trim() === "") {
        return "scoring_prompt_revision_id 不能为空字符串";
    }
    return null;
}

function normalize(raw: unknown): AiCoachAdminConfig {
    if (!raw || typeof raw !== "object") {
        return { ...DEFAULT_CONFIG };
    }
    const record = raw as Record<string, unknown>;
    const coachModeRaw = typeof record.coach_mode === "string" ? record.coach_mode : "mixed_drill";
    const allowedRaw = Array.isArray(record.allowed_interaction_types)
        ? record.allowed_interaction_types.filter((value): value is string => typeof value === "string")
        : DEFAULT_CONFIG.allowed_interaction_types;
    const allowedInteractionTypes = allowedRaw.filter(isInteractionType);
    const allowedUiRaw = Array.isArray(record.allowed_ui_event_types)
        ? record.allowed_ui_event_types.filter((value): value is string => typeof value === "string")
        : DEFAULT_CONFIG.allowed_ui_event_types;
    const allowedUiEventTypes = allowedUiRaw.filter(isUiEventType);
    const sessionStartRaw = typeof record.session_start_behavior === "string"
        ? record.session_start_behavior
        : DEFAULT_CONFIG.session_start_behavior;
    const remediationRaw = typeof record.remediation_strategy === "string"
        ? record.remediation_strategy
        : DEFAULT_CONFIG.remediation_strategy;
    const entryResumePolicyRaw = typeof record.entry_resume_policy === "string"
        ? record.entry_resume_policy
        : DEFAULT_CONFIG.entry_resume_policy;
    const nextActionRaw = Array.isArray(record.allowed_next_actions)
        ? record.allowed_next_actions.filter((value): value is string => typeof value === "string")
        : DEFAULT_CONFIG.allowed_next_actions;
    const allowedNextActions = nextActionRaw.filter(isNextAction);
    const recoveryPromptsRaw = Array.isArray(record.empty_response_recovery_prompts)
        ? record.empty_response_recovery_prompts.filter((value): value is string => (
            typeof value === "string" && value.trim().length > 0
        ))
        : DEFAULT_CONFIG.empty_response_recovery_prompts;
    const recoveryPrompts = recoveryPromptsRaw.slice(0, RECOVERY_PROMPT_MAX);
    const generationFailurePromptsRaw = Array.isArray(record.generation_failure_recovery_prompts)
        ? record.generation_failure_recovery_prompts.filter((value): value is string => (
            typeof value === "string" && value.trim().length > 0
        ))
        : DEFAULT_CONFIG.generation_failure_recovery_prompts;
    const generationFailurePrompts = generationFailurePromptsRaw.slice(0, RECOVERY_PROMPT_MAX);
    return {
        ...DEFAULT_CONFIG,
        ...record,
        enabled: Boolean(record.enabled),
        chat_enabled: typeof record.chat_enabled === "boolean"
            ? record.chat_enabled
            : DEFAULT_CONFIG.chat_enabled,
        streaming_enabled: typeof record.streaming_enabled === "boolean"
            ? record.streaming_enabled
            : DEFAULT_CONFIG.streaming_enabled,
        entry_resume_policy: isEntryResumePolicy(entryResumePolicyRaw)
            ? entryResumePolicyRaw
            : DEFAULT_CONFIG.entry_resume_policy,
        generation_timeout_seconds: Number.isFinite(record.generation_timeout_seconds)
            ? Number(record.generation_timeout_seconds)
            : DEFAULT_CONFIG.generation_timeout_seconds,
        coach_mode: isCoachMode(coachModeRaw) ? coachModeRaw : "mixed_drill",
        allowed_interaction_types: allowedInteractionTypes.length > 0
            ? allowedInteractionTypes
            : DEFAULT_CONFIG.allowed_interaction_types,
        allowed_ui_event_types: allowedUiEventTypes.length > 0
            ? allowedUiEventTypes
            : DEFAULT_CONFIG.allowed_ui_event_types,
        max_cards_per_message: Number.isFinite(record.max_cards_per_message)
            ? Number(record.max_cards_per_message)
            : DEFAULT_CONFIG.max_cards_per_message,
        proactive_coaching_enabled: typeof record.proactive_coaching_enabled === "boolean"
            ? record.proactive_coaching_enabled
            : DEFAULT_CONFIG.proactive_coaching_enabled,
        session_start_behavior: isSessionStartBehavior(sessionStartRaw)
            ? sessionStartRaw
            : DEFAULT_CONFIG.session_start_behavior,
        auto_advance_enabled: typeof record.auto_advance_enabled === "boolean"
            ? record.auto_advance_enabled
            : DEFAULT_CONFIG.auto_advance_enabled,
        max_auto_steps_per_session: Number.isFinite(record.max_auto_steps_per_session)
            ? Number(record.max_auto_steps_per_session)
            : DEFAULT_CONFIG.max_auto_steps_per_session,
        correct_streak_to_increase_difficulty: Number.isFinite(record.correct_streak_to_increase_difficulty)
            ? Number(record.correct_streak_to_increase_difficulty)
            : DEFAULT_CONFIG.correct_streak_to_increase_difficulty,
        incorrect_streak_to_remediate: Number.isFinite(record.incorrect_streak_to_remediate)
            ? Number(record.incorrect_streak_to_remediate)
            : DEFAULT_CONFIG.incorrect_streak_to_remediate,
        incorrect_streak_to_pause: Number.isFinite(record.incorrect_streak_to_pause)
            ? Number(record.incorrect_streak_to_pause)
            : DEFAULT_CONFIG.incorrect_streak_to_pause,
        remediation_strategy: isRemediationStrategy(remediationRaw)
            ? remediationRaw
            : DEFAULT_CONFIG.remediation_strategy,
        summary_when_mastery_reached: typeof record.summary_when_mastery_reached === "boolean"
            ? record.summary_when_mastery_reached
            : DEFAULT_CONFIG.summary_when_mastery_reached,
        allowed_next_actions: allowedNextActions.length > 0
            ? allowedNextActions
            : DEFAULT_CONFIG.allowed_next_actions,
        chat_welcome_message: typeof record.chat_welcome_message === "string" && record.chat_welcome_message.trim()
            ? record.chat_welcome_message
            : DEFAULT_CONFIG.chat_welcome_message,
        empty_response_recovery_message: typeof record.empty_response_recovery_message === "string" && record.empty_response_recovery_message.trim()
            ? record.empty_response_recovery_message
            : DEFAULT_CONFIG.empty_response_recovery_message,
        empty_response_recovery_prompts: recoveryPrompts.length > 0
            ? recoveryPrompts
            : DEFAULT_CONFIG.empty_response_recovery_prompts,
        generation_failure_recovery_message: typeof record.generation_failure_recovery_message === "string" && record.generation_failure_recovery_message.trim()
            ? record.generation_failure_recovery_message
            : DEFAULT_CONFIG.generation_failure_recovery_message,
        generation_failure_recovery_prompts: generationFailurePrompts.length > 0
            ? generationFailurePrompts
            : DEFAULT_CONFIG.generation_failure_recovery_prompts,
        min_turns: Number.isFinite(record.min_turns) ? Number(record.min_turns) : DEFAULT_CONFIG.min_turns,
        max_turns: Number.isFinite(record.max_turns) ? Number(record.max_turns) : DEFAULT_CONFIG.max_turns,
        mastery_threshold: Number.isFinite(record.mastery_threshold)
            ? Number(record.mastery_threshold)
            : DEFAULT_CONFIG.mastery_threshold,
        prompt_template_id: typeof record.prompt_template_id === "string" && record.prompt_template_id.trim()
            ? record.prompt_template_id.trim()
            : null,
        prompt_revision_id: typeof record.prompt_revision_id === "string" && record.prompt_revision_id.trim()
            ? record.prompt_revision_id.trim()
            : null,
        // Read-only fields: prefer backend value, fall back to defaults.
        prompt_contract_hash: typeof record.prompt_contract_hash === "string"
            ? record.prompt_contract_hash
            : null,
        scoring_prompt_template_id: typeof record.scoring_prompt_template_id === "string" && record.scoring_prompt_template_id.trim()
            ? record.scoring_prompt_template_id.trim()
            : null,
        scoring_prompt_revision_id: typeof record.scoring_prompt_revision_id === "string" && record.scoring_prompt_revision_id.trim()
            ? record.scoring_prompt_revision_id.trim()
            : null,
        scoring_contract_hash: typeof record.scoring_contract_hash === "string"
            ? record.scoring_contract_hash
            : null,
        output_schema_version: typeof record.output_schema_version === "string"
            ? record.output_schema_version
            : DEFAULT_CONFIG.output_schema_version,
    };
}

export default function AdminAiCoachConfigPage() {
    const [moduleKey] = useState("business_skills");
    const [config, setConfig] = useState<AiCoachAdminConfig>(DEFAULT_CONFIG);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isPublishing, setIsPublishing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [remediation, setRemediation] = useState<string | null>(null);
    const [actionMessage, setActionMessage] = useState<string | null>(null);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        setRemediation(null);
        try {
            const response = await requestConfig(moduleKey);
            setConfig(response);
        } catch (loadError) {
            const message = getApiErrorMessage(loadError);
            setError(message);
            setRemediation(
                "无法加载 AI 教练配置。请检查路径配置中心是否已发布商务技巧模块，或联系管理员。",
            );
        } finally {
            setIsLoading(false);
        }
    }, [moduleKey]);

    useEffect(() => {
        let isActive = true;
        void requestConfig(moduleKey)
            .then((response) => {
                if (!isActive) {
                    return;
                }
                setConfig(response);
            })
            .catch((loadError) => {
                if (!isActive) {
                    return;
                }
                const message = getApiErrorMessage(loadError);
                setError(message);
                setRemediation(
                    "无法加载 AI 教练配置。请检查路径配置中心是否已发布商务技巧模块，或联系管理员。",
                );
            })
            .finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });
        return () => {
            isActive = false;
        };
    }, [moduleKey]);

    const validationError = useMemo(() => validate(config), [config]);
    const hasRemediation = remediation !== null;

    function updateField<K extends keyof AiCoachAdminConfig>(key: K, value: AiCoachAdminConfig[K]) {
        setConfig((current) => ({ ...current, [key]: value }));
    }

    function toggleInteractionType(value: InteractionType) {
        setConfig((current) => {
            const exists = current.allowed_interaction_types.includes(value);
            const next = exists
                ? current.allowed_interaction_types.filter((entry) => entry !== value)
                : [...current.allowed_interaction_types, value];
            return {
                ...current,
                allowed_interaction_types: next.length > 0 ? next : current.allowed_interaction_types,
            };
        });
    }

    function toggleUiEventType(value: UiEventType) {
        setConfig((current) => {
            const exists = current.allowed_ui_event_types.includes(value);
            const next = exists
                ? current.allowed_ui_event_types.filter((entry) => entry !== value)
                : [...current.allowed_ui_event_types, value];
            return {
                ...current,
                allowed_ui_event_types: next.length > 0 ? next : current.allowed_ui_event_types,
            };
        });
    }

    function toggleNextAction(value: NextAction) {
        setConfig((current) => {
            const exists = current.allowed_next_actions.includes(value);
            const next = exists
                ? current.allowed_next_actions.filter((entry) => entry !== value)
                : [...current.allowed_next_actions, value];
            return {
                ...current,
                allowed_next_actions: next.length > 0 ? next : current.allowed_next_actions,
            };
        });
    }

    function updateRecoveryPrompt(index: number, value: string) {
        setConfig((current) => {
            const next = [...current.empty_response_recovery_prompts];
            next[index] = value;
            return {
                ...current,
                empty_response_recovery_prompts: next,
            };
        });
    }

    function updateGenerationFailurePrompt(index: number, value: string) {
        setConfig((current) => {
            const next = [...current.generation_failure_recovery_prompts];
            next[index] = value;
            return {
                ...current,
                generation_failure_recovery_prompts: next,
            };
        });
    }

    async function save() {
        if (validationError) {
            setError(validationError);
            return;
        }
        setIsSaving(true);
        setError(null);
        setActionMessage(null);
        try {
            const response = await saveConfig(moduleKey, config);
            setConfig(response.ai_coach);
            setActionMessage("AI 教练配置已保存草稿。点击 发布 让其对未来学员生效。");
        } catch (saveError) {
            const message = getApiErrorMessage(saveError);
            setError(message);
            setRemediation("保存失败：检查 min_turns/max_turns/mastery_threshold/prompt 绑定是否符合后端约束。");
        } finally {
            setIsSaving(false);
        }
    }

    async function publish() {
        if (validationError) {
            setError(validationError);
            return;
        }
        setIsPublishing(true);
        setError(null);
        setActionMessage(null);
        try {
            const response = await publishConfig(moduleKey);
            setActionMessage(
                `已发布：active_revision_no=${response.active_revision_no ?? "--"}，只影响后续学员。`,
            );
        } catch (publishError) {
            const message = getApiErrorMessage(publishError);
            setError(message);
            setRemediation("发布失败：确认有 working 版本可发布，或前往路径配置中心完成发布/回滚。");
        } finally {
            setIsPublishing(false);
        }
    }

    return (
        <div className="space-y-6 pb-20">
            <AdminPageHeader
                title="AI 教练配置"
                description="管理商务技巧模块 AI 教练的开关、训练模式、轮数、掌握阈值和 prompt 绑定。"
            />

            {error ? (
                <GlassCard className="border-red-100 bg-red-50 p-4 text-sm text-red-700">{error}</GlassCard>
            ) : null}
            {actionMessage ? (
                <GlassCard className="border-emerald-100 bg-emerald-50 p-4 text-sm text-emerald-700">
                    {actionMessage}
                </GlassCard>
            ) : null}
            {hasRemediation ? (
                <GlassCard className="border-amber-100 bg-amber-50 p-4 text-sm text-amber-800">
                    <p className="font-semibold">配置不可用</p>
                    <p className="mt-1">{remediation}</p>
                </GlassCard>
            ) : null}

            {isLoading ? (
                <div className="h-64 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
            ) : hasRemediation ? (
                <GlassCard className="space-y-3 p-6">
                    <p className="text-sm text-slate-700">
                        模块 <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{moduleKey}</code> 当前没有可编辑的 AI 教练配置。
                    </p>
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => void load()}
                    >
                        重新加载
                    </Button>
                </GlassCard>
            ) : (
                <GlassCard className="space-y-5 p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900">商务技巧 · AI 教练</h2>
                            <p className="text-sm text-slate-500">
                                module_key: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{moduleKey}</code>
                            </p>
                        </div>
                        <Badge className={config.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}>
                            {config.enabled ? "已开启" : "已关闭"}
                        </Badge>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 p-3">
                            <div>
                                <p className="text-sm font-semibold text-slate-900">启用 AI 教练</p>
                                <p className="text-xs text-slate-500">关闭后学员入口隐藏，固定题闭环不受影响。</p>
                            </div>
                            <input
                                type="checkbox"
                                className="h-5 w-5 rounded border-slate-300"
                                checked={config.enabled}
                                onChange={(event) => updateField("enabled", event.target.checked)}
                            />
                        </label>

                        <label className="flex items-center justify-between gap-3 rounded-2xl border border-violet-100 bg-violet-50/60 p-3">
                            <div>
                                <p className="text-sm font-semibold text-slate-900">启用 Chatbot 形态</p>
                                <p className="text-xs text-slate-500">开启后 /coach 使用对话流和白名单卡片。</p>
                            </div>
                            <input
                                type="checkbox"
                                className="h-5 w-5 rounded border-slate-300"
                                checked={config.chat_enabled}
                                onChange={(event) => updateField("chat_enabled", event.target.checked)}
                            />
                        </label>

                        <label className="flex flex-col gap-1 text-sm">
                            <span className="font-medium text-slate-700">coach_mode（训练模式）</span>
                            <select
                                className="h-10 rounded-xl border border-slate-200 bg-white px-3"
                                value={config.coach_mode}
                                onChange={(event) => {
                                    if (isCoachMode(event.target.value)) {
                                        updateField("coach_mode", event.target.value);
                                    }
                                }}
                            >
                                {COACH_MODE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <fieldset className="rounded-2xl border border-slate-100 p-3 md:col-span-2">
                            <legend className="px-1 text-sm font-semibold text-slate-900">allowed_interaction_types</legend>
                            <p className="text-xs text-slate-500">勾选允许出现的题型；至少保留一项。</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {INTERACTION_TYPE_OPTIONS.map((option) => {
                                    const checked = config.allowed_interaction_types.includes(option.value);
                                    return (
                                        <label
                                            key={option.value}
                                            className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
                                                checked
                                                    ? "border-slate-900 bg-slate-900 text-white"
                                                    : "border-slate-200 bg-white text-slate-700"
                                            }`}
                                        >
                                            <input
                                                type="checkbox"
                                                className="h-3.5 w-3.5"
                                                checked={checked}
                                                onChange={() => toggleInteractionType(option.value)}
                                            />
                                            {option.label}
                                        </label>
                                    );
                                })}
                            </div>
                        </fieldset>

                        <fieldset className="rounded-2xl border border-violet-100 bg-violet-50/40 p-3 md:col-span-2">
                            <legend className="px-1 text-sm font-semibold text-slate-900">allowed_ui_event_types</legend>
                            <p className="text-xs text-slate-500">控制 AI 在消息流里可插入的白名单卡片。</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {UI_EVENT_TYPE_OPTIONS.map((option) => {
                                    const checked = config.allowed_ui_event_types.includes(option.value);
                                    return (
                                        <label
                                            key={option.value}
                                            className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
                                                checked
                                                    ? "border-violet-700 bg-violet-700 text-white"
                                                    : "border-violet-100 bg-white text-slate-700"
                                            }`}
                                        >
                                            <input
                                                type="checkbox"
                                                className="h-3.5 w-3.5"
                                                checked={checked}
                                                onChange={() => toggleUiEventType(option.value)}
                                            />
                                            {option.label}
                                        </label>
                                    );
                                })}
                            </div>
                        </fieldset>

                        <fieldset className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4 md:col-span-2">
                            <legend className="px-1 text-sm font-semibold text-slate-900">主动教练闭环</legend>
                            <div className="mt-2 grid gap-4 md:grid-cols-2">
                                <label className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-100 bg-white p-3">
                                    <div>
                                        <p className="text-sm font-semibold text-slate-900">启用主动教练</p>
                                        <p className="text-xs text-slate-500">开启后后端可在会话开始时主动给计划或首题。</p>
                                    </div>
                                    <input
                                        type="checkbox"
                                        className="h-5 w-5 rounded border-slate-300"
                                        checked={config.proactive_coaching_enabled}
                                        onChange={(event) => updateField("proactive_coaching_enabled", event.target.checked)}
                                    />
                                </label>
                                <label className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-100 bg-white p-3">
                                    <div>
                                        <p className="text-sm font-semibold text-slate-900">答后自动推进</p>
                                        <p className="text-xs text-slate-500">提交卡片后由后端生成一个下一步动作。</p>
                                    </div>
                                    <input
                                        type="checkbox"
                                        className="h-5 w-5 rounded border-slate-300"
                                        checked={config.auto_advance_enabled}
                                        onChange={(event) => updateField("auto_advance_enabled", event.target.checked)}
                                    />
                                </label>
                                <label className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-100 bg-white p-3">
                                    <div>
                                        <p className="text-sm font-semibold text-slate-900">启用流式训练体验</p>
                                        <p className="text-xs text-slate-500">开启后学员端通过 SSE 展示生成、批改和下一步状态。</p>
                                    </div>
                                    <input
                                        type="checkbox"
                                        className="h-5 w-5 rounded border-slate-300"
                                        checked={config.streaming_enabled}
                                        onChange={(event) => updateField("streaming_enabled", event.target.checked)}
                                    />
                                </label>
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="font-medium text-slate-700">session_start_behavior</span>
                                    <select
                                        className="h-10 rounded-xl border border-slate-200 bg-white px-3"
                                        value={config.session_start_behavior}
                                        onChange={(event) => {
                                            if (isSessionStartBehavior(event.target.value)) {
                                                updateField("session_start_behavior", event.target.value);
                                            }
                                        }}
                                    >
                                        {SESSION_START_BEHAVIOR_OPTIONS.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="font-medium text-slate-700">entry_resume_policy</span>
                                    <select
                                        className="h-10 rounded-xl border border-slate-200 bg-white px-3"
                                        value={config.entry_resume_policy}
                                        onChange={(event) => {
                                            if (isEntryResumePolicy(event.target.value)) {
                                                updateField("entry_resume_policy", event.target.value);
                                            }
                                        }}
                                    >
                                        {ENTRY_RESUME_POLICY_OPTIONS.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <label className="flex flex-col gap-1 text-sm">
                                    <span className="font-medium text-slate-700">remediation_strategy</span>
                                    <select
                                        className="h-10 rounded-xl border border-slate-200 bg-white px-3"
                                        value={config.remediation_strategy}
                                        onChange={(event) => {
                                            if (isRemediationStrategy(event.target.value)) {
                                                updateField("remediation_strategy", event.target.value);
                                            }
                                        }}
                                    >
                                        {REMEDIATION_STRATEGY_OPTIONS.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <FieldInput
                                    label="generation_timeout_seconds（5-120）"
                                    type="number"
                                    min={GENERATION_TIMEOUT_MIN}
                                    max={GENERATION_TIMEOUT_MAX}
                                    value={config.generation_timeout_seconds}
                                    onChange={(value) => updateField("generation_timeout_seconds", Number(value))}
                                />
                                <FieldInput
                                    label="max_auto_steps_per_session（1-10）"
                                    type="number"
                                    min={MAX_AUTO_STEPS_MIN}
                                    max={MAX_AUTO_STEPS_MAX}
                                    value={config.max_auto_steps_per_session}
                                    onChange={(value) => updateField("max_auto_steps_per_session", Number(value))}
                                />
                                <FieldInput
                                    label="correct_streak_to_increase_difficulty（1-10）"
                                    type="number"
                                    min={STREAK_MIN}
                                    max={STREAK_MAX}
                                    value={config.correct_streak_to_increase_difficulty}
                                    onChange={(value) => updateField("correct_streak_to_increase_difficulty", Number(value))}
                                />
                                <FieldInput
                                    label="incorrect_streak_to_remediate（1-10）"
                                    type="number"
                                    min={STREAK_MIN}
                                    max={STREAK_MAX}
                                    value={config.incorrect_streak_to_remediate}
                                    onChange={(value) => updateField("incorrect_streak_to_remediate", Number(value))}
                                />
                                <FieldInput
                                    label="incorrect_streak_to_pause（1-10）"
                                    type="number"
                                    min={STREAK_MIN}
                                    max={STREAK_MAX}
                                    value={config.incorrect_streak_to_pause}
                                    onChange={(value) => updateField("incorrect_streak_to_pause", Number(value))}
                                />
                                <label className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-100 bg-white p-3 md:col-span-2">
                                    <div>
                                        <p className="text-sm font-semibold text-slate-900">达到掌握阈值后总结</p>
                                        <p className="text-xs text-slate-500">达到最小轮数且平均分达标时生成复盘动作。</p>
                                    </div>
                                    <input
                                        type="checkbox"
                                        className="h-5 w-5 rounded border-slate-300"
                                        checked={config.summary_when_mastery_reached}
                                        onChange={(event) => updateField("summary_when_mastery_reached", event.target.checked)}
                                    />
                                </label>
                                <label className="flex flex-col gap-1 text-sm md:col-span-2">
                                    <span className="font-medium text-slate-700">empty_response_recovery_message</span>
                                    <textarea
                                        value={config.empty_response_recovery_message}
                                        onChange={(event) => updateField("empty_response_recovery_message", event.target.value)}
                                        rows={2}
                                        className="rounded-xl border border-slate-200 bg-white px-3 py-2"
                                    />
                                </label>
                                <div className="space-y-2 md:col-span-2">
                                    <p className="text-sm font-semibold text-slate-900">empty_response_recovery_prompts</p>
                                    <div className="grid gap-2 md:grid-cols-3">
                                        {config.empty_response_recovery_prompts.map((prompt, index) => (
                                            <FieldInput
                                                key={`recovery-prompt-${index}`}
                                                label={`兜底动作 ${index + 1}`}
                                                value={prompt}
                                                onChange={(value) => updateRecoveryPrompt(index, String(value))}
                                            />
                                        ))}
                                    </div>
                                </div>
                                <label className="flex flex-col gap-1 text-sm md:col-span-2">
                                    <span className="font-medium text-slate-700">generation_failure_recovery_message</span>
                                    <textarea
                                        value={config.generation_failure_recovery_message}
                                        onChange={(event) => updateField("generation_failure_recovery_message", event.target.value)}
                                        rows={2}
                                        className="rounded-xl border border-slate-200 bg-white px-3 py-2"
                                    />
                                </label>
                                <div className="space-y-2 md:col-span-2">
                                    <p className="text-sm font-semibold text-slate-900">generation_failure_recovery_prompts</p>
                                    <div className="grid gap-2 md:grid-cols-3">
                                        {config.generation_failure_recovery_prompts.map((prompt, index) => (
                                            <FieldInput
                                                key={`generation-failure-prompt-${index}`}
                                                label={`失败恢复动作 ${index + 1}`}
                                                value={prompt}
                                                onChange={(value) => updateGenerationFailurePrompt(index, String(value))}
                                            />
                                        ))}
                                    </div>
                                </div>
                            </div>
                            <div className="mt-4">
                                <p className="text-sm font-semibold text-slate-900">allowed_next_actions</p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                    {NEXT_ACTION_OPTIONS.map((option) => {
                                        const checked = config.allowed_next_actions.includes(option.value);
                                        return (
                                            <label
                                                key={option.value}
                                                className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
                                                    checked
                                                        ? "border-emerald-700 bg-emerald-700 text-white"
                                                        : "border-emerald-100 bg-white text-slate-700"
                                                }`}
                                            >
                                                <input
                                                    type="checkbox"
                                                    className="h-3.5 w-3.5"
                                                    checked={checked}
                                                    onChange={() => toggleNextAction(option.value)}
                                                />
                                                {option.label}
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>
                        </fieldset>

                        <FieldInput
                            label="min_turns（最小轮数）"
                            type="number"
                            min={MIN_TURNS_MIN}
                            max={MIN_TURNS_MAX}
                            value={config.min_turns}
                            onChange={(value) => updateField("min_turns", Number(value))}
                        />
                        <FieldInput
                            label="max_turns（最大轮数）"
                            type="number"
                            min={MAX_TURNS_MIN}
                            max={MAX_TURNS_MAX}
                            value={config.max_turns}
                            onChange={(value) => updateField("max_turns", Number(value))}
                        />
                        <FieldInput
                            label="mastery_threshold（掌握阈值 0-100）"
                            type="number"
                            min={MASTERY_MIN}
                            max={MASTERY_MAX}
                            value={config.mastery_threshold}
                            onChange={(value) => updateField("mastery_threshold", Number(value))}
                        />
                        <FieldInput
                            label="max_cards_per_message（每轮最多卡片）"
                            type="number"
                            min={1}
                            max={5}
                            value={config.max_cards_per_message}
                            onChange={(value) => updateField("max_cards_per_message", Number(value))}
                        />
                        <label className="flex flex-col gap-1 text-sm md:col-span-2">
                            <span className="font-medium text-slate-700">chat_welcome_message</span>
                            <textarea
                                value={config.chat_welcome_message}
                                onChange={(event) => updateField("chat_welcome_message", event.target.value)}
                                rows={3}
                                className="rounded-xl border border-slate-200 bg-white px-3 py-2"
                            />
                        </label>
                    </div>

                    <div className="rounded-2xl border border-amber-100 bg-amber-50 p-4 text-xs text-amber-800">
                        <p className="font-semibold">Prompt 绑定（高风险）</p>
                        <p className="mt-1">
                            填写 prompt_template_id 后，保存操作会要求
                            <code className="rounded bg-amber-100 px-1">sales_trainer.manage_prompts</code>
                            权限。空值时只保存模块级配置。
                        </p>
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                            <FieldInput
                                label="prompt_template_id"
                                value={config.prompt_template_id ?? ""}
                                onChange={(value) => updateField("prompt_template_id", String(value) || null)}
                            />
                            <FieldInput
                                label="prompt_revision_id（可选）"
                                value={config.prompt_revision_id ?? ""}
                                onChange={(value) => updateField("prompt_revision_id", String(value) || null)}
                            />
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2">
                            <ReadonlyField
                                label="prompt_contract_hash（运行时审计）"
                                value={config.prompt_contract_hash ?? "--"}
                            />
                            <ReadonlyField
                                label="output_schema_version（后端固定）"
                                value={config.output_schema_version}
                            />
                        </div>
                    </div>

                    <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 text-xs text-blue-800">
                        <p className="font-semibold">简答评分 Prompt</p>
                        <p className="mt-1">
                            只有 allowed_interaction_types 包含 short_answer 时必填；单选/多选训练不会调用该评分 prompt。
                        </p>
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                            <FieldInput
                                label="scoring_prompt_template_id"
                                value={config.scoring_prompt_template_id ?? ""}
                                onChange={(value) => updateField("scoring_prompt_template_id", String(value) || null)}
                            />
                            <FieldInput
                                label="scoring_prompt_revision_id（可选）"
                                value={config.scoring_prompt_revision_id ?? ""}
                                onChange={(value) => updateField("scoring_prompt_revision_id", String(value) || null)}
                            />
                        </div>
                        <div className="mt-3">
                            <ReadonlyField
                                label="scoring_contract_hash（运行时审计）"
                                value={config.scoring_contract_hash ?? "--"}
                            />
                        </div>
                    </div>

                    {validationError ? (
                        <p className="text-sm font-medium text-red-700">{validationError}</p>
                    ) : null}

                    <div className="flex items-center justify-between gap-2">
                        <Button
                            variant="outline"
                            className="rounded-full"
                            onClick={() => void load()}
                            disabled={isSaving || isPublishing}
                        >
                            重新加载
                        </Button>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                className="rounded-full"
                                onClick={() => void publish()}
                                disabled={isSaving || isPublishing || Boolean(validationError)}
                            >
                                <Send className="mr-2 h-4 w-4" />
                                {isPublishing ? "发布中..." : "发布"}
                            </Button>
                            <Button
                                className="rounded-full bg-slate-900 text-white"
                                onClick={() => void save()}
                                disabled={isSaving || isPublishing || Boolean(validationError)}
                            >
                                <Save className="mr-2 h-4 w-4" />
                                {isSaving ? "保存中..." : "保存草稿"}
                            </Button>
                        </div>
                    </div>

                    <p className="text-xs text-slate-500">
                        <Sparkles className="mr-1 inline h-3 w-3" />
                        发布/停用/回滚请到 新人训练路径 → 路径配置中心。AI 教练配置是路径修订的一部分，历史 session 不会受影响。
                    </p>
                </GlassCard>
            )}
        </div>
    );
}

function FieldInput({
    label,
    type = "text",
    value,
    onChange,
    min,
    max,
}: {
    readonly label: string;
    readonly type?: "text" | "number";
    readonly value: string | number;
    readonly onChange: (value: string | number) => void;
    readonly min?: number;
    readonly max?: number;
}) {
    return (
        <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">{label}</span>
            <input
                type={type}
                value={value}
                min={min}
                max={max}
                onChange={(event) => {
                    if (type === "number") {
                        const next = Number(event.target.value);
                        onChange(Number.isNaN(next) ? 0 : next);
                    } else {
                        onChange(event.target.value);
                    }
                }}
                className="h-10 rounded-xl border border-slate-200 bg-white px-3"
            />
        </label>
    );
}

function ReadonlyField({
    label,
    value,
}: {
    readonly label: string;
    readonly value: string;
}) {
    return (
        <div className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">{label}</span>
            <code className="h-10 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                {value}
            </code>
        </div>
    );
}

async function requestConfig(moduleKey: string): Promise<AiCoachAdminConfig> {
    const config = await api.admin.newcomerTraining.getAiCoachConfig(moduleKey);
    if (!config) {
        throw new Error("响应缺少 data 字段");
    }
    return normalize(config);
}

async function saveConfig(moduleKey: string, payload: AiCoachAdminConfig): Promise<ConfigResponse> {
    const response = await api.admin.newcomerTraining.saveAiCoachConfig(
        moduleKey,
        payload as unknown as AiCoachAdminConfigLike,
    );
    if (!response) {
        throw new Error("保存响应为空");
    }
    return {
        module_key: response.module_key ?? moduleKey,
        ai_coach: normalize(response.ai_coach),
    };
}

interface PublishResponse {
    module_key: string;
    active_revision_id: string;
    active_revision_no: number;
    previous_revision_id?: string | null;
    change_class: string;
    impact_scope: string;
}

async function publishConfig(moduleKey: string): Promise<PublishResponse> {
    const response = await api.admin.newcomerTraining.publishAiCoachConfig(moduleKey);
    if (!response) {
        throw new Error("发布响应为空");
    }
    return {
        module_key: response.module_key ?? moduleKey,
        active_revision_id: response.active_revision_id,
        active_revision_no: response.active_revision_no,
        previous_revision_id: response.previous_revision_id,
        change_class: response.change_class,
        impact_scope: response.impact_scope,
    };
}
