import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminGovernancePage from "./page";

const getGovernancePermissionsMatrixMock = vi.hoisted(() => vi.fn());
const getGovernanceSettingsBacklogMock = vi.hoisted(() => vi.fn());
const getAiGovernanceExplainabilityMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getGovernancePermissionsMatrix: getGovernancePermissionsMatrixMock,
                getGovernanceSettingsBacklog: getGovernanceSettingsBacklogMock,
                getAiGovernanceExplainability: getAiGovernanceExplainabilityMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
    },
}));

const mockPermissionsResponse = {
    items: [
        {
            route_family: "admin.api.users",
            auth_surface: "Depends(get_current_admin_user)",
            routes: ["GET /admin/users*"],
            allowed_roles: ["admin"],
            non_admin_deny_path: "common.auth.service.get_current_admin_user -> 403 [ROLE_REQUIRED]",
            current_evidence: ["backend/src/admin/api/users.py"],
            risk: "baseline",
            priority: "baseline",
            rationale: "positive control",
        },
    ],
    total: 1,
    fix_first_route_families: [],
    positive_control_route_families: ["admin.api.users"],
    support_log_redaction: {
        visible_fields: ["action", "status"],
        diagnostic_allowlist: ["trace_id"],
        backend_only_fields: ["token"],
        guidance: "redaction guidance",
        quality_event_prerequisite: "quality event prerequisite",
    },
};

const mockBacklogResponse = {
    items: [
        {
            surface: "general",
            label: "常规设置",
            status: "read_only_backlog",
            missing_capabilities: ["system settings persistence API"],
            fallback_policy: "frontend remains read-only",
        },
    ],
    total: 1,
    policy: "governed settings only",
};

const mockExplainabilityResponse = {
    session: {
        session_id: "ses_test123",
        scenario_id: "scn_test456",
        scenario_type: "sales",
        user_id: "usr_test789",
        status: "completed",
        report_status: "completed",
        report_generated_at: "2026-05-10T10:00:00",
    },
    model: { provider: "stepfun", name: "sales-model" },
    prompt: { template_id: "sales-prompt" },
    rag: { profile: "sales-rag" },
    knowledge: { sources: ["sales-kb"] },
    scoring: { ruleset: "sales-rules" },
    evidence: {
        input_reference: { conversation_messages: ["turn-1", "turn-2"] },
        completeness: { conversation: true, knowledge: true },
        report_evidence: { highlights: ["turn-2"] },
    },
    evaluation: {
        run_id: "run_test001",
        status: "succeeded",
        started_at: "2026-05-10T10:00:00",
        finished_at: "2026-05-10T10:01:00",
        input_evidence_reference: {},
        result_payload: { overall_score: 84 },
        result_summary: "sales evaluation succeeded",
        error_message: null,
        config_bundle_id: "bundle_test001",
        config_version_id: "version_test001",
        created_at: "2026-05-10T10:00:00",
        updated_at: "2026-05-10T10:01:00",
    },
    report: {
        payload: { report_id: "sales-report", summary: "sales report summary" },
        lineage: {
            snapshot_id: "snap_test001",
            evaluation_run_id: "run_test001",
            generated_at: "2026-05-10T10:01:00",
            ruleset_source: "sales_ruleset",
            ruleset_version: "2026.05",
            score_basis: "persisted_snapshot",
            non_evaluable_reason: null,
            config_bundle_id: "bundle_test001",
            config_version_id: "version_test001",
            bundle_key: "sales.explain.bundle",
            source: "config_version",
            config_bundle_snapshot: {
                model: { provider: "stepfun", name: "sales-model" },
            },
            created_at: "2026-05-10T10:01:00",
        },
    },
};

