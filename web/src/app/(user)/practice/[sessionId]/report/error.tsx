"use client";

import { LearnerRouteErrorState } from "@/components/learner/learner-route-error-state";

export default function ReportError({
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
            title="报告加载失败"
            description="训练报告遇到了一些问题，请稍后重试。"
            backHref="/history"
            backLabel="返回历史记录"
            errorTag="practice-report"
        />
    );
}
