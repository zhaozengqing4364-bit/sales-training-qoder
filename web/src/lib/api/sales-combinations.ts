import type {
    SalesCombinationFallbackPolicy,
    SalesCombinationRule,
    SalesCombinationRuleAuditSummary,
    SalesCombinationRuleSet,
} from "./types";

export type SalesCombinationFallbackReason =
    | "not_loaded"
    | "api_error"
    | "server_missing"
    | "invalid_server_ruleset"
    | "empty_server_ruleset";

export interface SalesCombinationViewModel {
    id: string;
    capability: string;
    role: string;
    priority: number;
    enabled: boolean;
    requiredAgentMatch: string[];
    requiredPersonaMatch: string[];
}

export interface SalesCombinationResolution {
    source: "server" | "client_default";
    ruleSetId: string;
    version: string;
    fallbackReason: SalesCombinationFallbackReason | null;
    invalidReason: string | null;
    fallbackPolicy: SalesCombinationFallbackPolicy;
    auditSummary: SalesCombinationRuleAuditSummary | null;
    combinations: SalesCombinationViewModel[];
}

export class SalesCombinationRuleSetValidationError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "SalesCombinationRuleSetValidationError";
    }
}

export const CLIENT_DEFAULT_SALES_COMBINATIONS_VERSION = "client_default_v1";

