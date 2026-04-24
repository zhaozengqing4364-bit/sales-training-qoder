import { describe, expect, it } from "vitest";

import {
    CLIENT_DEFAULT_SALES_COMBINATIONS_V1,
    normalizeSalesCombinationRuleSet,
    resolveSalesCombinationRuleSet,
} from "./sales-combinations";
import type { SalesCombinationRuleSet } from "./types";

const validRuleSet = (overrides: Partial<SalesCombinationRuleSet> = {}): SalesCombinationRuleSet => ({
    rule_set_id: "sales-core",
    version: "v2",
    status: "published",
    effective_at: "2026-04-24T00:00:00.000Z",
    fallback_policy: "client_default_v1",
    audit_summary: {
        published_by: "教研运营",
        published_at: "2026-04-24T00:00:00.000Z",
        reason: "季度更新",
        trace_id: "trace-1",
    },
    combinations: [
        {
            id: "server-2",
            capability: "异议处理",
            role: "强势质疑型客户",
            priority: 2,
            enabled: true,
        },
        {
            id: "server-disabled",
            capability: "破冰建立信任",
            role: "冷淡型客户",
            priority: 1,
            enabled: false,
        },
        {
            id: "server-1",
            capability: "需求挖掘",
            role: "价格敏感型客户",
            priority: 1,
            enabled: true,
            required_agent_match: ["需求挖掘"],
            required_persona_match: ["价格敏感"],
        },
    ],
    ...overrides,
});

describe("sales combination ruleset adapter", () => {
    it("normalizes enabled server combinations by priority and preserves governance metadata", () => {
        const normalized = normalizeSalesCombinationRuleSet(validRuleSet());

        expect(normalized.source).toBe("server");
        expect(normalized.ruleSetId).toBe("sales-core");
        expect(normalized.version).toBe("v2");
        expect(normalized.auditSummary?.reason).toBe("季度更新");
        expect(normalized.combinations.map((item) => item.id)).toEqual(["server-1", "server-2"]);
        expect(normalized.combinations[0]).toMatchObject({
            capability: "需求挖掘",
            role: "价格敏感型客户",
            requiredAgentMatch: ["需求挖掘"],
            requiredPersonaMatch: ["价格敏感"],
        });
    });

    it("falls back to the client default when the active ruleset is missing", () => {
        const resolved = resolveSalesCombinationRuleSet(null);

        expect(resolved.source).toBe("client_default");
        expect(resolved.fallbackReason).toBe("server_missing");
        expect(resolved.combinations).toHaveLength(CLIENT_DEFAULT_SALES_COMBINATIONS_V1.length);
    });

    it("rejects invalid server combinations and maps the invalid reason onto the fallback", () => {
        const resolved = resolveSalesCombinationRuleSet(validRuleSet({
            combinations: [
                {
                    id: "broken",
                    capability: "",
                    role: "价格敏感型客户",
                    priority: 1,
                    enabled: true,
                },
            ],
        }));

        expect(resolved.source).toBe("client_default");
        expect(resolved.fallbackReason).toBe("invalid_server_ruleset");
        expect(resolved.invalidReason).toContain("capability is required");
    });

    it("allows an explicit hide_all policy to publish zero enabled combinations without pretending defaults were used", () => {
        const normalized = normalizeSalesCombinationRuleSet(validRuleSet({
            fallback_policy: "hide_all",
            combinations: [
                {
                    id: "disabled",
                    capability: "需求挖掘",
                    role: "价格敏感型客户",
                    priority: 1,
                    enabled: false,
                },
            ],
        }));

        expect(normalized.source).toBe("server");
        expect(normalized.fallbackPolicy).toBe("hide_all");
        expect(normalized.combinations).toEqual([]);
    });
});
