"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
    DEFAULT_VOICE_SPEED_PREFERENCE,
    normalizeVoiceSpeedPreference,
} from "./use-voice-speed-preference";
import { debug } from "@/lib/debug";

/**
 * Streaming Audio Player State
 * 
 * Tracks the current state of the streaming audio player including
 * playback status, buffering state, and timing information.
 */
export interface StreamingAudioPlayerState {
    /** Whether audio is currently playing */
    isPlaying: boolean;
    /** Whether the player is buffering (waiting for more data) */
    isBuffering: boolean;
    /** Current playback time in seconds */
    currentTime: number;
    /** Total duration in seconds (updated as chunks arrive) */
    duration: number;
    /** Whether MediaSource API is supported */
    isSupported: boolean;
    /** Whether the stream has ended */
    isEnded: boolean;
}

/**
 * TTS Chunk data received from WebSocket
 */
export interface TTSChunkData {
    chunk_index: number;
    audio: string;  // Base64 encoded audio data
    duration_ms: number;
    is_final: boolean;
    text?: string;
    total_duration_ms?: number;
    audio_format?: string;
    sample_rate?: number;
    playback_rate?: number;
}

/**
 * Options for the streaming audio player hook
 */
export interface UseStreamingAudioPlayerOptions {
    /** Callback when playback starts */
    onPlaybackStart?: () => void;
    /** Callback when playback ends */
    onPlaybackEnd?: () => void;
    /** Callback when an error occurs */
    onError?: (error: string) => void;
    /** MIME type for the audio (default: audio/mpeg) */
    mimeType?: string;
    /** Playback rate shared by every streaming path */
    playbackRate?: number;
}

/**
 * Interrupt reason types
 */
export type InterruptReason = 'user_speaking' | 'manual';

/**
 * Return type for the useStreamingAudioPlayer hook
 */
export interface UseStreamingAudioPlayerReturn {
    /** Current state of the player */
    state: StreamingAudioPlayerState;
    /** Initialize the player and start playback */
    start: () => void;
    /** Append an audio chunk to the buffer */
    appendChunk: (chunk: TTSChunkData) => void;
    /** Signal that the stream has ended */
    end: () => void;
    /** Stop playback and clean up resources */
    stop: () => void;
    /** Check if MediaSource API is supported */
    isSupported: () => boolean;
    /** Reset the player for a new stream */
    reset: () => void;
    /**
     * Clear the audio chunk queue
     * Returns the number of chunks that were cleared
     * 
     * Property 7: Interrupt Queue Clearing
     * - Queue must be cleared before sending interrupt signal
     */
    clearQueue: () => number;
    /**
     * Interrupt playback immediately
     * Stops playback and clears the queue in a single operation
     * Returns true if playback was active and interrupted
     * 
     * Property 6: Interrupt Stops Playback
     * - Audio stops within the same event loop tick
     * 
     * Property 7: Interrupt Queue Clearing
     * - Queue is cleared before any signal is sent
     */
    interrupt: () => { wasPlaying: boolean; clearedChunks: number };
}

/**
 * Check if MediaSource API is supported in the current browser
 */
function checkMediaSourceSupport(mimeType: string): boolean {
    if (typeof window === 'undefined') {
        return false;
    }

    if (!('MediaSource' in window)) {
        return false;
    }

    try {
        return MediaSource.isTypeSupported(mimeType);
    } catch {
        return false;
    }
}

/**
 * Decode Base64 string to ArrayBuffer
 */
function base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

function applyPlaybackRateToActivePcmSources(
    sources: Iterable<AudioBufferSourceNode>,
    playbackRate: number,
): void {
    for (const source of sources) {
        source.playbackRate.value = playbackRate;
    }
}


/**
 * useStreamingAudioPlayer Hook
 * 
 * A React hook for streaming audio playback using MediaSource API.
 * Supports real-time audio streaming by appending chunks as they arrive.
 * Falls back to buffered playback when MediaSource is not supported.
 * 
 * Requirements: 2.2, 2.3
 * - Begin playback immediately when first chunk arrives (2.2)
 * - Use MediaSource API to append audio data to playback buffer (2.3)
 */
