import { describe, expect, it } from "vitest";

import {
    DEFAULT_WEEKLY_GOAL_SESSIONS,
    MAX_WEEKLY_GOAL_SESSIONS,
    resolveDashboardWeeklyGoalSessions,
} from "./dashboard-config";

describe("resolveDashboardWeeklyGoalSessions", () => {
    it("uses the safe default when no configured value is present", () => {
        expect(resolveDashboardWeeklyGoalSessions(undefined)).toEqual({
            weeklyGoalSessions: DEFAULT_WEEKLY_GOAL_SESSIONS,
            source: "default",
            fallbackReason: "missing",
        });
    });

    it("accepts configured integer goals inside the supported range", () => {
        expect(resolveDashboardWeeklyGoalSessions("5")).toEqual({
            weeklyGoalSessions: 5,
            source: "env",
            fallbackReason: null,
        });
    });

    it.each(["0", "-1", "1.5", "abc", String(MAX_WEEKLY_GOAL_SESSIONS + 1)])(
        "falls back for invalid configured goal %s",
        (rawValue) => {
            expect(resolveDashboardWeeklyGoalSessions(rawValue)).toEqual({
                weeklyGoalSessions: DEFAULT_WEEKLY_GOAL_SESSIONS,
                source: "default",
                fallbackReason: "invalid",
            });
        },
    );
});
