"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function ReportError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error("[ReportError]", error);
    }, [error]);

    return (
        <div className="flex items-center justify-center min-h-[60vh] p-8">
            <div className="max-w-md w-full text-center space-y-6">
                <div className="w-16 h-16 bg-amber-50 rounded-full flex items-center justify-center mx-auto">
                    <AlertTriangle className="w-8 h-8 text-amber-500" />
                </div>
                <div className="space-y-2">
                    <h2 className="text-xl font-bold text-slate-900">报告加载失败</h2>
                    <p className="text-slate-500 text-sm">
                        训练报告遇到了一些问题，请稍后重试。
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
                    <Button variant="outline" className="rounded-full" onClick={() => reset()}>
                        <RefreshCw className="w-4 h-4 mr-2" /> 重试
                    </Button>
                    <Link href="/history">
                        <Button className="rounded-full bg-slate-900 text-white">
                            <ArrowLeft className="w-4 h-4 mr-2" /> 返回历史记录
                        </Button>
                    </Link>
                </div>
            </div>
        </div>
    );
}
