"use client";

import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Mic, Square, FileText, ArrowLeft, AlertCircle, Wifi, WifiOff, Play, MicOff, Pause, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatBubble } from "@/components/ui/chat-bubble";
import { AudioVisualizer } from "@/components/ui/audio-visualizer";
import { AudioWaveform } from "@/components/ui/audio-waveform";
import { GlassSheet } from "@/components/ui/glass-sheet";
import { cn } from "@/lib/utils";
import { usePracticeWebSocket } from "@/hooks/use-practice-websocket";
import type { ConnectionState, SessionStatus } from "@/hooks/use-practice-websocket";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { RightPanelContent } from "@/components/practice/RightPanelContent";
import { CoachHealthNotice } from "@/components/practice/CoachHealthNotice";
import { usePracticeRuntimeLock, normalizeVoiceMode } from "./runtime-lock";
import { usePracticeRecordingHotkeys } from "./use-practice-recording-hotkeys";
import { usePracticeSessionLifecycle } from "./use-practice-session-lifecycle";
import { formatGoalTypeLabel, formatIssueTypeLabel } from "@/lib/session-evidence";

const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
    preparing: "准备中",
    in_progress: "进行中",
    paused: "已暂停",
    completed: "已完成",
    scoring: "评分中",
};

const CONNECTION_STATUS_LABELS: Record<ConnectionState, string> = {
    connecting: "连接中...",
    connected: "已连接",
    reconnecting: "重连中...",
    failed: "连接失败",
};

