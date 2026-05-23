import type { PromptType } from "@/lib/api/types";

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
        default: return issue;
    }
}

export function formatCategoryLabel(category: string): string {
    switch (category) {
        case "sales": return "销售训练";
        case "presentation": return "PPT 演练";
        default: return category;
    }
}
