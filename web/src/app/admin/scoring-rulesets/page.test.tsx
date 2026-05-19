import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminScoringRulesetsPage from "./page";
import type { ScoringRulesetRecord } from "@/lib/api/types";

const {
    listScoringRulesetsMock,
    getActiveScoringRulesetMock,
    createScoringRulesetMock,
    updateScoringRulesetMock,
    publishScoringRulesetMock,
    rollbackScoringRulesetMock,
    dryRunScoringRulesetMock,
    listScoringRulesetAuditLogsMock,
} = vi.hoisted(() => ({
    listScoringRulesetsMock: vi.fn(),
    getActiveScoringRulesetMock: vi.fn(),
    createScoringRulesetMock: vi.fn(),
    updateScoringRulesetMock: vi.fn(),
    publishScoringRulesetMock: vi.fn(),
    rollbackScoringRulesetMock: vi.fn(),
    dryRunScoringRulesetMock: vi.fn(),
    listScoringRulesetAuditLogsMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listScoringRulesets: listScoringRulesetsMock,
                getActiveScoringRuleset: getActiveScoringRulesetMock,
                createScoringRuleset: createScoringRulesetMock,
                updateScoringRuleset: updateScoringRulesetMock,
                publishScoringRuleset: publishScoringRulesetMock,
                rollbackScoringRuleset: rollbackScoringRulesetMock,
                dryRunScoringRuleset: dryRunScoringRulesetMock,
                listScoringRulesetAuditLogs: listScoringRulesetAuditLogsMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
    },
}));

const defaultDefinition = {
    schema_version: "scoring_ruleset_schema_v1",
    scenario_type: "sales",
    score_basis: "session_evidence_projection_evaluable_only",
    dimensions: [
        {
            dimension_id: "value_logic",
            label: "价值逻辑",
            weight: 1,
            rollup_contributions: [{ rollup_id: "logic", weight: 1 }],
            min_evidence: {},
        },
    ],
    min_evidence: {
        min_messages: 1,
        require_score_evidence: true,
        require_stage_evidence: false,
    },
    not_evaluable_reasons: {
        missing_min_messages: "缺少足够对话证据，无法按当前评分规则评估。",
    },
};

const activeRuleset: ScoringRulesetRecord = {
    ruleset_id: "ruleset-active",
    scenario_type: "sales",
    version: "sales-v1",
    display_name: "Sales scoring v1",
    description: "baseline",
    status: "published",
    definition: defaultDefinition,
    is_active: true,
    source: "admin",
    created_at: "2026-04-23T10:00:00.000Z",
    updated_at: "2026-04-23T10:00:00.000Z",
    published_at: "2026-04-23T10:00:00.000Z",
};

const draftRuleset: ScoringRulesetRecord = {
    ...activeRuleset,
    ruleset_id: "ruleset-draft",
    version: "sales-v2",
    display_name: "Sales scoring v2",
    description: "candidate",
    status: "draft",
    is_active: false,
    published_at: null,
};

const publishedHistory: ScoringRulesetRecord = {
    ...activeRuleset,
    ruleset_id: "ruleset-history",
    version: "sales-v0",
    display_name: "Sales scoring v0",
    is_active: false,
    published_at: "2026-04-22T10:00:00.000Z",
};

