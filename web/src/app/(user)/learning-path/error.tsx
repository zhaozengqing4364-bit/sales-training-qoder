"use client";

import { LearnerRouteErrorState } from "@/components/learner/learner-route-error-state";

export default function LearningPathRouteError({
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
            title="学习路径暂时不可用"
            description="你可以重试当前页面；如果仍失败，请先返回训练大厅继续练习。"
            backHref="/training"
            backLabel="返回训练大厅"
            errorTag="learning-path"
        />
    );
}
