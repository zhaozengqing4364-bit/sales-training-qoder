"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { debug } from "@/lib/debug";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function DashboardError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        debug.durableError("route-error.dashboard", error, {
            digest: error.digest,
            route: "/dashboard",
        });
    }, [error]);

    return (
        <div className="flex items-center justify-center min-h-[60vh] p-8">
            <div className="max-w-md w-full text-center space-y-6">
                <div className="w-16 h-16 bg-amber-50 rounded-full flex items-center justify-center mx-auto">
                    <AlertTriangle className="w-8 h-8 text-amber-500" />
                </div>

                <div className="space-y-2">
                    <h2 className="text-xl font-bold text-slate-900">页面出了点问题</h2>
                    <p className="text-slate-500 text-sm">
                        我们正在修复这个问题，请稍后重试或返回首页。
                    </p>
                </div>

                {process.env.NODE_ENV === "development" && (
                    <div className="p-4 bg-red-50 rounded-xl text-left overflow-auto">
                        <p className="text-xs font-mono text-red-600 break-all">
                            {error.message}
                        </p>
                    </div>
                )}

                <div className="flex gap-3 justify-center">
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => reset()}
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        重试
                    </Button>
                    <Link href="/">
                        <Button className="rounded-full bg-slate-900 text-white">
                            <Home className="w-4 h-4 mr-2" />
                            返回首页
                        </Button>
                    </Link>
                </div>
            </div>
        </div>
    );
}
