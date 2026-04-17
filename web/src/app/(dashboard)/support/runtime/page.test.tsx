import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SupportRuntimePage from "./page";
import { ApiRequestError } from "@/lib/api/client";
import type {
    SupportRuntimeFaultsResponse,
    SupportRuntimeOverview,
} from "@/lib/api/types";

const {
    getOverviewMock,
    getFaultsMock,
    useAuthProtectionMock,
} = vi.hoisted(() => ({
    getOverviewMock: vi.fn(),
    getFaultsMock: vi.fn(),
    useAuthProtectionMock: vi.fn(),
}));

vi.mock("@/hooks/use-auth-protection", () => ({
    useAuthProtection: useAuthProtectionMock,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            supportRuntime: {
                ...actual.api.supportRuntime,
                getOverview: getOverviewMock,
                getFaults: getFaultsMock,
            },
        },
    };
});

const blockingOverview = {
    generated_at: "2026-03-24T08:00:00Z",
    window_hours: 24,
    session_health: {
        active_sessions: 3,
        total_sessions_window: 12,
        completed_sessions_window: 7,
        scoring_sessions: 2,
        stuck_scoring_sessions: 1,
        not_evaluable_completed_sessions_window: 1,
        completion_rate: 58.33,
    },
    release_health: {
        status: "blocking",
        blocking_count: 2,
        warning_count: 1,
        typed_anomaly_count: 3,
        blocking_sessions_count: 2,
        warning_sessions_count: 1,
        supplemental_warning_log_count: 1,
    },
    anomaly_summary: {
        blocking: [
            { kind: "stuck_scoring", count: 1 },
            { kind: "knowledge_search_failed", count: 1 },
        ],
        warning: [{ kind: "upstream_unstable", count: 1 }],
    },
};

const warningOverview = {
    ...blockingOverview,
    release_health: {
        ...blockingOverview.release_health,
        status: "warning",
        blocking_count: 0,
        warning_count: 2,
        typed_anomaly_count: 2,
        blocking_sessions_count: 0,
        warning_sessions_count: 2,
        supplemental_warning_log_count: 0,
    },
    anomaly_summary: {
        blocking: [],
        warning: [
            { kind: "presentation_degraded_missing_page_metadata", count: 1 },
            { kind: "optional_report_failed", count: 1 },
        ],
    },
};

const healthyOverview = {
    ...blockingOverview,
    release_health: {
        ...blockingOverview.release_health,
        status: "healthy",
        blocking_count: 0,
        warning_count: 0,
        typed_anomaly_count: 0,
        blocking_sessions_count: 0,
        warning_sessions_count: 0,
        supplemental_warning_log_count: 0,
    },
    anomaly_summary: {
        blocking: [],
        warning: [],
    },
};

const blockingFaults = {
    generated_at: "2026-03-24T08:00:00Z",
    items: [
        {
            source: "session",
            severity: "blocking",
            kind: "stuck_scoring",
            summary: "会话长时间停留在 scoring，尚未进入 completed。",
            detected_at: "2026-03-24T07:55:00Z",
            session_id: "session-stuck",
            scenario_type: "sales",
            session_status: "scoring",
            report_status: "processing",
            diagnostics: {
                stuck_for_minutes: 35,
            },
        },
        {
            source: "session",
            severity: "blocking",
            kind: "knowledge_search_failed",
            summary: "知识检索触发失败，请检查知识库或 Embedding 服务。",
            detected_at: "2026-03-24T07:40:00Z",
            session_id: "session-kb",
            scenario_type: "sales",
            session_status: "completed",
            report_status: "completed",
            diagnostics: {
                last_status: "search_failed",
                last_error: "[KNOWLEDGE_SEARCH_UNAVAILABLE]",
            },
        },
        {
            source: "session",
            severity: "warning",
            kind: "upstream_unstable",
            summary: "上游实时链路最近 5 分钟断连次数偏高，存在不稳定迹象。",
            detected_at: "2026-03-24T07:30:00Z",
            session_id: "session-upstream",
            scenario_type: "presentation",
            session_status: "completed",
            report_status: "completed",
            diagnostics: {
                upstream_disconnect_count_5m: 4,
            },
        },
    ],
    count: 3,
    limit: 20,
    severity: null,
};

const warningFaults = {
    generated_at: "2026-03-24T08:00:00Z",
    items: [
        {
            source: "session",
            severity: "warning",
            kind: "presentation_degraded_missing_page_metadata",
            summary: "PPT 会后复盘缺少页码证据，逐页总结与覆盖判断已降级。",
            detected_at: "2026-03-24T07:20:00Z",
            session_id: "session-ppt",
            scenario_type: "presentation",
            session_status: "completed",
            report_status: "completed",
            diagnostics: {
                degraded_reasons: ["missing_page_metadata"],
            },
        },
        {
            source: "session",
            severity: "warning",
            kind: "optional_report_failed",
            summary: "增强报告生成失败，但 canonical report 仍走统一 evidence 读线。",
            detected_at: "2026-03-24T07:10:00Z",
            session_id: "session-report",
            scenario_type: "sales",
            session_status: "completed",
            report_status: "failed",
            diagnostics: {
                report_error_code: "[REPORT_GENERATION_FAILED]",
            },
        },
    ],
    count: 2,
    limit: 20,
    severity: null,
};

