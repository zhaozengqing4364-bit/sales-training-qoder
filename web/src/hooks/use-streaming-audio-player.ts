"use client";

import { useCallback, useRef, useState } from "react";

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
  } = options;

  // State
  const [state, setState] = useState<StreamingAudioPlayerState>({
    isPlaying: false,
    isBuffering: false,
    currentTime: 0,
    duration: 0,
    isSupported: checkMediaSourceSupport(mimeType),
    isEnded: false,
  });

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
  const isFallbackModeRef = useRef(false);

  // Callback refs to avoid stale closures
  const onPlaybackStartRef = useRef(onPlaybackStart);
  const onPlaybackEndRef = useRef(onPlaybackEnd);
  const onErrorRef = useRef(onError);
  
  // Update callback refs
  onPlaybackStartRef.current = onPlaybackStart;
  onPlaybackEndRef.current = onPlaybackEnd;
  onErrorRef.current = onError;

  /**
   * Check if MediaSource API is supported
   */
  const isSupported = useCallback((): boolean => {
    return checkMediaSourceSupport(mimeType);
  }, [mimeType]);

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
        console.error('[StreamingAudioPlayer] Failed to append buffer:', err);
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
   */
  const initializeMediaSource = useCallback(() => {
    if (isInitializedRef.current) {
      return;
    }
    
    if (!isSupported()) {
      console.warn('[StreamingAudioPlayer] MediaSource not supported, using fallback mode');
      isFallbackModeRef.current = true;
      return;
    }
    
    try {
      // Create audio element
      const audio = new Audio();
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
        console.error('[StreamingAudioPlayer] Audio error:', errorMessage);
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
            console.error('[StreamingAudioPlayer] SourceBuffer error');
            onErrorRef.current?.('SourceBuffer error');
          };
          
          isInitializedRef.current = true;
          
          // Process any queued chunks
          processChunkQueue();
          
          console.log('[StreamingAudioPlayer] MediaSource initialized');
        } catch (err) {
          console.error('[StreamingAudioPlayer] Failed to create SourceBuffer:', err);
          onErrorRef.current?.('Failed to initialize audio streaming');
          isFallbackModeRef.current = true;
        }
      };
      
      mediaSource.onsourceended = () => {
        console.log('[StreamingAudioPlayer] MediaSource ended');
      };
      
      mediaSource.onsourceclose = () => {
        console.log('[StreamingAudioPlayer] MediaSource closed');
      };
      
    } catch (err) {
      console.error('[StreamingAudioPlayer] Failed to initialize MediaSource:', err);
      onErrorRef.current?.('Failed to initialize audio streaming');
      isFallbackModeRef.current = true;
    }
  }, [isSupported, mimeType, handleUpdateEnd, processChunkQueue]);

  /**
   * Start the streaming audio player
   */
  const start = useCallback(() => {
    initializeMediaSource();
    setState(prev => ({ ...prev, isEnded: false }));
  }, [initializeMediaSource]);

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
    const { chunk_index, audio, duration_ms, is_final, total_duration_ms } = chunk;
    
    // Decode base64 audio data
    let audioBuffer: ArrayBuffer;
    try {
      audioBuffer = base64ToArrayBuffer(audio);
    } catch (err) {
      console.error('[StreamingAudioPlayer] Failed to decode audio chunk:', err);
      onErrorRef.current?.('Failed to decode audio data');
      return;
    }
    
    // Update total duration if provided
    if (total_duration_ms) {
      totalDurationRef.current = total_duration_ms / 1000;
      setState(prev => ({ ...prev, duration: total_duration_ms / 1000 }));
    }
    
    // Handle fallback mode (buffered playback)
    if (isFallbackModeRef.current) {
      fallbackChunksRef.current.push(audioBuffer);
      
      // In fallback mode, wait for final chunk then play all at once
      if (is_final) {
        playFallbackAudio();
      }
      return;
    }
    
    // Initialize if not already done
    if (!isInitializedRef.current) {
      initializeMediaSource();
    }
    
    // Add chunk to queue
    chunkQueueRef.current.push(audioBuffer);
    
    // Process queue
    processChunkQueue();
    
    // Property 4: Start playback on first chunk (chunk_index=0)
    if (chunk_index === 0 && audioRef.current) {
      // Start playback immediately when first chunk arrives
      const playPromise = audioRef.current.play();
      if (playPromise) {
        playPromise.catch(err => {
          console.warn('[StreamingAudioPlayer] Auto-play blocked:', err);
          // Auto-play might be blocked, user interaction required
          setState(prev => ({ ...prev, isBuffering: true }));
        });
      }
    }
    
    console.log(`[StreamingAudioPlayer] Chunk ${chunk_index} appended (${audioBuffer.byteLength} bytes, duration: ${duration_ms}ms, final: ${is_final})`);
  }, [initializeMediaSource, processChunkQueue]);

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
        console.warn('[StreamingAudioPlayer] Fallback auto-play blocked:', err);
      });
      
      console.log('[StreamingAudioPlayer] Playing in fallback mode');
    } catch (err) {
      console.error('[StreamingAudioPlayer] Fallback playback failed:', err);
      onErrorRef.current?.('Failed to play audio');
    }
  }, [mimeType]);

  /**
   * Signal that the stream has ended
   */
  const end = useCallback(() => {
    if (isFallbackModeRef.current) {
      // In fallback mode, play the buffered audio
      playFallbackAudio();
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
            console.log('[StreamingAudioPlayer] Stream ended');
          } catch (err) {
            console.warn('[StreamingAudioPlayer] Failed to end stream:', err);
          }
        }
      };
      
      if (sourceBuffer.updating) {
        sourceBuffer.addEventListener('updateend', endStream, { once: true });
      } else {
        endStream();
      }
    }
  }, [playFallbackAudio]);

  /**
   * Stop playback and clean up resources
   */
  const stop = useCallback(() => {
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
    
    console.log('[StreamingAudioPlayer] Stopped and cleaned up');
  }, [mimeType]);

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
    console.log(`[StreamingAudioPlayer] Queue cleared (${clearedCount} chunks)`);
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
    const wasPlaying = state.isPlaying || isAppendingRef.current;
    
    // Property 6: Immediately stop TTS playback (same event loop tick)
    // Stop audio playback first
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    
    // Property 7: Clear the queue before any signal is sent
    const clearedChunks = clearQueue();
    
    // Stop any browser speech synthesis if active
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    
    // Clean up MediaSource
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
    
    // Reset flags
    isAppendingRef.current = false;
    
    // Update state immediately
    setState(prev => ({
      ...prev,
      isPlaying: false,
      isBuffering: false,
      isEnded: true,
    }));
    
    console.log(`[StreamingAudioPlayer] Interrupted (wasPlaying: ${wasPlaying}, clearedChunks: ${clearedChunks})`);
    
    return { wasPlaying, clearedChunks };
  }, [state.isPlaying, clearQueue]);

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
