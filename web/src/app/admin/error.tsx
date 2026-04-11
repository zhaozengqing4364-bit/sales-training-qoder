
"use client";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { debug } from "@/lib/debug";
import { AlertCircle, RefreshCcw } from "lucide-react";
import { useEffect } from "react";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        debug.durableError("route-error.admin", error, {
            digest: error.digest,
            route: "/admin",
        });
    }, [error]);

    return (
        <div className="h-[600px] flex items-center justify-center p-4">
            <GlassCard className="max-w-md w-full p-8 text-center flex flex-col items-center">
                <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center text-red-500 mb-6 shadow-sm">
                    <AlertCircle className="w-8 h-8" strokeWidth={1.5} />
                </div>
                <h2 className="text-xl font-black text-slate-900 mb-2">Something went wrong!</h2>
                <p className="text-slate-500 text-sm mb-8 leading-relaxed">
                    An unexpected error occurred while loading the dashboard.
                    Our team has been notified.
                </p>
                <div className="flex gap-4 w-full">
                    <Button
                        variant="outline"
                        onClick={() => window.location.href = '/'}
                        className="flex-1 rounded-full border-slate-200"
                    >
                        Go Home
                    </Button>
                    <Button
                        onClick={reset}
                        className="flex-1 rounded-full bg-slate-900 hover:bg-slate-800 text-white"
                    >
                        <RefreshCcw className="w-4 h-4 mr-2" /> Retry
                    </Button>
                </div>
            </GlassCard>
        </div>
    );
}
