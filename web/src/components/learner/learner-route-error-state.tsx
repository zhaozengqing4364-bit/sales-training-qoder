"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

type LearnerRouteErrorStateProps = {
    error: unknown;
    reset: () => void;
    title?: string;
    description?: string;
    backHref?: string;
    backLabel?: string;
    errorTag?: string;
};

const DEFAULT_TITLE = "页面加载失败";
const DEFAULT_DESCRIPTION = "页面遇到了一些问题，请稍后重试。";
const DEFAULT_BACK_HREF = "/history";
const DEFAULT_BACK_LABEL = "返回历史";
const DEV_MESSAGE_LIMIT = 280;

function getDiagnosticMessage(error: unknown): string | null {
    if (
        typeof error === "object" &&
        error !== null &&
        "message" in error &&
        typeof error.message === "string"
    ) {
        const normalized = error.message.trim();
        if (!normalized) {
            return null;
        }
        return normalized.slice(0, DEV_MESSAGE_LIMIT);
    }

    return null;
}

export function LearnerRouteErrorState({
    error,
    reset,
    title = DEFAULT_TITLE,
    description = DEFAULT_DESCRIPTION,
    backHref = DEFAULT_BACK_HREF,
    backLabel = DEFAULT_BACK_LABEL,
    errorTag = "learner-route",
}: LearnerRouteErrorStateProps) {
    const diagnosticMessage = getDiagnosticMessage(error);
    const showDiagnosticMessage = process.env.NODE_ENV === "development" && Boolean(diagnosticMessage);

    useEffect(() => {
        console.error(`[LearnerRouteErrorState:${errorTag}]`, error);
    }, [error, errorTag]);

    return (
        <div className="flex min-h-[60vh] items-center justify-center p-8">
            <div className="w-full max-w-md space-y-6 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-50">
                    <AlertTriangle className="h-8 w-8 text-amber-500" />
                </div>
                <div className="space-y-2">
                    <h2 className="text-xl font-bold text-slate-900">{title}</h2>
                    <p className="text-sm text-slate-500">{description}</p>
                </div>
                {showDiagnosticMessage ? (
                    <div className="overflow-auto rounded-xl bg-red-50 p-4 text-left">
                        <p className="break-all text-xs font-mono text-red-600">{diagnosticMessage}</p>
                    </div>
                ) : null}
                <div className="flex justify-center gap-3">
                    <Button variant="outline" className="rounded-full" onClick={() => reset()}>
                        <RefreshCw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                    <Link href={backHref}>
                        <Button className="rounded-full bg-slate-900 text-white">
                            <ArrowLeft className="mr-2 h-4 w-4" /> {backLabel}
                        </Button>
                    </Link>
                </div>
            </div>
        </div>
    );
}
