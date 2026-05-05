export const DEFAULT_WEEKLY_GOAL_SESSIONS = 3;
export const MAX_WEEKLY_GOAL_SESSIONS = 21;

export type DashboardConfigSource = "env" | "default";
export type DashboardConfigFallbackReason = "missing" | "invalid" | null;

export interface DashboardWeeklyGoalResolution {
    weeklyGoalSessions: number;
    source: DashboardConfigSource;
    fallbackReason: DashboardConfigFallbackReason;
}

function readEnvValue(name: string): string | undefined {
    const value = process.env[name];
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function resolveDashboardWeeklyGoalSessions(
    rawValue = readEnvValue("NEXT_PUBLIC_DASHBOARD_WEEKLY_GOAL_SESSIONS"),
): DashboardWeeklyGoalResolution {
    if (rawValue === undefined) {
        return {
            weeklyGoalSessions: DEFAULT_WEEKLY_GOAL_SESSIONS,
            source: "default",
            fallbackReason: "missing",
        };
    }

    const parsed = Number(rawValue);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > MAX_WEEKLY_GOAL_SESSIONS) {
        return {
            weeklyGoalSessions: DEFAULT_WEEKLY_GOAL_SESSIONS,
            source: "default",
            fallbackReason: "invalid",
        };
    }

    return {
        weeklyGoalSessions: parsed,
        source: "env",
        fallbackReason: null,
    };
}

export const dashboardConfig = {
    weeklyGoal: resolveDashboardWeeklyGoalSessions(),
} as const;
