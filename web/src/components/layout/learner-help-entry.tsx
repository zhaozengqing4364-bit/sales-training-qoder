"use client";

import { MessageSquareWarning } from "lucide-react";
import { useParams, usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/glass-tooltip";
import { cn } from "@/lib/utils";

type LearnerHelpEntryProps = {
    compact?: boolean;
    className?: string;
};

function sanitizeSegment(segment: string): string {
    return segment
        .replace(/[^\p{L}\p{N}_-]/gu, "")
        .slice(0, 24);
}

function getBoundedPathname(pathname: unknown): string | null {
    if (typeof pathname !== "string") {
        return null;
    }

    const normalized = pathname.split("?")[0]?.split("#")[0]?.trim();
    if (!normalized || !normalized.startsWith("/")) {
        return null;
    }

    const segments = normalized
        .split("/")
        .filter(Boolean)
        .slice(0, 4)
        .map(sanitizeSegment)
        .filter(Boolean);

    if (segments.length === 0) {
        return "/";
    }

    return `/${segments.join("/")}`.slice(0, 80);
}

function getBoundedSessionId(rawSessionId: unknown): string | null {
    if (typeof rawSessionId !== "string") {
        return null;
    }

    const normalized = rawSessionId
        .trim()
        .replace(/[^A-Za-z0-9_-]/g, "")
        .slice(0, 40);

    return normalized || null;
}

export function LearnerHelpEntry({ compact = false, className }: LearnerHelpEntryProps) {
    const pathname = usePathname();
    const params = useParams<{ sessionId?: string | string[] }>();
    const boundedPathname = getBoundedPathname(pathname);
    const boundedSessionId = getBoundedSessionId(
        Array.isArray(params?.sessionId) ? params.sessionId[0] : params?.sessionId,
    );

    const trigger = compact ? (
        <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="打开帮助与反馈"
            className={cn(
                "mx-auto h-10 w-10 rounded-full border border-slate-200 bg-white/80 text-slate-600 shadow-sm hover:bg-white hover:text-slate-900",
                className,
            )}
        >
            <MessageSquareWarning className="h-4 w-4" />
        </Button>
    ) : (
        <Button
            type="button"
            variant="outline"
            className={cn(
                "w-full justify-start gap-2 rounded-2xl border-slate-200/80 bg-white/80 px-4 text-slate-700 shadow-sm hover:bg-white hover:text-slate-900",
                className,
            )}
        >
            <MessageSquareWarning className="h-4 w-4" />
            <span>帮助与反馈</span>
        </Button>
    );

    return (
        <Dialog>
            <TooltipProvider delayDuration={0}>
                {compact ? (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <DialogTrigger asChild>{trigger}</DialogTrigger>
                        </TooltipTrigger>
                        <TooltipContent side="right">帮助与反馈</TooltipContent>
                    </Tooltip>
                ) : (
                    <DialogTrigger asChild>{trigger}</DialogTrigger>
                )}
            </TooltipProvider>

            <DialogContent>
                <DialogHeader>
                    <DialogTitle>帮助与反馈</DialogTitle>
                    <DialogDescription>
                        如果页面异常、入口缺失或结果不对，请把页面路径 / 会话编号反馈给管理员。当前入口只展示本地上下文，不会自动创建工单。
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50/80 p-4 text-sm text-slate-700">
                    <p className="font-medium text-slate-900">建议你反馈时直接复制下面这两项：</p>
                    <dl className="space-y-2">
                        <div className="flex flex-col gap-1 rounded-2xl bg-white/80 px-3 py-2">
                            <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">页面路径</dt>
                            <dd className="break-all font-mono text-xs text-slate-900">
                                {boundedPathname || "未能识别当前页面，请直接描述你看到的问题。"}
                            </dd>
                        </div>
                        {boundedSessionId ? (
                            <div className="flex flex-col gap-1 rounded-2xl bg-white/80 px-3 py-2">
                                <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">会话编号</dt>
                                <dd className="break-all font-mono text-xs text-slate-900">{boundedSessionId}</dd>
                            </div>
                        ) : null}
                    </dl>
                    <p className="text-xs leading-6 text-slate-500">
                        请只反馈当前页面路径、会话编号和你实际看到的现象；不要粘贴 token、邮箱配置或浏览器中的完整敏感链接。
                    </p>
                </div>
            </DialogContent>
        </Dialog>
    );
}