export default function PracticeSessionPage() {
    const params = useParams();
    const router = useRouter();
    const searchParams = useSearchParams();
    
    const sessionId = params.sessionId as string;
    const queryAgentId = searchParams.get("agent_id") || undefined;
    const queryPersonaId = searchParams.get("persona_id") || undefined;
    const queryPresentationId = searchParams.get("presentation_id") || undefined;
    const queryScenarioType = (searchParams.get("scenario_type") as "sales" | "presentation") || "sales";
    const queryVoiceMode = normalizeVoiceMode(searchParams.get("voice_mode"));
    const searchParamsString = searchParams.toString();
    const runtimeSearchParams = React.useMemo(
        () => new URLSearchParams(searchParamsString),
        [searchParamsString],
    );

    const [lockedScenarioType, setLockedScenarioType] = React.useState<"sales" | "presentation">(queryScenarioType);
    const [lockedVoiceMode, setLockedVoiceMode] = React.useState<"legacy" | "stepfun_realtime">(queryVoiceMode);
    const [lockedAgentId, setLockedAgentId] = React.useState<string | undefined>(queryAgentId);
    const [lockedPersonaId, setLockedPersonaId] = React.useState<string | undefined>(queryPersonaId);
    const [lockedPresentationId, setLockedPresentationId] = React.useState<string | undefined>(queryPresentationId);

    const [isPanelOpen, setIsPanelOpen] = React.useState(false);
    const [sessionTime, setSessionTime] = React.useState(0);
    const messagesEndRef = React.useRef<HTMLDivElement>(null);
    
    // 防止快速点击导致多个录音会话 (Critical Fix #1)
    const isStartingRef = React.useRef(false);

    // WebSocket 连接
    const {
        connectionState,
        isConnected,
        sessionStatus,
        aiState,
        messages,
        fuzzyDetections,
        salesStage,
        scores,
        liveSessionSummary,
        actionCard,
        coachHealth,
        error: wsError,
        isPlayingAudio,
        interimTranscript,
        audioUnlocked,
        isNetworkSlow,
        currentSlide,
        points,
        forbiddenWords,
        sendAudio,
        sendAudioBinary,
        sendAudioEnd,
        startSpeaking,
        sendInterrupt,
        unlockAudio,
        sendMessage,
        connect,
    } = usePracticeWebSocket({
        sessionId,
        scenarioType: lockedScenarioType,
        agentId: lockedAgentId,
        personaId: lockedPersonaId,
        voiceMode: lockedVoiceMode,
    });

    // 音频录制
    const {
        isRecording,
        hasPermission,
        error: audioError,
        stream,
        startRecording,
        stopRecording,
        requestPermission,
    } = useAudioRecorder({
        onAudioData: (base64Audio) => {
            if (isConnected) {
                // 流式发送音频数据
                sendAudio(base64Audio);
            }
        },
        onAudioDataBinary: (pcmData) => {
            if (isConnected) {
                sendAudioBinary(pcmData);
            }
        },
        onAudioEnd: () => {
            if (isConnected) {
                // 发送音频结束信号
                sendAudioEnd();
            }
        },
        onSpeakingChange: (speaking) => {
            if (isConnected && speaking) {
                if (aiIsBusyRef.current) {
                    sendInterrupt("user_speaking");
                }
                // 只在开始说话时发送信号
                startSpeaking();
            }
        },
    });

    const {
        lockedScenarioType: runtimeScenarioType,
        lockedVoiceMode: runtimeVoiceMode,
        lockedAgentId: runtimeAgentId,
        lockedPersonaId: runtimePersonaId,
        lockedPresentationId: runtimePresentationId,
        focusIntent,
        sessionMetaError,
    } = usePracticeRuntimeLock({
        sessionId,
        query: {
            scenarioType: queryScenarioType,
            voiceMode: queryVoiceMode,
            agentId: queryAgentId,
            personaId: queryPersonaId,
            presentationId: queryPresentationId,
        },
        searchParams: runtimeSearchParams,
        onRewriteQuery: router.replace,
    });

    React.useEffect(() => {
        setLockedScenarioType(runtimeScenarioType);
    }, [runtimeScenarioType]);

    React.useEffect(() => {
        setLockedVoiceMode(runtimeVoiceMode);
    }, [runtimeVoiceMode]);

    React.useEffect(() => {
        setLockedAgentId(runtimeAgentId);
    }, [runtimeAgentId]);

    React.useEffect(() => {
        setLockedPersonaId(runtimePersonaId);
    }, [runtimePersonaId]);

    React.useEffect(() => {
        setLockedPresentationId(runtimePresentationId);
    }, [runtimePresentationId]);

    // 计时器
    React.useEffect(() => {
        if (!isConnected) return;
        
        const timer = setInterval(() => {
            setSessionTime(prev => prev + 1);
        }, 1000);
        
        return () => clearInterval(timer);
    }, [isConnected]);

    // 自动滚动到最新消息
    React.useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const scenarioType = lockedScenarioType;
    const voiceMode = lockedVoiceMode;
    const focusIssueTypeLabel = React.useMemo(
        () => formatIssueTypeLabel(focusIntent?.main_issue?.issue_type ?? null),
        [focusIntent],
    );
    const focusGoalTypeLabel = React.useMemo(
        () => formatGoalTypeLabel(focusIntent?.next_goal?.goal_type ?? null),
        [focusIntent],
    );
    const showCarryForwardFocus = scenarioType === "sales" && Boolean(focusIntent);

    // AI 是否正在忙碌（说话或思考中），用于一来一回交互模式
    const aiIsBusy = isPlayingAudio || aiState === "thinking" || aiState === "speaking";
    // 使用 ref 保持最新值，避免闭包过时问题
    const aiIsBusyRef = React.useRef(aiIsBusy);
    const isRecordingRef = React.useRef(isRecording);
    const recordBtnRef = React.useRef<HTMLButtonElement>(null);

    React.useEffect(() => {
        aiIsBusyRef.current = aiIsBusy;
    }, [aiIsBusy]);

    React.useEffect(() => {
        isRecordingRef.current = isRecording;
    }, [isRecording]);

    const {
        canToggleLifecycle,
        handleEndSession,
        handleTogglePauseResume,
        isEndingSession,
        isSessionPaused,
        isSessionTerminal,
        lifecycleError,
        pendingLifecycleAction,
    } = usePracticeSessionLifecycle({
        sessionId,
        connectionState,
        sessionStatus,
        isRecordingRef,
        stopRecording,
    });
    const practiceError = lifecycleError || wsError || audioError || sessionMetaError;
    const canToggleRecordingBase =
        connectionState === "connected"
        && sessionStatus === "in_progress"
        && pendingLifecycleAction === null;
    const canRecord = canToggleRecordingBase && hasPermission !== false;
    const canRequestPermission = canToggleRecordingBase && hasPermission === false;

    // 统一的录音切换函数 - 点击一次开始，再点击一次结束
    const toggleRecording = React.useCallback(() => {
        console.log('[Recording] toggleRecording called, isRecording:', isRecordingRef.current, 'aiIsBusy:', aiIsBusyRef.current, 'isConnected:', isConnected, 'hasPermission:', hasPermission);
        
        if (connectionState !== "connected") return;
        if (sessionStatus !== "in_progress") return;
        if (pendingLifecycleAction) return;

        if (hasPermission === false) {
            void requestPermission().then((granted) => {
                if (!granted) return;
                if (isRecordingRef.current) return;
                unlockAudio();
                startRecording();
            });
            return;
        }
        
        // 防止快速双击
        if (isStartingRef.current) {
            console.log('[Recording] Blocked: already starting');
            return;
        }
        
        if (isRecordingRef.current) {
            // 正在录音 → 停止
            stopRecording();
        } else {
            // 没在录音 → 开始
            isStartingRef.current = true;
            unlockAudio();
            startRecording();
            setTimeout(() => {
                isStartingRef.current = false;
            }, 300);
        }
    }, [connectionState, hasPermission, isConnected, pendingLifecycleAction, requestPermission, sessionStatus, unlockAudio, startRecording, stopRecording]);

    usePracticeRecordingHotkeys({
        onToggleRecording: toggleRecording,
        onStopRecording: stopRecording,
        isRecordingRef,
    });

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    // v1-12 Fix: RightPanelContent extracted to separate component file
    // See: @/components/practice/RightPanelContent

    return (
        <div className="flex h-full w-full">
            {/* 开始练习覆盖层 - 用于解锁音频 */}
            {!audioUnlocked && isConnected && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
                    <div className="bg-white rounded-3xl p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)] max-w-sm mx-4 text-center">
                        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-indigo-100 flex items-center justify-center">
                            <Play className="w-10 h-10 text-indigo-600 ml-1" />
                        </div>
                        <h2 className="text-xl font-bold text-slate-800 mb-2">准备开始练习</h2>
                        <p className="text-slate-500 text-sm mb-6">
                            点击下方按钮开始与 AI 对话，系统将播放欢迎语音
                        </p>
                        <Button
                            size="lg"
                            className="w-full rounded-full bg-indigo-600 hover:bg-indigo-700 text-white py-6 text-lg font-semibold"
                            onClick={unlockAudio}
                        >
                            开始练习
                        </Button>
                    </div>
                </div>
            )}

            {/* 左侧聊天区域 */}
            <div className="flex-1 flex flex-col h-full relative">
                {/* 头部 */}
                <header className="h-16 px-4 md:px-6 flex items-center justify-between bg-white/40 backdrop-blur-md border-b border-white/20 z-10">
                    <div className="flex items-center gap-3">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => router.push("/")}
                            aria-label="退出练习并返回首页"
                            className="md:hidden"
                        >
                            <ArrowLeft className="w-5 h-5" />
                        </Button>
                        <div>
                            <h1 className="text-base md:text-lg font-bold text-slate-800">
                                {scenarioType === 'presentation' ? 'PPT演讲练习' : '销售对练'}
                            </h1>
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <span className="flex items-center gap-1">
                                    {connectionState === "connected" ? (
                                        <>
                                            <Wifi className="w-3 h-3 text-emerald-500" />
                                            <span className="text-emerald-600">{CONNECTION_STATUS_LABELS[connectionState]}</span>
                                        </>
                                    ) : connectionState === "connecting" || connectionState === "reconnecting" ? (
                                        <>
                                            <span className="w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                                            <span>{CONNECTION_STATUS_LABELS[connectionState]}</span>
                                        </>
                                    ) : (
                                        <>
                                            <WifiOff className="w-3 h-3 text-red-500" />
                                            <span className="text-red-600">{CONNECTION_STATUS_LABELS[connectionState]}</span>
                                        </>
                                    )}
                                </span>
                                <span>•</span>
                                <span>{formatTime(sessionTime)}</span>
                                <span>•</span>
                                <span>{SESSION_STATUS_LABELS[sessionStatus]}</span>
                                <span>•</span>
                                <span>{voiceMode === "stepfun_realtime" ? "Realtime 模式" : "经典模式"}</span>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={handleTogglePauseResume}
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
                            onClick={handleEndSession}
                            disabled={isEndingSession || isSessionTerminal || pendingLifecycleAction !== null}
                            className="hidden md:flex rounded-full"
                        >
                            {isEndingSession ? (
                                <>
                                    <span className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    生成报告中...
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
                            onClick={handleTogglePauseResume}
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
                            onClick={handleEndSession}
                            disabled={isEndingSession || isSessionTerminal || pendingLifecycleAction !== null}
                            className="md:hidden text-red-500"
                        >
                            {isEndingSession ? "生成中..." : "结束"}
                        </Button>
                    </div>
                </header>

                {showCarryForwardFocus && focusIntent && (
                    <div className="mx-4 mt-4 rounded-2xl border border-indigo-100 bg-indigo-50/80 p-4 text-slate-700 shadow-sm">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="inline-flex items-center rounded-full bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white">
                                定向再练
                            </span>
                            <p className="text-sm font-semibold text-slate-900">本次练习聚焦上次复盘问题</p>
                        </div>
                        <p className="mt-2 text-sm text-slate-600">
                            这次不是普通新建会话，系统已带入上一轮的主问题和下一轮目标，方便你直接针对性再练。
                        </p>
                        <div className="mt-3 grid gap-3 md:grid-cols-2">
                            {focusIntent.main_issue && (
                                <div className="rounded-xl border border-amber-100 bg-white/80 p-3">
                                    <p className="text-xs font-semibold text-amber-700">主问题{focusIssueTypeLabel ? ` · ${focusIssueTypeLabel}` : ""}</p>
                                    <p className="mt-1 text-sm text-amber-950">{focusIntent.main_issue.issue_text}</p>
                                    {focusIntent.main_issue.recovery_rule && (
                                        <p className="mt-2 text-xs text-amber-800">修正动作：{focusIntent.main_issue.recovery_rule}</p>
                                    )}
                                </div>
                            )}
                            {focusIntent.next_goal && (
                                <div className="rounded-xl border border-sky-100 bg-white/80 p-3">
                                    <p className="text-xs font-semibold text-sky-700">下一轮目标{focusGoalTypeLabel ? ` · ${focusGoalTypeLabel}` : ""}</p>
                                    <p className="mt-1 text-sm text-sky-950">{focusIntent.next_goal.goal_text}</p>
                                    {focusIntent.next_goal.rule && (
                                        <p className="mt-2 text-xs text-sky-800">判定条件：{focusIntent.next_goal.rule}</p>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* 错误提示 */}
                {practiceError && (
                    <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-100 rounded-lg flex flex-col gap-3 text-sm text-red-600 md:flex-row md:items-center">
                        <div className="flex items-center gap-2 min-w-0">
                            <AlertCircle className="w-4 h-4 shrink-0" />
                            <span className="min-w-0 break-words">{practiceError}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 md:ml-auto">
                            {lifecycleError && !isSessionTerminal && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={handleEndSession}
                                    disabled={isEndingSession || connectionState !== "connected"}
                                    className="h-8 rounded-full border-red-200 text-red-700 hover:bg-red-100"
                                >
                                    <Square className="w-3 h-3 mr-1 fill-current" />
                                    重试结束
                                </Button>
                            )}
                            {connectionState === "failed" && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={connect}
                                    className="h-8 rounded-full border-red-200 text-red-700 hover:bg-red-100"
                                >
                                    <RefreshCw className="w-3 h-3 mr-1" />
                                    重新连接
                                </Button>
                            )}
                        </div>
                    </div>
                )}

                {/* 网络慢提示 */}
                {isNetworkSlow && (
                    <div className="mx-4 mt-4 p-3 bg-amber-50 border border-amber-100 rounded-lg flex items-center gap-2 text-sm text-amber-600">
                        <AlertCircle className="w-4 h-4" />
                        网络较慢，部分语音可能丢失，请检查网络连接
                    </div>
                )}

                {/* 聊天列表 */}
                <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-[220px] md:pb-[200px]">
                    <div className="max-w-3xl mx-auto">
                        {messages.length === 0 && isConnected && (
                            <div className="text-center text-slate-600 py-8">
                                <p>
                                    {isSessionPaused
                                        ? "会话已暂停，点击“继续”后恢复对话"
                                        : "连接成功！点击麦克风按钮或按空格键开始对话"}
                                </p>
                            </div>
                        )}
                        {messages.map((msg) => (
                            <ChatBubble
                                key={msg.id}
                                message={msg.message}
                                sender={msg.sender}
                                timestamp={msg.timestamp}
                                avatar={
                                    msg.sender === "ai"
                                        ? "/ai-avatar.svg"
                                        : undefined
                                }
                            />
                        ))}
                        <div ref={messagesEndRef} />
                    </div>
                </div>

                {/* 底部控制区 */}
                <div className="absolute bottom-0 left-0 right-0 p-4 md:p-6 bg-gradient-to-t from-white via-white/90 to-transparent z-20">
                    <div className="max-w-3xl mx-auto flex flex-col items-center gap-4">
                        <CoachHealthNotice
                            coachHealth={coachHealth}
                            title="辅导状态提醒"
                            variant="shell"
                        />

                        {interimTranscript && (
                            <div className="w-full max-w-md px-4 py-2 bg-indigo-50 border border-indigo-100 rounded-xl">
                                <p className="text-sm text-indigo-700 text-center animate-pulse">
                                    {interimTranscript}
                                </p>
                            </div>
                        )}

                        <div
                            role="status"
                            aria-live="polite"
                            aria-atomic="true"
                            className="sr-only"
                        >
                            {interimTranscript && `正在识别: ${interimTranscript}`}
                        </div>
                        
                        {/* 波形显示 - 使用真实音频可视化 */}
                        <div className="flex items-center gap-2 h-8 text-slate-500">
                            {isRecording ? (
                                <>
                                    <AudioVisualizer stream={stream} isActive={isRecording} barCount={16} />
                                    <span className="text-xs">正在录音...</span>
                                </>
                            ) : isPlayingAudio ? (
                                <>
                                    <AudioWaveform isAnimate={true} barCount={12} />
                                    <span className="text-xs">AI 正在说话...</span>
                                </>
                            ) : aiState === "thinking" ? (
                                <span className="text-xs animate-pulse">AI 思考中...</span>
                            ) : aiState === "speaking" ? (
                                <span className="text-xs">AI 正在回复...</span>
                            ) : isSessionPaused ? (
                                <span className="text-xs">会话已暂停</span>
                            ) : (
                                <span className="text-xs">等待输入...</span>
                            )}
                        </div>

                        <div className="flex items-center gap-4 w-full justify-center relative">
                            <Button
                                variant="ghost"
                                size="icon"
                                aria-label="打开实时分析面板"
                                className="md:hidden absolute left-0"
                                onClick={() => setIsPanelOpen(true)}
                            >
                                <FileText className="w-5 h-5 text-slate-500" />
                            </Button>

                            {/* 录音按钮 - 统一 toggle 模式：点击/空格切换录音 */}
                            <Button
                                ref={recordBtnRef}
                                size="lg"
                                disabled={!(canRecord || canRequestPermission)}
                                aria-label={
                                    isRecording
                                        ? "停止录音"
                                        : hasPermission === false
                                        ? "点击重新请求麦克风权限"
                                        : sessionStatus === "paused"
                                        ? "会话已暂停"
                                        : sessionStatus !== "in_progress"
                                        ? "会话不可录音"
                                        : aiIsBusy
                                        ? "打断AI并开始录音"
                                        : "开始录音"
                                }
                                aria-pressed={isRecording}
                                onClick={toggleRecording}
                                className={cn(
                                    "rounded-full w-16 h-16 md:w-20 md:h-20 shadow-xl transition-all duration-300",
                                    isRecording
                                        ? "bg-red-500 hover:bg-red-600 scale-110"
                                        : canRequestPermission
                                        ? "bg-amber-500 hover:bg-amber-600"
                                        : aiIsBusy
                                        ? "bg-amber-500 hover:bg-amber-600"
                                        : !canRecord
                                        ? "bg-slate-300 cursor-not-allowed opacity-60"
                                        : "bg-indigo-600 hover:bg-indigo-700"
                                )}
                            >
                                {isRecording ? (
                                    <MicOff className="w-6 h-6 md:w-8 md:h-8 animate-pulse" />
                                ) : (
                                    <Mic className="w-6 h-6 md:w-8 md:h-8" />
                                )}
                            </Button>

                            {/* 桌面端：空格键提示 */}
                            <div className="hidden md:block absolute right-0 text-xs text-slate-500">
                                空格键 / 点击切换录音
                            </div>
                        </div>

                        <p className="text-xs text-slate-500 font-medium">
                            {connectionState === "failed"
                                ? "连接失败，请点击“重新连接”恢复会话"
                                : connectionState === "reconnecting"
                                ? "网络波动，正在自动重连..."
                                : connectionState === "connecting"
                                ? "正在建立连接..."
                                : audioError
                                ? audioError.includes("HTTP/IP")
                                    ? "当前地址不是安全上下文，请改用 HTTPS 域名访问"
                                    : audioError.includes("未检测到可用麦克风")
                                    ? "未检测到可用麦克风设备"
                                    : audioError.includes("被其他应用占用")
                                    ? "麦克风被其他应用占用"
                                    : "请先处理麦克风访问问题"
                                : hasPermission === false
                                ? "请允许麦克风权限"
                                : pendingLifecycleAction
                                ? "正在更新会话状态..."
                                : isSessionTerminal
                                ? "会话已结束，正在生成/查看结果"
                                : isSessionPaused
                                ? "会话已暂停，点击顶部继续按钮恢复"
                                : isPlayingAudio
                                ? "AI 正在说话，点击麦克风可打断"
                                : aiState === "thinking"
                                ? "AI 思考中，点击麦克风可打断并发言"
                                : isRecording
                                ? "再次点击或按空格结束录音"
                                : "点击或按空格开始说话"}
                        </p>
                    </div>
                </div>
            </div>

            {/* 右侧面板 (桌面端) */}
            <div className="hidden md:block w-80 lg:w-96 border-l border-white/40 bg-white/30 backdrop-blur-xl p-6 overflow-y-auto">
                <RightPanelContent
                    scenarioType={scenarioType}
                    presentationId={lockedPresentationId}
                    currentSlide={currentSlide}
                    points={points}
                    forbiddenWords={forbiddenWords}
                    scores={scores}
                    liveSessionSummary={liveSessionSummary}
                    actionCard={actionCard}
                    coachHealth={coachHealth}
                    fuzzyDetections={fuzzyDetections}
                    salesStage={salesStage}
                    sendMessage={sendMessage}
                />
            </div>

            {/* 移动端底部面板 */}
            <GlassSheet
                isOpen={isPanelOpen}
                onClose={() => setIsPanelOpen(false)}
                side="bottom"
                className="h-[80vh]"
            >
                <div className="h-full overflow-y-auto pb-8">
                    <h2 className="text-lg font-bold mb-6 text-slate-800">实时分析面板</h2>
                    <RightPanelContent
                        scenarioType={scenarioType}
                        presentationId={lockedPresentationId}
                        currentSlide={currentSlide}
                        points={points}
                        forbiddenWords={forbiddenWords}
                        scores={scores}
                        liveSessionSummary={liveSessionSummary}
                        actionCard={actionCard}
                        coachHealth={coachHealth}
                        fuzzyDetections={fuzzyDetections}
                        salesStage={salesStage}
                        sendMessage={sendMessage}
                    />
                </div>
            </GlassSheet>
        </div>
    );
}
