import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminGovernancePage from "./page";

const getGovernancePermissionsMatrixMock = vi.hoisted(() => vi.fn());
const getGovernanceSettingsBacklogMock = vi.hoisted(() => vi.fn());
const getAiGovernanceExplainabilityMock = vi.hoisted(() => vi.fn());
const getSupportRuntimeOverviewMock = vi.hoisted(() => vi.fn());

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
            supportRuntime: {
                ...actual.api.supportRuntime,
                getOverview: getSupportRuntimeOverviewMock,
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

const mockSupportRuntimeOverview = {
    generated_at: "2026-05-10T10:00:00",
    window_hours: 168,
    session_health: {
        active_sessions: 1,
        total_sessions_window: 8,
        completed_sessions_window: 6,
        scoring_sessions: 0,
        stuck_scoring_sessions: 0,
        not_evaluable_completed_sessions_window: 1,
        completion_rate: 0.75,
    },
    release_health: {
        status: "healthy",
        blocking_count: 0,
        warning_count: 1,
        typed_anomaly_count: 1,
        blocking_sessions_count: 0,
        warning_sessions_count: 1,
        supplemental_warning_log_count: 0,
    },
    anomaly_summary: { blocking: [], warning: [] },
    roleplay: {
        ready_sessions: 5,
        legacy_sessions: 2,
        missing_sessions: 1,
        invalid_sessions: 0,
        violation_count: 3,
        blocking_violation_count: 1,
        regenerate_count: 1,
        cancel_stream_count: 1,
        hidden_leak_prevented_count: 2,
        high_violation_situation_packs: [
            { situation_code: "first_visit", violation_count: 3 },
        ],
        compile_failure_rank: [
            { kind: "roleplay_contract_missing", count: 1 },
        ],
    },
};

const mockConfigAssetCenterOverview = {
    ...mockSupportRuntimeOverview,
    config_asset_center: {
        status: "warning",
        dual_read: {
            enabled: true,
            authority: "phase_a",
            lookup_count: 10,
            mismatch_count: 1,
            matched_count: 9,
            sample_mismatches: [
                {
                    code: "first_visit",
                    phase_a_hash: "sha256:a",
                    phase_b1_hash: "sha256:b",
                },
            ],
        },
        projection_sync: {
            status: "ok",
            last_sync_at: "2026-05-10T09:00:00",
            packs_synced: 4,
            packs_failed: 0,
            recent_failures: [],
        },
        asset_resolution: {
            session_count: 8,
            legacy_warning_sessions: 2,
            frozen_ref_sessions: 5,
            mode_breakdown: [
                { mode: "template_frozen_refs", count: 5 },
                { mode: "template_legacy_live", count: 2 },
                { mode: "direct_practice_live", count: 1 },
            ],
        },
    },
};

describe("AdminGovernancePage", () => {
    beforeEach(() => {
        getGovernancePermissionsMatrixMock.mockResolvedValue(mockPermissionsResponse);
        getGovernanceSettingsBacklogMock.mockResolvedValue(mockBacklogResponse);
        getSupportRuntimeOverviewMock.mockResolvedValue(mockSupportRuntimeOverview);
        getAiGovernanceExplainabilityMock.mockReset();
    });

    it("renders permissions matrix and settings backlog from read-only governance APIs", async () => {
        render(<AdminGovernancePage />);

        expect(await screen.findByRole("heading", { name: "治理矩阵" })).toBeTruthy();
        expect(screen.getByText("admin.api.users")).toBeTruthy();
        expect(screen.getByText(/positive control/)).toBeTruthy();
        expect(screen.getByText(/常规设置/)).toBeTruthy();
        expect(screen.getByText(/redaction guidance/)).toBeTruthy();
        expect(screen.getByText("Roleplay 合同治理")).toBeTruthy();
        expect(screen.getByText("first_visit")).toBeTruthy();
        expect(screen.getByText("roleplay_contract_missing")).toBeTruthy();
    });

    it("renders config asset center observability when runtime overview includes config_asset_center", async () => {
        getSupportRuntimeOverviewMock.mockResolvedValue(mockConfigAssetCenterOverview);

        render(<AdminGovernancePage />);

        expect(await screen.findByText("Config Asset Center 运行时健康")).toBeTruthy();
        expect(screen.getByText("Dual-read 对账")).toBeTruthy();
        expect(screen.getByText("Projection sync")).toBeTruthy();
        expect(screen.getByText("Asset resolution 模式")).toBeTruthy();
        expect(screen.getByText(/phase_a: sha256:a/)).toBeTruthy();
        expect(screen.getByText(/Template frozen refs/)).toBeTruthy();
    });

    it("shows pending config asset center state when backend field is absent", async () => {
        render(<AdminGovernancePage />);

        expect(await screen.findByText("Config Asset Center 运行时健康")).toBeTruthy();
        expect(screen.getByText(/config_asset_center/)).toBeTruthy();
        expect(screen.getByText(/待观测状态/)).toBeTruthy();
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

    it("shows explainability frozen asset refs when lineage includes published_asset_refs", async () => {
        getAiGovernanceExplainabilityMock.mockResolvedValue({
            ...mockExplainabilityResponse,
            report: {
                ...mockExplainabilityResponse.report,
                lineage: {
                    ...mockExplainabilityResponse.report.lineage,
                    config_bundle_snapshot: {
                        published_asset_refs: {
                            persona_ref: {
                                asset_type: "persona",
                                asset_id: "persona-1",
                                version: "3",
                                content_hash: "sha256:persona",
                                snapshot_label: "published",
                            },
                        },
                    },
                },
                payload: {
                    runtime_dossier: {
                        dossier_hash: "sha256:dossier",
                    },
                },
            },
        });

        render(<AdminGovernancePage />);
        await screen.findByRole("heading", { name: "治理矩阵" });

        fireEvent.click(screen.getByRole("button", { name: "AI 可解释性" }));
        fireEvent.change(screen.getByPlaceholderText("输入会话 ID（例如：ses_abc123）"), {
            target: { value: "ses_test123" },
        });
        fireEvent.click(screen.getByRole("button", { name: "查询可解释性" }));

        await waitFor(() => {
            expect(screen.getByText("published_asset_refs")).toBeTruthy();
        });
        expect(screen.getByText(/persona_ref · persona · persona-1/)).toBeTruthy();
        expect(screen.getAllByText(/sha256:dossier/).length).toBeGreaterThan(0);
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
