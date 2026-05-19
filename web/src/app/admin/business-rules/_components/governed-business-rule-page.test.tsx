import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GovernedBusinessRulePage } from "./governed-business-rule-page";
import type { BusinessRuleConfigRecord, BusinessRuleHistoryResponse } from "@/lib/api/types";

const {
    getBusinessRuleHistoryMock,
    saveBusinessRuleDraftMock,
    validateBusinessRuleMock,
    previewBusinessRuleMock,
    publishBusinessRuleMock,
    rollbackBusinessRuleMock,
} = vi.hoisted(() => ({
    getBusinessRuleHistoryMock: vi.fn(),
    saveBusinessRuleDraftMock: vi.fn(),
    validateBusinessRuleMock: vi.fn(),
    previewBusinessRuleMock: vi.fn(),
    publishBusinessRuleMock: vi.fn(),
    rollbackBusinessRuleMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getBusinessRuleHistory: getBusinessRuleHistoryMock,
                saveBusinessRuleDraft: saveBusinessRuleDraftMock,
                validateBusinessRule: validateBusinessRuleMock,
                previewBusinessRule: previewBusinessRuleMock,
                publishBusinessRule: publishBusinessRuleMock,
                rollbackBusinessRule: rollbackBusinessRuleMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
    },
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: ({ open, title, description, confirmText, onConfirm }: {
        open: boolean;
        title: string;
        description: string;
        confirmText?: string;
        onConfirm: () => void;
    }) => open ? (
        <div role="dialog" aria-label={title}>
            <div>{description}</div>
            <button type="button" onClick={onConfirm}>{confirmText ?? "确认"}</button>
        </div>
    ) : null,
}));

const configKey = "recommendation.next_practice.ruleset";

const defaultValue = {
    version: "recommendation_default",
    enabled: true,
    weak_score_threshold: 60,
    dimensions: {},
    fallback: {
        title: "保持复练节奏",
        reason: "继续训练",
        action_label: "继续练习",
        target_path: "/training",
    },
};

const activeConfig: BusinessRuleConfigRecord = {
    id: "active-config",
    domain: "next_practice_recommendation",
    key: configKey,
    schema_version: "business_rule_config_v1",
    status: "published",
    version: 1,
    value: {
        ...defaultValue,
        version: "recommendation_v1",
    },
    default_value: defaultValue,
    type: "rule_json",
    range_or_allowlist: {
        weak_score_threshold: { min_exclusive: 0, max_inclusive: 100 },
    },
    read_path: "common.recommendations.next_practice.NextPracticeRecommendationService",
    admin_entry: "/admin/business-rules/next-practice-recommendations",
    permission: "admin_publish_only",
    audit_policy: "publish/rollback require actor and reason",
    fallback_policy: "use bundled default ruleset and expose ruleset_source in payload",
    rollback_policy: "restore a prior archived/published version for this key",
    enabled: true,
    validation_errors: [],
    created_by: "admin-a",
    updated_by: "admin-a",
    created_at: "2026-04-23T10:00:00.000Z",
    updated_at: "2026-04-23T10:00:00.000Z",
};

const draftConfig: BusinessRuleConfigRecord = {
    ...activeConfig,
    id: "draft-config",
    status: "draft",
    version: 2,
    value: {
        ...defaultValue,
        version: "recommendation_v2_draft",
        weak_score_threshold: 66,
    },
    updated_at: "2026-04-24T10:00:00.000Z",
};

const archivedConfig: BusinessRuleConfigRecord = {
    ...activeConfig,
    id: "archived-config",
    status: "archived",
    version: 0,
    value: {
        ...defaultValue,
        version: "recommendation_v0",
    },
    updated_by: "admin-b",
    updated_at: "2026-04-22T10:00:00.000Z",
};

function historyResponse(items: BusinessRuleConfigRecord[] = [draftConfig, activeConfig, archivedConfig]): BusinessRuleHistoryResponse {
    return {
        definition: {
            key: configKey,
            domain: "next_practice_recommendation",
            schema_version: "business_rule_config_v1",
            default_value: defaultValue,
            type: "rule_json",
            range_or_allowlist: {
                weak_score_threshold: { min_exclusive: 0, max_inclusive: 100 },
            },
            read_path: "common.recommendations.next_practice.NextPracticeRecommendationService",
            admin_entry: "/admin/business-rules/next-practice-recommendations",
            permission: "admin_publish_only",
            audit_policy: "publish/rollback require actor and reason",
            fallback_policy: "use bundled default ruleset and expose ruleset_source in payload",
            rollback_policy: "restore a prior archived/published version for this key",
        },
        items,
        total: items.length,
        audit_logs: [
            {
                id: "audit-1",
                action: "publish",
                actor: "admin-a",
                before_version: "0",
                after_version: "1",
                reason: "baseline",
                trace_id: "trace-active",
            },
        ],
    };
}

function renderPage() {
    return render(
        <GovernedBusinessRulePage
            configKey={configKey}
            title="练后推荐规则"
            description="管理练后下一步推荐。"
        />,
    );
}

