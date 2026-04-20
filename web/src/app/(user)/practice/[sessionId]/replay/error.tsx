"use client";

import { LearnerRouteErrorState } from "@/components/learner/learner-route-error-state";

export default function ReplayError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return (
        <LearnerRouteErrorState
            error={error}
            reset={reset}
            title="回放加载失败"
            description="加载回放数据时出现问题，请稍后重试。"
            backHref="/history"
            backLabel="返回历史"
            errorTag="practice-replay"
        />
    );
}
