"use client";

import { LearnerRouteErrorState } from "@/components/learner/learner-route-error-state";

export default function AuthRouteError({
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
            title="认证页面暂时不可用"
            description="请稍后重试；如果仍然失败，可先返回登录页重新开始。"
            backHref="/login"
            backLabel="返回登录"
            errorTag="auth-route"
        />
    );
}