describe("GovernedBusinessRulePage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getBusinessRuleHistoryMock.mockResolvedValue(historyResponse());
        saveBusinessRuleDraftMock.mockResolvedValue(draftConfig);
        validateBusinessRuleMock.mockResolvedValue({
            valid: true,
            normalized_value: draftConfig.value,
        });
        previewBusinessRuleMock.mockResolvedValue({
            valid: true,
            summary: { weak_score_threshold: 66, enabled: true },
            active_version: 1,
            active_config_id: "active-config",
        });
        publishBusinessRuleMock.mockResolvedValue({
            ...draftConfig,
            status: "published",
        });
        rollbackBusinessRuleMock.mockResolvedValue({
            ...archivedConfig,
            status: "published",
        });
    });

    it("loads rule definition, active version, draft JSON, fallback policy, and audit data", async () => {
        renderPage();

        expect(await screen.findByText("练后推荐规则")).toBeTruthy();
        expect(screen.getByText(/配置标识：recommendation.next_practice.ruleset/)).toBeTruthy();
        expect(screen.getByText("v1")).toBeTruthy();
        expect(screen.getByText(/use bundled default ruleset/)).toBeTruthy();
        expect(screen.getByText(/recommendation_v2_draft/)).toBeTruthy();
        expect(screen.getByText(/publish · admin-a · 0 → 1 · baseline · trace trace-active/)).toBeTruthy();
    });

    it("validates and previews through backend APIs without publishing active config", async () => {
        renderPage();

        await screen.findByText(/recommendation_v2_draft/);
        fireEvent.change(screen.getByPlaceholderText("操作原因（保存、发布、回滚必填，将进入审计记录）"), {
            target: { value: "impact review" },
        });
        fireEvent.click(screen.getByRole("button", { name: "后端校验" }));

        expect(await screen.findByText("后端配置校验通过，编辑区已更新为规范化配置。")).toBeTruthy();
        expect(validateBusinessRuleMock).toHaveBeenCalledWith(
            configKey,
            expect.objectContaining({ version: "recommendation_v2_draft" }),
            "impact review",
        );

        fireEvent.click(screen.getByRole("button", { name: "预览影响" }));

        expect(await screen.findByText(/预览完成；当前生效版本仍为 1/)).toBeTruthy();
        expect(screen.getByText(/weak_score_threshold: 66/)).toBeTruthy();
        expect(publishBusinessRuleMock).not.toHaveBeenCalled();
    });

    it("saves a governed draft and then publishes the draft with an audit reason", async () => {
        renderPage();

        await screen.findByText(/recommendation_v2_draft/);
        fireEvent.change(screen.getByPlaceholderText("操作原因（保存、发布、回滚必填，将进入审计记录）"), {
            target: { value: "publish governed recommendation" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));

        expect(await screen.findByText(/草稿已保存：v2/)).toBeTruthy();
        expect(saveBusinessRuleDraftMock).toHaveBeenCalledWith(
            configKey,
            expect.objectContaining({ version: "recommendation_v2_draft" }),
            "publish governed recommendation",
        );

        fireEvent.click(screen.getByRole("button", { name: "发布草稿" }));
        expect(publishBusinessRuleMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));

        await waitFor(() => {
            expect(publishBusinessRuleMock).toHaveBeenCalledWith(
                configKey,
                "draft-config",
                "publish governed recommendation",
            );
        });
    });

    it("blocks invalid JSON before calling mutation APIs", async () => {
        renderPage();

        const editor = await screen.findByLabelText("练后推荐规则 JSON 配置");
        fireEvent.change(editor, { target: { value: "not-json" } });
        expect(screen.getByText(/JSON 格式错误/)).toBeTruthy();
        expect((screen.getByRole("button", { name: "保存草稿" }) as HTMLButtonElement).disabled).toBe(true);
        expect(saveBusinessRuleDraftMock).not.toHaveBeenCalled();
    });

    it("rolls back to a historical config only after an audit reason is present", async () => {
        renderPage();

        await screen.findByText(/recommendation_v2_draft/);
        fireEvent.click(screen.getAllByRole("button", { name: "回滚到此版本" })[1]);
        expect(await screen.findByText("保存、发布或回滚前必须填写原因，原因会进入审计记录。")).toBeTruthy();
        expect(rollbackBusinessRuleMock).not.toHaveBeenCalled();

        fireEvent.change(screen.getByPlaceholderText("操作原因（保存、发布、回滚必填，将进入审计记录）"), {
            target: { value: "restore stable recommendation" },
        });
        fireEvent.click(screen.getAllByRole("button", { name: "回滚到此版本" })[1]);
        expect(rollbackBusinessRuleMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认回滚" }));

        await waitFor(() => {
            expect(rollbackBusinessRuleMock).toHaveBeenCalledWith(
                configKey,
                "archived-config",
                "restore stable recommendation",
            );
        });
    });
});
