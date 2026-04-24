import { ArrowLeft, Pause, Play, Square, Wifi, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ConnectionState } from "@/hooks/use-practice-websocket";

export function formatPracticeElapsedTime(seconds: number): string {
    const safeSeconds = Math.max(0, Math.floor(seconds));
    const mins = Math.floor(safeSeconds / 60);
    const secs = safeSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export interface PracticeHeaderProps {
    scenarioType: "sales" | "presentation";
    connectionState: ConnectionState;
    connectionStatusLabel: string;
    sessionStatusLabel: string;
    voiceMode: "legacy" | "stepfun_realtime";
    sessionTime: number;
    canToggleLifecycle: boolean;
    pendingLifecycleAction: string | null;
    isSessionPaused: boolean;
    isEndingSession: boolean;
    isSessionTerminal: boolean;
    endButtonLabel: string;
    onExit: () => void;
    onTogglePauseResume: () => void;
    onEndSession: () => void;
}

function ConnectionStatusPill({
    connectionState,
    connectionStatusLabel,
}: {
    connectionState: ConnectionState;
    connectionStatusLabel: string;
}) {
    if (connectionState === "connected") {
        return (
            <>
                <Wifi className="w-3 h-3 text-emerald-500" />
                <span className="text-emerald-600">{connectionStatusLabel}</span>
            </>
        );
    }

    if (connectionState === "connecting" || connectionState === "reconnecting") {
        return (
            <>
                <span className="w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                <span>{connectionStatusLabel}</span>
            </>
        );
    }

    return (
        <>
            <WifiOff className="w-3 h-3 text-red-500" />
            <span className="text-red-600">{connectionStatusLabel}</span>
        </>
    );
}

export function PracticeHeader({
    scenarioType,
    connectionState,
    connectionStatusLabel,
    sessionStatusLabel,
    voiceMode,
    sessionTime,
    canToggleLifecycle,
    pendingLifecycleAction,
    isSessionPaused,
    isEndingSession,
    isSessionTerminal,
    endButtonLabel,
    onExit,
    onTogglePauseResume,
    onEndSession,
}: PracticeHeaderProps) {
    return (
        <header className="h-16 px-4 md:px-6 flex items-center justify-between bg-white/40 backdrop-blur-md border-b border-white/20 z-10">
            <div className="flex items-center gap-3">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onExit}
                    aria-label="退出练习并返回首页"
                    className="md:hidden"
                >
                    <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                    <h1 className="text-base md:text-lg font-bold text-slate-800">
                        {scenarioType === "presentation" ? "PPT演讲练习" : "销售对练"}
                    </h1>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                            <ConnectionStatusPill
                                connectionState={connectionState}
                                connectionStatusLabel={connectionStatusLabel}
                            />
                        </span>
                        <span>•</span>
                        <span>{formatPracticeElapsedTime(sessionTime)}</span>
                        <span>•</span>
                        <span>{sessionStatusLabel}</span>
                        <span>•</span>
                        <span>{voiceMode === "stepfun_realtime" ? "Realtime 模式" : "经典模式"}</span>
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onTogglePauseResume}
                    disabled={!canToggleLifecycle}
                    className="hidden md:flex rounded-full"
                >
                    {pendingLifecycleAction ? (
                        <>
                            <span className="w-4 h-4 mr-2 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                            处理中...
                        </>
                    ) : isSessionPaused ? (
                        <>
                            <Play className="w-4 h-4 mr-2 fill-current" />
                            继续练习
                        </>
                    ) : (
                        <>
                            <Pause className="w-4 h-4 mr-2" />
                            暂停
                        </>
                    )}
                </Button>
                <Button
                    variant="destructive"
                    size="sm"
                    onClick={onEndSession}
                    disabled={isEndingSession || isSessionTerminal || pendingLifecycleAction !== null}
                    className="hidden md:flex rounded-full"
                >
                    {isEndingSession ? (
                        <>
                            <span className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            {endButtonLabel}
                        </>
                    ) : (
                        <>
                            <Square className="w-4 h-4 mr-2 fill-current" />
                            结束练习
                        </>
                    )}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onTogglePauseResume}
                    disabled={!canToggleLifecycle}
                    className="md:hidden"
                >
                    {pendingLifecycleAction
                        ? "处理中..."
                        : isSessionPaused
                        ? "继续"
                        : "暂停"}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onEndSession}
                    disabled={isEndingSession || isSessionTerminal || pendingLifecycleAction !== null}
                    className="md:hidden text-red-500"
                >
                    {isEndingSession ? "生成中..." : "结束"}
                </Button>
            </div>
        </header>
    );
}
