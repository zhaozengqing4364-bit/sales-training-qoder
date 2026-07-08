import type {
    NewcomerArticle,
    NewcomerExamPaper,
    NewcomerPathModuleConfig,
    SalesTrainerUnit,
} from "@/lib/api/types";

import {
    NEWCOMER_TRAINING_PATH_KEY,
    NEW_SELLER_MODULES_PATH_KEY,
} from "./module-path";
import {
    appendAudioIssues,
    audioBindings,
} from "./config-center-audio";
import {
    CORE_MODULE_DEFINITIONS,
    MODULE_DEFINITIONS,
} from "./config-center-definitions";
import { isAudioEvaluationModuleKey } from "./audio-evaluation-scenarios";
import type {
    ModuleDefinition,
    NewcomerConfigCenterInput,
    NewcomerConfigCenterModel,
    NewcomerConfigCenterSummary,
    NewcomerConfigCenterGovernance,
    NewcomerConfigIssue,
    NewcomerConfigModuleKey,
    NewcomerConfigModuleSummary,
    NewcomerConfigStatus,
    NewcomerOperationalCheck,
} from "./config-center-types";
import { readRealtimeProviderReadinessDiagnostics } from "./realtime-provider-readiness";

export type {
    ModuleDefinition,
    NewcomerConfigCenterInput,
    NewcomerConfigCenterModel,
    NewcomerConfigCenterSummary,
    NewcomerConfigIssue,
    NewcomerConfigModuleKey,
    NewcomerConfigModuleSummary,
    NewcomerConfigStatus,
    NewcomerOperationalCheck,
} from "./config-center-types";

const PATH_KEYS = new Set<string>([NEWCOMER_TRAINING_PATH_KEY, NEW_SELLER_MODULES_PATH_KEY]);
const RUNTIME_HEALTH_HREF = "/support/runtime";
const REALTIME_ROLEPLAY_DEFINITION = {
    moduleKey: "realtime_roleplay",
    title: "实时对练",
    orderLabel: "第四关",
    description: "绑定实时运行时、provider readiness 和权限策略，学员进入真实对练会话。",
    remediationHref: "/admin/sales-trainer/paths?module=realtime_roleplay",
    learnerPreview: "进入实时对练前会先检查运行时绑定和 provider readiness。",
} as const satisfies ModuleDefinition;

export function buildNewcomerConfigCenter(
    input: NewcomerConfigCenterInput,
): NewcomerConfigCenterModel {
    const modules = orderedDefinitions(input).map((definition, index) => (
        buildModuleSummary(definition, input, index + 1)
    ));
    const operationalChecks = buildOperationalChecks(input);
    const summary = buildSummary(modules);
    const governance = buildGovernance(input);
    return { modules, operationalChecks, summary, governance };
}

function buildModuleSummary(
    definition: ModuleDefinition,
    input: NewcomerConfigCenterInput,
    displayOrder: number,
): NewcomerConfigModuleSummary {
    const pathModule = pathModuleForDefinition(input, definition.moduleKey);
    const units = unitsForModule(input, definition.moduleKey, pathModule);
    const issues = moduleIssues(definition.moduleKey, units, input, pathModule);
    const bindings = moduleBindings(definition.moduleKey, units, input, pathModule);
    const enabled = moduleEnabled(definition.moduleKey, units, pathModule, Boolean(input.pathConfig));
    return {
        moduleKey: definition.moduleKey,
        title: configuredTitle(definition, units, pathModule),
        orderLabel: configuredOrderLabel(displayOrder),
        description: configuredDescription(definition, units, pathModule),
        status: moduleStatus(definition.moduleKey, enabled, issues),
        enabled,
        canPublish: enabled && issues.length === 0,
        unitIds: configuredUnitIds(units, pathModule),
        bindings,
        issues,
        remediationHref: definition.remediationHref,
        learnerPreview: definition.learnerPreview,
    };
}

