import { describe, expect, it } from "vitest";

import type { UserSessionItem } from "@/lib/api/types";
import {
    EMPTY_ADMIN_MANAGER_INTERVENTIONS,
    EMPTY_ADMIN_MANAGER_LITE_LISTS,
    EMPTY_ADMIN_OPERATING_PACK,
    EMPTY_ADMIN_USER_SESSIONS,
    buildInterventionResultById,
    buildOperatingPackReadModel,
    buildUserProgressOverview,
    formatAdminDegradedReasonLabel,
    formatAdminRelativeTime,
    formatAdminScoreBasisLabel,
    formatAdminUserRoleLabel,
    formatAdminUserStatusLabel,
    getAdminTrendSummary,
    getUserSessionOverallResultLabel,
    getUserSessionOverallResultTone,
    getUserSessionPreview,
    hasEvaluableUserProgress,
} from "./read-models";
import type { UserSessionItem } from "@/lib/api/types";

describe("read-models", () => {
    it("provides stable empty admin read-model defaults", () => {
        expect(EMPTY_ADMIN_MANAGER_LITE_LISTS).toEqual({
            not_passed: [],
            inactive_streak: [],
            improving: [],
        });
        expect(EMPTY_ADMIN_OPERATING_PACK.manager_lists).toEqual(EMPTY_ADMIN_MANAGER_LITE_LISTS);
        expect(EMPTY_ADMIN_USER_SESSIONS).toEqual({
            items: [],
            total: 0,
            page: 1,
            page_size: 10,
            has_more: false,
            manager_intervention_results: [],
        });
        expect(EMPTY_ADMIN_MANAGER_INTERVENTIONS).toEqual([]);
    });

    it("formats shared analytics copy and derives operating-pack highlight fallbacks", () => {
        const operatingPack = {
            ...EMPTY_ADMIN_OPERATING_PACK,
            weekly_summary: {
                ...EMPTY_ADMIN_OPERATING_PACK.weekly_summary,
                top_issue_family: {
                    issue_family: "value_expression",
                    issue_type: "value_expression",
                    issue_text: "价值表达还停留在功能层。",
                    count: 2,
                    user_count: 2,
                    department_count: 1,
                },
                top_degraded_reason: null,
            },
            cohort_issue_buckets: [
                {
                    issue_family: "evidence_gap",
                    issue_type: "evidence_gap",
                    issue_text: "缺少客户案例证据。",
                    count: 3,
                    user_count: 2,
                    department_count: 1,
                },
            ],
            repeated_blocker_families: [],
            degradation_breakdown: {
                not_evaluable_reasons: [],
                degraded_reasons: [{ reason: "message_scores", count: 2 }],
            },
        };

        expect(formatAdminScoreBasisLabel("session_evidence_projection_evaluable_only")).toBe(
            "统一训练证据 · 仅统计可评估的已完成训练",
        );
        expect(formatAdminScoreBasisLabel("custom_basis")).toBe("custom_basis");
        expect(formatAdminDegradedReasonLabel("page_metadata")).toBe("页码证据缺失");
        expect(formatAdminDegradedReasonLabel("custom_reason")).toBe("custom_reason");

        expect(buildOperatingPackReadModel(operatingPack)).toMatchObject({
            repeatedBlockerFamilies: operatingPack.cohort_issue_buckets,
            topBlockerFamily: operatingPack.weekly_summary.top_issue_family,
            topDegradedReason: operatingPack.degradation_breakdown.degraded_reasons[0],
            managerLite: EMPTY_ADMIN_MANAGER_LITE_LISTS,
        });
    });

    it("formats shared admin user labels and relative-time fallbacks for the users route family", () => {
        expect(formatAdminUserStatusLabel("active")).toBe("活跃");
        expect(formatAdminUserStatusLabel("custom_status")).toBe("custom_status");
        expect(formatAdminUserStatusLabel()).toBe("未知状态");

        expect(formatAdminUserRoleLabel("support")).toBe("支持角色");
        expect(formatAdminUserRoleLabel("custom_role")).toBe("custom_role");
        expect(formatAdminUserRoleLabel()).toBe("未分配角色");

        expect(formatAdminRelativeTime()).toBe("从未");
        expect(formatAdminRelativeTime(new Date().toISOString())).toBe("刚刚");
    });

    it("derives progress view state from evaluable history and degraded branches", () => {
        const progress = {
            granularity: "week",
            trend_data: [
                {
                    date: "2026-03-09T00:00:00Z",
                    sessions_count: 2,
                    evaluable_session_count: 1,
                    not_evaluable_session_count: 1,
                    average_score: 72,
                    logic_score: 70,
                    accuracy_score: 72,
                    completeness_score: 74,
                },
            ],
            improvement_rate: -12.5,
            total_data_points: 1,
            completed_session_count: 2,
            evaluable_session_count: 1,
            not_evaluable_session_count: 1,
            non_completed_session_count: 0,
            repeated_main_issues: [],
            repeated_next_goals: [],
            should_switch_focus: true,
            recommendation: {
                reason: "stalled_repeated_focus",
                summary: "最近没有改善，建议切换训练重点。",
            },
        };

        expect(hasEvaluableUserProgress(progress)).toBe(true);
        expect(getAdminTrendSummary(progress.improvement_rate).title).toBe("最近在回落");
        expect(buildUserProgressOverview("success", progress, null)).toMatchObject({
            title: "建议切换训练重点",
            subtitle: "最近在回落 · 1 次可评估训练",
            valueClassName: "text-amber-700",
        });
        expect(buildUserProgressOverview("empty", {
            ...progress,
            trend_data: [],
            evaluable_session_count: 0,
            completed_session_count: 3,
            not_evaluable_session_count: 3,
            should_switch_focus: false,
        }, null)).toMatchObject({
            title: "证据不足",
            subtitle: "最近 3 次已完成训练暂不可评估。",
        });
        expect(buildUserProgressOverview("error", null, "网络错误")).toMatchObject({
            title: "加载失败",
            subtitle: "网络错误",
        });
    });

    it("derives current user session and intervention read models without page-local branching", () => {
        const nonEvaluableSession: UserSessionItem = {
            session_id: "session-1",
            start_time: "2026-03-23T09:00:00Z",
            end_time: "2026-03-23T09:03:00Z",
            status: "completed",
            duration_minutes: 3,
            scenario_name: "销售演练",
            scenario_type: "sales",
            agent_name: "销售教练",
            persona_name: "采购经理",
            scores: {
                logic: null,
                accuracy: null,
                completeness: null,
                overall: null,
            },
            evaluable: false,
            overall_result: null,
            not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
            feedback_summary: null,
            main_issue: null,
            next_goal: null,
            interruption_count: 0,
        } satisfies UserSessionItem;
        const completedSession = {
            session_id: "session-2",
            start_time: "2026-03-23T10:00:00Z",
            end_time: "2026-03-23T10:05:00Z",
            status: "completed",
            duration_minutes: 5,
            scenario_name: "销售演练",
            scenario_type: "sales",
            agent_name: "销售教练",
            persona_name: "采购经理",
            scores: {
                logic: 80,
                accuracy: 78,
                completeness: 82,
                overall: 80,
            },
            evaluable: true,
            overall_result: "pass",
            not_evaluable_reason: null,
            feedback_summary: "最近一次报告提示：先把价值表达说具体。",
            main_issue: {
                issue_type: "value_expression",
                issue_text: "价值表达不具体。",
                recovery_rule: "补齐客户业务影响。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "下一轮补齐客户案例证据。",
                rule: "至少补 1 个可验证客户案例。",
            },
            interruption_count: 0,
        } satisfies UserSessionItem;

        expect(getUserSessionOverallResultLabel(nonEvaluableSession)).toBe("不可评估");
        expect(getUserSessionOverallResultTone(nonEvaluableSession)).toBe("bg-amber-50 text-amber-700");
        expect(getUserSessionOverallResultLabel(completedSession)).toBe("Pass");
        expect(getUserSessionOverallResultTone(completedSession)).toBe("bg-blue-50 text-blue-700");
        expect(getUserSessionPreview(nonEvaluableSession)).toBe("对话轮次不足，暂无法形成稳定评估。");
        expect(getUserSessionPreview(completedSession)).toBe("最近一次报告提示：先把价值表达说具体。");

        const byId = buildInterventionResultById({
            manager_intervention_results: [
                {
                    intervention_id: "intervention-1",
                    status: "improved",
                    reason: "issue_family_shifted",
                    summary: "最近一次可评估训练的主问题已转向其他家族。",
                    issue_family: "evidence_gap",
                    created_at: "2026-03-23T09:30:00Z",
                },
            ],
        });

        expect(byId.get("intervention-1")).toMatchObject({
            status: "improved",
            summary: "最近一次可评估训练的主问题已转向其他家族。",
        });
    });
});
