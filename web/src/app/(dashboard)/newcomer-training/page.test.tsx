import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Page from "./page";

vi.mock("@/lib/server-api", () => ({
    ServerApiError: class ServerApiError extends Error {
        constructor(readonly status: number) { super(String(status)); }
    },
    serverApiGet: vi.fn().mockResolvedValue({
                contract_version: "journey_projection_v1",
                generated_at: "2026-07-16T00:00:00Z",
                data_freshness: "fresh",
                capabilities: ["view_journey"],
                status: "not_enrolled",
                status_label: "尚未分配训练",
                status_reason: "请联系培训负责人分配训练路径。",
                enrollment: null,
                path: null,
                progress: { completed_required: 0, total_required: 0, percentage: 0 },
                stages: [],
                current_activity: null,
                background_tasks: [],
                recent_outcomes: [],
                primary_action: null,
                projection_version: 0,
            }),
}));

describe("newcomer training page", () => {
    it("loads the canonical learner journey without a legacy module request", async () => {
        render(await Page());
        expect(screen.getByText("尚未分配训练")).toBeTruthy();
        expect(screen.getByText("新人销售基础训练")).toBeTruthy();
    });
});
