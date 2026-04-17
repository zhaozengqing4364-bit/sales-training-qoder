"use client";

import { useCallback, useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import { debug } from "@/lib/debug";
import { normalizeVoiceSpeedPreference } from "../use-voice-speed-preference";
import type { PracticeState, TTSAudioData } from "./types";

interface UseAudioPlaybackOptions {
    onTTSAudio?: (data: TTSAudioData) => void;
    setState: Dispatch<SetStateAction<PracticeState>>;
}

/**
 * Hook for managing TTS audio playback queue.
 *
 * Handles:
 * - Audio queue (FIFO) with sequential playback
 * - Browser audio unlock (required for autoplay policy)
 * - Fallback to browser SpeechSynthesis when audio fails
 */
export function useAudioPlayback({ onTTSAudio, setState }: UseAudioPlaybackOptions) {
    const audioQueueRef = useRef<TTSAudioData[]>([]);
    const isPlayingRef = useRef(false);
    const audioUnlockedRef = useRef(false);
    const playTTSAudioInternalRef = useRef<(data: TTSAudioData) => Promise<void> | void>(() => {});

    // 处理音频队列
    const processAudioQueue = useCallback(() => {
        if (isPlayingRef.current || audioQueueRef.current.length === 0) {
            return;
        }
        
        if (!audioUnlockedRef.current) {
            // 音频未解锁，保存到待播放列表
            return;
        }
        
        isPlayingRef.current = true;
        const nextAudio = audioQueueRef.current.shift();
        if (nextAudio) {
            playTTSAudioInternalRef.current(nextAudio);
        } else {
            isPlayingRef.current = false;
        }
    }, []);

    // 内部播放函数
    const playTTSAudioInternal = useCallback(async (data: TTSAudioData) => {
        const normalizedPlaybackRate = normalizeVoiceSpeedPreference(data.playback_rate);

        // 使用浏览器 TTS 作为 fallback
        if (data.fallback === "browser_tts" || !data.audio) {
            if ("speechSynthesis" in window) {
                const utterance = new SpeechSynthesisUtterance(data.text);
                utterance.lang = "zh-CN";
                utterance.rate = normalizedPlaybackRate;
                utterance.onend = () => {
                    setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                    isPlayingRef.current = false;
                    processAudioQueue();
                };
                utterance.onerror = () => {
                    setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                    isPlayingRef.current = false;
                    processAudioQueue();
                };
                window.speechSynthesis.speak(utterance);
                setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));
            } else {
                isPlayingRef.current = false;
                processAudioQueue();
            }
            return;
        }

        try {
            const binaryString = atob(data.audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const normalizedFormat = (data.audio_format || "mp3").toLowerCase();
            const mimeType =
                normalizedFormat === "wav"
                    ? "audio/wav"
                    : normalizedFormat === "pcm16"
                        ? "audio/wav"
                        : "audio/mp3";
            const blob = new Blob([bytes], { type: mimeType });
            const audioUrl = URL.createObjectURL(blob);
            const audio = new Audio(audioUrl);
            audio.playbackRate = normalizedPlaybackRate;

            setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));

            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                isPlayingRef.current = false;
                processAudioQueue();
            };

            audio.onerror = () => {
                URL.revokeObjectURL(audioUrl);
                setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                isPlayingRef.current = false;
                // 回退到浏览器 TTS
                if ("speechSynthesis" in window) {
                    const utterance = new SpeechSynthesisUtterance(data.text);
                    utterance.lang = "zh-CN";
                    utterance.rate = normalizedPlaybackRate;
                    window.speechSynthesis.speak(utterance);
                }
                processAudioQueue();
            };

            await audio.play();
        } catch (e) {
            debug.error("Failed to play TTS audio:", e);
            setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
            isPlayingRef.current = false;
            // 回退到浏览器 TTS
            if ("speechSynthesis" in window) {
                const utterance = new SpeechSynthesisUtterance(data.text);
                utterance.lang = "zh-CN";
                utterance.rate = normalizedPlaybackRate;
                window.speechSynthesis.speak(utterance);
            }
            processAudioQueue();
        }
    }, [processAudioQueue, setState]);

    useEffect(() => {
        playTTSAudioInternalRef.current = playTTSAudioInternal;
    }, [playTTSAudioInternal]);

    // 添加音频到队列
    const queueTTSAudio = useCallback((data: TTSAudioData) => {
        audioQueueRef.current.push(data);
        onTTSAudio?.(data);
        
        if (audioUnlockedRef.current && !isPlayingRef.current) {
            processAudioQueue();
        }
    }, [onTTSAudio, processAudioQueue]);

    // 解锁音频 - 用户点击"开始"按钮时调用
    const unlockAudio = useCallback(async () => {
        if (audioUnlockedRef.current) return;
        
        try {
            // 播放一个静音音频来解锁
            const audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
            
            if (audioContext.state === "suspended") {
                await audioContext.resume();
            }
            
            // 创建一个短暂的静音缓冲区并播放
            const buffer = audioContext.createBuffer(1, 1, 22050);
            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);
            source.start(0);
            
            // NEW-8 Fix: Close AudioContext after silent buffer finishes to prevent leak
            source.onended = () => {
                audioContext.close().catch(() => {});
            };
            
            audioUnlockedRef.current = true;
            setState(prev => ({ ...prev, audioUnlocked: true }));
            
            // 播放待播放的音频
            if (audioQueueRef.current.length > 0 && !isPlayingRef.current) {
                processAudioQueue();
            }
            
            debug.log("Audio unlocked successfully");
        } catch (e) {
            debug.error("Failed to unlock audio:", e);
            // 即使失败也标记为已解锁，让后续尝试播放
            audioUnlockedRef.current = true;
            setState(prev => ({ ...prev, audioUnlocked: true }));
        }
    }, [processAudioQueue, setState]);

    return {
        audioQueueRef,
        isPlayingRef,
        audioUnlockedRef,
        queueTTSAudio,
        unlockAudio,
    };
}
