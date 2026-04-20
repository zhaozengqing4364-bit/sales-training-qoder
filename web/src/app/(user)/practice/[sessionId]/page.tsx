"use client";
import { debug } from "@/lib/debug";

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
import type { ActionCard, ConnectionState, SessionStatus } from "@/hooks/use-practice-websocket";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { useContinuousAudioUploader } from "@/hooks/use-continuous-audio-uploader";
import { RightPanelContent } from "@/components/practice/RightPanelContent";
import type { ActionCompletionStatus } from "@/components/practice/RightPanelContent";
import { CoachHealthNotice } from "@/components/practice/CoachHealthNotice";
import { api } from "@/lib/api/client";
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

type TrackedActionCard = {
    key: string;
    card: ActionCard;
    userMessageCount: number;
    suggestionCount: number;
    overallScore: number;
};

function buildActionCardKey(actionCard: ActionCard): string {
    return [actionCard.issue, actionCard.replacement, actionCard.next_turn_rule].join("|");
}

type PracticePreflightBrief = {
    trainingGoal: string;
    evaluationCopy: string;
    roleCopy: string;
};

function buildFallbackPreflightBrief(scenarioType: "sales" | "presentation"): PracticePreflightBrief {
    if (scenarioType === "presentation") {
        return {
            trainingGoal: "围绕当前 PPT 完成一轮演讲表达，开口前先想清楚开场、重点页和收尾推进。",
            evaluationCopy: "系统会重点看流畅连贯、内容准确、专业表达、互动问答与整体表现。",
            roleCopy: "你将面对会关注表达清晰度和现场问答的评委/听众角色。",
        };
    }

    return {
        trainingGoal: "围绕当前销售主题进行一轮销售对练，开口前先想好价值主张和下一步推进。",
        evaluationCopy: "系统会重点看价值翻译、证据支撑和异议推进的完成度。",
        roleCopy: "你将面对一个会持续追问价值、证据和下一步动作的客户角色。",
    };
}

type PracticeFaultSeverity = "error" | "warning" | "info";

type PracticeFault = {
    id: string;
    severity: PracticeFaultSeverity;
    title: string;
    message: string;
    guidance?: string | null;
    action?: React.ReactNode;
};

const PRACTICE_FAULT_STYLES: Record<PracticeFaultSeverity, {
    container: string;
    badge: string;
    icon: string;
}> = {
    error: {
        container: "border-red-100 bg-red-50 text-red-700",
        badge: "bg-red-100 text-red-700",
        icon: "text-red-500",
    },
    warning: {
        container: "border-amber-200 bg-amber-50 text-amber-800",
        badge: "bg-amber-100 text-amber-800",
        icon: "text-amber-600",
    },
    info: {
        container: "border-sky-100 bg-sky-50 text-sky-800",
        badge: "bg-sky-100 text-sky-800",
        icon: "text-sky-600",
    },
};