export const CLIENT_DEFAULT_SALES_COMBINATIONS_V1: SalesCombinationViewModel[] = [
    { id: "c1", capability: "破冰建立信任", role: "冷淡型客户", priority: 1, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c2", capability: "破冰建立信任", role: "强势质疑型客户", priority: 2, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c3", capability: "需求挖掘", role: "价格敏感型客户", priority: 3, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c4", capability: "需求挖掘", role: "拖延决策型客户", priority: 4, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c5", capability: "价值表达", role: "竞品比较型客户", priority: 5, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c6", capability: "价值表达", role: "价格敏感型客户", priority: 6, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c7", capability: "异议处理", role: "强势质疑型客户", priority: 7, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c8", capability: "异议处理", role: "竞品比较型客户", priority: 8, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c9", capability: "推进下一步行动", role: "拖延决策型客户", priority: 9, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
    { id: "c10", capability: "推进下一步行动", role: "冷淡型客户", priority: 10, enabled: true, requiredAgentMatch: [], requiredPersonaMatch: [] },
];

function normalizeStringList(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return value
        .map((item) => typeof item === "string" ? item.trim() : "")
        .filter(Boolean);
}

function normalizeRule(rule: SalesCombinationRule, index: number): SalesCombinationViewModel {
    const id = String(rule.id || "").trim();
    const capability = String(rule.capability || "").trim();
    const role = String(rule.role || "").trim();
    const priority = Number(rule.priority);

    if (!id) {
        throw new SalesCombinationRuleSetValidationError(`combination[${index}].id is required`);
    }
    if (!capability) {
        throw new SalesCombinationRuleSetValidationError(`combination[${index}].capability is required`);
    }
    if (!role) {
        throw new SalesCombinationRuleSetValidationError(`combination[${index}].role is required`);
    }
    if (!Number.isFinite(priority) || priority < 1) {
        throw new SalesCombinationRuleSetValidationError(`combination[${index}].priority must be a positive number`);
    }

    return {
        id,
        capability,
        role,
        priority,
        enabled: rule.enabled !== false,
        requiredAgentMatch: normalizeStringList(rule.required_agent_match),
        requiredPersonaMatch: normalizeStringList(rule.required_persona_match),
    };
}

function assertUniqueRules(rules: SalesCombinationViewModel[]) {
    const seenIds = new Set<string>();
    const seenPairs = new Set<string>();

    for (const rule of rules) {
        const pairKey = `${rule.capability}::${rule.role}`.toLowerCase();
        if (seenIds.has(rule.id)) {
            throw new SalesCombinationRuleSetValidationError(`duplicate combination id: ${rule.id}`);
        }
        if (seenPairs.has(pairKey)) {
            throw new SalesCombinationRuleSetValidationError(`duplicate capability/role pair: ${rule.capability} × ${rule.role}`);
        }
        seenIds.add(rule.id);
        seenPairs.add(pairKey);
    }
}

export function normalizeSalesCombinationRuleSet(
    input: SalesCombinationRuleSet,
): SalesCombinationResolution {
    if (!input || typeof input !== "object") {
        throw new SalesCombinationRuleSetValidationError("active sales-combination ruleset is missing");
    }

    const ruleSetId = String(input.rule_set_id || "").trim();
    const version = String(input.version || "").trim();
    const fallbackPolicy = input.fallback_policy || CLIENT_DEFAULT_SALES_COMBINATIONS_VERSION;

    if (!ruleSetId) {
        throw new SalesCombinationRuleSetValidationError("rule_set_id is required");
    }
    if (!version) {
        throw new SalesCombinationRuleSetValidationError("version is required");
    }
    if (!Array.isArray(input.combinations)) {
        throw new SalesCombinationRuleSetValidationError("combinations must be an array");
    }
    if (fallbackPolicy !== "client_default_v1" && fallbackPolicy !== "hide_all") {
        throw new SalesCombinationRuleSetValidationError(`unsupported fallback_policy: ${fallbackPolicy}`);
    }

    const allRules = input.combinations.map(normalizeRule);
    assertUniqueRules(allRules);

    const enabledRules = allRules
        .filter((rule) => rule.enabled)
        .sort((left, right) => left.priority - right.priority || left.id.localeCompare(right.id));

    if (enabledRules.length === 0 && fallbackPolicy !== "hide_all") {
        throw new SalesCombinationRuleSetValidationError("published sales-combination ruleset has no enabled combinations");
    }

    return {
        source: "server",
        ruleSetId,
        version,
        fallbackReason: null,
        invalidReason: null,
        fallbackPolicy,
        auditSummary: input.audit_summary ?? null,
        combinations: enabledRules,
    };
}

export function buildClientDefaultSalesCombinationResolution(
    fallbackReason: SalesCombinationFallbackReason,
    invalidReason: string | null = null,
): SalesCombinationResolution {
    return {
        source: "client_default",
        ruleSetId: "client-default-sales-combinations",
        version: CLIENT_DEFAULT_SALES_COMBINATIONS_VERSION,
        fallbackReason,
        invalidReason,
        fallbackPolicy: "client_default_v1",
        auditSummary: null,
        combinations: CLIENT_DEFAULT_SALES_COMBINATIONS_V1,
    };
}

export function resolveSalesCombinationRuleSet(
    input: SalesCombinationRuleSet | null | undefined,
): SalesCombinationResolution {
    if (!input) {
        return buildClientDefaultSalesCombinationResolution(
            "server_missing",
            "active sales-combination ruleset response was empty",
        );
    }

    try {
        return normalizeSalesCombinationRuleSet(input);
    } catch (error) {
        return buildClientDefaultSalesCombinationResolution(
            "invalid_server_ruleset",
            error instanceof Error ? error.message : "active sales-combination ruleset is invalid",
        );
    }
}

export function formatSalesCombinationFallbackReason(resolution: SalesCombinationResolution): string | null {
    if (!resolution.fallbackReason) {
        return null;
    }

    const reasonCopy: Record<SalesCombinationFallbackReason, string> = {
        not_loaded: "正在读取后台组合配置，暂用安全兜底。",
        api_error: "后台组合配置读取失败，已使用前端安全兜底。",
        server_missing: "后台尚未发布销售训练组合，已使用前端安全兜底。",
        invalid_server_ruleset: "后台销售训练组合配置无效，已使用前端安全兜底。",
        empty_server_ruleset: "后台销售训练组合为空，已使用前端安全兜底。",
    };

    return reasonCopy[resolution.fallbackReason];
}
