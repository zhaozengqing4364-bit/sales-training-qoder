"use client";

import { LearnerRouteErrorState } from "@/components/learner/learner-route-error-state";

export default function PracticeRouteError({
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
            title="训练页面暂时不可用"
            description="你可以先重试当前页面；如果仍失败，请先返回训练大厅重新进入本场练习。"
            backHref="/training"
            backLabel="返回训练大厅"
            errorTag="practice-live"
        />
    );
}