function orderedDefinitions(input: NewcomerConfigCenterInput): readonly ModuleDefinition[] {
    const modules = input.pathConfig?.path.modules ?? [];
    if (modules.length === 0) {
        return CORE_MODULE_DEFINITIONS;
    }
    const definitionByKey = new Map<NewcomerConfigModuleKey, ModuleDefinition>(
        [...MODULE_DEFINITIONS, REALTIME_ROLEPLAY_DEFINITION].map((definition) => [
            definition.moduleKey,
            definition,
        ]),
    );
    const configured = [...modules]
        .filter((module): module is NewcomerPathModuleConfig & { readonly module_key: NewcomerConfigModuleKey } => (
            isModuleKey(module.module_key)
        ))
        .sort((left, right) => left.order_index - right.order_index)
        .map((module) => definitionByKey.get(module.module_key))
        .filter((definition): definition is ModuleDefinition => Boolean(definition));
    const configuredKeys = new Set(configured.map((definition) => definition.moduleKey));
    const remaining = CORE_MODULE_DEFINITIONS.filter((definition) => {
        if (definition.moduleKey === "realtime_roleplay_placeholder" && configuredKeys.has("realtime_roleplay")) {
            return false;
        }
        return !configuredKeys.has(definition.moduleKey);
    });
    return [...configured, ...remaining];
}

function pathModuleForDefinition(
    input: NewcomerConfigCenterInput,
    moduleKey: NewcomerConfigModuleKey,
): NewcomerPathModuleConfig | null {
    const modules = input.pathConfig?.path.modules ?? [];
    return modules.find((module) => module.module_key === moduleKey) ?? null;
}

function unitsForModule(
    input: NewcomerConfigCenterInput,
    moduleKey: NewcomerConfigModuleKey,
    pathModule: NewcomerPathModuleConfig | null,
): readonly SalesTrainerUnit[] {
    if (!input.pathConfig) {
        return input.units.filter((unit) => moduleKeyForUnit(unit) === moduleKey);
    }
    if (pathModule?.target_unit_id) {
        return input.units.filter((unit) => unit.unit_id === pathModule.target_unit_id);
    }
    return [];
}

function moduleKeyForUnit(unit: SalesTrainerUnit): NewcomerConfigModuleKey | null {
    const path = unit.config.path;
    if (!path?.enabled || !path.path_key || !PATH_KEYS.has(path.path_key)) {
        return null;
    }
    if (isModuleKey(path.module_key)) {
        return path.module_key;
    }
    return null;
}

function isModuleKey(value: string | null | undefined): value is NewcomerConfigModuleKey {
    return [...MODULE_DEFINITIONS, REALTIME_ROLEPLAY_DEFINITION].some(
        (definition) => definition.moduleKey === value,
    );
}

function moduleStatus(
    moduleKey: NewcomerConfigModuleKey,
    enabled: boolean,
    issues: readonly NewcomerConfigIssue[],
): NewcomerConfigStatus {
    if (moduleKey === "realtime_roleplay_placeholder" && !enabled) {
        return "disabled";
    }
    if (issues.some((issue) => issue.code.endsWith("_missing"))) {
        return "missing";
    }
    return issues.length ? "warning" : "ready";
}

function moduleIssues(
    moduleKey: NewcomerConfigModuleKey,
    units: readonly SalesTrainerUnit[],
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
): NewcomerConfigIssue[] {
    const issues: NewcomerConfigIssue[] = [];
    if (moduleKey !== "realtime_roleplay_placeholder" && !pathModule && units.length === 0) {
        issues.push(issue(
            "module_unit_missing",
            "缺少路径配置中心里的关卡配置。",
            `/admin/sales-trainer/paths?module=${moduleKey}`,
        ));
    }
    if (isAudioEvaluationModuleKey(moduleKey)) {
        appendAudioIssues(moduleKey, issues, units, input, pathModule);
    }
    if (moduleKey === "business_skills") {
        appendBusinessIssues(issues, units, input, pathModule);
    }
    if (moduleKey === "realtime_roleplay") {
        appendRealtimeIssues(issues, pathModule);
    }
    return issues;
}

