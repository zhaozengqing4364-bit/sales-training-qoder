import type {
    ExaminerAgentCreateRequest,
    ExaminerAgentLearnerLevel,
    ExaminerAgentLearnerLevelStrategy,
    ExaminerAgentRecord,
    ExaminerAgentUpdateRequest,
} from "@/lib/api/types";

export const LEARNER_LEVEL_OPTIONS: Array<{ value: ExaminerAgentLearnerLevel; label: string }> = [
    { value: "conservative", label: "保守" },
    { value: "beginner", label: "初级" },
    { value: "intermediate", label: "中级" },
    { value: "advanced", label: "高级" },
];

export interface JsonFieldState {
    text: string;
    parsed: Record<string, unknown> | null;
    error: string | null;
}

export interface ExaminerAgentFormState {
    name: string;
    description: string;
    question_source_ids_text: string;
    learner_default_level: ExaminerAgentLearnerLevel;
    learner_allowed_levels_text: string;
    scoring_policy_id: string;
    timeout_max_seconds: number;
    safety_config: JsonFieldState;
    prompt_config: JsonFieldState;
    simulation_config: JsonFieldState;
}

export function emptyJsonField(): JsonFieldState {
    return { text: "{}", parsed: {}, error: null };
}

export function createEmptyExaminerAgentForm(scoringPolicyId = ""): ExaminerAgentFormState {
    return {
        name: "",
        description: "",
        question_source_ids_text: "",
        learner_default_level: "intermediate",
        learner_allowed_levels_text: "conservative, beginner, intermediate, advanced",
        scoring_policy_id: scoringPolicyId,
        timeout_max_seconds: 30,
        safety_config: emptyJsonField(),
        prompt_config: emptyJsonField(),
        simulation_config: emptyJsonField(),
    };
}

export function parseJsonField(text: string): JsonFieldState {
    const trimmed = text.trim();
    if (!trimmed) return { text: trimmed, parsed: {}, error: null };
    try {
        const parsed = JSON.parse(trimmed);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return { text: trimmed, parsed: null, error: "值必须是 JSON 对象。" };
        }
        return { text: trimmed, parsed: parsed as Record<string, unknown>, error: null };
    } catch (err) {
        return {
            text: trimmed,
            parsed: null,
            error: err instanceof Error ? err.message : "JSON 格式无效。",
        };
    }
}

export function questionSourceIdsFromText(value: string): string[] {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function statusVariant(status: string): "green" | "orange" | "gray" {
    if (status === "published") return "green";
    if (status === "draft") return "orange";
    return "gray";
}

export function statusLabel(status: string): string {
    if (status === "published") return "已发布";
    if (status === "draft") return "草稿";
    if (status === "archived") return "已归档";
    return status;
}

export function learnerLevelLabel(level: string): string {
    const found = LEARNER_LEVEL_OPTIONS.find((option) => option.value === level);
    return found?.label ?? level;
}

export function strategySummary(strategy: { default_level: string; allowed_levels: string[] }): string {
    const levels = strategy.allowed_levels.map((l) => learnerLevelLabel(l)).join(", ");
    return `默认：${learnerLevelLabel(strategy.default_level)} · 允许：${levels || "无"}`;
}

export function formatDateTime(value?: string | null): string {
    if (!value) return "未记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "未记录";
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

export function formFromRecord(record: ExaminerAgentRecord): ExaminerAgentFormState {
    return {
        name: record.name,
        description: record.description ?? "",
        question_source_ids_text: record.question_source_ids.join(", "),
        learner_default_level: record.learner_level_strategy.default_level,
        learner_allowed_levels_text: record.learner_level_strategy.allowed_levels.join(", "),
        scoring_policy_id: record.scoring_policy_id ?? "",
        timeout_max_seconds: record.timeout_config.max_seconds ?? 30,
        safety_config: {
            text: JSON.stringify(record.safety_config, null, 2),
            parsed: record.safety_config,
            error: null,
        },
        prompt_config: {
            text: JSON.stringify(record.prompt_config, null, 2),
            parsed: record.prompt_config,
            error: null,
        },
        simulation_config: {
            text: JSON.stringify(record.simulation_config, null, 2),
            parsed: record.simulation_config,
            error: null,
        },
    };
}

function buildStrategyObject(form: ExaminerAgentFormState): ExaminerAgentLearnerLevelStrategy {
    return {
        default_level: form.learner_default_level,
        allowed_levels: questionSourceIdsFromText(form.learner_allowed_levels_text) as ExaminerAgentLearnerLevel[],
    };
}

export function buildCreatePayload(form: ExaminerAgentFormState): ExaminerAgentCreateRequest {
    return {
        name: form.name,
        description: form.description || null,
        question_source_ids: questionSourceIdsFromText(form.question_source_ids_text),
        learner_level_strategy: buildStrategyObject(form),
        scoring_policy_id: form.scoring_policy_id || null,
        timeout_config: { max_seconds: form.timeout_max_seconds },
        safety_config: form.safety_config.parsed ?? {},
        prompt_config: form.prompt_config.parsed ?? {},
        simulation_config: form.simulation_config.parsed ?? {},
    };
}

export function buildUpdatePayload(form: ExaminerAgentFormState): ExaminerAgentUpdateRequest {
    return buildCreatePayload(form);
}

export function validateExaminerAgentForm(form: ExaminerAgentFormState): string | null {
    const jsonErrors = [form.safety_config, form.prompt_config, form.simulation_config]
        .map((field, index) => {
            const names = ["安全配置", "提示词配置", "模拟配置"];
            return field.error ? `${names[index]} JSON 格式错误：${field.error}` : null;
        })
        .filter(Boolean);

    if (jsonErrors.length > 0) {
        return jsonErrors.join("；");
    }

    const allowedLevels = questionSourceIdsFromText(form.learner_allowed_levels_text);
    if (allowedLevels.length === 0) {
        return "允许等级不能为空，请至少填入一个等级。";
    }
    if (!allowedLevels.includes(form.learner_default_level)) {
        return `默认等级「${learnerLevelLabel(form.learner_default_level)}」不在允许等级列表中，请修正。`;
    }

    return null;
}
