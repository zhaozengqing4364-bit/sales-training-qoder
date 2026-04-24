import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminSalesCombinationsPage from "./page";
import type {
    SalesCombinationPreviewResponse,
    SalesCombinationRuleSet,
    SalesCombinationRuleSetListResponse,
} from "@/lib/api/types";

const {
    getSalesCombinationRuleSetsMock,
    previewSalesCombinationRuleSetMock,
    publishSalesCombinationRuleSetMock,
    rollbackSalesCombinationRuleSetMock,
} = vi.hoisted(() => ({
    getSalesCombinationRuleSetsMock: vi.fn(),
    previewSalesCombinationRuleSetMock: vi.fn(),
    publishSalesCombinationRuleSetMock: vi.fn(),
    rollbackSalesCombinationRuleSetMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getSalesCombinationRuleSets: getSalesCombinationRuleSetsMock,
                previewSalesCombinationRuleSet: previewSalesCombinationRuleSetMock,
                publishSalesCombinationRuleSet: publishSalesCombinationRuleSetMock,
                rollbackSalesCombinationRuleSet: rollbackSalesCombinationRuleSetMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
    },
}));

const activeRuleSet: SalesCombinationRuleSet = {
    rule_set_id: "active-sales-core",
    version: "v1",
    status: "published",
    effective_at: "2026-04-23T10:00:00.000Z",
    fallback_policy: "client_default_v1",
    audit_summary: {
        published_by: "admin-a",
        published_at: "2026-04-23T10:00:00.000Z",
        reason: "baseline",
        trace_id: "trace-active",
    },
    combinations: [
        {
            id: "c1",
            capability: "需求挖掘",
            role: "价格敏感型客户",
            priority: 1,
            enabled: true,
        },
    ],
};

const draftRuleSet: SalesCombinationRuleSet = {
    rule_set_id: "draft-sales-core",
    version: "v2-draft",
    status: "draft",
    effective_at: null,
    fallback_policy: "client_default_v1",
    combinations: [
        {
            id: "d1",
            capability: "异议处理",
            role: "强势质疑型客户",
            priority: 1,
            enabled: true,
        },
        {
            id: "d2",
            capability: "需求挖掘",
            role: "价格敏感型客户",
            priority: 2,
            enabled: true,
        },
    ],
};

const historyRuleSet: SalesCombinationRuleSet = {
    ...activeRuleSet,
    rule_set_id: "published-v0",
    version: "v0",
    audit_summary: {
        published_by: "admin-b",
        published_at: "2026-04-22T10:00:00.000Z",
        reason: "previous",
        trace_id: "trace-history",
    },
};

function listResponse(overrides: Partial<SalesCombinationRuleSetListResponse> = {}): SalesCombinationRuleSetListResponse {
    return {
        active: activeRuleSet,
        drafts: [draftRuleSet],
        history: [historyRuleSet],
        audit_log: [
            {
                id: "audit-1",
                action: "publish",
                actor: "admin-a",
                before_version: "v0",
                after_version: "v1",
                reason: "baseline",
                trace_id: "trace-active",
            },
        ],
        permissions: {
            can_view: true,
            can_mutate: true,
            can_publish: true,
            reason: null,
        },
        ...overrides,
    };
}

const previewResponse: SalesCombinationPreviewResponse = {
    valid: true,
    ruleset_version: "v2-draft",
    previewed_at: "2026-04-24T10:00:00.000Z",
    coverage: {
        total: 2,
        matched: 1,
        missing_agent: 1,
        missing_persona: 0,
        disabled: 0,
    },
    items: [],
};

