"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

interface AdminLoadErrorCardProps {
    title: string;
    description: string;
    message?: string | null;
    retryLabel?: string;
    onRetry: () => void;
}

export function AdminLoadErrorCard({
    title,
    description,
    message,
    retryLabel = "重试加载",
    onRetry,
}: AdminLoadErrorCardProps) {
    return (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
            <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
                <div className="space-y-3">
                    <div>
                        <h2 className="font-bold text-amber-950">{title}</h2>
                        <p className="mt-1 text-sm leading-6">{description}</p>
                        {message ? (
                            <p className="mt-2 text-sm font-medium">{message}</p>
                        ) : null}
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        className="bg-white"
                        onClick={onRetry}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {retryLabel}
                    </Button>
                </div>
            </div>
        </div>
    );
}