function appendBusinessIssues(
    issues: NewcomerConfigIssue[],
    units: readonly SalesTrainerUnit[],
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
): void {
    const article = businessArticle(input, pathModule);
    if (input.boundArticleLoadError) {
        issues.push(issue(
            "article_binding_unavailable",
            `学习专题内容绑定状态读取失败：${input.boundArticleLoadError}`,
        "/admin/sales-trainer/learning-topics",
        ));
    }
    if (!article && !input.boundArticleLoadError) {
        issues.push(issue("article_missing", "缺少已发布学习专题内容绑定。", "/admin/sales-trainer/learning-topics"));
    } else if (article && article.chapters.length === 0) {
        issues.push(issue("article_chapters_missing", "学习专题内容还没有学习章节。", "/admin/sales-trainer/learning-topics"));
    }
    const paperIds = new Set(units.map((unit) => unit.config.path?.exam_paper_id).filter(Boolean));
    const configuredPaperId = pathModule?.exam_paper_id ?? null;
    const paperOk = Boolean(configuredPaperId && input.papers.some((paper) => paper.paper_id === configuredPaperId && paper.status === "published"))
        || [...paperIds].some((id) => input.papers.some((paper) => paper.paper_id === id && paper.status === "published"))
        || input.papers.some((paper) => paper.module_key === "business_skills" && paper.status === "published");
    if (!paperOk) {
        issues.push(issue("paper_missing", "缺少已发布学习专题考卷绑定。", "/admin/sales-trainer/learning-topics/papers"));
    }
}

function moduleBindings(
    moduleKey: NewcomerConfigModuleKey,
    units: readonly SalesTrainerUnit[],
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
): string[] {
    if (moduleKey === "business_skills") {
        const article = businessArticle(input, pathModule);
        const paper = businessPaper(input, pathModule, units);
        return [
            article ? `专题内容：${article.title}（${article.chapters.length} 节）` : "专题内容：未绑定",
            paper ? `考卷：${paper.title}（${paper.questions.length} 题）` : "考卷：未绑定",
        ];
    }
    if (moduleKey === "realtime_roleplay_placeholder") {
        return ["实时对练：当前版本仅占位，不创建实时会话"];
    }
    if (moduleKey === "realtime_roleplay") {
        return realtimeBindings(pathModule);
    }
    return audioBindings(units, input, pathModule);
}

function businessArticle(
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
): NewcomerArticle | null {
    if (pathModule?.learning_content_id) {
        return input.articles.find((article) => article.learning_content_id === pathModule.learning_content_id)
            ?? input.boundArticle;
    }
    return input.boundArticle;
}

function businessPaper(
    input: NewcomerConfigCenterInput,
    pathModule: NewcomerPathModuleConfig | null,
    units: readonly SalesTrainerUnit[],
): NewcomerExamPaper | null {
    if (pathModule?.exam_paper_id) {
        return input.papers.find((paper) => paper.paper_id === pathModule.exam_paper_id) ?? null;
    }
    const paperIds = new Set(units.map((unit) => unit.config.path?.exam_paper_id).filter(Boolean));
    return input.papers.find((paper) => paperIds.has(paper.paper_id) && paper.status === "published")
        ?? input.papers.find((paper) => paper.module_key === "business_skills" && paper.status === "published")
        ?? null;
}

function buildOperationalChecks(input: NewcomerConfigCenterInput): NewcomerOperationalCheck[] {
    const settings = input.settings;
    const checks: NewcomerOperationalCheck[] = [
        {
            key: "path_revision_authority",
            label: "路径真源",
            ok: input.pathConfig?.source === "active_revision",
            detail: input.pathConfig
                ? pathAuthorityDetail(input.pathConfig.fallback_reason ?? null)
                : "路径配置读取失败",
            href: "/admin/sales-trainer/paths",
        },
        {
            key: "asr",
            label: "ASR 转写",
            ok: Boolean(settings && (settings.asr_mode === "mock" || settings.dashscope_configured)),
            detail: settings ? `${settings.asr_mode} / ${settings.asr_model}` : "设置读取失败",
            href: "/admin/sales-trainer/settings",
        },
        {
            key: "ai_scoring",
            label: "AI 评分服务",
            ok: Boolean(settings?.deucate_configured),
            detail: settings?.deucate_model ?? "未配置评分模型",
            href: "/admin/sales-trainer/settings",
        },
    ];
    for (const diagnostic of realtimeProviderDiagnostics(input)) {
        checks.push({
            key: `realtime_provider_${diagnostic.moduleKey}`,
            label: "实时对练 Provider",
            ok: diagnostic.ready,
            detail: diagnostic.detail,
            href: RUNTIME_HEALTH_HREF,
        });
    }
    if (input.pathConfig?.has_unpublished_revision) {
        checks.push({
            key: "path_publish_preview",
            label: "发布预览",
            ok: Boolean(input.publishPreview && !input.publishPreviewLoadError),
            detail: publishPreviewDetail(input),
            href: "/admin/sales-trainer/paths",
        });
    }
    return checks;
}

