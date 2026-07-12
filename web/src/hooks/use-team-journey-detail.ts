"use client";

import { useQuery } from "@tanstack/react-query";

import { teamDetailQueryOptions } from "@/lib/query/team-detail";
import type { JourneyResponse } from "@/lib/api/types/newcomer-training";

export interface UseTeamJourneyDetailParams {
    learnerId: string;
}

export interface UseTeamJourneyDetailResult {
    journey: JourneyResponse | undefined;
    isLoading: boolean;
    isError: boolean;
    error: Error | null;
    refetch: () => Promise<unknown>;
}

/**
 * 获取单个学员完整 journey 的 hook（详情页用）。
 *
 * 数据权限由后端 get_admin_journey 的 team_department 校验保证（AC5）：
 * training_manager 调跨部门学员详情会被后端返回 404 [TRAINING_RECORD_NOT_FOUND]，
 * 不泄露学员是否存在，前端统一显示「学员记录不存在或无权查看」。
 */
export function useTeamJourneyDetail(
    params: UseTeamJourneyDetailParams,
): UseTeamJourneyDetailResult {
    const query = useQuery(teamDetailQueryOptions(params.learnerId));

    return {
        journey: query.data,
        isLoading: query.isPending,
        isError: query.isError,
        error: query.error ?? null,
        refetch: async () => query.refetch(),
    };
}