describe("AdminGovernancePage", () => {
    beforeEach(() => {
        getGovernancePermissionsMatrixMock.mockResolvedValue(mockPermissionsResponse);
        getGovernanceSettingsBacklogMock.mockResolvedValue(mockBacklogResponse);
        getAiGovernanceExplainabilityMock.mockReset();
    });

    it("renders permissions matrix and settings backlog from read-only governance APIs", async () => {
        render(<AdminGovernancePage />);

        expect(await screen.findByRole("heading", { name: "治理矩阵" })).toBeTruthy();
        expect(screen.getByText("admin.api.users")).toBeTruthy();
        expect(screen.getByText(/positive control/)).toBeTruthy();
        expect(screen.getByText(/常规设置/)).toBeTruthy();
        expect(screen.getByText(/redaction guidance/)).toBeTruthy();
    });

    it("switches to explainability tab and shows session id input", async () => {
        render(<AdminGovernancePage />);

        await screen.findByRole("heading", { name: "治理矩阵" });

        const explainabilityTab = screen.getByRole("button", { name: "AI 可解释性" });
        fireEvent.click(explainabilityTab);

        expect(screen.getByPlaceholderText("输入会话 ID（例如：ses_abc123）")).toBeTruthy();
        expect(screen.getByRole("button", { name: "查询可解释性" })).toBeTruthy();
    });

    it("renders explainability data after successful query", async () => {
        getAiGovernanceExplainabilityMock.mockResolvedValue(mockExplainabilityResponse);

        render(<AdminGovernancePage />);
        await screen.findByRole("heading", { name: "治理矩阵" });

        fireEvent.click(screen.getByRole("button", { name: "AI 可解释性" }));

        const input = screen.getByPlaceholderText("输入会话 ID（例如：ses_abc123）");
        fireEvent.change(input, { target: { value: "ses_test123" } });
        fireEvent.click(screen.getByRole("button", { name: "查询可解释性" }));

        await waitFor(() => {
            expect(screen.getByText("ses_test123")).toBeTruthy();
        });

        expect(screen.getByText("会话信息")).toBeTruthy();
        expect(screen.getByText("sales")).toBeTruthy();
        expect(screen.getByText("模型配置")).toBeTruthy();
        expect(screen.getByText("提示词配置")).toBeTruthy();
        expect(screen.getByText("RAG 配置")).toBeTruthy();
        expect(screen.getByText("知识库来源")).toBeTruthy();
        expect(screen.getByText("评分配置")).toBeTruthy();
        expect(screen.getByText("证据来源")).toBeTruthy();
        expect(screen.getByText("评估溯源")).toBeTruthy();
        expect(screen.getByText("报告快照溯源")).toBeTruthy();
        expect(screen.getByText("succeeded")).toBeTruthy();
    });

    it("shows explainability incomplete error when backend returns 409", async () => {
        const { ApiRequestError: ApiRequestErrorClass } = await import("@/lib/api/client");
        getAiGovernanceExplainabilityMock.mockRejectedValue(
            new ApiRequestErrorClass({
                status: 409,
                errorCode: "[AI_GOVERNANCE_EXPLAINABILITY_INCOMPLETE]",
                message: "AI governance explainability lineage is incomplete for this session.",
            }),
        );

        render(<AdminGovernancePage />);
        await screen.findByRole("heading", { name: "治理矩阵" });

        fireEvent.click(screen.getByRole("button", { name: "AI 可解释性" }));

        const input = screen.getByPlaceholderText("输入会话 ID（例如：ses_abc123）");
        fireEvent.change(input, { target: { value: "ses_missing" } });
        fireEvent.click(screen.getByRole("button", { name: "查询可解释性" }));

        await waitFor(() => {
            expect(screen.getByText("可解释性数据不完整")).toBeTruthy();
        });

        expect(screen.getByText(/AI governance explainability lineage is incomplete/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
    });

    it("shows explainability error for invalid session id input", async () => {
        render(<AdminGovernancePage />);
        await screen.findByRole("heading", { name: "治理矩阵" });

        fireEvent.click(screen.getByRole("button", { name: "AI 可解释性" }));

        fireEvent.click(screen.getByRole("button", { name: "查询可解释性" }));

        await waitFor(() => {
            expect(screen.getByText(/请输入会话 ID/)).toBeTruthy();
        });
    });
});