describe("SupportRuntimePage", () => {
    beforeEach(() => {
        getOverviewMock.mockReset();
        getFaultsMock.mockReset();
        useAuthProtectionMock.mockReset();

        useAuthProtectionMock.mockReturnValue({
            isLoading: false,
            isAuthorized: true,
        });
    });

    it("renders blocking release health from the typed overview and typed anomaly list", async () => {
        getOverviewMock.mockResolvedValue(blockingOverview as unknown as SupportRuntimeOverview);
        getFaultsMock.mockResolvedValue(blockingFaults as unknown as SupportRuntimeFaultsResponse);

        render(<SupportRuntimePage />);

        await waitFor(() => {
            expect(getOverviewMock).toHaveBeenCalledWith({ window_hours: 24 });
            expect(getFaultsMock).toHaveBeenCalledWith({ limit: 20 });
        });

        expect((await screen.findAllByText("阻塞发布")).length).toBeGreaterThan(0);
        expect(screen.getByText("Blocking")).toBeTruthy();
        expect(screen.getByText("2 个阻塞异常，影响 2 个会话")).toBeTruthy();
        expect(screen.getByText("进行中 3 · scoring 2")).toBeTruthy();
        expect(screen.getByText("stuck_scoring")).toBeTruthy();
        expect(screen.getByText("knowledge_search_failed")).toBeTruthy();
        expect(screen.getByText("session-stuck")).toBeTruthy();
        expect(screen.getByText("sales · scoring · processing")).toBeTruthy();
        expect(screen.getByText("stuck_for_minutes: 35")).toBeTruthy();
    });

    it("renders a warning-only release state without inventing blocking severity on the client", async () => {
        getOverviewMock.mockResolvedValue(warningOverview as unknown as SupportRuntimeOverview);
        getFaultsMock.mockResolvedValue(warningFaults as unknown as SupportRuntimeFaultsResponse);

        render(<SupportRuntimePage />);

        expect((await screen.findAllByText("仅警告")).length).toBeGreaterThan(0);
        expect(screen.getByText("0 个阻塞异常，影响 0 个会话")).toBeTruthy();
        expect(screen.getByText("2 个 warning 异常，影响 2 个会话")).toBeTruthy();
        expect(screen.getByText("presentation_degraded_missing_page_metadata")).toBeTruthy();
        expect(screen.getByText("optional_report_failed")).toBeTruthy();
    });

    it("shows a local empty state when the typed anomaly list is empty", async () => {
        getOverviewMock.mockResolvedValue(healthyOverview as unknown as SupportRuntimeOverview);
        getFaultsMock.mockResolvedValue({
            generated_at: "2026-03-24T08:00:00Z",
            items: [],
            count: 0,
            limit: 20,
            severity: null,
        } as unknown as SupportRuntimeFaultsResponse);

        render(<SupportRuntimePage />);

        expect((await screen.findAllByText("健康")).length).toBeGreaterThan(0);
        expect(screen.getByText("最近没有需要处理的 blocking / warning 异常。"))
            .toBeTruthy();
        expect(screen.getByRole("button", { name: "刷新" })).toBeTruthy();
    });

    it("keeps the release summary visible and shows a local anomaly-list error when faults loading fails", async () => {
        getOverviewMock.mockResolvedValue(blockingOverview as unknown as SupportRuntimeOverview);
        getFaultsMock.mockRejectedValue(
            new ApiRequestError({
                status: 0,
                errorCode: "[NETWORK_ERROR]",
                message: "network down",
            }),
        );

        render(<SupportRuntimePage />);

        expect((await screen.findAllByText("阻塞发布")).length).toBeGreaterThan(0);
        expect(screen.getByText(
            "异常列表加载失败：网络连接失败，请检查后端服务或网络设置后重试。",
        )).toBeTruthy();
        expect(screen.queryByText("最近没有需要处理的 blocking / warning 异常。")).toBeNull();
    });

    it("refreshes the typed overview and faults together without leaving the page shell", async () => {
        getOverviewMock
            .mockResolvedValueOnce(warningOverview as unknown as SupportRuntimeOverview)
            .mockResolvedValueOnce(blockingOverview as unknown as SupportRuntimeOverview);
        getFaultsMock
            .mockResolvedValueOnce(warningFaults as unknown as SupportRuntimeFaultsResponse)
            .mockResolvedValueOnce(blockingFaults as unknown as SupportRuntimeFaultsResponse);

        render(<SupportRuntimePage />);

        expect((await screen.findAllByText("仅警告")).length).toBeGreaterThan(0);

        fireEvent.click(screen.getByRole("button", { name: "刷新" }));

        expect((await screen.findAllByText("阻塞发布")).length).toBeGreaterThan(0);
        await waitFor(() => {
            expect(getOverviewMock).toHaveBeenCalledTimes(2);
            expect(getFaultsMock).toHaveBeenCalledTimes(2);
        });
        expect(screen.getByText("session-stuck")).toBeTruthy();
    });
});
