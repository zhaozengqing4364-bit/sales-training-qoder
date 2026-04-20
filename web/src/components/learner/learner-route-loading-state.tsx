import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type LearnerRouteLoadingStateProps = {
    label: string;
    hint?: string;
    className?: string;
    children: ReactNode;
};

export function LearnerRouteLoadingState({
    label,
    hint,
    className,
    children,
}: LearnerRouteLoadingStateProps) {
    return (
        <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className={cn("mx-auto w-full px-4 py-6 md:px-6 md:py-8", className)}
        >
            <span className="sr-only">{label}</span>
            {hint ? <p className="mb-4 text-sm text-slate-500">{hint}</p> : null}
            {children}
        </div>
    );
}
