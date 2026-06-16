import type { PromptBusinessPurpose, PromptType } from "@/lib/api/types";

export const PROMPT_TYPE_LABELS: Record<PromptType, string> = {
  summary: "总结", system: "系统", system_prompt: "系统提示词", extraction: "信息提取",
  scoring: "评分", realtime_scoring: "实时评分", stage: "阶段", fuzzy_detection: "模糊检测",
  interruption: "打断检测", tracking: "跟踪", welcome: "欢迎词", evaluation: "实时评价", report: "综合报告",
};

export const PROMPT_TYPE_COLORS: Record<PromptType, string> = {
  summary: "bg-blue-100 text-blue-700", system: "bg-slate-200 text-slate-700", system_prompt: "bg-slate-200 text-slate-700",
  extraction: "bg-green-100 text-green-700", scoring: "bg-amber-100 text-amber-700", realtime_scoring: "bg-violet-100 text-violet-700",
  stage: "bg-orange-100 text-orange-700", fuzzy_detection: "bg-rose-100 text-rose-700", interruption: "bg-pink-100 text-pink-700",
  tracking: "bg-cyan-100 text-cyan-700", welcome: "bg-indigo-100 text-indigo-700", evaluation: "bg-teal-100 text-teal-700", report: "bg-zinc-200 text-zinc-700",
};

export const PROMPT_BUSINESS_PURPOSE = {
    AI_COACH_CONVERSATION: "ai_coach_conversation_generation",
    BUSINESS_ETIQUETTE_QUESTION: "business_etiquette_question_generation",
} as const satisfies Record<string, PromptBusinessPurpose>;

export const PROMPT_BUSINESS_PURPOSE_LABELS: Record<PromptBusinessPurpose, string> = {
    ai_coach_conversation_generation: "AI 教练对话生成",
    business_etiquette_question_generation: "商务礼仪题目生成",
};

export const PROMPT_BUSINESS_PURPOSE_OPTIONS: Array<{
    value: PromptBusinessPurpose;
    label: string;
}> = Object.entries(PROMPT_BUSINESS_PURPOSE_LABELS).map(([value, label]) => ({
    value: value as PromptBusinessPurpose,
    label,
}));

export function isPromptBusinessPurpose(value: string | null | undefined): value is PromptBusinessPurpose {
    return Boolean(value && value in PROMPT_BUSINESS_PURPOSE_LABELS);
}

export function formatBusinessPurpose(
    purpose?: string | null,
    displayBusinessPurpose?: string | null,
): string {
    if (displayBusinessPurpose) return displayBusinessPurpose;
    if (!purpose) return "未指定业务用途";
    return PROMPT_BUSINESS_PURPOSE_LABELS[purpose as PromptBusinessPurpose] || purpose;
}

export function formatGovernanceIssue(issue: string): string {
    switch (issue) {
        case "variables_object_migratable":
        case "variables_object_schema": return "历史变量对象已标记待迁移";
        case "variables_string_not_json_array":
        case "variables_json_not_array":
        case "variables_not_array":
        case "variables_invalid_json":
        case "variables_non_string_item":
        case "variables_not_list": return "变量字段不是字符串数组";
        case "prompt_type_not_allowed":
        case "invalid_prompt_type": return "提示词类型不在允许列表";
        case "empty_template": return "模板内容为空";
        case "multiple_default_templates": return "同一用途存在多个默认模板";
        default: return issue;
    }
}

export function formatCategoryLabel(category: string): string {
    switch (category) {
        case "common": return "通用";
        case "sales": return "销售训练";
        case "sales_bot": return "销售实时对练";
        case "business_etiquette": return "商务礼仪";
        case "sales_trainer_ai_coach": return "新人训练 AI 教练";
        case "presentation": return "PPT 演练";
        case "system": return "系统报告";
        default: return category;
    }
}

export function formatTemplateName(name: string, displayName?: string | null): string {
    if (displayName) return displayName;
    switch (name) {
        case "Sales Conversation Summary": return "销售对话总结";
        case "Default Sales Persona": return "默认销售客户人格";
        case "PPT Point Extraction": return "PPT 要点提取";
        case "Interruption Feedback - Vague": return "PPT 模糊表达打断反馈";
        case "Interruption Detection Rules": return "PPT 打断判断规则";
        case "Point Tracking Configuration": return "PPT 要点跟踪配置";
        case "Fuzzy Detection - Uncertain": return "销售不确定表达检测";
        case "Fuzzy Detection - Filler": return "销售填充词检测";
        case "Fuzzy Detection - Vague Number": return "销售模糊数字检测";
        case "Realtime Scoring Rules": return "销售实时评分规则";
        case "Sales Stage Definition": return "销售阶段定义";
        case "Welcome Message 1": return "销售欢迎话术 1";
        case "Welcome Message 2": return "销售欢迎话术 2";
        case "Welcome Message 3": return "销售欢迎话术 3";
        case "新人训练路径商务技巧 AI 教练题目生成 v1": return "商务礼仪题目草稿生成 v1";
        default: return name;
    }
}

export function formatPromptType(type: string, displayType?: string | null): string {
    if (displayType) return displayType;
    return PROMPT_TYPE_LABELS[type as PromptType] || type;
}