describe("AdminSalesCombinationsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getSalesCombinationRuleSetsMock.mockResolvedValue(listResponse());
        previewSalesCombinationRuleSetMock.mockResolvedValue(previewResponse);
        publishSalesCombinationRuleSetMock.mockResolvedValue({
            ruleset: {
                ...draftRuleSet,
                status: "published",
                audit_summary: {
                    published_by: "admin-a",
                    published_at: "2026-04-24T10:05:00.000Z",
                    reason: "publish reason",
                    trace_id: "trace-publish",
                },
            },
            audit: {
                action: "publish",
                actor: "admin-a",
                before_version: "v1",
                after_version: "v2-draft",
                reason: "publish reason",
                trace_id: "trace-publish",
            },
        });
        rollbackSalesCombinationRuleSetMock.mockResolvedValue({
            ruleset: historyRuleSet,
            audit: {
                action: "rollback",
                actor: "admin-a",
                before_version: "v1",
                after_version: "v0",
                reason: "rollback reason",
                trace_id: "trace-rollback",
            },
        });
    });

    it("renders active, draft, history, and audit metadata from the governance API", async () => {
        render(<AdminSalesCombinationsPage />);

        expect(await screen.findByText("销售训练组合规则")).toBeTruthy();
        expect(screen.getByText("v1")).toBeTruthy();
        expect(screen.getByText(/发布人：admin-a/)).toBeTruthy();
        expect(screen.getByText(/原因：baseline/)).toBeTruthy();
        expect(screen.getByText("v2-draft")).toBeTruthy();
        expect(screen.getByText("trace: trace-history")).toBeTruthy();
        expect(screen.getByText(/publish · admin-a · v0 → v1 · baseline · trace trace-active/)).toBeTruthy();
    });

    it("keeps preview read-only and leaves the active version unchanged", async () => {
        render(<AdminSalesCombinationsPage />);

        await screen.findByText("v2-draft");
        fireEvent.click(screen.getByRole("button", { name: "预览覆盖率" }));

        expect(await screen.findByText(/预览完成；当前 active 仍为 v1/)).toBeTruthy();
        expect(screen.getByText("预览覆盖率 · v2-draft")).toBeTruthy();
        expect(previewSalesCombinationRuleSetMock).toHaveBeenCalledWith(expect.objectContaining({
            rule_set_id: "draft-sales-core",
        }));
        expect(publishSalesCombinationRuleSetMock).not.toHaveBeenCalled();
    });

    it("disables mutation controls for read-only admins instead of offering fake save actions", async () => {
        getSalesCombinationRuleSetsMock.mockResolvedValueOnce(listResponse({
            permissions: {
                can_view: true,
                can_mutate: false,
                can_publish: false,
                reason: "需要业务规则发布权限",
            },
        }));

        render(<AdminSalesCombinationsPage />);

        expect(await screen.findByText("需要业务规则发布权限")).toBeTruthy();
        expect((screen.getByRole("button", { name: "发布当前草稿" }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getAllByRole("button", { name: "回滚到此版本" })[0] as HTMLButtonElement).disabled).toBe(true);
    });

    it("blocks invalid schema publish before calling the mutation API", async () => {
        getSalesCombinationRuleSetsMock.mockResolvedValueOnce(listResponse({
            drafts: [{
                ...draftRuleSet,
                combinations: [
                    {
                        id: "dup",
                        capability: "需求挖掘",
                        role: "价格敏感型客户",
                        priority: 1,
                        enabled: true,
                    },
                    {
                        id: "dup",
                        capability: "需求挖掘",
                        role: "价格敏感型客户",
                        priority: 2,
                        enabled: true,
                    },
                ],
            }],
        }));

        render(<AdminSalesCombinationsPage />);

        expect(await screen.findByText(/组合 ID 重复：dup/)).toBeTruthy();
        expect(screen.getByText(/能力 × 角色重复：需求挖掘 × 价格敏感型客户/)).toBeTruthy();
        expect((screen.getByRole("button", { name: "发布当前草稿" }) as HTMLButtonElement).disabled).toBe(true);
        expect(publishSalesCombinationRuleSetMock).not.toHaveBeenCalled();
    });

    it("surfaces publish and rollback audit fields returned by the backend", async () => {
        render(<AdminSalesCombinationsPage />);

        await screen.findByText("v2-draft");
        fireEvent.change(screen.getByPlaceholderText("发布/回滚原因（必填，将进入审计记录）"), {
            target: { value: "publish reason" },
        });
        fireEvent.click(screen.getByRole("button", { name: "发布当前草稿" }));

        expect(await screen.findByText(/发布完成：admin-a v1 → v2-draft，原因：publish reason，trace：trace-publish/)).toBeTruthy();

        fireEvent.change(screen.getByPlaceholderText("发布/回滚原因（必填，将进入审计记录）"), {
            target: { value: "rollback reason" },
        });
        fireEvent.click(screen.getAllByRole("button", { name: "回滚到此版本" })[0]);

        await waitFor(() => {
            expect(rollbackSalesCombinationRuleSetMock).toHaveBeenCalled();
        });
        expect(await screen.findByText(/回滚完成：admin-a v1 → v0，原因：rollback reason，trace：trace-rollback/)).toBeTruthy();
    });
});