describe("AdminScoringRulesetsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listScoringRulesetsMock.mockResolvedValue({
            items: [draftRuleset, activeRuleset, publishedHistory],
            total: 3,
            actor_id: "admin-a",
        });
        getActiveScoringRulesetMock.mockResolvedValue(activeRuleset);
        createScoringRulesetMock.mockResolvedValue(draftRuleset);
        updateScoringRulesetMock.mockResolvedValue(draftRuleset);
        publishScoringRulesetMock.mockResolvedValue({
            ...draftRuleset,
            status: "published",
            is_active: true,
        });
        rollbackScoringRulesetMock.mockResolvedValue({
            ...publishedHistory,
            is_active: true,
        });
        dryRunScoringRulesetMock.mockResolvedValue({
            session_id: "session-1",
            mode: "dry_run",
            mutates_history: false,
            baseline: { overall_score: 70 },
            candidate: { overall_score: 76 },
            delta: { overall_score: 6 },
        });
        listScoringRulesetAuditLogsMock.mockResolvedValue({
            items: [
                {
                    id: "audit-1",
                    action: "scoring_ruleset.publish",
                    actor_id: "admin-a",
                    actor_role: "admin",
                    reason: "publish scoring candidate",
                    trace_id: "trace-1",
                    before: { version: "sales-v1" },
                    after: { version: "sales-v2" },
                    created_at: "2026-04-23T10:30:00.000Z",
                },
            ],
            total: 1,
        });
    });

    it("loads active and draft scoring ruleset metadata from evaluation admin APIs", async () => {
        render(<AdminScoringRulesetsPage />);

        expect(await screen.findByText("评分规则集")).toBeTruthy();
        expect(screen.getByText("sales-v1")).toBeTruthy();
        expect(screen.getByText("Sales scoring v1")).toBeTruthy();
        expect(screen.getAllByText(/sales-v2/).length).toBeGreaterThan(0);
        expect(screen.getByText(/API: \/api\/v1\/evaluation\/admin\/scoring-rulesets/)).toBeTruthy();
        expect(await screen.findByText("审计日志")).toBeTruthy();
        expect(screen.getByText("scoring_ruleset.publish")).toBeTruthy();
        expect(screen.getByText(/publish scoring candidate/)).toBeTruthy();
        expect(listScoringRulesetAuditLogsMock).toHaveBeenCalled();
    });

    it("dry-runs selected candidate without publishing history", async () => {
        render(<AdminScoringRulesetsPage />);

        await screen.findAllByText(/sales-v2/);
        fireEvent.change(screen.getByPlaceholderText("试运行 session_id"), {
            target: { value: "session-1" },
        });
        fireEvent.click(screen.getByRole("button", { name: "试运行" }));

        expect(await screen.findByText(/试运行完成；不会修改历史记录/)).toBeTruthy();
        expect(screen.getByText(/"overall_score": 6/)).toBeTruthy();
        expect(dryRunScoringRulesetMock).toHaveBeenCalledWith({
            session_id: "session-1",
            candidate_ruleset_id: "ruleset-draft",
            candidate_definition: undefined,
        });
        expect(publishScoringRulesetMock).not.toHaveBeenCalled();
    });

    it("updates a draft and publishes it with an audit reason", async () => {
        render(<AdminScoringRulesetsPage />);

        await screen.findAllByText(/sales-v2/);
        fireEvent.change(screen.getByPlaceholderText("发布/回滚/更新原因（必填，将进入审计日志）"), {
            target: { value: "publish scoring candidate" },
        });
        fireEvent.click(screen.getByRole("button", { name: "更新草稿" }));

        expect(await screen.findByText(/草稿已更新：sales-v2/)).toBeTruthy();
        expect(updateScoringRulesetMock).toHaveBeenCalledWith(
            "ruleset-draft",
            expect.objectContaining({
                display_name: "Sales scoring v2",
                definition: expect.objectContaining({ schema_version: "scoring_ruleset_schema_v1" }),
            }),
        );

        fireEvent.click(screen.getByRole("button", { name: "发布选中规则" }));
        expect(publishScoringRulesetMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));

        await waitFor(() => {
            expect(publishScoringRulesetMock).toHaveBeenCalledWith("ruleset-draft", "publish scoring candidate");
        });
    });

    it("blocks invalid JSON before creating or updating ruleset drafts", async () => {
        render(<AdminScoringRulesetsPage />);

        const editor = await screen.findByLabelText("评分规则 JSON 定义");
        fireEvent.change(editor, { target: { value: "[" } });

        expect(screen.getByText(/JSON 格式错误/)).toBeTruthy();
        expect((screen.getByRole("button", { name: "更新草稿" }) as HTMLButtonElement).disabled).toBe(true);
        expect(updateScoringRulesetMock).not.toHaveBeenCalled();
    });

    it("rolls back only to a published historical ruleset after reason is supplied", async () => {
        render(<AdminScoringRulesetsPage />);

        await screen.findAllByText(/sales-v2/);
        const rollbackButtons = screen.getAllByRole("button", { name: "回滚到此版本" });
        fireEvent.click(rollbackButtons[1]);
        expect(await screen.findByText("发布、回滚或更新前必须填写原因，原因会进入后端审计日志。")).toBeTruthy();
        expect(rollbackScoringRulesetMock).not.toHaveBeenCalled();

        fireEvent.change(screen.getByPlaceholderText("发布/回滚/更新原因（必填，将进入审计日志）"), {
            target: { value: "restore baseline scoring" },
        });
        fireEvent.click(rollbackButtons[1]);
        expect(rollbackScoringRulesetMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认回滚" }));

        await waitFor(() => {
            expect(rollbackScoringRulesetMock).toHaveBeenCalledWith("ruleset-history", "restore baseline scoring");
        });
    });
});