function PracticeFaultPanel({ faults }: { faults: PracticeFault[] }) {
    if (faults.length === 0) {
        return null;
    }

    return (
        <section
            aria-label="练习故障与恢复面板"
            className="mx-4 mt-4 rounded-2xl border border-slate-200 bg-white/90 p-3 shadow-sm"
        >
            <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
                    故障面板
                </span>
                <p className="text-sm font-semibold text-slate-900">
                    当前有 {faults.length} 项需要处理的练习状态
                </p>
            </div>
            <div className="mt-3 grid gap-2">
                {faults.map((fault) => {
                    const styles = PRACTICE_FAULT_STYLES[fault.severity];

                    return (
                        <article
                            key={fault.id}
                            className={cn(
                                "rounded-xl border p-3",
                                styles.container,
                            )}
                        >
                            <div className="flex flex-col gap-3 md:flex-row md:items-start">
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2">
                                        <AlertCircle className={cn("h-4 w-4 shrink-0", styles.icon)} />
                                        <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", styles.badge)}>
                                            {fault.title}
                                        </span>
                                    </div>
                                    <p className="mt-2 text-sm leading-5">{fault.message}</p>
                                    {fault.guidance && (
                                        <p className="mt-1 text-xs leading-5 opacity-80">下一步：{fault.guidance}</p>
                                    )}
                                </div>
                                {fault.action && (
                                    <div className="flex flex-wrap items-center gap-2 md:ml-auto">
                                        {fault.action}
                                    </div>
                                )}
                            </div>
                        </article>
                    );
                })}
            </div>
        </section>
    );
}

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
    const [preflightBrief, setPreflightBrief] = React.useState<PracticePreflightBrief>(() => buildFallbackPreflightBrief(queryScenarioType));
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

    // 持续音频留痕 — 与 useAudioRecorder 并行运行
    // 录音开始时启动 OSS 直传；录音结束时落地最后一个分片
    const continuousUploader = useContinuousAudioUploader({
        sessionId,
        enabled: true,
        mediaStream: stream,
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

    React.useEffect(() => {
        let isCancelled = false;

        const applyFallback = () => {
            if (!isCancelled) {
                setPreflightBrief(buildFallbackPreflightBrief(scenarioType));
            }
        };

        const loadPreflightBrief = async () => {
            if (scenarioType === "sales") {
                if (!lockedAgentId) {
                    applyFallback();
                    return;
                }

                try {
                    const agent = await api.agents.getAgentWithPersonas(lockedAgentId);
                    if (isCancelled) {
                        return;
                    }
                    const persona = lockedPersonaId
                        ? agent.personas?.find((item) => item.id === lockedPersonaId)
                        : null;
                    setPreflightBrief({
                        trainingGoal: `围绕「${agent.name || "当前销售主题"}」进行销售对练，开口前先想好价值主张和下一步推进。`,
                        evaluationCopy: "系统会重点看价值翻译、证据支撑和异议推进的完成度。",
                        roleCopy: persona?.description
                            ? `${persona.name}：${persona.description}`
                            : persona?.name
                            ? `${persona.name}：会围绕当前销售对话持续追问，并判断你是否把价值和下一步说清楚。`
                            : "你将面对一个会持续追问价值、证据和下一步动作的客户角色。",
                    });
                } catch {
                    applyFallback();
                }
                return;
            }

            if (!lockedPresentationId) {
                applyFallback();
                return;
            }

            try {
                const presentation = await api.presentations.get(lockedPresentationId);
                if (isCancelled) {
                    return;
                }
                const presentationTitle = typeof presentation?.title === "string" && presentation.title.trim()
                    ? presentation.title.trim()
                    : "当前 PPT";
                setPreflightBrief({
                    trainingGoal: `围绕《${presentationTitle}》完成一轮演讲表达，开口前先想清楚开场、重点页和收尾推进。`,
                    evaluationCopy: "系统会重点看流畅连贯、内容准确、专业表达、互动问答与整体表现。",
                    roleCopy: "你将面对会关注表达清晰度、页级重点覆盖和临场问答的评委/听众角色。",
                });
            } catch {
                applyFallback();
            }
        };

        void loadPreflightBrief();

        return () => {
            isCancelled = true;
        };
    }, [lockedAgentId, lockedPersonaId, lockedPresentationId, scenarioType]);

    // AI 是否正在忙碌（说话或思考中），用于一来一回交互模式
    const aiIsBusy = isPlayingAudio || aiState === "thinking" || aiState === "speaking";
    const userMessageCount = React.useMemo(
        () => messages.filter((message) => message.sender === "user").length,
        [messages],
    );
    const actionCardKey = actionCard ? buildActionCardKey(actionCard) : null;
    const [trackedActionCard, setTrackedActionCard] = React.useState<TrackedActionCard | null>(null);

    React.useEffect(() => {
        setTrackedActionCard(null);
    }, [sessionId]);

    React.useEffect(() => {
        if (!actionCard || !actionCardKey) {
            return;
        }

        setTrackedActionCard((current) => {
            if (current?.key === actionCardKey) {
                return current;
            }

            return {
                key: actionCardKey,
                card: actionCard,
                userMessageCount,
                suggestionCount: scores?.suggestions?.length ?? 0,
                overallScore: scores?.overall_score ?? 0,
            };
        });
    }, [actionCard, actionCardKey, scores, userMessageCount]);

    const displayedActionCard = actionCard ?? trackedActionCard?.card ?? null;
    const actionCompletionStatus = React.useMemo<ActionCompletionStatus | null>(() => {
        if (!trackedActionCard) {
            return null;
        }

        const hasAttemptedAction = userMessageCount > trackedActionCard.userMessageCount;
        if (!hasAttemptedAction) {
            return {
                state: "waiting",
                label: "等待你在下一轮尝试",
                detail: "先按替换句完成下一次回应，系统会继续观察后续分数和建议变化。",
            };
        }

        const currentSuggestionCount = scores?.suggestions?.length ?? trackedActionCard.suggestionCount;
        const currentOverallScore = scores?.overall_score ?? trackedActionCard.overallScore;
        const hasImprovementSignal = currentSuggestionCount < trackedActionCard.suggestionCount
            || currentOverallScore > trackedActionCard.overallScore;

        if (hasImprovementSignal) {
            return {
                state: "improved",
                label: "本轮已尝试，继续巩固",
                detail: "后续建议减少或分数上升，说明这次回应已经出现积极信号。",
            };
        }

        return {
            state: "missed",
            label: "还未命中判定条件",
            detail: "已经检测到新的用户回应，但还没有看到建议减少或分数改善，请下一轮继续按判定条件尝试。",
        };
    }, [scores, trackedActionCard, userMessageCount]);
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
        handleStartSession,
        handleTogglePauseResume,
        audioEvidenceStatus = { status: "idle", message: null, error: null },
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
        flushAudioEvidence: continuousUploader.flushAndStop,
    });

    const lifecycleErrorMessage = lifecycleError?.message ?? null;
    const lifecycleErrorGuidance = lifecycleError?.guidance ?? null;
    const lifecycleRetryLabel = lifecycleError?.action === "start"
        ? "重试启动"
        : lifecycleError?.action === "end"
        ? "重试结束"
        : lifecycleError?.action === "resume"
        ? "重试继续"
        : lifecycleError?.action === "pause"
        ? "重试暂停"
        : null;
    const audioUploadError = continuousUploader.uploadStatus === "error"
        ? continuousUploader.lastError || "录音留痕上传失败"
        : null;
    const audioEvidenceEndState = audioEvidenceStatus.status === "failed" || audioEvidenceStatus.status === "timed_out"
        ? audioEvidenceStatus
        : null;
    const handleRestartAudioUpload = React.useCallback(async () => {
        await continuousUploader.stopUpload();
        await continuousUploader.startUpload();
    }, [continuousUploader]);
    const practiceFaults = React.useMemo<PracticeFault[]>(() => {
        const faults: PracticeFault[] = [];

        if (wsError || connectionState === "failed" || connectionState === "reconnecting") {
            const isFailed = connectionState === "failed";
            faults.push({
                id: "connection",
                severity: isFailed ? "error" : "warning",
                title: isFailed ? "连接失败" : "连接恢复中",
                message: wsError || (isFailed ? "实时连接失败。" : "网络波动，正在自动重连。"),
                guidance: isFailed ? "点击重新连接恢复会话；如果仍失败，可刷新页面后重新进入。" : "自动重连期间请先不要结束页面，系统会尽量恢复当前会话。",
                action: isFailed ? (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={connect}
                        className="h-8 rounded-full border-red-200 text-red-700 hover:bg-red-100"
                    >
                        <RefreshCw className="w-3 h-3 mr-1" />
                        重新连接
                    </Button>
                ) : null,
            });
        }

        if (sessionMetaError) {
            faults.push({
                id: "session-meta",
                severity: "error",
                title: "会话配置",
                message: sessionMetaError,
                guidance: "请返回训练入口重新选择智能体、客户画像或 PPT 后再进入练习。",
            });
        }

        if (lifecycleErrorMessage) {
            faults.push({
                id: `lifecycle-${lifecycleError?.action ?? "unknown"}`,
                severity: "error",
                title: "会话状态",
                message: lifecycleErrorMessage,
                guidance: lifecycleErrorGuidance,
                action: lifecycleError && !isSessionTerminal && lifecycleRetryLabel ? (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={lifecycleError.action === "start"
                            ? handleStartSession
                            : lifecycleError.action === "end"
                            ? handleEndSession
                            : handleTogglePauseResume}
                        disabled={lifecycleError.action === "start"
                            ? connectionState !== "connected"
                            : lifecycleError.action === "end"
                            ? isEndingSession || connectionState !== "connected"
                            : !canToggleLifecycle}
                        className="h-8 rounded-full border-red-200 text-red-700 hover:bg-red-100"
                    >
                        {lifecycleError.action === "start" ? (
                            <RefreshCw className="w-3 h-3 mr-1" />
                        ) : lifecycleError.action === "end" ? (
                            <Square className="w-3 h-3 mr-1 fill-current" />
                        ) : lifecycleError.action === "resume" ? (
                            <Play className="w-3 h-3 mr-1 fill-current" />
                        ) : (
                            <Pause className="w-3 h-3 mr-1" />
                        )}
                        {lifecycleRetryLabel}
                    </Button>
                ) : null,
            });
        }

        if (audioError || hasPermission === false) {
            faults.push({
                id: "microphone",
                severity: "warning",
                title: "麦克风",
                message: audioError || "浏览器还没有麦克风权限。",
                guidance: audioError
                    ? "请检查浏览器权限、设备占用和 HTTPS 访问条件，处理后再重新录音。"
                    : "点击麦克风按钮重新请求权限，或在浏览器地址栏允许麦克风。",
            });
        }

        if (audioUploadError) {
            faults.push({
                id: "audio-upload",
                severity: "warning",
                title: "音频留痕",
                message: `实时对话仍可继续，但回放或报告的音频证据可能缺失。原因：${audioUploadError}`,
                guidance: "如果仍在录音，可点击重试留痕；系统会保留已成功登记的分片。",
                action: (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={handleRestartAudioUpload}
                        disabled={!isRecording || continuousUploader.isUploading}
                        className="h-8 rounded-full border-amber-300 text-amber-800 hover:bg-amber-100"
                    >
                        <RefreshCw className="mr-1 h-3 w-3" />
                        重试留痕
                    </Button>
                ),
            });
        }

        if (audioEvidenceEndState?.message) {
            faults.push({
                id: "audio-evidence-end",
                severity: "warning",
                title: audioEvidenceEndState.status === "timed_out" ? "留痕超时" : "留痕失败",
                message: audioEvidenceEndState.error
                    ? `${audioEvidenceEndState.message} 原因：${audioEvidenceEndState.error}`
                    : audioEvidenceEndState.message,
                guidance: "报告会继续生成；查看报告或回放时请结合证据完整度解释本轮结果。",
            });
        }

        return faults;
    }, [
        audioError,
        audioEvidenceEndState,
        audioUploadError,
        canToggleLifecycle,
        connect,
        connectionState,
        continuousUploader.isUploading,
        handleEndSession,
        handleRestartAudioUpload,
        handleStartSession,
        handleTogglePauseResume,
        hasPermission,
        isEndingSession,
        isRecording,
        isSessionTerminal,
        lifecycleError,
        lifecycleErrorGuidance,
        lifecycleErrorMessage,
        lifecycleRetryLabel,
        sessionMetaError,
        wsError,
    ]);
    const audioUploadStatusLabel = audioEvidenceStatus.status === "flushing"
        ? "保存收尾中"
        : audioEvidenceStatus.status === "completed"
        ? "留痕已保存"
        : audioEvidenceStatus.status === "failed"
        ? "留痕失败"
        : audioEvidenceStatus.status === "timed_out"
        ? "留痕超时"
        : continuousUploader.pendingUploads > 0
        ? `留痕保存中(${continuousUploader.pendingUploads})`
        : continuousUploader.uploadStatus === "uploading"
        ? "留痕保存中"
        : continuousUploader.uploadStatus === "error"
        ? "留痕失败"
        : continuousUploader.uploadStatus === "stopped"
        ? "留痕已停止"
        : "留痕待开始";
    const connectionStatusLabel = CONNECTION_STATUS_LABELS[connectionState];
    const lifecycleStatusLabel = SESSION_STATUS_LABELS[sessionStatus];
    const microphoneStatusLabel = audioError
        ? "麦克风异常"
        : hasPermission === false
        ? "需授权麦克风"
        : isRecording
        ? "录音中"
        : "麦克风就绪";
    const aiStatusLabel = isPlayingAudio
        ? "AI 说话中"
        : aiState === "thinking"
        ? "AI 思考中"
        : aiState === "speaking"
        ? "AI 回复中"
        : "AI 待命";
    const canToggleRecordingBase =
        connectionState === "connected"
        && sessionStatus === "in_progress"
        && pendingLifecycleAction === null;
    const canRecord = canToggleRecordingBase && hasPermission !== false;
    const canRequestPermission = canToggleRecordingBase && hasPermission === false;

    // 统一的录音切换函数 - 点击一次开始，再点击一次结束
    const toggleRecording = React.useCallback(() => {
        debug.log('[Recording] toggleRecording called, isRecording:', isRecordingRef.current, 'aiIsBusy:', aiIsBusyRef.current, 'isConnected:', isConnected, 'hasPermission:', hasPermission);
        
        if (connectionState !== "connected") return;
        if (sessionStatus !== "in_progress") return;
        if (pendingLifecycleAction) return;

        if (hasPermission === false) {
            void requestPermission().then((granted) => {
                if (!granted) return;
                if (isRecordingRef.current) return;
                unlockAudio();
                startRecording();
                void continuousUploader.startUpload();
            });
            return;
        }
        
        // 防止快速双击
        if (isStartingRef.current) {
            debug.log('[Recording] Blocked: already starting');
            return;
        }
        
        if (isRecordingRef.current) {
            // 正在录音 → 停止
            stopRecording();
            void continuousUploader.stopUpload();
        } else {
            // 没在录音 → 开始
            isStartingRef.current = true;
            unlockAudio();
            startRecording();
            void continuousUploader.startUpload();
            setTimeout(() => {
                isStartingRef.current = false;
            }, 300);
        }
    }, [connectionState, hasPermission, isConnected, pendingLifecycleAction, requestPermission, sessionStatus, unlockAudio, startRecording, stopRecording, continuousUploader]);

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
                                    {audioEvidenceStatus.status === "flushing" ? "保存音频中..." : "生成报告中..."}
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

                {messages.length === 0 && !isSessionTerminal && (
                    <div className="mx-4 mt-4 rounded-2xl border border-slate-200 bg-white/90 p-4 text-slate-700 shadow-sm">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="inline-flex items-center rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
                                开练前预告
                            </span>
                            <p className="text-sm font-semibold text-slate-900">开始前先看本次练习重点</p>
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-3">
                            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                                <p className="text-xs font-semibold text-slate-500">训练目标</p>
                                <p className="mt-1 text-sm text-slate-900">{preflightBrief.trainingGoal}</p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                                <p className="text-xs font-semibold text-slate-500">评价标准</p>
                                <p className="mt-1 text-sm text-slate-900">{preflightBrief.evaluationCopy}</p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                                <p className="text-xs font-semibold text-slate-500">角色简介</p>
                                <p className="mt-1 text-sm text-slate-900">{preflightBrief.roleCopy}</p>
                            </div>
                        </div>
                    </div>
                )}

                <PracticeFaultPanel faults={practiceFaults} />

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
                                knowledgeAnswerDiagnostics={msg.knowledgeAnswerDiagnostics}
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

                        <div
                            aria-label="训练实时状态"
                            className="grid w-full max-w-2xl grid-cols-2 gap-2 px-4 text-xs text-slate-600 md:grid-cols-5"
                        >
                            {[
                                ["连接", connectionStatusLabel],
                                ["会话", lifecycleStatusLabel],
                                ["麦克风", microphoneStatusLabel],
                                ["留痕", audioUploadStatusLabel],
                                ["AI", aiStatusLabel],
                            ].map(([label, value]) => (
                                <div
                                    key={label}
                                    className="flex min-h-8 items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white/80 px-2.5 py-1.5"
                                >
                                    <span className="shrink-0 text-slate-400">{label}</span>
                                    <span className="min-w-0 truncate font-medium text-slate-700">{value}</span>
                                </div>
                            ))}
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
                                ? audioEvidenceStatus.status === "flushing"
                                    ? audioEvidenceStatus.message
                                    : audioEvidenceStatus.status === "failed" || audioEvidenceStatus.status === "timed_out"
                                    ? audioEvidenceStatus.message
                                    : "会话已结束，正在生成/查看结果"
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
                    actionCard={displayedActionCard}
                    actionCompletionStatus={actionCompletionStatus}
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
                        actionCard={displayedActionCard}
                        actionCompletionStatus={actionCompletionStatus}
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
