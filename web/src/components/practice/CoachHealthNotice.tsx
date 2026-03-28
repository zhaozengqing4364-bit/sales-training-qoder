import { cn } from "@/lib/utils";
import type { CoachHealth } from "@/hooks/use-practice-websocket";

interface CoachHealthNoticeProps {
    coachHealth: CoachHealth;
    title?: string;
    variant?: "panel" | "shell";
}

const STATUS_STYLES = {
    degraded: {
        container: {
            panel: "bg-amber-50/90 border-amber-200 shadow-[0_8px_30px_rgb(0,0,0,0.04)]",
            shell: "bg-amber-50/95 border-amber-200/90 shadow-sm",
        },
        dot: "bg-amber-500",
        text: "text-amber-800",
        badge: "bg-amber-100 text-amber-700",
    },
    resumed: {
        container: {
            panel: "bg-emerald-50/90 border-emerald-200 shadow-[0_8px_30px_rgb(0,0,0,0.04)]",
            shell: "bg-emerald-50/95 border-emerald-200/90 shadow-sm",
        },
        dot: "bg-emerald-500",
        text: "text-emerald-800",
        badge: "bg-emerald-100 text-emerald-700",
    },
} as const;

export function CoachHealthNotice({
    coachHealth,
    title = "辅导状态",
    variant = "panel",
}: CoachHealthNoticeProps) {
    const message = typeof coachHealth?.message === "string" ? coachHealth.message.trim() : "";

    if (coachHealth?.status === "healthy" || !message) {
        return null;
    }

    const styles = STATUS_STYLES[coachHealth.status];

    if (variant === "shell") {
        return (
            <div
                className={cn(
                    "w-full max-w-xl rounded-2xl border px-4 py-3",
                    styles.container.shell,
                )}
            >
                <div className="flex items-start gap-3">
                    <span
                        aria-hidden="true"
                        className={cn("mt-1 h-2.5 w-2.5 shrink-0 rounded-full", styles.dot)}
                    />
                    <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-slate-900">{title}</p>
                            <span
                                className={cn(
                                    "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium",
                                    styles.badge,
                                )}
                            >
                                {coachHealth.status === "degraded" ? "已降级" : "已恢复"}
                            </span>
                        </div>
                        <p className={cn("mt-1 text-xs leading-5", styles.text)}>{message}</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div
            className={cn(
                "rounded-2xl border p-4",
                styles.container.panel,
            )}
        >
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span className={cn("h-2 w-2 rounded-full", styles.dot)} />
                {title}
            </h3>
            <p className={cn("text-xs leading-6", styles.text)}>{message}</p>
        </div>
    );
}
