import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionReportData } from "./use-session-report-data";
import type { PracticeSessionReport } from "@/lib/api/types";

const getReportMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            sessions: {
                ...actual.api.sessions,
                getReport: getReportMock,
            },
        },
        getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "unknown error",
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        log: vi.fn(),
        error: vi.fn(),
    },
}));

const report = {
    session_id: "session-1",
    scenario_type: "sales",
    overall_score: 82,
    evaluable: true,
    not_evaluable_reason: null,
    evidence_completeness: {
        complete: true,
    },
    presentation_review: null,
} as PracticeSessionReport;

describe("useSessionReportData", () => {
    beforeEach(() => {
        getReportMock.mockReset();
        getReportMock.mockResolvedValue(report);
    });

    it("loads the unified report contract and exposes stable state for the report page", async () => {
        const { result } = renderHook(() => useSessionReportData("session-1"));

        expect(result.current.loading).toBe(true);

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(getReportMock).toHaveBeenCalledWith("session-1");
        expect(result.current.report?.overall_score).toBe(82);
        expect(result.current.error).toBeNull();
    });

    it("turns report API failures into page-safe error copy and supports reload", async () => {
        getReportMock.mockRejectedValueOnce(new Error("report unavailable"));
        const { result } = renderHook(() => useSessionReportData("session-1"));

        await waitFor(() => {
            expect(result.current.error).toBe("统一训练证据加载失败：report unavailable");
        });
        expect(result.current.report).toBeNull();

        getReportMock.mockResolvedValueOnce(report);
        await act(async () => {
            await result.current.reload();
        });

        expect(result.current.report?.session_id).toBe("session-1");
        expect(result.current.error).toBeNull();
    });
});