function buildSummary(modules: readonly NewcomerConfigModuleSummary[]): NewcomerConfigCenterSummary {
    const readyCount = modules.filter((module) => module.status === "ready").length;
    const missingCount = modules.filter((module) => module.status === "missing").length;
    const warningCount = modules.filter((module) => module.status === "warning").length;
    const disabledCount = modules.filter((module) => module.status === "disabled").length;
    return {
        ready: missingCount === 0 && warningCount === 0,
        readyCount,
        missingCount,
        warningCount,
        disabledCount,
    };
}

function buildGovernance(input: NewcomerConfigCenterInput): NewcomerConfigCenterGovernance {
    const pathConfig = input.pathConfig;
    const revisions = input.pathRevisions ?? [];
    if (!pathConfig) {
        return {
            source: "legacy_units",
            sourceLabel: "兼容单元聚合",
            activeRevisionLabel: "尚未建立路径级版本",
            workingRevisionLabel: "无待发布修订",
            hasUnpublishedRevision: false,
            revisionCount: revisions.length,
            latestReason: revisions[0]?.reason ?? null,
            revisions,
            fallbackApplied: true,
            fallbackReason: "path_config_unavailable",
            publishPreview: null,
            publishPreviewLoadError: input.publishPreviewLoadError ?? null,
        };
    }
    return {
        source: pathConfig.source,
        sourceLabel: pathConfig.source === "active_revision" ? "路径级发布配置" : "兼容迁移视图",
        activeRevisionLabel: pathConfig.active_revision_no
            ? `当前生效版本 v${pathConfig.active_revision_no}`
            : "尚未发布路径级版本",
        workingRevisionLabel: pathConfig.working_revision_no
            ? `待发布修订 v${pathConfig.working_revision_no}`
            : "无待发布修订",
        hasUnpublishedRevision: pathConfig.has_unpublished_revision,
        revisionCount: revisions.length,
        latestReason: revisions[0]?.reason ?? null,
        revisions,
        fallbackApplied: Boolean(pathConfig.fallback_reason || pathConfig.legacy_snapshot_only),
        fallbackReason: pathConfig.fallback_reason ?? null,
        publishPreview: input.publishPreview ?? null,
        publishPreviewLoadError: input.publishPreviewLoadError ?? null,
    };
}

function configuredTitle(
    definition: ModuleDefinition,
    units: readonly SalesTrainerUnit[],
    pathModule: NewcomerPathModuleConfig | null,
): string {
    if (pathModule?.title) {
        return pathModule.title;
    }
    return units[0]?.config.path?.level_title ?? definition.title;
}

function configuredOrderLabel(
    displayOrder: number,
): string {
    const labels: Record<number, string> = {
        1: "第一关",
        2: "第二关",
        3: "第三关",
        4: "第四关",
    };
    return labels[displayOrder] ?? `第${displayOrder}关`;
}

function configuredDescription(
    definition: ModuleDefinition,
    units: readonly SalesTrainerUnit[],
    pathModule: NewcomerPathModuleConfig | null,
): string {
    if (pathModule?.description) {
        return pathModule.description;
    }
    return units[0]?.config.path?.level_description ?? definition.description;
}