export function useStreamingAudioPlayer(
    options: UseStreamingAudioPlayerOptions = {}
): UseStreamingAudioPlayerReturn {
    const {
        onPlaybackStart,
        onPlaybackEnd,
        onError,
        mimeType = 'audio/mpeg',
        playbackRate = DEFAULT_VOICE_SPEED_PREFERENCE,
    } = options;
    const normalizedPlaybackRate = normalizeVoiceSpeedPreference(playbackRate);
    const playbackRateRef = useRef(normalizedPlaybackRate);

    // State
    const [state, setState] = useState<StreamingAudioPlayerState>({
        isPlaying: false,
        isBuffering: false,
        currentTime: 0,
        duration: 0,
        isSupported: checkMediaSourceSupport(mimeType),
        isEnded: false,
    });
    const stateRef = useRef(state);

    // Refs for MediaSource components
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const mediaSourceRef = useRef<MediaSource | null>(null);
    const sourceBufferRef = useRef<SourceBuffer | null>(null);
    const chunkQueueRef = useRef<ArrayBuffer[]>([]);
    const isAppendingRef = useRef(false);
    const isInitializedRef = useRef(false);
    const totalDurationRef = useRef(0);

    // Refs for fallback mode (buffered playback)
    const fallbackChunksRef = useRef<ArrayBuffer[]>([]);
    const playFallbackAudioRef = useRef<() => void>(() => { });
    const isFallbackModeRef = useRef(false);

    // Refs for PCM16 streaming mode (Web Audio scheduling)
    const pcmContextRef = useRef<AudioContext | null>(null);
    const pcmActiveSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
    const pcmPendingSourcesRef = useRef(0);
    const pcmNextStartTimeRef = useRef(0);
    const pcmStreamEndedRef = useRef(false);
    const pcmPlaybackStartedRef = useRef(false);

    // Callback refs to avoid stale closures
    const onPlaybackStartRef = useRef(onPlaybackStart);
    const onPlaybackEndRef = useRef(onPlaybackEnd);
    const onErrorRef = useRef(onError);

    // Update callback refs
    useEffect(() => {
        onPlaybackStartRef.current = onPlaybackStart;
        onPlaybackEndRef.current = onPlaybackEnd;
        onErrorRef.current = onError;
    }, [onError, onPlaybackEnd, onPlaybackStart]);

    useEffect(() => {
        stateRef.current = state;
    }, [state]);

    useEffect(() => {
        playbackRateRef.current = normalizedPlaybackRate;

        if (audioRef.current) {
            audioRef.current.playbackRate = normalizedPlaybackRate;
        }

        for (const source of pcmActiveSourcesRef.current) {
            source.playbackRate.value = normalizedPlaybackRate;
        }
    }, [normalizedPlaybackRate]);

    /**
     * Check if MediaSource API is supported
     */
    const isSupported = useCallback((): boolean => {
        return checkMediaSourceSupport(mimeType);
    }, [mimeType]);

    const stopPCMPlayback = useCallback((closeContext: boolean) => {
        for (const source of pcmActiveSourcesRef.current) {
            try {
                source.stop();
            } catch {
                // Ignore stale source stop failures
            }
            source.disconnect();
        }
        pcmActiveSourcesRef.current.clear();
        pcmPendingSourcesRef.current = 0;
        pcmNextStartTimeRef.current = 0;
        pcmStreamEndedRef.current = false;
        pcmPlaybackStartedRef.current = false;

        if (closeContext && pcmContextRef.current) {
            pcmContextRef.current.close().catch(() => { });
            pcmContextRef.current = null;
        }
    }, []);

    const ensurePCMContext = useCallback((sampleRate: number): AudioContext | null => {
        if (typeof window === 'undefined') {
            return null;
        }

        if (!pcmContextRef.current || pcmContextRef.current.state === 'closed') {
            try {
                pcmContextRef.current = new AudioContext({ sampleRate });
            } catch {
                // Safari may reject custom sampleRate; fallback to default context
                pcmContextRef.current = new AudioContext();
            }
            pcmNextStartTimeRef.current = pcmContextRef.current.currentTime;
        }

        if (pcmContextRef.current.state === 'suspended') {
            pcmContextRef.current.resume().catch(() => { });
        }

        return pcmContextRef.current;
    }, []);

    /**
     * Process the chunk queue - append chunks sequentially
     */
    const processChunkQueue = useCallback(() => {
        const sourceBuffer = sourceBufferRef.current;

        if (!sourceBuffer || isAppendingRef.current || chunkQueueRef.current.length === 0) {
            return;
        }

        // Check if sourceBuffer is ready for appending
        if (sourceBuffer.updating) {
            return;
        }

        isAppendingRef.current = true;
        const chunk = chunkQueueRef.current.shift();

        if (chunk) {
            try {
                sourceBuffer.appendBuffer(chunk);
            } catch (err) {
                debug.error('[StreamingAudioPlayer] Failed to append buffer:', err);
                isAppendingRef.current = false;
                onErrorRef.current?.('Failed to append audio buffer');
            }
        } else {
            isAppendingRef.current = false;
        }
    }, []);

    /**
     * Handle sourceBuffer updateend event
     */
    const handleUpdateEnd = useCallback(() => {
        isAppendingRef.current = false;

        // Update duration from buffer
        const sourceBuffer = sourceBufferRef.current;
        if (sourceBuffer && sourceBuffer.buffered.length > 0) {
            const bufferedEnd = sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);
            setState(prev => ({
                ...prev,
                duration: Math.max(prev.duration, bufferedEnd),
            }));
        }

        // Process next chunk in queue
        processChunkQueue();
    }, [processChunkQueue]);

    /**
     * Initialize MediaSource and audio element
     * IMPORTANT: This is called from both start() and appendChunk()
     * We need to prevent race conditions during async onsourceopen
     */
    const initializeMediaSource = useCallback(() => {
        // Prevent multiple concurrent initialization attempts
        // isInitializedRef is set to true ONLY after onsourceopen completes
        // But we need to prevent re-entry during the async period
        if (isInitializedRef.current || mediaSourceRef.current) {
            return;
        }

        if (!isSupported()) {
            debug.warn('[StreamingAudioPlayer] MediaSource not supported, using fallback mode');
            isFallbackModeRef.current = true;
            return;
        }

        try {
            // Create audio element
            const audio = new Audio();
            audio.playbackRate = playbackRateRef.current;
            audioRef.current = audio;

            // Create MediaSource
            const mediaSource = new MediaSource();
            mediaSourceRef.current = mediaSource;

            // Set up audio element
            audio.src = URL.createObjectURL(mediaSource);

            // Handle audio events
            audio.onplay = () => {
                setState(prev => ({ ...prev, isPlaying: true, isBuffering: false }));
                onPlaybackStartRef.current?.();
            };

            audio.onpause = () => {
                setState(prev => ({ ...prev, isPlaying: false }));
            };

            audio.onended = () => {
                setState(prev => ({ ...prev, isPlaying: false, isEnded: true }));
                onPlaybackEndRef.current?.();

                // Clean up MediaSource after playback ends to free resources
                // This is crucial to avoid SourceBuffer limit on next stream
                if (audio.src) {
                    URL.revokeObjectURL(audio.src);
                }
                audioRef.current = null;
                mediaSourceRef.current = null;
                sourceBufferRef.current = null;
                isInitializedRef.current = false;
                debug.log('[StreamingAudioPlayer] Playback ended, resources cleaned up');
            };

            audio.onwaiting = () => {
                setState(prev => ({ ...prev, isBuffering: true }));
            };

            audio.onplaying = () => {
                setState(prev => ({ ...prev, isBuffering: false }));
            };

            audio.ontimeupdate = () => {
                setState(prev => ({ ...prev, currentTime: audio.currentTime }));
            };

            audio.onerror = () => {
                const errorMessage = audio.error?.message || 'Audio playback error';
                debug.error('[StreamingAudioPlayer] Audio error:', errorMessage);
                onErrorRef.current?.(errorMessage);
            };

            // Handle MediaSource sourceopen event
            mediaSource.onsourceopen = () => {
                try {
                    // Create SourceBuffer for audio/mpeg
                    const sourceBuffer = mediaSource.addSourceBuffer(mimeType);
                    sourceBufferRef.current = sourceBuffer;

                    // Handle updateend to process queue
                    sourceBuffer.onupdateend = handleUpdateEnd;

                    sourceBuffer.onerror = () => {
                        debug.error('[StreamingAudioPlayer] SourceBuffer error');
                        onErrorRef.current?.('SourceBuffer error');
                    };

                    isInitializedRef.current = true;

                    // Process any queued chunks that arrived before onsourceopen
                    processChunkQueue();

                    // Start playback if there are queued chunks
                    // This handles the case where chunks arrived before SourceBuffer was ready
                    if (chunkQueueRef.current.length > 0 || sourceBuffer.buffered.length > 0) {
                        const playPromise = audio.play();
                        if (playPromise) {
                            playPromise.catch(err => {
                                debug.warn('[StreamingAudioPlayer] Auto-play blocked in onsourceopen:', err);
                            });
                        }
                    }

                    debug.log('[StreamingAudioPlayer] MediaSource initialized, queued chunks:', chunkQueueRef.current.length);
                } catch (err) {
                    debug.error('[StreamingAudioPlayer] Failed to create SourceBuffer:', err);
                    onErrorRef.current?.('Failed to initialize audio streaming');
                    isFallbackModeRef.current = true;
                }
            };

            mediaSource.onsourceended = () => {
                debug.log('[StreamingAudioPlayer] MediaSource ended');
            };

            mediaSource.onsourceclose = () => {
                debug.log('[StreamingAudioPlayer] MediaSource closed');
            };

        } catch (err) {
            debug.error('[StreamingAudioPlayer] Failed to initialize MediaSource:', err);
            onErrorRef.current?.('Failed to initialize audio streaming');
            isFallbackModeRef.current = true;
        }
    }, [isSupported, mimeType, handleUpdateEnd, processChunkQueue]);

    /**
     * Start the streaming audio player
     * IMPORTANT: Always clean up previous stream first to avoid SourceBuffer limit
     */
    const start = useCallback(() => {
        stopPCMPlayback(true);

        // Clean up any previous MediaSource/SourceBuffer to avoid QuotaExceededError
        // This is crucial - browsers limit the number of active SourceBuffers
        if (audioRef.current) {
            audioRef.current.pause();
            if (audioRef.current.src) {
                URL.revokeObjectURL(audioRef.current.src);
            }
            audioRef.current = null;
        }

        if (mediaSourceRef.current && mediaSourceRef.current.readyState === 'open') {
            try {
                mediaSourceRef.current.endOfStream();
            } catch {
                // Ignore errors during cleanup
            }
        }
        mediaSourceRef.current = null;
        sourceBufferRef.current = null;

        // Clear queues
        chunkQueueRef.current = [];
        fallbackChunksRef.current = [];

        // Reset flags
        isAppendingRef.current = false;
        isInitializedRef.current = false;
        isFallbackModeRef.current = false;
        totalDurationRef.current = 0;

        // Reset state for new stream
        setState(prev => ({
            ...prev,
            isEnded: false,
            isPlaying: false,
            isBuffering: false,
            currentTime: 0,
            duration: 0,
        }));

        // Now initialize new MediaSource
        initializeMediaSource();
        debug.log('[StreamingAudioPlayer] Started new stream (previous cleaned up)');
    }, [initializeMediaSource, stopPCMPlayback]);

    /**
     * Append an audio chunk to the buffer
     * 
     * Property 4: Streaming Playback Initialization
     * - When chunk_index=0 is received, playback starts immediately
     * 
     * Property 5: MediaSource Buffer Appending
     * - For each non-final chunk, appendBuffer is called
     */
    const appendChunk = useCallback((chunk: TTSChunkData) => {
        const {
            chunk_index,
            audio,
            duration_ms,
            is_final,
            total_duration_ms,
            audio_format,
            sample_rate,
            playback_rate,
        } = chunk;
        const normalizedFormat = (audio_format || 'mp3').toLowerCase();

        if (playback_rate !== undefined) {
            const normalizedChunkPlaybackRate = normalizeVoiceSpeedPreference(playback_rate);
            playbackRateRef.current = normalizedChunkPlaybackRate;
            if (audioRef.current) {
                audioRef.current.playbackRate = normalizedChunkPlaybackRate;
            }
            applyPlaybackRateToActivePcmSources(
                pcmActiveSourcesRef.current,
                normalizedChunkPlaybackRate,
            );
        }

        // Update total duration if provided
        if (total_duration_ms) {
            totalDurationRef.current = total_duration_ms / 1000;
            setState(prev => ({ ...prev, duration: total_duration_ms / 1000 }));
        }

        // PCM16 streaming path: schedule each chunk with Web Audio API.
        if (normalizedFormat === 'pcm16') {
            if (is_final) {
                pcmStreamEndedRef.current = true;
                if (pcmPendingSourcesRef.current === 0) {
                    setState(prev => ({ ...prev, isPlaying: false, isEnded: true }));
                    onPlaybackEndRef.current?.();
                }
                return;
            }

            let pcmBuffer: ArrayBuffer;
            try {
                pcmBuffer = base64ToArrayBuffer(audio);
            } catch (err) {
                debug.error('[StreamingAudioPlayer] Failed to decode PCM chunk:', err);
                onErrorRef.current?.('Failed to decode PCM data');
                return;
            }
            if (pcmBuffer.byteLength === 0) {
                return;
            }

            const chunkSampleRate = sample_rate || 24000;
            const audioContext = ensurePCMContext(chunkSampleRate);
            if (!audioContext) {
                onErrorRef.current?.('PCM playback unavailable');
                return;
            }

            const int16Array = new Int16Array(pcmBuffer);
            const float32Array = new Float32Array(int16Array.length);
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768;
            }

            const webAudioBuffer = audioContext.createBuffer(1, float32Array.length, chunkSampleRate);
            webAudioBuffer.copyToChannel(float32Array, 0);

            const source = audioContext.createBufferSource();
            source.buffer = webAudioBuffer;
            source.playbackRate.value = playbackRateRef.current;
            source.connect(audioContext.destination);

            const now = audioContext.currentTime;
            const startTime = Math.max(now, pcmNextStartTimeRef.current || now);
            source.start(startTime);
            pcmNextStartTimeRef.current = startTime + (webAudioBuffer.duration / playbackRateRef.current);

            pcmPendingSourcesRef.current += 1;
            pcmActiveSourcesRef.current.add(source);

            if (!pcmPlaybackStartedRef.current) {
                pcmPlaybackStartedRef.current = true;
                setState(prev => ({ ...prev, isPlaying: true, isBuffering: false, isEnded: false }));
                onPlaybackStartRef.current?.();
            }

            source.onended = () => {
                pcmActiveSourcesRef.current.delete(source);
                pcmPendingSourcesRef.current = Math.max(0, pcmPendingSourcesRef.current - 1);
                source.disconnect();

                if (pcmStreamEndedRef.current && pcmPendingSourcesRef.current === 0) {
                    setState(prev => ({ ...prev, isPlaying: false, isEnded: true }));
                    onPlaybackEndRef.current?.();
                }
            };

            debug.log(
                `[StreamingAudioPlayer] PCM chunk ${chunk_index} scheduled (${pcmBuffer.byteLength} bytes, ${duration_ms}ms)`
            );
            return;
        }

        // Decode base64 compressed audio data (e.g., MP3)
        let audioBuffer: ArrayBuffer;
        try {
            audioBuffer = base64ToArrayBuffer(audio);
        } catch (err) {
            debug.error('[StreamingAudioPlayer] Failed to decode audio chunk:', err);
            onErrorRef.current?.('Failed to decode audio data');
            return;
        }

        // Handle fallback mode (buffered playback)
        if (isFallbackModeRef.current) {
            if (audioBuffer.byteLength > 0) {
                fallbackChunksRef.current.push(audioBuffer);
            }

            // In fallback mode, wait for final chunk then play all at once
            if (is_final) {
                playFallbackAudioRef.current();
            }
            return;
        }

        // Initialize if not already done (check both flags for race condition safety)
        if (!isInitializedRef.current && !mediaSourceRef.current) {
            initializeMediaSource();
        }

        // Add chunk to queue
        if (audioBuffer.byteLength > 0) {
            chunkQueueRef.current.push(audioBuffer);
        }

        // Process queue (will be no-op if SourceBuffer not ready yet)
        processChunkQueue();

        // Property 4: Start playback on first chunk (chunk_index=0)
        // But only if audio element exists and SourceBuffer is initialized
        if (chunk_index === 0 && audioRef.current && isInitializedRef.current) {
            // Start playback immediately when first chunk arrives
            const playPromise = audioRef.current.play();
            if (playPromise) {
                playPromise.catch(err => {
                    debug.warn('[StreamingAudioPlayer] Auto-play blocked:', err);
                    // Auto-play might be blocked, user interaction required
                    setState(prev => ({ ...prev, isBuffering: true }));
                });
            }
        }

        debug.log(`[StreamingAudioPlayer] Chunk ${chunk_index} appended (${audioBuffer.byteLength} bytes, duration: ${duration_ms}ms, final: ${is_final}, initialized: ${isInitializedRef.current})`);
    }, [ensurePCMContext, initializeMediaSource, processChunkQueue]);

    /**
     * Play audio in fallback mode (buffered playback)
     * Used when MediaSource API is not supported
     */
    const playFallbackAudio = useCallback(() => {
        if (fallbackChunksRef.current.length === 0) {
            return;
        }

        try {
            // Combine all chunks into a single blob
            const combinedBuffer = new Blob(fallbackChunksRef.current, { type: mimeType });
            const audioUrl = URL.createObjectURL(combinedBuffer);

            const audio = new Audio(audioUrl);
            audio.playbackRate = playbackRateRef.current;
            audioRef.current = audio;

            audio.onplay = () => {
                setState(prev => ({ ...prev, isPlaying: true }));
                onPlaybackStartRef.current?.();
            };

            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                setState(prev => ({ ...prev, isPlaying: false, isEnded: true }));
                onPlaybackEndRef.current?.();
            };

            audio.onerror = () => {
                URL.revokeObjectURL(audioUrl);
                onErrorRef.current?.('Fallback audio playback error');
            };

            audio.play().catch(err => {
                debug.warn('[StreamingAudioPlayer] Fallback auto-play blocked:', err);
            });

            debug.log('[StreamingAudioPlayer] Playing in fallback mode');
        } catch (err) {
            debug.error('[StreamingAudioPlayer] Fallback playback failed:', err);
            onErrorRef.current?.('Failed to play audio');
        }
    }, [mimeType]);

    useEffect(() => {
        playFallbackAudioRef.current = playFallbackAudio;
    }, [playFallbackAudio]);

    /**
     * Signal that the stream has ended
     */
    const end = useCallback(() => {
        if (pcmPlaybackStartedRef.current || pcmPendingSourcesRef.current > 0) {
            pcmStreamEndedRef.current = true;
            if (pcmPendingSourcesRef.current === 0) {
                setState(prev => ({ ...prev, isPlaying: false, isEnded: true }));
                onPlaybackEndRef.current?.();
            }
            return;
        }

        if (isFallbackModeRef.current) {
            // In fallback mode, play the buffered audio
            playFallbackAudioRef.current();
            return;
        }

        const mediaSource = mediaSourceRef.current;
        const sourceBuffer = sourceBufferRef.current;

        if (mediaSource && sourceBuffer && mediaSource.readyState === 'open') {
            // Wait for any pending appends to complete
            const endStream = () => {
                if (!sourceBuffer.updating && mediaSource.readyState === 'open') {
                    try {
                        mediaSource.endOfStream();
                        debug.log('[StreamingAudioPlayer] Stream ended');
                    } catch (err) {
                        debug.warn('[StreamingAudioPlayer] Failed to end stream:', err);
                    }
                }
            };

            if (sourceBuffer.updating) {
                sourceBuffer.addEventListener('updateend', endStream, { once: true });
            } else {
                endStream();
            }
        }
    }, []);

    /**
     * Stop playback and clean up resources
     */
    const stop = useCallback(() => {
        stopPCMPlayback(true);

        // Stop audio playback
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;

            // Revoke object URL if exists
            if (audioRef.current.src) {
                URL.revokeObjectURL(audioRef.current.src);
            }
            audioRef.current = null;
        }

        // Clean up MediaSource
        if (mediaSourceRef.current && mediaSourceRef.current.readyState === 'open') {
            try {
                mediaSourceRef.current.endOfStream();
            } catch {
                // Ignore errors during cleanup
            }
        }
        mediaSourceRef.current = null;
        sourceBufferRef.current = null;

        // Clear queues
        chunkQueueRef.current = [];
        fallbackChunksRef.current = [];

        // Reset flags
        isAppendingRef.current = false;
        isInitializedRef.current = false;
        isFallbackModeRef.current = false;
        totalDurationRef.current = 0;

        // Reset state
        setState({
            isPlaying: false,
            isBuffering: false,
            currentTime: 0,
            duration: 0,
            isSupported: checkMediaSourceSupport(mimeType),
            isEnded: false,
        });

        debug.log('[StreamingAudioPlayer] Stopped and cleaned up');
    }, [mimeType, stopPCMPlayback]);

    /**
     * Reset the player for a new stream
     */
    const reset = useCallback(() => {
        stop();
    }, [stop]);

    /**
     * Clear the audio chunk queue
     * Returns the number of chunks that were cleared
     * 
     * Property 7: Interrupt Queue Clearing
     * - Queue must be cleared before sending interrupt signal
     * 
     * Validates: Requirements 3.2
     */
    const clearQueue = useCallback((): number => {
        const clearedCount = chunkQueueRef.current.length + fallbackChunksRef.current.length;
        chunkQueueRef.current = [];
        fallbackChunksRef.current = [];
        debug.log(`[StreamingAudioPlayer] Queue cleared (${clearedCount} chunks)`);
        return clearedCount;
    }, []);

    /**
     * Interrupt playback immediately
     * Stops playback and clears the queue in a single operation
     * Returns true if playback was active and interrupted
     * 
     * Property 6: Interrupt Stops Playback
     * - Audio stops within the same event loop tick
     * 
     * Property 7: Interrupt Queue Clearing
     * - Queue is cleared before any signal is sent
     * 
     * Validates: Requirements 3.1, 3.2
     */
    const interrupt = useCallback((): { wasPlaying: boolean; clearedChunks: number } => {
        const wasPlaying =
            stateRef.current.isPlaying ||
            isAppendingRef.current ||
            pcmPlaybackStartedRef.current ||
            pcmPendingSourcesRef.current > 0;

        // Property 6: Immediately stop TTS playback (same event loop tick)
        // Stop audio playback first
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;

            // Revoke object URL to free resources
            if (audioRef.current.src) {
                URL.revokeObjectURL(audioRef.current.src);
            }
            audioRef.current = null;
        }

        // Stop PCM playback immediately
        stopPCMPlayback(true);

        // Property 7: Clear the queue before any signal is sent
        const clearedChunks = clearQueue();

        // Stop any browser speech synthesis if active
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }

        // Clean up MediaSource completely to avoid SourceBuffer limit
        if (mediaSourceRef.current && mediaSourceRef.current.readyState === 'open') {
            try {
                // Abort any pending operations on the source buffer
                if (sourceBufferRef.current && sourceBufferRef.current.updating) {
                    sourceBufferRef.current.abort();
                }
                mediaSourceRef.current.endOfStream();
            } catch {
                // Ignore errors during cleanup
            }
        }

        // Null out refs to allow garbage collection
        mediaSourceRef.current = null;
        sourceBufferRef.current = null;

        // Reset ALL flags so next stream can initialize fresh
        isAppendingRef.current = false;
        isInitializedRef.current = false;  // Critical: allows next stream to create new MediaSource
        isFallbackModeRef.current = false;
        totalDurationRef.current = 0;

        // Update state immediately
        setState(prev => {
            if (
                !prev.isPlaying
                && !prev.isBuffering
                && prev.isEnded
                && prev.currentTime === 0
                && prev.duration === 0
            ) {
                return prev;
            }
            return {
                ...prev,
                isPlaying: false,
                isBuffering: false,
                isEnded: true,
                currentTime: 0,
                duration: 0,
            };
        });

        debug.log(`[StreamingAudioPlayer] Interrupted and cleaned up (wasPlaying: ${wasPlaying}, clearedChunks: ${clearedChunks})`);

        return { wasPlaying, clearedChunks };
    }, [clearQueue, stopPCMPlayback]);

    return {
        state,
        start,
        appendChunk,
        end,
        stop,
        isSupported,
        reset,
        clearQueue,
        interrupt,
    };
}
