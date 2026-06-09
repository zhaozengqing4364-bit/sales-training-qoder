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
import { MODULE_DEFINITIONS } from "./config-center-definitions";
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
        return MODULE_DEFINITIONS;
    }
    const definitionByKey = new Map<NewcomerConfigModuleKey, ModuleDefinition>(
        MODULE_DEFINITIONS.map((definition) => [definition.moduleKey, definition]),
    );
    const configured = [...modules]
        .filter((module): module is NewcomerPathModuleConfig & { readonly module_key: NewcomerConfigModuleKey } => (
            isModuleKey(module.module_key)
        ))
        .sort((left, right) => left.order_index - right.order_index)
        .map((module) => definitionByKey.get(module.module_key))
        .filter((definition): definition is ModuleDefinition => Boolean(definition));
    const configuredKeys = new Set(configured.map((definition) => definition.moduleKey));
    const remaining = MODULE_DEFINITIONS.filter((definition) => !configuredKeys.has(definition.moduleKey));
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
    return MODULE_DEFINITIONS.some((definition) => definition.moduleKey === value);
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
    if (moduleKey === "ppt_explanation" || moduleKey === "elevator_pitch") {
        appendAudioIssues(moduleKey, issues, units, input, pathModule);
    }
    if (moduleKey === "business_skills") {
        appendBusinessIssues(issues, units, input, pathModule);
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
    if (!article) {
        issues.push(issue("article_missing", "缺少已发布商务技巧学习文章绑定。", "/admin/sales-trainer/articles"));
    } else if (article.chapters.length === 0) {
        issues.push(issue("article_chapters_missing", "商务技巧文章还没有学习章节。", "/admin/sales-trainer/articles"));
    }
    const paperIds = new Set(units.map((unit) => unit.config.path?.exam_paper_id).filter(Boolean));
    const configuredPaperId = pathModule?.exam_paper_id ?? null;
    const paperOk = Boolean(configuredPaperId && input.papers.some((paper) => paper.paper_id === configuredPaperId && paper.status === "published"))
        || [...paperIds].some((id) => input.papers.some((paper) => paper.paper_id === id && paper.status === "published"))
        || input.papers.some((paper) => paper.module_key === "business_skills" && paper.status === "published");
    if (!paperOk) {
        issues.push(issue("paper_missing", "缺少已发布商务技巧考卷绑定。", "/admin/sales-trainer/papers"));
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
            article ? `学习文章：${article.title}（${article.chapters.length} 节）` : "学习文章：未绑定",
            paper ? `考卷：${paper.title}（${paper.questions.length} 题）` : "考卷：未绑定",
        ];
    }
    if (moduleKey === "realtime_roleplay_placeholder") {
        return ["实时对练：当前版本仅占位，不创建实时会话"];
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
    return [
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
