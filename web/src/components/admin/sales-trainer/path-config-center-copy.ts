import type {
    NewcomerConfigModuleSummary,
    NewcomerConfigStatus,
} from "@/lib/sales-trainer/config-center";
import {
    audioEvaluationScenarioForModule,
    isAudioEvaluationModuleKey,
} from "@/lib/sales-trainer/audio-evaluation-scenarios";

export const STATUS_COPY: Record<
    NewcomerConfigStatus,
    { readonly label: string; readonly className: string }
> = {
    disabled: { label: "未开放", className: "bg-slate-100 text-slate-600 border-slate-200" },
    missing: { label: "缺配置", className: "bg-red-50 text-red-700 border-red-100" },
    ready: { label: "可发布", className: "bg-emerald-50 text-emerald-700 border-emerald-100" },
    warning: { label: "需确认", className: "bg-amber-50 text-amber-700 border-amber-100" },
};

export function statusCopy(status: NewcomerConfigStatus) {
    return STATUS_COPY[status];
}

export function issueActionLabel(code: string): string {
    if (code === "module_unit_missing") {
        return "配置路径模块";
    }
    if (code === "score_prompt_missing") {
        return "选择评分标准";
    }
    if (code === "material_missing") {
        return "选择材料版本";
    }
    if (code === "paper_missing") {
        return "配置考卷";
    }
    if (code === "article_missing" || code === "article_chapters_missing") {
        return "配置专题内容";
    }
    if (code === "runtime_binding_missing") {
        return "配置运行时绑定";
    }
    if (code === "provider_readiness_not_ready") {
        return "查看配置健康";
    }
    return "去配置";
}

export function remediationLabel(module: NewcomerConfigModuleSummary): string {
    if (module.moduleKey === "business_skills") {
        return "配置学习专题";
    }
    if (isAudioEvaluationModuleKey(module.moduleKey)) {
        return `治理${audioEvaluationScenarioForModule(module.moduleKey).title}`;
    }
    if (module.moduleKey === "realtime_roleplay") {
        return "配置实时对练";
    }
    return "配置占位说明";
}

export function moduleAvailabilityLabel(module: NewcomerConfigModuleSummary): string {
    if (module.canPublish) {
        return "学员端可见";
    }
    if (module.status === "missing") {
        return "需补齐后发布";
    }
    if (module.enabled) {
        return "需确认后发布";
    }
    return "当前不开放";
}

export function learnerPreviewStatusLabel(module: NewcomerConfigModuleSummary): string {
    if (module.status === "missing") {
        return "待配置";
    }
    return module.enabled ? "启用" : "关闭";
}
