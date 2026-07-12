import type {
    TrainingJourneyResponse,
    TrainingJourneyStage,
} from "@/lib/api/types/training-journey";

/**
 * 团队看板与学员详情页共用的 ViewModel 映射。
 *
 * 这里集中处理「工程字段 → 用户可读文案」的转换，遵循 AGENTS.md：
 * 普通用户界面不得直接展示 module_key / stage 原始枚举 / risk_reason 工程字符串。
 * 看板页（team/page.tsx）与详情页（team/[learnerId]/page.tsx）共同 import 此模块，
 * 避免重复实现（code-reuse-thinking-guide.md：相同逻辑出现 3+ 次应抽取）。
 */

export const STAGE_LABELS: Record<TrainingJourneyStage, string> = {
    not_started: "未开始",
    in_progress: "训练中",
    waiting_upload: "待上传",
    processing: "处理中",
    scored: "已评分",
    passed: "已通过",
    failed: "未通过",
    needs_remediation: "待补救",
    manual_review: "待复核",
    disabled: "已停用",
    archived: "已归档",
    error_terminal: "异常",
    error_transient: "异常",
};

export function getStageLabel(stage: TrainingJourneyStage | string | null | undefined): string {
    if (!stage) {
        return "未识别状态";
    }
    return STAGE_LABELS[stage as TrainingJourneyStage] ?? stage;
}

export function getStageToneClass(stage: TrainingJourneyStage | string | null | undefined): string {
    if (stage === "passed" || stage === "scored") {
        return "bg-emerald-50 text-emerald-700 border-emerald-100";
    }
    if (stage === "failed" || stage === "error_terminal" || stage === "manual_review") {
        return "bg-red-50 text-red-700 border-red-100";
    }
    if (stage === "needs_remediation" || stage === "error_transient") {
        return "bg-amber-50 text-amber-700 border-amber-100";
    }
    return "bg-blue-50 text-blue-700 border-blue-100";
}

/**
 * 后端 module_key 是工程枚举（path_config_models.py CANONICAL_NEWCOMER_MODULE_KEYS），
 * 看板/详情页面向 training_manager，不得直接展示工程 key。这里提供兜底中文模块名，
 * 优先用 journey.modules[].title（受治理的运营文案）关联。
 */
export const MODULE_KEY_FALLBACK_LABELS: Record<string, string> = {
    ppt_explanation: "PPT 讲解",
    business_skills: "商务技巧",
    elevator_pitch: "电梯演讲",
    realtime_roleplay: "实时对练",
    realtime_roleplay_placeholder: "实时对练",
    ai_coach: "AI 教练",
    unknown: "训练模块",
};

/**
 * 解析后端 _analytics_risk_reason 产出的工程字符串为中文可读文案。
 * 格式 1："{module_key}:not_passed" → "{模块名}未通过"
 * 格式 2："{module_key}:status:{status}" → "{模块名}状态异常：{状态中文}"
 */
export function formatRiskReason(
    reason: string,
    moduleKeyToTitle: Map<string, string>,
): string {
    const trimmed = reason?.trim();
    if (!trimmed) {
        return "";
    }

    const notPassedSuffix = ":not_passed";
    if (trimmed.endsWith(notPassedSuffix)) {
        const moduleKey = trimmed.slice(0, -notPassedSuffix.length);
        const moduleLabel = moduleKeyToTitle.get(moduleKey)
            ?? MODULE_KEY_FALLBACK_LABELS[moduleKey]
            ?? MODULE_KEY_FALLBACK_LABELS.unknown;
        return `${moduleLabel}未通过`;
    }

    const statusPrefix = ":status:";
    const statusIndex = trimmed.indexOf(statusPrefix);
    if (statusIndex > 0) {
        const moduleKey = trimmed.slice(0, statusIndex);
        const status = trimmed.slice(statusIndex + statusPrefix.length);
        const moduleLabel = moduleKeyToTitle.get(moduleKey)
            ?? MODULE_KEY_FALLBACK_LABELS[moduleKey]
            ?? MODULE_KEY_FALLBACK_LABELS.unknown;
        const statusLabel = getStageLabel(status);
        return `${moduleLabel}状态异常：${statusLabel}`;
    }

    // 未知格式：不直接展示工程字符串，兜底为通用提示。
    return "需关注";
}

/**
 * 把多条 risk_reason 映射成中文，最多保留 2 条（避免详情页/看板条目过长）。
 */
export function formatRiskReasons(
    reasons: string[],
    moduleKeyToTitle: Map<string, string>,
): string[] {
    const mapped: string[] = [];
    for (const reason of reasons) {
        const label = formatRiskReason(reason, moduleKeyToTitle);
        if (label && !mapped.includes(label)) {
            mapped.push(label);
        }
        if (mapped.length >= 2) {
            break;
        }
    }
    return mapped;
}

/**
 * 从多条 journey 中构建 module_key → title 的映射，用于把 risk_reason 工程 key
 * 还原成学员可读的模块名。
 */
export function buildModuleKeyToTitleMap(journeys: TrainingJourneyResponse[]): Map<string, string> {
    const map = new Map<string, string>();
    for (const journey of journeys) {
        for (const journeyModule of journey.modules ?? []) {
            const key = journeyModule.module_key;
            const title = journeyModule.title?.trim();
            if (key && title && !map.has(key)) {
                map.set(key, title);
            }
        }
    }
    return map;
}

/**
 * 从单条 journey 的 modules 构建 module_key → title 映射（详情页用）。
 */
export function buildModuleKeyToTitleMapFromJourney(journey: TrainingJourneyResponse): Map<string, string> {
    const map = new Map<string, string>();
    for (const journeyModule of journey.modules ?? []) {
        const key = journeyModule.module_key;
        const title = journeyModule.title?.trim();
        if (key && title) {
            map.set(key, title);
        }
    }
    return map;
}

/**
 * 与后端 RISK_MODULE_STATUSES 一致的判定（training_journey_service.py:75）。
 * 详情页用本地 modules 自行判定待辅导，无需再调 analytics。
 */
const RISK_MODULE_STATUSES: ReadonlySet<string> = new Set([
    "failed",
    "needs_remediation",
    "manual_review",
    "error_terminal",
    "error_transient",
]);

export interface ModuleRiskIndicator {
    module_key: string;
    reason: string;
}

/**
 * 基于单条 journey 的 modules 本地判定该学员是否有待辅导模块。
 * 判定逻辑与后端 _analytics_risk_learners 一致：
 *   module.passed === false 或 module.status ∈ RISK_MODULE_STATUSES
 * 返回 risk_reason 工程 key 列表（未映射，调用方用 formatRiskReasons 转中文）。
 */
export function detectJourneyRiskModules(journey: TrainingJourneyResponse): ModuleRiskIndicator[] {
    const indicators: ModuleRiskIndicator[] = [];
    for (const journeyModule of journey.modules ?? []) {
        const passed = journeyModule.passed;
        const status = journeyModule.status;
        if (passed === false) {
            indicators.push({
                module_key: journeyModule.module_key,
                reason: `${journeyModule.module_key}:not_passed`,
            });
        } else if (typeof status === "string" && RISK_MODULE_STATUSES.has(status)) {
            indicators.push({
                module_key: journeyModule.module_key,
                reason: `${journeyModule.module_key}:status:${status}`,
            });
        }
    }
    return indicators;
}
