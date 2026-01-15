"use client";

import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Mic, Square, FileText, ArrowLeft, AlertCircle, Wifi, WifiOff, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatBubble } from "@/components/ui/chat-bubble";
import { AudioVisualizer } from "@/components/ui/audio-visualizer";
import { AudioWaveform } from "@/components/ui/audio-waveform";
import { GlassSheet } from "@/components/ui/glass-sheet";
import { cn } from "@/lib/utils";
import { usePracticeWebSocket } from "@/hooks/use-practice-websocket";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";

export default function PracticeSessionPage() {
    const params = useParams();
    const router = useRouter();
    const searchParams = useSearchParams();
    
    const sessionId = params.sessionId as string;
    const agentId = searchParams.get("agent_id") || undefined;
    const personaId = searchParams.get("persona_id") || undefined;
    
    const [isPanelOpen, setIsPanelOpen] = React.useState(false);
    const [sessionTime, setSessionTime] = React.useState(0);
    const messagesEndRef = React.useRef<HTMLDivElement>(null);

    // WebSocket 连接
    const {
        isConnected,
        isConnecting,
        aiState,
        messages,
        fuzzyDetections,
        salesStage,
        scores,
        error: wsError,
        isPlayingAudio,
        interimTranscript,
        audioUnlocked,
        sendAudio,
        sendAudioEnd,
        sendControl,
        startSpeaking,
        unlockAudio,
    } = usePracticeWebSocket({
        sessionId,
        agentId,
        personaId,
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
        onAudioEnd: () => {
            if (isConnected) {
                // 发送音频结束信号
                sendAudioEnd();
            }
        },
        onSpeakingChange: (speaking) => {
            if (isConnected && speaking) {
                // 只在开始说话时发送信号
                startSpeaking();
            }
        },
    });

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

    // 请求麦克风权限
    React.useEffect(() => {
        if (hasPermission === null) {
            requestPermission();
        }
    }, [hasPermission, requestPermission]);

    // 统一的录音开始处理 - 包含所有业务逻辑检查
    const handleStartRecording = React.useCallback(() => {
        // 业务逻辑检查（按钮的 disabled 已处理连接和权限，这里主要处理 AI 说话状态）
        if (!isConnected || hasPermission === false) {
            return;
        }
        
        // 如果已经在录音，不重复开始
        if (isRecording) {
            return;
        }
        
        // 解锁音频并开始录音
        unlockAudio();
        startRecording();
    }, [isConnected, hasPermission, isRecording, unlockAudio, startRecording]);

    // 统一的录音停止处理
    const handleStopRecording = React.useCallback(() => {
        if (isRecording) {
            stopRecording();
        }
    }, [isRecording, stopRecording]);

    // 空格键按住说话
    React.useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // 忽略输入框中的空格
            const target = e.target as HTMLElement;
            if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
                return;
            }
            
            if (e.code === "Space" && !e.repeat) {
                e.preventDefault();
                handleStartRecording();
            }
        };

        const handleKeyUp = (e: KeyboardEvent) => {
            // 忽略输入框中的空格
            const target = e.target as HTMLElement;
            if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
                return;
            }
            
            if (e.code === "Space") {
                e.preventDefault();
                handleStopRecording();
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        window.addEventListener("keyup", handleKeyUp);

        return () => {
            window.removeEventListener("keydown", handleKeyDown);
            window.removeEventListener("keyup", handleKeyUp);
        };
    }, [handleStartRecording, handleStopRecording]);

    const handleEndSession = () => {
        sendControl("end");
        router.push(`/practice/${sessionId}/report`);
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    // 右侧面板内容
    const RightPanelContent = () => (
        <div className="space-y-6">
            {/* 模糊词检测 */}
            {fuzzyDetections.length > 0 && (
                <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                        实时提示
                    </h3>
                    <div className="space-y-3">
                        {fuzzyDetections.map((detection, idx) => (
                            <div
                                key={idx}
                                className={cn(
                                    "p-3 rounded-lg border",
                                    detection.severity === "high"
                                        ? "bg-red-50 border-red-100"
                                        : detection.severity === "medium"
                                        ? "bg-amber-50 border-amber-100"
                                        : "bg-blue-50 border-blue-100"
                                )}
                            >
                                <div className={cn(
                                    "text-xs font-bold mb-1",
                                    detection.severity === "high"
                                        ? "text-red-600"
                                        : detection.severity === "medium"
                                        ? "text-amber-600"
                                        : "text-blue-600"
                                )}>
                                    {detection.severity === "high" ? "⚠️" : "💡"} {detection.category === "feedback" ? "反馈" : "模糊词检测"}
                                </div>
                                {detection.matched.length > 0 && (
                                    <p className="text-xs text-slate-600 mb-1">
                                        检测到: {detection.matched.join(", ")}
                                    </p>
                                )}
                                <p className="text-xs text-slate-600">{detection.suggestion}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 销售阶段 */}
            {salesStage && (
                <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                    <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        当前阶段
                    </h3>
                    <div className="bg-blue-50 border border-blue-100 p-3 rounded-lg">
                        <div className="text-xs text-blue-600 font-bold mb-1">
                            📊 {salesStage.stage_name}
                        </div>
                        <div className="w-full h-1.5 bg-blue-100 rounded-full mb-2">
                            <div
                                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                                style={{ width: `${salesStage.progress * 100}%` }}
                            />
                        </div>
                        <ul className="text-xs text-slate-600 list-disc list-inside space-y-1">
                            {salesStage.key_actions.map((action, idx) => (
                                <li key={idx}>{action}</li>
                            ))}
                        </ul>
                        {salesStage.guidance && (
                            <p className="text-xs text-slate-500 mt-2 italic">{salesStage.guidance}</p>
                        )}
                    </div>
                </div>
            )}

            {/* 实时评分 */}
            <div className="bg-white/50 backdrop-blur-sm rounded-2xl p-4 border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
                <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    实时评分
                </h3>
                <div className="space-y-3">
                    {(scores?.dimensions || [
                        { name: "专业度", score: 0, trend: "stable" as const, delta: 0 },
                        { name: "沟通技巧", score: 0, trend: "stable" as const, delta: 0 },
                        { name: "销售流程", score: 0, trend: "stable" as const, delta: 0 },
                    ]).map((item) => (
                        <div key={item.name}>
                            <div className="flex justify-between text-xs text-slate-600 mb-1">
                                <span className="flex items-center gap-1">
                                    {item.name}
                                    {item.trend === "up" && <span className="text-emerald-500">↑</span>}
                                    {item.trend === "down" && <span className="text-red-500">↓</span>}
                                </span>
                                <span>{item.score}</span>
                            </div>
                            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all duration-500 bg-indigo-500"
                                    style={{ width: `${item.score}%` }}
                                />
                            </div>
                        </div>
                    ))}
                    <div className="pt-2 border-t border-slate-200 mt-2">
                        <div className="flex justify-between items-center">
                            <span className="text-sm font-bold text-slate-700">综合评分</span>
                            <span className="text-lg font-bold text-indigo-600">
                                {scores?.overall || 0}
                            </span>
                        </div>
                        {scores?.feedback && (
                            <p className="text-xs text-slate-500 mt-1">{scores.feedback}</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );

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
                        <Button variant="ghost" size="icon" onClick={() => router.back()} className="md:hidden">
                            <ArrowLeft className="w-5 h-5" />
                        </Button>
                        <div>
                            <h1 className="text-base md:text-lg font-bold text-slate-800">销售对练</h1>
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <span className="flex items-center gap-1">
                                    {isConnected ? (
                                        <>
                                            <Wifi className="w-3 h-3 text-emerald-500" />
                                            <span className="text-emerald-600">已连接</span>
                                        </>
                                    ) : isConnecting ? (
                                        <>
                                            <span className="w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                                            <span>连接中...</span>
                                        </>
                                    ) : (
                                        <>
                                            <WifiOff className="w-3 h-3 text-red-500" />
                                            <span className="text-red-600">未连接</span>
                                        </>
                                    )}
                                </span>
                                <span>•</span>
                                <span>{formatTime(sessionTime)}</span>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={handleEndSession}
                            className="hidden md:flex rounded-full"
                        >
                            <Square className="w-4 h-4 mr-2 fill-current" />
                            结束练习
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleEndSession}
                            className="md:hidden text-red-500"
                        >
                            结束
                        </Button>
                    </div>
                </header>

                {/* 错误提示 */}
                {(wsError || audioError) && (
                    <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-100 rounded-lg flex items-center gap-2 text-sm text-red-600">
                        <AlertCircle className="w-4 h-4" />
                        {wsError || audioError}
                    </div>
                )}

                {/* 聊天列表 */}
                <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-[220px] md:pb-[200px]">
                    <div className="max-w-3xl mx-auto">
                        {messages.length === 0 && isConnected && (
                            <div className="text-center text-slate-400 py-8">
                                <p>连接成功！按住麦克风按钮开始对话</p>
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
                                        ? "https://api.dicebear.com/7.x/avataaars/svg?seed=Felix"
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
                        {/* 实时转录显示 */}
                        {interimTranscript && (
                            <div className="w-full max-w-md px-4 py-2 bg-indigo-50 border border-indigo-100 rounded-xl">
                                <p className="text-sm text-indigo-700 text-center animate-pulse">
                                    {interimTranscript}
                                </p>
                            </div>
                        )}
                        
                        {/* 波形显示 - 使用真实音频可视化 */}
                        <div className="flex items-center gap-2 h-8 text-slate-400">
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
                            ) : (
                                <span className="text-xs">等待输入...</span>
                            )}
                        </div>

                        <div className="flex items-center gap-4 w-full justify-center relative">
                            {/* 移动端面板按钮 */}
                            <Button
                                variant="ghost"
                                size="icon"
                                className="md:hidden absolute left-0"
                                onClick={() => setIsPanelOpen(true)}
                            >
                                <FileText className="w-5 h-5 text-slate-500" />
                            </Button>

                            {/* 录音按钮 */}
                            <Button
                                size="lg"
                                disabled={!isConnected || hasPermission === false}
                                className={cn(
                                    "rounded-full w-16 h-16 md:w-20 md:h-20 shadow-xl transition-all duration-300",
                                    isRecording
                                        ? "bg-red-500 hover:bg-red-600 scale-110"
                                        : "bg-indigo-600 hover:bg-indigo-700"
                                )}
                                onMouseDown={handleStartRecording}
                                onMouseUp={handleStopRecording}
                                onMouseLeave={handleStopRecording}
                                onTouchStart={handleStartRecording}
                                onTouchEnd={handleStopRecording}
                            >
                                <Mic className={cn("w-6 h-6 md:w-8 md:h-8", isRecording && "animate-pulse")} />
                            </Button>

                            <div className="hidden md:block absolute right-0 text-xs text-slate-400">
                                按住空格键也可以说话
                            </div>
                        </div>

                        <p className="text-xs text-slate-400 font-medium">
                            {!isConnected
                                ? "等待连接..."
                                : hasPermission === false
                                ? "请允许麦克风权限"
                                : isPlayingAudio
                                ? "AI 正在说话..."
                                : isRecording
                                ? "正在录音..."
                                : "按住说话 / 松开发送"}
                        </p>
                    </div>
                </div>
            </div>

            {/* 右侧面板 (桌面端) */}
            <div className="hidden md:block w-80 lg:w-96 border-l border-white/40 bg-white/30 backdrop-blur-xl p-6 overflow-y-auto">
                <RightPanelContent />
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
                    <RightPanelContent />
                </div>
            </GlassSheet>
        </div>
    );
}
