/**
 * Status Indicator Component
 * Shows loading, success, error states
 */

import { cn } from "@/lib/utils";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

interface StatusIndicatorProps {
    status: "loading" | "success" | "error" | "idle";
    message?: string;
    className?: string;
}

export function StatusIndicator({ status, message, className }: StatusIndicatorProps) {
    const icons = {
        idle: null,
        loading: <Loader2 className="w-5 h-5 animate-spin text-blue-500" />,
        success: <CheckCircle className="w-5 h-5 text-green-500" />,
        error: <XCircle className="w-5 h-5 text-red-500" />,
    };

    const defaultMessages = {
        idle: "",
        loading: "加载中...",
        success: "完成",
        error: "出错了",
    };

    if (status === "idle") return null;

    return (
        <div className={cn("flex items-center gap-2 text-sm", className)}>
            {icons[status]}
            <span className={cn(
                status === "loading" && "text-zinc-600",
                status === "success" && "text-green-600",
                status === "error" && "text-red-600"
            )}>
                {message || defaultMessages[status]}
            </span>
        </div>
    );
}