function configuredUnitIds(
    units: readonly SalesTrainerUnit[],
    pathModule: NewcomerPathModuleConfig | null,
): readonly string[] {
    if (pathModule?.target_unit_id) {
        return [pathModule.target_unit_id];
    }
    return units.map((unit) => unit.unit_id);
}

function moduleEnabled(
    moduleKey: NewcomerConfigModuleKey,
    units: readonly SalesTrainerUnit[],
    pathModule: NewcomerPathModuleConfig | null,
    hasPathConfig: boolean,
): boolean {
    if (pathModule) {
        return pathModule.enabled;
    }
    if (hasPathConfig) {
        return false;
    }
    if (moduleKey === "realtime_roleplay_placeholder") {
        return false;
    }
    return units.some((unit) => unit.config.path?.enabled !== false);
}

function issue(code: string, message: string, href: string): NewcomerConfigIssue {
    return { code, message, href };
}

function appendRealtimeIssues(
    issues: NewcomerConfigIssue[],
    pathModule: NewcomerPathModuleConfig | null,
): void {
    if (!pathModule?.runtime_binding) {
        issues.push(issue(
            "runtime_binding_missing",
            "实时对练缺少 runtime binding，发布会被后端拒绝。",
            "/admin/sales-trainer/paths?module=realtime_roleplay",
        ));
        return;
    }
    const readiness = pathModule.runtime_binding.provider_readiness_snapshot;
    if (!readiness.ready) {
        issues.push(issue(
            "provider_readiness_not_ready",
            `实时对练 provider readiness 未通过：${readiness.failure_message ?? readiness.failure_code ?? "provider 未就绪"}`,
            RUNTIME_HEALTH_HREF,
        ));
    }
}

function realtimeBindings(pathModule: NewcomerPathModuleConfig | null): string[] {
    const binding = pathModule?.runtime_binding;
    if (!binding) {
        return ["运行时绑定：未配置", "Provider readiness：未检查"];
    }
    const readiness = binding.provider_readiness_snapshot;
    return [
        `运行时：${binding.runtime_descriptor_id} / ${binding.runtime_config_revision_id}`,
        readiness.ready
            ? `Provider readiness：${readiness.provider ?? "unknown"} 已就绪`
            : `Provider readiness：未就绪（${readiness.failure_message ?? readiness.failure_code ?? "unknown"}）`,
    ];
}

function pathAuthorityDetail(fallbackReason: string | null): string {
    if (!fallbackReason) {
        return "active path revision";
    }
    return `fallback_applied=true / ${fallbackReason}`;
}

function publishPreviewDetail(input: NewcomerConfigCenterInput): string {
    if (input.publishPreviewLoadError) {
        return input.publishPreviewLoadError;
    }
    const preview = input.publishPreview;
    if (!preview) {
        return "待发布修订存在，但发布预览尚未生成";
    }
    const changedModules = stringListFromUnknown(preview.impact_scope.changed_module_keys);
    return `${preview.risk_level} 风险 / 影响 ${changedModules.length ? changedModules.join(", ") : "路径元数据"}`;
}

function realtimeProviderDiagnostics(input: NewcomerConfigCenterInput): {
    readonly moduleKey: string;
    readonly ready: boolean;
    readonly detail: string;
}[] {
    const fromDiagnostics = readRealtimeProviderReadinessDiagnostics(input.pathConfig?.diagnostics);
    if (fromDiagnostics) {
        return fromDiagnostics;
    }
    return (input.pathConfig?.path.modules ?? [])
        .filter((module) => module.module_type === "realtime_roleplay")
        .map((module) => {
            const binding = module.runtime_binding;
            const readiness = binding?.provider_readiness_snapshot;
            return {
                moduleKey: module.module_key,
                ready: Boolean(readiness?.ready),
                detail: readiness?.ready
                    ? `${readiness.provider ?? "unknown"} / ${binding?.runtime_descriptor_id ?? "runtime 未知"}`
                    : readiness?.failure_message ?? readiness?.failure_code ?? "runtime binding 或 provider readiness 未就绪",
            };
        });
}

function stringListFromUnknown(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter((item): item is string => typeof item === "string");
}
